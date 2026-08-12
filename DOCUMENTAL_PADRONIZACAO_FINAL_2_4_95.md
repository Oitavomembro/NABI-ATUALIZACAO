# DOCUMENTAL — PADRONIZAÇÃO FINAL 2.4.95

Base auditada: `NabiCode_v2_4_95_TESTE_REIMPRESSAO_LAYOUT`

## Escopo auditado

- impressão 80 mm;
- reimpressão;
- PDF;
- renderização documental;
- compatibilidade ESC/POS;
- corte automático;
- segunda via.

Nenhuma alteração de Interface, layout, PDV, Financeiro, Cadastros, `BackgroundManager`, `ThemeManager` ou `nabicode_legacy.py` foi realizada.

## Alterações realizadas

### `services/printing_service.py`

- centralizados os bytes ESC/POS de corte total e parcial;
- criada `_raw_payload()` como ponto único para montar o trabalho RAW;
- normalização de quebras de linha, codificação CP850, avanço de papel e corte passam por uma única rotina;
- `print_raw_text()` envia ao spooler exatamente um payload já finalizado;
- mantidos os comandos ESC/POS existentes `GS V 0` (total) e `GS V 1` (parcial), evitando alteração de protocolo sem necessidade;
- preservado limite de 0 a 12 linhas antes do corte;
- preservada configuração para desativar corte automático.

### `services/document_rendering.py`

- removido `profile_for_output_format()`, helper sem qualquer chamada no projeto;
- preservados `THERMAL_58_PROFILE` e suporte interno de 58 mm necessário para compatibilidade histórica;
- preservado 80 mm como formato térmico oficial.

## PDF / reimpressão / segunda via

Auditoria concluída sem alteração necessária nesses arquivos.

Confirmado no código e nos testes existentes:

- PDF continua separado da impressão física;
- reimpressão utiliza o preview unificado;
- PDF de reimpressão só é criado mediante ação explícita de salvar PDF;
- impressão física permanece em 80 mm;
- suporte interno histórico de 58 mm não foi removido;
- segunda via não exigiu mudança de serviço nesta sprint.

## Código morto e imports mortos

- removido 1 helper documental morto: `profile_for_output_format()`;
- análise AST dos serviços documentais auditados não encontrou imports mortos em:
  - `services/printing_service.py`;
  - `services/document_rendering.py`;
  - `services/pdf_document_service.py`;
  - `services/receipt_service.py`;
  - `services/emitted_document_service.py`.

## Testes modificados

### `tests/test_printing_service.py`

Incluídos testes para:

- payload RAW com CP850 e CRLF;
- corte parcial exatamente uma vez;
- corte total;
- limite máximo de avanço antes do corte;
- corte automático desativado.

### `tests/test_v243_splash_and_cutter.py`

Atualizado teste legado que dependia da implementação antiga `payload += self._cut_payload()`.
O teste agora valida o contrato consolidado `_raw_payload()` + envio único ao `WritePrinter`.

## Resultados

Testes focados iniciais:

`48 passed`

Testes históricos de corte, diálogo e reimpressão:

`22 passed`

Suíte completa:

`795 passed, 12 subtests passed, 0 falhas`

Tempo observado da suíte completa: `16.40 s`.

Compilação dos arquivos alterados: aprovada.

## `python main.py`

Executado antes da entrega.

A aplicação não abriu neste ambiente por bloqueios externos ao módulo documental:

- `_tkinter.TclError: couldn't connect to display ":0"`;
- `ModuleNotFoundError: No module named 'customtkinter'`.

Portanto, a validação automatizada está aprovada, mas a abertura gráfica precisa ser confirmada no Windows antes de considerar a sprint completamente validada em runtime.

## Regressões

Nenhuma regressão automatizada encontrada.

Nenhuma alteração visual foi realizada.
Nenhum EXE foi gerado.
