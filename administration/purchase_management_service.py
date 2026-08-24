from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
import json

from repositories.assistant_operation_journal_repository import AssistantOperationJournalRepository
from services.compra_service import CompraService


@dataclass(frozen=True, slots=True)
class SupplierView:
    supplier_id: int
    name: str
    legal_name: str
    document: str
    active: bool


@dataclass(frozen=True, slots=True)
class PurchaseProductView:
    product_id: int
    code: str
    description: str
    unit_cost: Decimal
    current_stock: Decimal


@dataclass(frozen=True, slots=True)
class PurchaseOrderView:
    order_id: int
    status: str
    supplier_name: str
    created_at: str
    total: Decimal
    pending_quantity: Decimal
    user: str


class PurchaseManagementService:
    """Fachada Qt: ator/permissão vêm da sessão e o recebimento não é duplicado."""

    def __init__(self, purchase_service, supplier_repository, security) -> None:
        if purchase_service is None or supplier_repository is None or security is None:
            raise ValueError("Compras, fornecedores e segurança são obrigatórios.")
        self.purchase_service = purchase_service
        self.repository = purchase_service.repository
        self.suppliers = supplier_repository
        self.security = security
        self.operation_journal = AssistantOperationJournalRepository()
        supplier_path = getattr(getattr(self.suppliers, "database", None), "database_path", None)
        purchase_path = getattr(getattr(self.purchase_service, "database", None), "database_path", None)
        if isinstance(supplier_path, (str, bytes)) and isinstance(purchase_path, (str, bytes)) and supplier_path != purchase_path:
            raise ValueError("Compras e fornecedores devem utilizar o mesmo banco de dados.")

    def _require(self, action: str) -> str:
        session = self.security.session
        if session is None or self.security.is_expired():
            raise PermissionError("Sessão expirada. Entre novamente.")
        if not self.security.require("compras", action):
            raise PermissionError("Usuário sem permissão para esta operação de compras.")
        self.security.touch()
        return str(session.user.username)

    def list_orders(self, status: str = "", *, limit: int = 100) -> tuple[PurchaseOrderView, ...]:
        self._require("view")
        normalized = str(status or "").strip().upper()
        rows = self.repository.listar_pedidos(
            None if normalized in {"", "TODOS"} else normalized,
            limite=max(1, min(int(limit), 200)),
        )
        return tuple(PurchaseOrderView(
            int(row["id"]), str(row.get("status") or ""),
            str(row.get("fornecedor_nome") or ""), str(row.get("criado_em") or ""),
            Decimal(str(row.get("valor_total") or 0)),
            Decimal(str(row.get("quantidade_pendente") or 0)),
            str(row.get("usuario") or ""),
        ) for row in rows)

    def get_order(self, order_id: int):
        self._require("view")
        order = self.repository.obter_pedido(int(order_id))
        if order is None: raise ValueError("Pedido de compra não encontrado.")
        return order

    def list_suppliers(self) -> tuple[SupplierView, ...]:
        self._require("view")
        rows = self.repository.listar_fornecedores(somente_ativos=False)
        return tuple(SupplierView(
            int(row["id"]), str(row.get("nome_fantasia") or row.get("razao_social") or ""),
            str(row.get("razao_social") or ""), str(row.get("cnpj") or ""), bool(row.get("ativo")),
        ) for row in rows)

    def create_supplier(self, name: str, *, legal_name: str = "", document: str = "") -> int:
        self._require("create")
        normalized = " ".join(str(name or "").split())
        if not normalized: raise ValueError("Informe o nome do fornecedor.")
        return int(self.suppliers.criar(
            normalized, razao_social=" ".join(str(legal_name or "").split()) or normalized,
            cnpj=str(document or "").strip(),
        ))

    def create_supplier_assisted(
        self, name: str, *, legal_name: str = "", document: str = "",
        phone: str = "", email: str = "", expected_username: str,
        idempotency_key: str, operation_fingerprint: str,
    ) -> int:
        username = self._require("create")
        if username != str(expected_username or ""):
            raise PermissionError("A confirmação pertence a outra sessão de usuário.")
        normalized = " ".join(str(name or "").split())
        if not normalized:
            raise ValueError("Informe o nome do fornecedor.")
        key, fingerprint = CompraService._idempotency_fields(
            idempotency_key, operation_fingerprint
        )
        with self.purchase_service.database.session(write=True) as connection:
            previous = self.operation_journal.get(connection, key)
            if previous is not None:
                if previous["fingerprint"].lower() != fingerprint:
                    raise PermissionError("A chave idempotente já pertence a outro conteúdo.")
                if previous["status"].upper() != "COMMITTED":
                    raise RuntimeError("A operação assistida possui estado persistente desconhecido.")
                return int(json.loads(previous["result_json"])["supplier_id"])
            self.operation_journal.begin(
                connection, idempotency_key=key,
                operation_kind="SUPPLIER_CREATE", fingerprint=fingerprint,
                username=username,
            )
            supplier_id = self.suppliers.criar(
                normalized, connection=connection,
                razao_social=" ".join(str(legal_name or "").split()) or normalized,
                cnpj=str(document or "").strip(), telefone=str(phone or "").strip(),
                email=str(email or "").strip(),
            )
            connection.execute(
                """INSERT INTO auditoria(data,usuario,modulo,acao,objeto,detalhes,resultado)
                   VALUES(datetime('now','localtime'),?,'Compras','CRIAR_FORNECEDOR',?,?, 'SUCESSO')""",
                (username, str(supplier_id), f"Fornecedor {normalized}; idempotency={key}"),
            )
            self.operation_journal.commit(
                connection, idempotency_key=key,
                result_json=json.dumps({"supplier_id": supplier_id}, sort_keys=True, separators=(",", ":")),
            )
        return supplier_id

    def list_products(self, supplier_id: int | None = None) -> tuple[PurchaseProductView, ...]:
        self._require("view")
        return tuple(PurchaseProductView(
            int(row["id"]), str(row.get("codigo") or ""), str(row.get("nome") or ""),
            Decimal(str(row.get("preco_custo") or 0)), Decimal(str(row.get("estoque_atual") or 0)),
        ) for row in self.repository.listar_produtos_compra(supplier_id))

    def create_order(self, supplier_id: int, items, *, notes: str = "") -> int:
        username = self._require("create")
        return int(self.purchase_service.criar_pedido(
            int(supplier_id), tuple(items), observacao=str(notes or ""), usuario=username,
        ))

    def create_order_assisted(
        self, supplier_id: int, items, *, notes: str = "",
        expected_username: str, idempotency_key: str,
        operation_fingerprint: str,
    ) -> int:
        username = self._require("create")
        if username != str(expected_username or ""):
            raise PermissionError("A confirmação pertence a outra sessão de usuário.")
        return int(self.purchase_service.criar_pedido(
            int(supplier_id), tuple(items), observacao=str(notes or ""),
            usuario=username, idempotency_key=idempotency_key,
            operation_fingerprint=operation_fingerprint,
        ))

    def receive_order(
        self, order_id: int, items, *, document: str = "", notes: str = "",
        create_payable: bool = False, due_date: str | None = None,
    ):
        username = self._require("receive")
        # Uma única chamada ao serviço transacional oficial. A GUI não cria
        # estoque, custo, título financeiro ou journal separadamente.
        return self.purchase_service.receber(
            int(order_id), tuple(items), documento=str(document or ""),
            observacao=str(notes or ""), usuario=username,
            gerar_conta_pagar=bool(create_payable), data_vencimento=due_date,
        )
