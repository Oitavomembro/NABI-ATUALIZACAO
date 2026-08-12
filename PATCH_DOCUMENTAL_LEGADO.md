# PATCH DOCUMENTAL DO LEGADO — NabiCode v2.4.90

`nabicode_legacy.py` **não foi alterado** nesta sprint. Este arquivo descreve somente o encaminhamento necessário dos saldos já reconciliados pelo Financeiro.

## Motivo

`FinanceiroService.receber_pagamento_cliente()` já retorna `saldo_anterior` e `novo_saldo`, mas o legado encaminha ao recibo apenas `pagamento_mov_id` e `alocacoes`. O módulo documental não deve reconstruir esses saldos.

## Função `receber_pagamento_cliente` / callback `confirmar`

Substituir:

```python
self.janela_recibo_pagamento_cliente(resultado["pagamento_mov_id"], resultado["alocacoes"])
```

por:

```python
self.janela_recibo_pagamento_cliente(
    resultado["pagamento_mov_id"],
    resultado["alocacoes"],
    saldo_anterior=resultado["saldo_anterior"],
    novo_saldo=resultado["novo_saldo"],
)
```

## Função `texto_recibo_pagamento_cliente`

Alterar a assinatura para receber `saldo_anterior=None, novo_saldo=None` e encaminhar:

```python
return self._servico_comprovantes().build_payment_text(
    mov_id,
    alocacoes,
    balance_before=saldo_anterior,
    balance_after=novo_saldo,
)
```

## Função `janela_recibo_pagamento_cliente`

Alterar a assinatura para receber `saldo_anterior=None, novo_saldo=None` e repassar os mesmos valores para `texto_recibo_pagamento_cliente` e para a ação opcional de PDF.

## Função `gerar_pdf_pagamento_cliente`

Alterar a assinatura para receber `saldo_anterior=None, novo_saldo=None` e encaminhar:

```python
return self._servico_pdf_documentos().generate_customer_payment(
    mov_id,
    allocations=alocacoes,
    destination=destino,
    balance_before=saldo_anterior,
    balance_after=novo_saldo,
)
```

Este patch não altera regra financeira, persistência ou valores. Apenas transporta os dados reconciliados já produzidos pelo Financeiro até os renderizadores documentais.
