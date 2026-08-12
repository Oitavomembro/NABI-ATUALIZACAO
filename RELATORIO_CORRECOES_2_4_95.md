# NabiCode 2.4.95 — Reimpressão, layout e impressão

## Correções

- Reduzido espaçamento/fonte dos botões da área de Clientes para manter `Histórico` integralmente visível em resoluções menores.
- Reimpressão de venda deixou de usar o diálogo nativo antigo `Sim / Não / Cancelar`.
- Reimpressão agora usa o mesmo padrão visual do recibo de pagamento: pré-visualização textual, `Imprimir cupom 80 mm`, `Salvar PDF (opcional)` e `Fechar`.
- A impressão da segunda via usa o mesmo caminho de impressão textual 80 mm já validado no recibo, em vez de depender da impressão direta do PDF.
- PDF da segunda via passa a ser gerado somente quando o usuário clicar em `Salvar PDF (opcional)`.
- Reimpressões de outras movimentações também utilizam a janela unificada de pré-visualização.
- Corte automático 80 mm preservado da 2.4.94, já validado no Windows pelo usuário.

## Validação automatizada

- `python -m compileall -q .`: aprovado.
- Testes focados de impressão/documental/reimpressão: 26 passed.
- Suíte completa: 792 passed, 12 subtests passed, 0 falhas.

## Execução gráfica

`python main.py` foi tentado neste ambiente, mas a abertura ficou bloqueada por ambiente sem display e sem customtkinter:

- `_tkinter.TclError: couldn't connect to display ":0"`
- `ModuleNotFoundError: No module named 'customtkinter'`

A validação visual/física deve ser concluída no Windows.

## Testes manuais prioritários no Windows

1. Confirmar que o botão `Histórico` aparece inteiro na tela Clientes.
2. Reimprimir uma venda e confirmar o novo layout de pré-visualização.
3. Clicar `Imprimir cupom 80 mm` na segunda via e confirmar impressão física + corte.
4. Clicar `Salvar PDF (opcional)` e confirmar que o PDF só é gerado nesse momento.
5. Reimprimir pagamento e demais comprovantes e confirmar padrão visual consistente.
