from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from uuid import uuid4
from collections import OrderedDict
from threading import Lock


_CENT = Decimal("0.01")
_QUANTITY = Decimal("0.0001")
_PAYMENT_METHODS = {"DINHEIRO", "PIX", "DEBITO", "CREDITO", "CREDIARIO", "OUTROS"}


def _quantity(value) -> Decimal:
    if isinstance(value, bool) or isinstance(value, float):
        raise ValueError("Quantidade deve ser informada como texto decimal.")
    try:
        result = Decimal(str(value)).quantize(_QUANTITY)
    except (InvalidOperation, ValueError) as error:
        raise ValueError("Quantidade inválida.") from error
    if not result.is_finite() or result <= 0:
        raise ValueError("Quantidade deve ser maior que zero.")
    return result


@dataclass(frozen=True, slots=True)
class SaleDraftItemRequest:
    product_id: int
    quantity: Decimal

    def __post_init__(self) -> None:
        if isinstance(self.product_id, bool) or int(self.product_id) <= 0:
            raise ValueError("Produto inválido no rascunho.")
        object.__setattr__(self, "product_id", int(self.product_id))
        object.__setattr__(self, "quantity", _quantity(self.quantity))


@dataclass(frozen=True, slots=True)
class SaleDraftItem:
    product_id: int
    code: str
    description: str
    quantity: Decimal
    unit_price: Decimal
    line_total: Decimal
    stock_before: Decimal
    stock_after: Decimal


@dataclass(frozen=True, slots=True)
class SaleDraft:
    draft_id: str
    fingerprint: str
    customer_id: int | None
    payment_method: str
    items: tuple[SaleDraftItem, ...]
    total: Decimal


