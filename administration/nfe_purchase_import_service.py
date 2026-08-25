from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from enum import Enum
import hashlib
import json
from pathlib import Path
import re
import unicodedata
from datetime import datetime

from assistant_nabi import NFeEntryDraftService


STANDARD_UNITS = (
    ("UN", "Unidade"), ("CX", "Caixa"), ("PCT", "Pacote"),
    ("FD", "Fardo"), ("DZ", "Dúzia"), ("PAR", "Par"),
    ("KIT", "Kit"), ("KG", "Quilograma"), ("G", "Grama"),
    ("L", "Litro"), ("ML", "Mililitro"), ("M", "Metro"),
    ("M2", "Metro quadrado"), ("M3", "Metro cúbico"),
)


class FactorSuggestionConfidence(str, Enum):
    """Confiança limitada à evidência textual determinística encontrada."""

    HIGH = "ALTA"


@dataclass(frozen=True, slots=True)
class PurchaseFactorSuggestion:
    """Sugestão informativa; não representa decisão nem autorização de gravação."""

    factor: Decimal
    evidence: str
    confidence: FactorSuggestionConfidence


_EXPLICIT_PACKAGE_PATTERNS = (
    re.compile(r"\bCAIXA\s+(?:COM|C/)\s*(?P<count>\d+)\s*UN(?:IDADE)?S?\b"),
    re.compile(r"\bCX\s+(?:COM|C/)\s*(?P<count>\d+)(?:\s*UN(?:IDADE)?S?)?\b"),
    re.compile(r"\bPACK\s+(?P<count>\d+)(?:\s*UN(?:IDADE)?S?)?\b"),
)


