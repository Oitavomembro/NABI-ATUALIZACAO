from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
import hashlib
import json
from pathlib import Path
import re

from lxml import etree

from commercial.application.product_dto import ProductCreateCommand
from services.nfe_xml_service import NFeXMLService


MAX_LOCAL_XML_BYTES = 8 * 1024 * 1024
_NCM = re.compile(r"\d{8}")
_CEST = re.compile(r"\d{7}")
_UNIT = re.compile(r"[A-Za-z0-9]{1,6}")


@dataclass(frozen=True, slots=True)
class ProductXMLMatch:
    product_id: int
    code: str
    barcode: str
    description: str


@dataclass(frozen=True, slots=True)
class ProductXMLDraftItem:
    source_item: int
    code: str
    description: str
    barcode: str
    ncm: str
    cest: str
    unit: str
    cost_price: Decimal
    matches: tuple[ProductXMLMatch, ...]
    state: str
    warnings: tuple[str, ...]
    duplicate_of_item: int | None = None


@dataclass(frozen=True, slots=True)
class ProductXMLDraft:
    source_name: str
    source_sha256: str
    prepared_by: str
    items: tuple[ProductXMLDraftItem, ...]
    warnings: tuple[str, ...]
    fingerprint: str


@dataclass(frozen=True, slots=True)
class ProductXMLDecision:
    source_item: int
    action: str
    existing_product_id: int | None = None
    code: str = ""
    description: str = ""
    barcode: str = ""
    ncm: str = ""
    cest: str = ""
    unit: str = ""
    cost_price: Decimal = Decimal("0.00")
    sale_price: Decimal = Decimal("0.00")


@dataclass(frozen=True, slots=True)
class ProductXMLCommitResult:
    created_product_ids: tuple[int, ...]
    existing_product_ids: tuple[int, ...]
    skipped_source_items: tuple[int, ...]
    source_sha256: str