class SaleDraftService:
    """Prepara uma proposta imutável sem criar sessão de PDV ou alterar estado."""

    def __init__(self, query_service, *, max_items: int = 50) -> None:
        if query_service is None:
            raise ValueError("O serviço oficial de consultas é obrigatório.")
        self._queries = query_service
        self._max_items = max(1, min(int(max_items), 100))
        self._drafts: OrderedDict[str, SaleDraft] = OrderedDict()
        self._lock = Lock()

    def create(
        self,
        requests,
        *,
        payment_method: str,
        customer_id: int | None = None,
    ) -> SaleDraft:
        normalized = tuple(
            item if isinstance(item, SaleDraftItemRequest) else SaleDraftItemRequest(**item)
            for item in requests
        )
        if not normalized:
            raise ValueError("O rascunho exige ao menos um produto.")
        if len(normalized) > self._max_items:
            raise ValueError("O rascunho excede o limite seguro de itens.")
        ids = [item.product_id for item in normalized]
        if len(ids) != len(set(ids)):
            raise ValueError("O mesmo produto não pode aparecer duas vezes no rascunho.")
        method = str(payment_method or "").strip().upper()
        if method not in _PAYMENT_METHODS:
            raise ValueError("Forma de pagamento inválida no rascunho.")
        customer = None
        if customer_id is not None:
            if isinstance(customer_id, bool) or int(customer_id) <= 0:
                raise ValueError("Cliente inválido no rascunho.")
            customer = self._queries.get_customer(int(customer_id))
            if customer is None:
                raise ValueError("Cliente não encontrado.")
            customer_id = int(customer.customer_id)
        if method == "CREDIARIO" and customer_id is None:
            raise ValueError("Crediário exige cliente identificado.")

        items = tuple(self._resolve_item(item) for item in normalized)
        total = sum((item.line_total for item in items), Decimal("0.00")).quantize(_CENT)
        if total <= 0:
            raise ValueError("O total do rascunho deve ser maior que zero.")
        fingerprint = self._fingerprint(customer_id, method, items, total)
        draft = SaleDraft(
            draft_id=uuid4().hex,
            fingerprint=fingerprint,
            customer_id=customer_id,
            payment_method=method,
            items=items,
            total=total,
        )
        with self._lock:
            self._drafts[draft.draft_id] = draft
            while len(self._drafts) > 20:
                self._drafts.popitem(last=False)
        return draft

    def create_for_target(
        self,
        target_amount,
        *,
        tolerance_amount,
        max_units_per_product: int,
        payment_method: str,
        customer_id: int | None = None,
        candidate_limit: int = 20,
    ) -> SaleDraft:
        """Planeja por preços/estoques oficiais e só aceita resultado na tolerância."""
        target = self._positive_money(target_amount, "Valor alvo")
        tolerance = self._non_negative_money(tolerance_amount, "Tolerância")
        if target > Decimal("100000.00"):
            raise ValueError("Valor alvo excede o limite seguro do planejador.")
        if tolerance > target:
            raise ValueError("Tolerância não pode superar o valor alvo.")
        if isinstance(max_units_per_product, bool):
            raise ValueError("Limite de unidades por produto inválido.")
        max_units = int(max_units_per_product)
        if max_units < 1 or max_units > 100:
            raise ValueError("Limite de unidades por produto deve ficar entre 1 e 100.")

        candidates = tuple(self._queries.high_stock_products(
            limit=max(1, min(int(candidate_limit), 30))
        ))
        prepared = []
        for product in candidates:
            price = Decimal(str(product.sale_price)).quantize(_CENT, rounding=ROUND_HALF_UP)
            stock = Decimal(str(product.current_stock)).quantize(_QUANTITY)
            available_units = min(max_units, max(0, int(stock)))
            if bool(product.active) and price > 0 and available_units > 0:
                prepared.append((product, int(price * 100), available_units))
        if not prepared:
            raise ValueError("Não há produtos vendáveis com estoque positivo para o planejamento.")

        target_cents = int(target * 100)
        tolerance_cents = int(tolerance * 100)
        ceiling = target_cents + tolerance_cents
        states: dict[int, tuple[int, ...]] = {0: ()}
        for _, price_cents, available_units in prepared:
            next_states: dict[int, tuple[int, ...]] = {}
            for subtotal, counts in states.items():
                for amount in range(available_units + 1):
                    total = subtotal + (price_cents * amount)
                    if total <= ceiling and total not in next_states:
                        next_states[total] = counts + (amount,)
            if len(next_states) > 50000:
                retained = sorted(
                    next_states,
                    key=lambda subtotal: (abs(subtotal - target_cents), subtotal),
                )[:50000]
                next_states = {subtotal: next_states[subtotal] for subtotal in retained}
            states = next_states
        valid = [
            (subtotal, counts) for subtotal, counts in states.items()
            if subtotal > 0 and abs(subtotal - target_cents) <= tolerance_cents
        ]
        if not valid:
            closest = min(
                (subtotal for subtotal in states if subtotal > 0),
                key=lambda subtotal: (abs(subtotal - target_cents), subtotal),
                default=None,
            )
            suffix = ""
            if closest is not None:
                suffix = f" Combinação mais próxima: R$ {Decimal(closest) / 100:.2f}."
            raise ValueError("Nenhuma combinação atende à tolerância informada." + suffix)

        def rank(entry):
            subtotal, counts = entry
            high_stock_priority = sum(
                amount * (len(prepared) - index)
                for index, amount in enumerate(counts)
            )
            return (abs(subtotal - target_cents), -high_stock_priority, sum(counts), subtotal)

        _, selected = min(valid, key=rank)
        requests = tuple(
            SaleDraftItemRequest(product.product_id, str(amount))
            for (product, _, _), amount in zip(prepared, selected)
            if amount > 0
        )
        return self.create(
            requests, payment_method=payment_method, customer_id=customer_id
        )

    def get(self, draft_id: str) -> SaleDraft:
        with self._lock:
            draft = self._drafts.get(str(draft_id or ""))
        if draft is None:
            raise ValueError("Rascunho não encontrado ou descartado.")
        return draft

    def discard(self, draft_id: str) -> None:
        with self._lock:
            self._drafts.pop(str(draft_id or ""), None)

    @staticmethod
    def _positive_money(value, field: str) -> Decimal:
        result = SaleDraftService._non_negative_money(value, field)
        if result <= 0:
            raise ValueError(f"{field} deve ser maior que zero.")
        return result

    @staticmethod
    def _non_negative_money(value, field: str) -> Decimal:
        if isinstance(value, bool) or isinstance(value, float):
            raise ValueError(f"{field} deve ser informado como texto decimal.")
        try:
            result = Decimal(str(value).replace(",", ".")).quantize(_CENT)
        except (InvalidOperation, ValueError) as error:
            raise ValueError(f"{field} inválido.") from error
        if not result.is_finite() or result < 0:
            raise ValueError(f"{field} inválido.")
        return result

    def _resolve_item(self, request: SaleDraftItemRequest) -> SaleDraftItem:
        product = self._queries.get_product(request.product_id)
        if product is None or not bool(product.active):
            raise ValueError(f"Produto #{request.product_id} não encontrado ou inativo.")
        price = Decimal(str(product.unit_price)).quantize(_CENT, rounding=ROUND_HALF_UP)
        if price <= 0:
            raise ValueError(f"Produto {product.code} não possui preço de venda positivo.")
        stock = self._queries.product_stock(request.product_id)
        before = Decimal(str(stock.current_quantity)).quantize(_QUANTITY)
        after = (before - request.quantity).quantize(_QUANTITY)
        if after < 0 and not bool(stock.allow_negative_stock):
            raise ValueError(f"Estoque insuficiente para o produto {product.code}.")
        return SaleDraftItem(
            product_id=product.product_id,
            code=str(product.code),
            description=str(product.description),
            quantity=request.quantity,
            unit_price=price,
            line_total=(request.quantity * price).quantize(_CENT, rounding=ROUND_HALF_UP),
            stock_before=before,
            stock_after=after,
        )

    @staticmethod
    def _fingerprint(customer_id, payment_method, items, total) -> str:
        payload = {
            "customer_id": customer_id,
            "payment_method": payment_method,
            "items": [
                {
                    "product_id": item.product_id,
                    "quantity": format(item.quantity, "f"),
                    "unit_price": format(item.unit_price, "f"),
                    "line_total": format(item.line_total, "f"),
                    "stock_before": format(item.stock_before, "f"),
                }
                for item in items
            ],
            "total": format(total, "f"),
        }
        canonical = json.dumps(
            payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
        return hashlib.sha256(canonical).hexdigest()
