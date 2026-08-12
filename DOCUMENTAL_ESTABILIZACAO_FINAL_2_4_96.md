# DOCUMENTAL — Estabilização final do pipeline — NabiCode v2.4.96

## Base

`NabiCode_v2_4_96_TESTE_INTEGRADO_HOTFIX_CLIENTES`

## Escopo auditado

- impressão térmica 80 mm;
- ESC/POS e corte automático;
- PDF sob demanda;
- recibo de pagamento;
- reimpressão;
- segunda via / preview documental;
- venda parcelada;
- saldo histórico migrado.

Não foram alterados Financeiro, Cadastros, Interface, PDV ou `nabicode_legacy.py`.

## Correções aplicadas

### 1. Compatibilidade interna de 58 mm restrita ao legado conhecido

`services/document_rendering.py` mantinha a regra `"58" in model`, que fazia qualquer nome futuro contendo `58` cair no perfil de 58 mm. Isso criava risco de reintrodução acidental de um formato oficialmente descontinuado.

A compatibilidade interna foi restringida aos identificadores históricos explícitos:

- `Térmica 58 mm econômica`;
- variante sem acentos;
- `58 mm`.

Qualquer outro modelo desconhecido passa pelo perfil térmico oficial de 80 mm. O renderizador interno de 58 mm não foi removido.

### 2. Espaçamento configurado preservado no recibo PDF de pagamento

`services/pdf_document_service.py` obtinha o `step` por `_render_config()` e em seguida o sobrescrevia por `size * 1.35`. Isso anulava `impressao_espacamento` somente nesse recibo.

A sobrescrita foi removida. O recibo de pagamento agora usa a mesma configuração documental centralizada dos demais documentos.

## Reimpressão e segunda via

A base já contém preview unificado para reimpressão e ações explícitas:

- Pré-visualização;
- Imprimir cupom 80 mm;
- Salvar PDF (opcional);
- Fechar.

O fluxo de reimpressão usa callback de PDF sob demanda e não cria PDF automaticamente.

Existem testes históricos de diálogos antigos em fluxos legados. Como esta sprint proíbe alterações em Interface e `nabicode_legacy.py`, nenhum diálogo foi modificado. O caminho oficial de reimpressão/segunda via já usa o preview padrão e foi protegido por regressão.

## ESC/POS e corte

O `PrintingService` foi auditado e não exigiu alteração nesta sprint:

- único despacho térmico oficial: `Cupom 80 mm`;
- payload RAW em CP850;
- normalização CRLF;
- corte ESC/POS `GS V`;
- parcial `1D 56 01`;
- total `1D 56 00`;
- avanço configurável limitado a 0–12 linhas;
- corte anexado uma única vez ao payload;
- impressão física não importa nem chama `PDFDocumentService`.

## Contrato financeiro documental

Nenhum cálculo financeiro foi adicionado.

O recibo continua apenas exibindo:

- saldo antes reconciliado;
- valor recebido;
- saldo depois reconciliado;
- distribuição recebida;
- compras e parcelas associadas.

O teste de saldo histórico confirma que a distribuição recebida é exibida sem reconstrução do saldo do cliente.

## Testes criados/atualizados

`tests/test_document_pipeline.py`:

- confirma uso do espaçamento centralizado no PDF de pagamento;
- confirma compatibilidade 58 mm apenas para nomes legados explícitos;
- confirma 80 mm para modelos desconhecidos que apenas contenham o texto `58`.

`tests/test_documental_stabilization_2496.py`:

1. impressão 80 mm não cria PDF;
2. PDF não dispara impressão física;
3. reimpressão usa preview unificado e não usa diálogo antigo;
4. segunda via/preview possui ações padrão;
5. corte ESC/POS ocorre uma única vez;
6. recibo usa saldo antes/depois reconciliados;
7. venda parcelada mantém detalhamento das parcelas;
8. saldo histórico usa a distribuição reconciliada recebida.

## Resultados

Testes focados iniciais:

`49 passed`

Regressão documental ampliada:

`66 passed`

Suíte completa:

`835 passed, 11 subtests passed, 0 failed`

Compilação dos arquivos alterados: aprovada.

Auditoria de imports mortos nos arquivos alterados: nenhum encontrado.

## `python main.py`

Executado antes da entrega.

A aplicação não abriu por bloqueios do ambiente Linux:

- `_tkinter.TclError: couldn't connect to display ":0"`;
- `ModuleNotFoundError: No module named 'customtkinter'`.

Isso impede validação gráfica local. A sprint não deve ser considerada validada visualmente até execução no Windows com as dependências instaladas.

## Regressões

Nenhuma regressão automatizada detectada.
