# Hotfix bloqueador — smoke test Windows 2.4.99

## Bug 1 — impressão na finalização da venda

### Causa raiz

`janela_venda_finalizada` chamava `self.imprimir_cupom_venda_80mm`, mas o método foi perdido durante a extração para `LegacyBackendAdapterMixin`. Como `FicharioMoveisApp` herda de Tk, a resolução de atributo ausente foi delegada ao objeto Tcl/Tk interno, produzindo `'_tkinter.tkapp' object has no attribute ...`.

### Correção

O método foi restaurado no owner correto, `LegacyBackendAdapterMixin`. Ele monta o texto pelo `ReceiptService` e envia uma única vez por `PrintingService.print_text` com o formato oficial `Cupom 80 mm`. Não gera PDF. O corte continua pertencendo exclusivamente ao `_raw_payload` do pipeline já aprovado, portanto ocorre no máximo uma vez.

O pipeline de recebimento não foi alterado.

## Bug 2 — reimpressão histórica COMPRA

### Causa raiz

O histórico identifica vendas antigas pelo tipo persistido `COMPRA`. A reimpressão converte esse fluxo para comprovante `RECIBO`, mas `ReceiptValidator.TYPE_ALIASES` não reconhecia nem `RECIBO` nem `COMPRA` como venda. A validação endurecida na refatoração removeu compatibilidade histórica implícita.

### Correção

Adicionados aliases `RECIBO -> VENDA` e `COMPRA -> VENDA`. Nenhum registro antigo é alterado. O preview unificado, impressão 80 mm, PDF opcional e botão Fechar permanecem intactos; o diálogo antigo não foi restaurado.

## Bug 3 — foco ao fechar PDV

### Causa raiz

O `CTkToplevel` do PDV tinha master, mas não declarava explicitamente `transient(self)`, e `_fechar_pdv` apenas destruía a janela. No Windows, sem owner/foco restaurado, o sistema podia ativar outra aplicação.

### Correção

O PDV agora declara a janela principal como owner via `transient(self)`. Ao fechar, libera eventual grab, destrói somente o PDV, limpa a referência e agenda via `after_idle` a rotina já existente que verifica a janela principal, faz `deiconify` somente se retirada, aplica `lift` e restaura foco com segurança.

Não foi criada segunda `Tk`, não houve alteração no runtime lock e não foram adicionados loops/update repetitivos.

## Arquivos modificados

- `controllers/legacy_backend_adapter.py`
- `validators/receipt_validator.py`
- `nabicode_legacy.py`
- `tests/test_hotfix_smoke_windows_2499.py`
- este relatório

## Testes adicionados

Cinco regressões para owner do adapter, pipeline físico 80 mm único, ausência de PDF automático, aliases históricos, preview unificado e lifecycle/foco do PDV.

## Validação focada

`59 passed in 6.36s`.

## Status

Hotfix automatizado concluído. A versão não é declarada candidata estável novamente; exige novo smoke test manual no Windows.