def suggest_purchase_factor(description: str) -> PurchaseFactorSuggestion | None:
    """Extrai somente quantidades de embalagem declaradas explicitamente.

    O retorno é deliberadamente passivo: consumidores podem exibir a sugestão,
    mas o fator continua dependendo de revisão e confirmação humanas no fluxo de
    importação. Ausência, quantidade inválida ou mais de uma evidência não gera
    palpite.
    """

    normalized = unicodedata.normalize("NFKD", str(description or "").upper())
    normalized = "".join(character for character in normalized if not unicodedata.combining(character))
    normalized = " ".join(normalized.split())
    matches: list[tuple[Decimal, str]] = []
    for pattern in _EXPLICIT_PACKAGE_PATTERNS:
        for match in pattern.finditer(normalized):
            count = Decimal(match.group("count"))
            if count > 1:
                matches.append((count, match.group(0)))
    if len(matches) != 1:
        return None
    factor, evidence = matches[0]
    return PurchaseFactorSuggestion(
        factor=factor,
        evidence=evidence,
        confidence=FactorSuggestionConfidence.HIGH,
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
        self.database = imports.repository.database
        self._ensure_draft_schema()

    def _ensure_draft_schema(self):
        with self.database.session(write=True) as connection:
            connection.executescript("""
            CREATE TABLE IF NOT EXISTS nfe_importacao_rascunhos(
              id INTEGER PRIMARY KEY AUTOINCREMENT,usuario TEXT NOT NULL,empresa_documento TEXT NOT NULL,
              chave TEXT NOT NULL,xml_sha256 TEXT NOT NULL,arquivo_origem TEXT NOT NULL,numero TEXT NOT NULL DEFAULT '',
              fornecedor_nome TEXT NOT NULL DEFAULT '',fornecedor_documento TEXT NOT NULL DEFAULT '',pagina_atual INTEGER NOT NULL DEFAULT 0,
              estado_json TEXT NOT NULL,estado_sha256 TEXT NOT NULL,status TEXT NOT NULL DEFAULT 'PENDENTE',
              criado_em TEXT NOT NULL,atualizado_em TEXT NOT NULL,concluido_em TEXT,descartado_em TEXT,
              UNIQUE(usuario,empresa_documento,chave,xml_sha256));
            CREATE INDEX IF NOT EXISTS idx_nfe_rascunhos_pendentes ON nfe_importacao_rascunhos(usuario,empresa_documento,status,atualizado_em);
            CREATE TABLE IF NOT EXISTS nfe_importacao_rascunho_auditoria(
              id INTEGER PRIMARY KEY AUTOINCREMENT,rascunho_id INTEGER NOT NULL,usuario TEXT NOT NULL,
              evento TEXT NOT NULL,detalhe TEXT NOT NULL DEFAULT '',criado_em TEXT NOT NULL,
              FOREIGN KEY(rascunho_id) REFERENCES nfe_importacao_rascunhos(id));
            """)

    def _identity(self, permission=("produtos", "view")):
        actor = self._require(*permission)
        company = self._digits(self.company_document_provider() if self.company_document_provider else "")
        if not company:
            raise ValueError("A empresa precisa possuir CNPJ configurado para guardar rascunhos de NF-e.")
        return actor, company

    @staticmethod
    def _state_payload(rows, page):
        allowed = ("acao", "produto_id", "codigo", "descricao", "codigo_barras", "tipo_fator", "fator", "unidade", "margem", "preco", "raw_margin", "raw_price", "status")
        return {"version": 1, "page": int(page), "rows": [{key: (format(value, "f") if isinstance(value, Decimal) else value) for key, value in row.items() if key in allowed} for row in rows]}

    def save_draft(self, draft, rows, *, page=0):
        actor, company = self._identity()
        payload = json.dumps(self._state_payload(rows, page), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        digest = hashlib.sha256(payload.encode("utf-8")).hexdigest(); now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with self.database.session(write=True) as connection:
            previous = connection.execute(
                "SELECT id,estado_json,estado_sha256 FROM nfe_importacao_rascunhos WHERE usuario=? AND empresa_documento=? AND chave=? AND xml_sha256=?",
                (actor, company, draft.access_key, draft.source_sha256),
            ).fetchone()
            previous_content_hash = hashlib.sha256(
                str(previous["estado_json"]).encode("utf-8")
            ).hexdigest() if previous else ""
            if (
                previous
                and str(previous["estado_sha256"]) == digest
                and previous_content_hash == digest
            ):
                return int(previous["id"])
            connection.execute("""INSERT INTO nfe_importacao_rascunhos
              (usuario,empresa_documento,chave,xml_sha256,arquivo_origem,numero,fornecedor_nome,fornecedor_documento,pagina_atual,estado_json,estado_sha256,status,criado_em,atualizado_em)
              VALUES(?,?,?,?,?,?,?,?,?,?,?,'PENDENTE',?,?)
              ON CONFLICT(usuario,empresa_documento,chave,xml_sha256) DO UPDATE SET
              arquivo_origem=excluded.arquivo_origem,numero=excluded.numero,fornecedor_nome=excluded.fornecedor_nome,
              fornecedor_documento=excluded.fornecedor_documento,pagina_atual=excluded.pagina_atual,estado_json=excluded.estado_json,
              estado_sha256=excluded.estado_sha256,status='PENDENTE',atualizado_em=excluded.atualizado_em,concluido_em=NULL,descartado_em=NULL""",
              (actor,company,draft.access_key,draft.source_sha256,draft.source_path,draft.number,draft.supplier_name,draft.supplier_document,int(page),payload,digest,now,now))
            row = connection.execute("SELECT id FROM nfe_importacao_rascunhos WHERE usuario=? AND empresa_documento=? AND chave=? AND xml_sha256=?",(actor,company,draft.access_key,draft.source_sha256)).fetchone()
            if previous is None:
                connection.execute("INSERT INTO nfe_importacao_rascunho_auditoria(rascunho_id,usuario,evento,detalhe,criado_em) VALUES(?,?, 'CRIADO','rascunho automático iniciado',?)",(int(row['id']),actor,now))
            return int(row["id"])

    def pending_drafts(self):
        actor, company = self._identity()
        return tuple(dict(row) for row in self.database.fetch_all("""SELECT id,numero,fornecedor_nome,fornecedor_documento,chave,xml_sha256,arquivo_origem,pagina_atual,atualizado_em
          FROM nfe_importacao_rascunhos WHERE usuario=? AND empresa_documento=? AND status='PENDENTE' ORDER BY atualizado_em DESC,id DESC""",(actor,company)))

    def resume_draft(self, draft_id):
        actor, company = self._identity()
        row = self.database.fetch_one("SELECT * FROM nfe_importacao_rascunhos WHERE id=? AND usuario=? AND empresa_documento=? AND status='PENDENTE'",(int(draft_id),actor,company))
        if not row: raise PermissionError("Rascunho não localizado para este usuário e esta empresa.")
        raw = str(row["estado_json"]); digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
        if digest != row["estado_sha256"]: raise ValueError("O rascunho está corrompido e não pode ser retomado.")
        source = Path(row["arquivo_origem"])
        if not source.is_file() or hashlib.sha256(source.read_bytes()).hexdigest() != row["xml_sha256"]:
            raise ValueError("O XML original não existe mais ou foi alterado; o rascunho foi preservado.")
        draft = self.prepare(source)
        if draft.access_key != row["chave"] or draft.source_sha256 != row["xml_sha256"]:
            raise ValueError("A chave ou o conteúdo do XML não corresponde ao rascunho.")
        state = json.loads(raw)
        if state.get("version") != 1 or len(state.get("rows", ())) != len(draft.items): raise ValueError("O rascunho possui estrutura incompatível.")
        return draft, state

    def discard_draft(self, draft_id, *, confirmed=False):
        actor, company = self._identity()
        if not confirmed: raise PermissionError("Confirmação explícita obrigatória para descartar o rascunho.")
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with self.database.session(write=True) as connection:
            row=connection.execute("SELECT id FROM nfe_importacao_rascunhos WHERE id=? AND usuario=? AND empresa_documento=? AND status='PENDENTE'",(int(draft_id),actor,company)).fetchone()
            if not row: raise PermissionError("Rascunho não localizado para este usuário e esta empresa.")
            connection.execute("UPDATE nfe_importacao_rascunhos SET status='DESCARTADO',descartado_em=?,atualizado_em=? WHERE id=?",(now,now,int(draft_id)))
            connection.execute("INSERT INTO nfe_importacao_rascunho_auditoria(rascunho_id,usuario,evento,detalhe,criado_em) VALUES(?,?,'DESCARTADO','confirmação explícita',?)",(int(draft_id),actor,now))

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
        document = self.document(draft.draft_id)
        if str(getattr(document, "modelo", "") or "").strip() != "55":
            raise ValueError("Selecione um XML autorizado de NF-e modelo 55.")
        access_key = self._digits(getattr(document, "chave", ""))
        if len(access_key) != 44:
            raise ValueError("A chave de acesso da NF-e deve possuir 44 dígitos.")
        configured = self._digits(
            self.company_document_provider() if self.company_document_provider else ""
        )
        recipient = self._digits(draft.recipient_document)
        if configured:
            if not recipient:
                raise ValueError("O XML não informa o documento do destinatário.")
            if configured != recipient:
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
        source = Path(draft.source_path)
        try:
            current_hash = hashlib.sha256(source.read_bytes()).hexdigest()
        except OSError as exc:
            raise ValueError("O XML revisado não está mais disponível no local original.") from exc
        if current_hash != draft.source_sha256:
            raise ValueError(
                "O XML foi alterado depois da revisão. Selecione e revise o arquivo novamente."
            )
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
        result = self.imports.importar_atomicamente(
            document, arquivo_origem=draft.source_path, itens=prepared,
            expected_actor=actor, idempotency_key=key,
            operation_fingerprint=fingerprint,
        )
        actor, company = self._identity(("compras", "receive")); now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with self.database.session(write=True) as connection:
            matches=connection.execute("SELECT id FROM nfe_importacao_rascunhos WHERE usuario=? AND empresa_documento=? AND chave=? AND xml_sha256=? AND status='PENDENTE'",(actor,company,draft.access_key,draft.source_sha256)).fetchall()
            for saved in matches:
                connection.execute("UPDATE nfe_importacao_rascunhos SET status='CONCLUIDO',concluido_em=?,atualizado_em=? WHERE id=?",(now,now,int(saved['id'])))
                connection.execute("INSERT INTO nfe_importacao_rascunho_auditoria(rascunho_id,usuario,evento,detalhe,criado_em) VALUES(?,?,'CONCLUIDO','importação atômica concluída',?)",(int(saved['id']),actor,now))
        return result
