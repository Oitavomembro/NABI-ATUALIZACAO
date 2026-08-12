from __future__ import annotations

from typing import Any

from database import DatabaseManager


class ReceiptRepository:
    def __init__(self, database: DatabaseManager) -> None:
        self.database = database

    def customer(self, customer_id: int):
        return self.database.fetch_one(
            "SELECT nome, codigo, numero_ficha, telefone, endereco FROM clientes WHERE id=?",
            (customer_id,),
        )

    def payment(self, movement_id: int):
        return self.database.fetch_one(
            """SELECT m.cliente_id, COALESCE(c.nome,'Sem cliente'),
                      COALESCE(c.codigo,''), COALESCE(c.numero_ficha,''),
                      COALESCE(m.descricao,''), COALESCE(m.valor,0),
                      COALESCE(m.data,''), COALESCE(m.forma_pagamento,''),
                      COALESCE(m.responsavel,'')
               FROM movimentacoes m
               LEFT JOIN clientes c ON c.id=m.cliente_id
               WHERE m.id=? AND m.tipo='PAGAMENTO'""",
            (movement_id,),
        )

    def sale_allocation(self, movement_id: int):
        return self.database.fetch_one(
            """SELECT COALESCE(data,''), COALESCE(descricao,'Venda'),
                      COALESCE(valor,0), COALESCE(valor_aberto,0),
                      COALESCE(total_parcelas,1), COALESCE(status_pagamento,'')
               FROM movimentacoes WHERE id=?""",
            (movement_id,),
        )

    def sale_payment_plan(self, movement_id: int):
        return self.database.fetch_one(
            """SELECT COALESCE(forma_pagamento,''), COALESCE(total_parcelas,1),
                      COALESCE(valor_aberto,0), COALESCE(status_pagamento,'')
               FROM movimentacoes WHERE id=?""",
            (movement_id,),
        )

    def parcels(self, movement_id: int) -> list[Any]:
        return self.database.fetch_all(
            """SELECT id, numero_parcela, valor_parcela, COALESCE(vencimento,''),
                      COALESCE(status,'PENDENTE'), COALESCE(valor_pago,0),
                      COALESCE(data_pagamento,'')
               FROM parcelas WHERE movimentacao_id=?
               ORDER BY numero_parcela, id""",
            (movement_id,),
        )

    def payment_plan_parcels(self, movement_id: int) -> list[Any]:
        return self.database.fetch_all(
            """SELECT numero_parcela, valor_parcela, COALESCE(vencimento,''),
                      COALESCE(status,'PENDENTE')
               FROM parcelas WHERE movimentacao_id=?
               ORDER BY numero_parcela, id""",
            (movement_id,),
        )
