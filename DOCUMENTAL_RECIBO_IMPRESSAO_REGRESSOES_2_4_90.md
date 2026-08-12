# DOCUMENTAL — Recibo, impressão, PDF e reimpressão — NabiCode v2.4.90

## Base

`NabiCode_v2_4_90_BASE_OFICIAL_INTEGRADA(1).zip`

## Escopo auditado

- recibo de pagamento;
- impressão física;
- PDF sob demanda;
- reimpressão.

## Correções realizadas

- `PDFDocumentService.generate_customer_payment()` não calcula mais `Saldo antes` como `saldo atual + valor recebido`.
- `ReceiptService.build_payment_text()` não recalcula mais saldo do cliente.
- Os dois renderizadores recebem `balance_before` e `balance_after` como dados reconciliados externos.
- A consulta documental deixou de buscar `clientes.saldo_devedor` para reconstruir os saldos do recibo.
- Se uma reimpressão histórica não receber saldos reconciliados, o documento omite essas linhas em vez de inventar valores.
- Distribuição por compra e parcela continua sendo somente renderizada a partir de `allocations`; nenhuma regra financeira foi movida para o módulo documental.
- O `PrintingService` foi auditado e não precisou ser modificado: impressão 80 mm permanece no backend físico RAW, sem dependência de `PDFDocumentService`.

## Integração necessária com o legado

`FinanceiroService.receber_pagamento_cliente()` já retorna `saldo_anterior` e `novo_saldo`. O `nabicode_legacy.py` atual não encaminha esses campos ao recibo. Como o legado não pode ser modificado nesta conversa, foi entregue `PATCH_DOCUMENTAL_LEGADO.md` com o encaminhamento mínimo desses valores, sem modificar nem enviar o arquivo completo.

## Testes

Testes documentais focados:

- `47 passed`

Suíte completa da base:

- `744 passed, 12 subtests passed, 0 falhas`
- tempo observado: `13.68 s`

Também foram validados por testes existentes:

- impressão física separada de PDF;
- formato térmico oficial 80 mm;
- PDF apenas quando solicitado;
- fluxo de reimpressão;
- ação de abrir PDF sem impressão.

## Auditoria estática

- compilação dos arquivos Python modificados: aprovada;
- imports mortos detectados nos arquivos modificados: nenhum;
- recálculo documental de saldo removido;
- leitura documental desnecessária de `clientes.saldo_devedor` removida.

## `python main.py`

Executado após as alterações. A aplicação não abriu neste ambiente por bloqueios externos ao módulo documental:

```text
_tkinter.TclError: couldn't connect to display ":0"
ModuleNotFoundError: No module named 'customtkinter'
```

Por isso a validação gráfica não está concluída neste ambiente.

## Regressões / limitações

- Nenhuma regressão automatizada encontrada.
- Reimpressões históricas não têm como reconstruir corretamente saldo anterior/posterior se esses valores não tiverem sido persistidos ou encaminhados; o módulo documental deliberadamente não os recalcula.
- Nenhum arquivo de Financeiro, Interface, PDV ou Cadastro foi alterado.
- `nabicode_legacy.py` não foi alterado.
- Nenhum EXE foi gerado.
