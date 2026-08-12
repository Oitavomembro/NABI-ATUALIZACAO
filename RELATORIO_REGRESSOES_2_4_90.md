# Relatório de regressões — NabiCode 2.4.90

## Evidência automatizada

- Compilação Python: aprovada (`python -m compileall -q .`).
- Testes focados iniciais: 42 passed.
- Testes adicionais das regressões observadas no Windows: 5 passed.
- Suíte completa final: 740 passed, 12 subtests passed.
- Falhas finais automatizadas: 0.

## `python main.py`

A execução foi tentada no ambiente de integração, mas a validação gráfica não pôde ser concluída por bloqueios do ambiente:

- `_tkinter.TclError: couldn't connect to display ":0"`
- `ModuleNotFoundError: No module named 'customtkinter'`

Portanto, a validação manual no Windows permanece obrigatória para os fluxos gráficos.

## Smoke tests manuais ainda necessários no Windows

Login sem senha inesperada; Dashboard; Pesquisa de produtos; Lista de sugestões; Venda; Finalização; Impressão 80 mm; PDF somente quando solicitado; Reimpressão; Financeiro; Cadastros; Favoritar cliente; busca de clientes; histórico com saldo; venda autorizada de produto sem estoque.

## Vídeo

Nenhum arquivo de vídeo foi recebido nesta conversa. Os ajustes visuais foram baseados nas capturas de tela anexadas; glitches adicionais visíveis apenas no vídeo não foram validados.