class ProductXMLCatalogImportService:
    """Prepara somente cadastros a partir de XML local não confiável.

    Não recebe nem compõe serviço fiscal, estoque, financeiro, compras ou rede.
    A autoridade de sessão/permissão fica na porta administrativa chamadora.
    """

    def __init__(self, products, *, reader: NFeXMLService | None = None) -> None:
        if products is None:
            raise ValueError("A fachada oficial de produtos é obrigatória.")
        self.products = products
        self.reader = reader or NFeXMLService()

    @staticmethod
    def _local_bytes(path: str | Path) -> tuple[Path, bytes]:
        raw_path = str(path or "").strip()
        if not raw_path or raw_path.startswith(("\\\\", "//")) or "://" in raw_path:
            raise ValueError("Selecione um arquivo XML local desta máquina.")
        source = Path(raw_path)
        if source.suffix.casefold() != ".xml" or not source.is_file():
            raise ValueError("Selecione um arquivo XML local válido.")
        size = source.stat().st_size
        if size <= 0 or size > MAX_LOCAL_XML_BYTES:
            raise ValueError("O XML local está vazio ou excede o limite de 8 MB.")
        raw = source.read_bytes()
        lowered = raw.lower()
        if b"<!doctype" in lowered or b"<!entity" in lowered:
            raise ValueError("DTD e entidades não são aceitas no XML de cadastro.")
        try:
            root = etree.fromstring(
                raw,
                parser=etree.XMLParser(
                    resolve_entities=False, no_network=True, huge_tree=False,
                    remove_comments=True,
                ),
            )
        except etree.XMLSyntaxError as exc:
            raise ValueError("O arquivo não contém XML válido para cadastro.") from exc
        inf_nfe = root.xpath(".//*[local-name()='infNFe']")
        if len(inf_nfe) != 1:
            raise ValueError("O XML deve conter exatamente uma NF-e para preparar produtos.")
        return source, raw

    @staticmethod
    def _match(product) -> ProductXMLMatch:
        return ProductXMLMatch(
            product_id=int(product.product_id),
            code=str(product.code or "").strip(),
            barcode=str(product.barcode or "").strip(),
            description=str(product.description or "").strip(),
        )

    def _identifier_matches(self, code: str, barcode: str) -> tuple[ProductXMLMatch, ...]:
        found: dict[int, ProductXMLMatch] = {}
        code_key = str(code or "").strip().casefold()
        barcode_key = str(barcode or "").strip().casefold()
        for term in dict.fromkeys(value for value in (code, barcode) if str(value or "").strip()):
            for product in self.products.search_products(str(term), limit=200):
                exact_code = code_key and str(product.code or "").strip().casefold() == code_key
                exact_barcode = (
                    barcode_key
                    and str(product.barcode or "").strip().casefold() == barcode_key
                )
                if exact_code or exact_barcode:
                    found[int(product.product_id)] = self._match(product)
        return tuple(found[key] for key in sorted(found))

    @staticmethod
    def _canonical_payload(
        source_sha256: str, prepared_by: str, items: tuple[ProductXMLDraftItem, ...],
    ) -> bytes:
        payload = {
            "source_sha256": source_sha256,
            "prepared_by": prepared_by,
            "items": [
                {
                    "source_item": item.source_item,
                    "code": item.code,
                    "description": item.description,
                    "barcode": item.barcode,
                    "ncm": item.ncm,
                    "cest": item.cest,
                    "unit": item.unit,
                    "cost_price": format(item.cost_price, "f"),
                    "matches": [match.product_id for match in item.matches],
                    "state": item.state,
                    "warnings": list(item.warnings),
                    "duplicate_of_item": item.duplicate_of_item,
                }
                for item in items
            ],
        }
        return json.dumps(
            payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
        ).encode("utf-8")

    def prepare(self, path: str | Path, *, actor: str) -> ProductXMLDraft:
        actor = str(actor or "").strip()
        if not actor:
            raise PermissionError("A sessão autenticada não possui identidade válida.")
        source, raw = self._local_bytes(path)
        before_hash = hashlib.sha256(raw).hexdigest()
        document = self.reader.ler(source)
        if hashlib.sha256(source.read_bytes()).hexdigest() != before_hash:
            raise RuntimeError("O XML local mudou durante a leitura; selecione-o novamente.")

        items: list[ProductXMLDraftItem] = []
        seen_codes: dict[str, int] = {}
        seen_barcodes: dict[str, int] = {}
        seen_item_numbers: set[int] = set()
        for position, source_item in enumerate(document.itens, start=1):
            item_number = int(source_item.item_numero or position)
            if item_number <= 0 or item_number in seen_item_numbers:
                raise ValueError(
                    "O XML contém numeração de itens ausente, repetida ou inválida."
                )
            seen_item_numbers.add(item_number)
            code = str(source_item.codigo or "").strip()
            description = " ".join(str(source_item.descricao or "").split())
            raw_barcode = str(source_item.codigo_barras or "").strip()
            barcode = "" if raw_barcode.upper().replace(" ", "") == "SEMGTIN" else raw_barcode
            raw_ncm = str(source_item.ncm or "").strip()
            ncm = raw_ncm if _NCM.fullmatch(raw_ncm) else ""
            raw_cest = str(source_item.cest or "").strip()
            cest = raw_cest if not raw_cest or _CEST.fullmatch(raw_cest) else ""
            raw_unit = str(source_item.unidade or "").strip().upper()
            unit = raw_unit if _UNIT.fullmatch(raw_unit) else ""
            cost = Decimal(str(source_item.valor_unitario)).quantize(Decimal("0.01"))
            warnings: list[str] = []
            if not code:
                warnings.append("cProd ausente; informe um código antes de cadastrar.")
            if not description:
                warnings.append("Descrição ausente; o item não pode ser cadastrado.")
            if raw_barcode and not barcode:
                warnings.append("O XML declara item sem GTIN; código de barras ficará vazio.")
            if not raw_ncm:
                warnings.append("NCM ausente; nenhum NCM foi sugerido.")
            elif not ncm:
                warnings.append("NCM do XML é inválido e não será usado automaticamente.")
            if raw_cest and not cest:
                warnings.append("CEST do XML é inválido e não será usado automaticamente.")
            if raw_unit and not unit:
                warnings.append("Unidade do XML é inválida e não será usada automaticamente.")

            matches = self._identifier_matches(code, barcode)
            state = "NOVO" if not matches else "JA_CADASTRADO" if len(matches) == 1 else "AMBIGUO"
            if matches:
                warnings.append(
                    "Código e/ou barras já existem; nenhum cadastro duplicado será criado."
                )
            code_key = code.casefold()
            barcode_key = barcode.casefold()
            duplicate_of = (
                seen_codes.get(code_key) if code_key else None
            ) or (
                seen_barcodes.get(barcode_key) if barcode_key else None
            )
            if duplicate_of is not None:
                state = "DUPLICADO_NO_XML"
                warnings.append(
                    f"Mesmo código/barras do item {duplicate_of}; esta linha não será cadastrada."
                )
            else:
                if code_key:
                    seen_codes[code_key] = item_number
                if barcode_key:
                    seen_barcodes[barcode_key] = item_number
            items.append(ProductXMLDraftItem(
                source_item=item_number, code=code, description=description,
                barcode=barcode, ncm=ncm, cest=cest, unit=unit,
                cost_price=cost, matches=matches, state=state,
                warnings=tuple(warnings), duplicate_of_item=duplicate_of,
            ))

        item_tuple = tuple(items)
        fingerprint = hashlib.sha256(
            self._canonical_payload(before_hash, actor, item_tuple)
        ).hexdigest()
        document_warnings = (
            "Fonte: XML local usado somente para preparar cadastro de produtos.",
            "Protocolo, evento e status fiscal foram ignorados; este fluxo não prova autorização.",
            "Nenhum estoque, compra, financeiro, documento fiscal ou comunicação SEFAZ foi criado.",
        )
        return ProductXMLDraft(
            source_name=source.name, source_sha256=before_hash,
            prepared_by=actor, items=item_tuple, warnings=document_warnings,
            fingerprint=fingerprint,
        )

    @staticmethod
    def _decimal(value, field: str) -> Decimal:
        try:
            result = Decimal(str(value)).quantize(Decimal("0.01"))
        except (InvalidOperation, ValueError) as exc:
            raise ValueError(f"{field} inválido.") from exc
        if not result.is_finite() or result < 0:
            raise ValueError(f"{field} não pode ser negativo.")
        return result

    @classmethod
    def _create_command(cls, decision: ProductXMLDecision) -> ProductCreateCommand:
        code = str(decision.code or "").strip()
        description = " ".join(str(decision.description or "").split())
        barcode = str(decision.barcode or "").strip()
        ncm = str(decision.ncm or "").strip()
        cest = str(decision.cest or "").strip()
        unit = str(decision.unit or "").strip().upper()
        if not code:
            raise ValueError(f"Item {decision.source_item}: informe o código do produto.")
        if not description:
            raise ValueError(f"Item {decision.source_item}: informe a descrição do produto.")
        if ncm and not _NCM.fullmatch(ncm):
            raise ValueError(f"Item {decision.source_item}: NCM deve ter exatamente 8 dígitos ou ficar vazio.")
        if cest and not _CEST.fullmatch(cest):
            raise ValueError(f"Item {decision.source_item}: CEST deve ter exatamente 7 dígitos ou ficar vazio.")
        if unit and not _UNIT.fullmatch(unit):
            raise ValueError(f"Item {decision.source_item}: unidade inválida.")
        return ProductCreateCommand(
            code=code, description=description,
            sale_price=cls._decimal(decision.sale_price, "Preço de venda"),
            barcode=barcode,
            cost_price=cls._decimal(decision.cost_price, "Preço de custo"),
            current_stock=Decimal("0"), minimum_stock=Decimal("0"),
            allow_negative_stock=False, ncm=ncm, cest=cest, unit_code=unit,
        )

    def commit(
        self, draft: ProductXMLDraft, decisions: tuple[ProductXMLDecision, ...],
        *, actor: str, confirmed: bool,
    ) -> ProductXMLCommitResult:
        if type(draft) is not ProductXMLDraft:
            raise TypeError("Rascunho XML inválido.")
        actor = str(actor or "").strip()
        if not confirmed:
            raise PermissionError("Confirmação humana explícita é obrigatória.")
        if not actor or actor != draft.prepared_by:
            raise PermissionError("O rascunho pertence a outra sessão autenticada.")
        expected_fingerprint = hashlib.sha256(
            self._canonical_payload(draft.source_sha256, draft.prepared_by, draft.items)
        ).hexdigest()
        if draft.fingerprint != expected_fingerprint:
            raise ValueError("O rascunho XML foi alterado; prepare-o novamente.")
        by_item = {decision.source_item: decision for decision in decisions}
        if len(by_item) != len(decisions) or set(by_item) != {
            item.source_item for item in draft.items
        }:
            raise ValueError("Revise uma decisão para cada item do XML.")

        commands: list[ProductCreateCommand] = []
        existing_ids: list[int] = []
        skipped: list[int] = []
        codes: set[str] = set()
        barcodes: set[str] = set()
        for item in draft.items:
            decision = by_item[item.source_item]
            action = str(decision.action or "").strip().upper()
            if item.state == "DUPLICADO_NO_XML":
                if action != "SKIP":
                    raise ValueError(f"Item {item.source_item}: duplicidade interna deve ser ignorada.")
                skipped.append(item.source_item)
                continue

            current_matches = self._identifier_matches(item.code, item.barcode)
            if tuple(match.product_id for match in current_matches) != tuple(
                match.product_id for match in item.matches
            ):
                raise RuntimeError(
                    f"Item {item.source_item}: o catálogo mudou; prepare o XML novamente."
                )
            if item.state == "AMBIGUO":
                allowed = {match.product_id for match in item.matches}
                if action != "USE_EXISTING" or decision.existing_product_id not in allowed:
                    raise ValueError(
                        f"Item {item.source_item}: escolha explicitamente um dos produtos encontrados."
                    )
                existing_ids.append(int(decision.existing_product_id))
                continue
            if item.state == "JA_CADASTRADO":
                expected = item.matches[0].product_id
                if action != "USE_EXISTING" or int(decision.existing_product_id or 0) != expected:
                    raise ValueError(
                        f"Item {item.source_item}: confirme o produto existente identificado."
                    )
                existing_ids.append(expected)
                continue
            if action == "SKIP":
                skipped.append(item.source_item)
                continue
            if action != "CREATE":
                raise ValueError(f"Item {item.source_item}: decisão de cadastro inválida.")
            command = self._create_command(decision)
            if self._identifier_matches(command.code, command.barcode):
                raise RuntimeError(
                    f"Item {item.source_item}: código ou barras agora pertence a um cadastro; "
                    "prepare o XML novamente."
                )
            code_key = command.code.casefold()
            barcode_key = command.barcode.casefold()
            if code_key in codes or (barcode_key and barcode_key in barcodes):
                raise ValueError("Dois novos cadastros repetem código ou código de barras.")
            codes.add(code_key)
            if barcode_key:
                barcodes.add(barcode_key)
            commands.append(command)

        created = tuple(self.products.create_products_from_xml(
            tuple(commands), actor=actor, source_sha256=draft.source_sha256,
            draft_fingerprint=draft.fingerprint,
            resolved_existing_ids=tuple(existing_ids),
            skipped_source_items=tuple(skipped),
        ))
        return ProductXMLCommitResult(
            created_product_ids=tuple(int(item.product_id) for item in created),
            existing_product_ids=tuple(existing_ids),
            skipped_source_items=tuple(skipped),
            source_sha256=draft.source_sha256,
        )
