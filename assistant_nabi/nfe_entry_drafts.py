from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path
from threading import Lock
from uuid import uuid4

from services.nfe_xml_service import NFeXMLService
from services.nfe_packaging_factor_service import NFePackagingFactorService


@dataclass(frozen=True, slots=True)
class NFeEntryCandidate:
    product_id: int
    code: str
    description: str
    criterion: str
    similarity: str


@dataclass(frozen=True, slots=True)
class NFeEntryDraftItem:
    index: int
    supplier_code: str
    description: str
    quantity: str
    unit: str
    unit_cost: str
    suggested_conversion_factor: str
    factor_confidence: str
    factor_evidence: str
    match_status: str
    suggested_product_id: int | None
    match_criterion: str
    candidates: tuple[NFeEntryCandidate, ...]


@dataclass(frozen=True, slots=True)
class NFeEntryDraft:
    draft_id: str
    fingerprint: str
    source_path: str
    source_sha256: str
    access_key: str
    number: str
    supplier_name: str
    supplier_document: str
    protocol_status_evidence: str
    document_total: str
    recipient_name: str
    recipient_document: str
    items: tuple[NFeEntryDraftItem, ...]
    operation_kind: str = "NFE_ENTRY_REVIEW"
    persisted: bool = False
    executable: bool = False


@dataclass(frozen=True, slots=True)
class NFeEntryImportDraftItem:
    index: int
    product_id: int
    code: str
    description: str
    xml_quantity: Decimal
    conversion_factor: Decimal
    stock_quantity: Decimal
    purchase_unit: str
    unit_cost: Decimal


@dataclass(frozen=True, slots=True)
class NFeEntryImportDraft:
    draft_id: str
    fingerprint: str
    review_draft_id: str
    source_path: str
    source_sha256: str
    access_key: str
    number: str
    supplier_name: str
    supplier_document: str
    protocol_status_evidence: str
    document_total: Decimal
    recipient_name: str
    recipient_document: str
    items: tuple[NFeEntryImportDraftItem, ...]
    operation_kind: str = "NFE_ENTRY_IMPORT"
    persisted: bool = False
    executable: bool = True


