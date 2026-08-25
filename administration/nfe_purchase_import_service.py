from __future__ import annotations

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
import hashlib
import json

from assistant_nabi import NFeEntryDraftService


STANDARD_UNITS = (
    ("UN", "Unidade"), ("CX", "Caixa"), ("PCT", "Pacote"),
    ("FD", "Fardo"), ("DZ", "Dúzia"), ("PAR", "Par"),
    ("KIT", "Kit"), ("KG", "Quilograma"), ("G", "Grama"),
    ("L", "Litro"), ("ML", "Mililitro"), ("M", "Metro"),
    ("M2", "Metro quadrado"), ("M3", "Metro cúbico"),
)


class NFePurchaseImportManagementService:
    """Fachada humana para entrada de NF-e; a gravação final continua atômica."""

    def __init__(self, imports, security, *, company_document_provider=None) -> None:
        if imports is None or security is None:
            raise ValueError("Importação oficial e segurança são obrigatórias.")
        self.imports = imports
        self.security = security
        self.drafts = NFeEntryDraftService(imports)
        self.company_document_provider = company_document_provider

    def _require(self, module: str, action: str) -> str:
        session = self.security.session
        if session is None or self.security.is_expired():
            raise PermissionError("Sessão expirada. Entre novamente.")
        if not self.security.require(module, action):
            raise PermissionError(f"Permissão {module}/{action} obrigatória.")
        self.security.touch()
        return session.user.username

    @staticmethod
    def _digits(value) -> str:
        return "".join(ch for ch in str(value or "") if ch.isdigit())

    @staticmethod
    def _decimal(value, field: str, *, positive=False) -> Decimal:
        try:
            if isinstance(value, Decimal):
                parsed = value
            else:
                text = str(value or "").strip()
                normalized = text.replace(".", "").replace(",", ".") if "," in text else text
                parsed = Decimal(normalized)
        except (InvalidOperation, ValueError) as exc:
            raise ValueError(f"{field} inválido.") from exc
        if not parsed.is_finite() or parsed < 0 or (positive and parsed <= 0):
            raise ValueError(f"{field} inválido.")
        return parsed

    def prepare(self, path):
        self._require("produtos", "view")
        draft = self.drafts.prepare_selected_file(path)
        configured = self._digits(
            self.company_document_provider() if self.company_document_provider else ""
        )
        recipient = self._digits(draft.recipient_document)
        if configured and recipient and configured != recipient:
            raise ValueError(
                "O destinatário do XML não corresponde ao CNPJ configurado nesta empresa."
            )
        return draft

    def document(self, draft_id):
        return self.drafts.document_for(draft_id)

    def units(self) -> tuple[tuple[str, str], ...]:
        self._require("produtos", "view")
        found = {code: description for code, description in STANDARD_UNITS}
        for row in self.imports.repository.listar_unidades_ativas():
            code = str(row.get("sigla") or "").strip().upper()
            if code:
                found[code] = str(row.get("descricao") or code)
        return tuple(sorted(found.items()))

    def saved_link(self, draft, item_index: int):
        item = draft.items[item_index]
        return self.imports.repository.localizar_vinculo_fornecedor(
            fornecedor_documento=draft.supplier_document,
            codigo_fornecedor=item.supplier_code,
        )

    def commit(self, draft, rows, *, confirmed: bool):
        actor = self._require("compras", "receive")
        if not confirmed:
            raise PermissionError("A confirmação humana final é obrigatória.")
        document = self.document(draft.draft_id)
        if draft.protocol_status_evidence != "100":
            raise ValueError("O XML não contém evidência cStat 100; a entrada foi bloqueada.")
        if len(rows) != len(document.itens):
            raise ValueError("Revise todos os itens antes de confirmar a entrada.")
        prepared = []
        canonical = []
        allowed_units = {code for code, _description in self.units()}
        for index, (xml_item, row) in enumerate(zip(document.itens, rows), start=1):
            action = str(row.get("acao") or "").strip().upper()
            product_id = row.get("produto_id")
            self.imports.validar_decisao(action, product_id)
            unit = str(row.get("unidade") or "").strip().upper()
            if unit not in allowed_units:
                raise ValueError(f"Item {index}: selecione uma unidade cadastrada.")
            entered_factor = self._decimal(row.get("fator"), f"Item {index}: fator", positive=True)
            factor_kind = str(row.get("tipo_fator") or "MULTIPLICAR").upper()
            if factor_kind not in {"MULTIPLICAR", "DIVIDIR"}:
                raise ValueError(f"Item {index}: tipo de fator inválido.")
            factor = entered_factor if factor_kind == "MULTIPLICAR" else Decimal("1") / entered_factor
            factor = factor.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
            quantity = Decimal(str(xml_item.quantidade)).quantize(Decimal("0.0001"))
            stock_quantity = (quantity * factor).quantize(Decimal("0.0001"))
            if stock_quantity <= 0:
                raise ValueError(f"Item {index}: quantidade convertida inválida.")
            package_cost = Decimal(str(xml_item.valor_unitario))
            unit_cost = (package_cost / factor).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            price = self._decimal(row.get("preco"), f"Item {index}: preço")
            margin = self._decimal(row.get("margem"), f"Item {index}: margem")
            expected = (unit_cost * (Decimal("1") + margin / Decimal("100"))).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )
            if price != expected:
                raise ValueError(
                    f"Item {index}: preço e margem perderam sincronismo; revise novamente."
                )
            item_data = {
                "acao": action, "produto_id": int(product_id) if product_id else None,
                "codigo": str(row.get("codigo") or xml_item.codigo).strip(),
                "descricao": str(row.get("descricao") or xml_item.descricao).strip(),
                "codigo_barras": str(row.get("codigo_barras") or xml_item.codigo_barras).strip(),
                "ncm": str(xml_item.ncm or "").strip(), "cest": str(xml_item.cest or "").strip(),
                "unidade": unit, "quantidade": quantity, "fator": factor,
                "custo": unit_cost, "margem": margin, "preco": price,
            }
            prepared.append(item_data)
            canonical.append({key: str(value) for key, value in item_data.items()})
        fingerprint = hashlib.sha256(json.dumps(
            {"draft": draft.fingerprint, "items": canonical},
            ensure_ascii=False, sort_keys=True, separators=(",", ":"),
        ).encode("utf-8")).hexdigest()
        key = f"nfe-ui:{draft.access_key or draft.source_sha256}"
        return self.imports.importar_atomicamente(
            document, arquivo_origem=draft.source_path, itens=prepared,
            expected_actor=actor, idempotency_key=key,
            operation_fingerprint=fingerprint,
        )
