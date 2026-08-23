from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from threading import Lock
from uuid import uuid4

from services.nfe_xml_service import NFeXMLService


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
    items: tuple[NFeEntryDraftItem, ...]
    operation_kind: str = "NFE_ENTRY_REVIEW"
    persisted: bool = False
    executable: bool = False


class NFeEntryDraftService:
    """Lê XML selecionado pelo operador e prepara evidência; nunca importa."""

    def __init__(self, import_service, *, xml_service=None, max_bytes: int = 10_000_000) -> None:
        if import_service is None:
            raise ValueError("Serviço oficial de análise de NF-e obrigatório.")
        self._imports = import_service
        self._xml = xml_service or NFeXMLService()
        self._max_bytes = max(1024, min(int(max_bytes), 50_000_000))
        self._drafts: dict[str, NFeEntryDraft] = {}
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
            "items": [
                {
                    "index": item.index, "supplier_code": item.supplier_code,
                    "description": item.description, "quantity": item.quantity,
                    "unit": item.unit, "unit_cost": item.unit_cost,
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
            payload["document_total"], items,
        )
        with self._lock:
            self._drafts[draft.draft_id] = draft
            if len(self._drafts) > 10:
                self._drafts.pop(next(iter(self._drafts)))
        return draft

    def get(self, draft_id: str) -> NFeEntryDraft:
        with self._lock:
            draft = self._drafts.get(str(draft_id or ""))
        if draft is None:
            raise ValueError("Revisão de XML não encontrada ou descartada.")
        return draft

    @staticmethod
    def _item(analysis) -> NFeEntryDraftItem:
        xml_item = analysis.item
        candidates = tuple(NFeEntryCandidate(
            int(candidate.produto_id), str(candidate.codigo or ""),
            str(candidate.nome or ""), str(candidate.criterio or ""),
            format(float(candidate.similaridade or 0), ".2f"),
        ) for candidate in analysis.candidatos)
        return NFeEntryDraftItem(
            int(analysis.index), str(xml_item.codigo or ""),
            str(xml_item.descricao or ""), format(float(xml_item.quantidade), ".4f"),
            str(xml_item.unidade or ""), format(float(xml_item.valor_unitario), ".2f"),
            str(analysis.status or ""),
            int(analysis.produto_id) if analysis.produto_id is not None else None,
            str(analysis.criterio or ""), candidates,
        )