class NFeEntryDraftService:
    """Lê XML selecionado pelo operador e prepara evidência; nunca importa."""

    def __init__(self, import_service, *, xml_service=None, max_bytes: int = 10_000_000) -> None:
        if import_service is None:
            raise ValueError("Serviço oficial de análise de NF-e obrigatório.")
        self._imports = import_service
        self._xml = xml_service or NFeXMLService()
        self._max_bytes = max(1024, min(int(max_bytes), 50_000_000))
        self._drafts: dict[str, NFeEntryDraft | NFeEntryImportDraft] = {}
        self._documents: dict[str, object] = {}
        self._lock = Lock()

    def prepare_selected_file(self, path: str | Path) -> NFeEntryDraft:
        source = Path(path).expanduser().resolve(strict=True)
        if source.suffix.casefold() != ".xml" or not source.is_file():
            raise ValueError("Selecione um arquivo XML local de NF-e.")
        size = source.stat().st_size
        if size <= 0 or size > self._max_bytes:
            raise ValueError("O XML está vazio ou excede o limite seguro de tamanho.")
        raw = source.read_bytes()
        lowered = raw.lower()
        if b"<!doctype" in lowered or b"<!entity" in lowered:
            raise ValueError("XML com DTD ou entidade não é aceito na entrada assistida.")
        source_hash = hashlib.sha256(raw).hexdigest()
        document = self._xml.ler(source)
        self._imports.validar_nao_importada(document)
        analyses = tuple(self._imports.analisar(document))
        if len(analyses) != len(document.itens):
            raise RuntimeError("A análise oficial não cobriu todos os itens do XML.")
        items = tuple(self._item(analysis) for analysis in analyses)
        payload = {
            "source_sha256": source_hash,
            "access_key": str(document.chave or ""),
            "number": str(document.numero or ""),
            "supplier_document": str(document.cnpj or ""),
            "protocol_status_evidence": str(document.protocolo_status or ""),
            "document_total": format(float(document.valor_total or 0), ".2f"),
            "recipient_name": str(document.destinatario or ""),
            "recipient_document": str(document.destinatario_documento or ""),
            "items": [
                {
                    "index": item.index, "supplier_code": item.supplier_code,
                    "description": item.description, "quantity": item.quantity,
                    "unit": item.unit, "unit_cost": item.unit_cost,
                    "suggested_conversion_factor": item.suggested_conversion_factor,
                    "factor_confidence": item.factor_confidence,
                    "factor_evidence": item.factor_evidence,
                    "match_status": item.match_status,
                    "suggested_product_id": item.suggested_product_id,
                    "match_criterion": item.match_criterion,
                }
                for item in items
            ],
        }
        fingerprint = hashlib.sha256(json.dumps(
            payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")).hexdigest()
        draft = NFeEntryDraft(
            uuid4().hex, fingerprint, str(source), source_hash,
            payload["access_key"], payload["number"], str(document.fornecedor or ""),
            payload["supplier_document"], payload["protocol_status_evidence"],
            payload["document_total"], payload["recipient_name"],
            payload["recipient_document"], items,
        )
        with self._lock:
            self._drafts[draft.draft_id] = draft
            self._documents[draft.draft_id] = document
            if len(self._drafts) > 10:
                expired = next(iter(self._drafts))
                self._drafts.pop(expired)
                self._documents.pop(expired, None)
        return draft

    def prepare_exact_import(
        self, review_draft_id: str, conversion_factors
    ) -> NFeEntryImportDraft:
        """Prepara entrada apenas para vínculos exatos e fatores explícitos."""
        review = self.get(review_draft_id)
        if not isinstance(review, NFeEntryDraft):
            raise TypeError("A entrada deve partir de uma revisão local de XML.")
        factors = tuple(self._positive_decimal(value, "Fator de conversão") for value in conversion_factors)
        if len(factors) != len(review.items):
            raise ValueError("Informe o fator de conversão de todos os itens da NF-e.")
        if review.protocol_status_evidence != "100":
            raise ValueError(
                "A automação exige evidência local cStat 100 no XML; isso não valida "
                "autenticidade nem consulta a SEFAZ. Faça a conferência humana."
            )
        if not review.recipient_document:
            raise ValueError(
                "O destinatário da NF-e não possui documento no XML; faça a conferência humana."
            )
        unsafe = []
        for item in review.items:
            exact_ids = {
                candidate.product_id for candidate in item.candidates
                if candidate.criterion in {"EAN", "CÓDIGO"}
                and Decimal(candidate.similarity) == Decimal("100.00")
            }
            if (
                item.match_status != "VINCULAR"
                or item.match_criterion not in {"EAN", "CÓDIGO"}
                or item.suggested_product_id is None
                or exact_ids != {item.suggested_product_id}
            ):
                unsafe.append(item)
        if unsafe:
            raise ValueError(
                "A NF-e possui produto novo, ambíguo ou ligado somente por nome; "
                "faça a conferência humana antes da entrada."
            )
        source = Path(review.source_path).resolve(strict=True)
        raw = source.read_bytes()
        if hashlib.sha256(raw).hexdigest() != review.source_sha256:
            raise PermissionError("O arquivo XML mudou depois da revisão.")
        document = self._xml.ler(source)
        self._imports.validar_nao_importada(document)
        with self._lock:
            original = self._documents.get(review.draft_id)
        if original is None or document != original:
            raise PermissionError("O conteúdo fiscal local mudou depois da revisão.")
        items = tuple(
            NFeEntryImportDraftItem(
                item.index,
                int(item.suggested_product_id),
                item.supplier_code,
                item.description,
                self._positive_decimal(item.quantity, "Quantidade do XML"),
                factor,
                (self._positive_decimal(item.quantity, "Quantidade do XML") * factor).quantize(
                    Decimal("0.0001"), rounding=ROUND_HALF_UP
                ),
                item.unit,
                self._nonnegative_decimal(item.unit_cost, "Custo unitário"),
            )
            for item, factor in zip(review.items, factors)
        )
        payload = {
            "review_fingerprint": review.fingerprint,
            "source_sha256": review.source_sha256,
            "access_key": review.access_key,
            "items": [{
                "index": item.index,
                "product_id": item.product_id,
                "xml_quantity": format(item.xml_quantity, "f"),
                "conversion_factor": format(item.conversion_factor, "f"),
                "stock_quantity": format(item.stock_quantity, "f"),
                "unit_cost": format(item.unit_cost, "f"),
            } for item in items],
        }
        fingerprint = hashlib.sha256(json.dumps(
            payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")).hexdigest()
        draft = NFeEntryImportDraft(
            uuid4().hex, fingerprint, review.draft_id, review.source_path,
            review.source_sha256, review.access_key, review.number,
            review.supplier_name, review.supplier_document,
            review.protocol_status_evidence,
            self._nonnegative_decimal(review.document_total, "Total da NF-e"),
            review.recipient_name, review.recipient_document, items,
        )
        with self._lock:
            self._drafts[draft.draft_id] = draft
            self._documents[draft.draft_id] = document
        return draft

    def get(self, draft_id: str) -> NFeEntryDraft | NFeEntryImportDraft:
        with self._lock:
            draft = self._drafts.get(str(draft_id or ""))
        if draft is None:
            raise ValueError("Revisão de XML não encontrada ou descartada.")
        return draft

    def document_for(self, draft_id: str):
        with self._lock:
            document = self._documents.get(str(draft_id or ""))
        if document is None:
            raise ValueError("Documento da entrada não encontrado ou descartado.")
        return document

    @staticmethod
    def _positive_decimal(value, field: str) -> Decimal:
        try:
            parsed = Decimal(str(value).replace(",", ".")).quantize(Decimal("0.0001"))
        except (InvalidOperation, ValueError) as error:
            raise ValueError(f"{field} inválido.") from error
        if not parsed.is_finite() or parsed <= 0:
            raise ValueError(f"{field} inválido.")
        return parsed

    @staticmethod
    def _nonnegative_decimal(value, field: str) -> Decimal:
        try:
            parsed = Decimal(str(value).replace(",", ".")).quantize(Decimal("0.01"))
        except (InvalidOperation, ValueError) as error:
            raise ValueError(f"{field} inválido.") from error
        if not parsed.is_finite() or parsed < 0:
            raise ValueError(f"{field} inválido.")
        return parsed

    @staticmethod
    def _item(analysis) -> NFeEntryDraftItem:
        xml_item = analysis.item
        factor_suggestion = NFePackagingFactorService.suggest_from_description(
            xml_item.descricao
        )
        candidates = tuple(NFeEntryCandidate(
            int(candidate.produto_id), str(candidate.codigo or ""),
            str(candidate.nome or ""), str(candidate.criterio or ""),
            format(float(candidate.similaridade or 0), ".2f"),
        ) for candidate in analysis.candidatos)
        return NFeEntryDraftItem(
            int(analysis.index), str(xml_item.codigo or ""),
            str(xml_item.descricao or ""), format(float(xml_item.quantidade), ".4f"),
            str(xml_item.unidade or ""), format(float(xml_item.valor_unitario), ".2f"),
            format(factor_suggestion.factor, "f") if factor_suggestion else "",
            factor_suggestion.confidence if factor_suggestion else "",
            factor_suggestion.evidence if factor_suggestion else "",
            str(analysis.status or ""),
            int(analysis.produto_id) if analysis.produto_id is not None else None,
            str(analysis.criterio or ""), candidates,
        )
