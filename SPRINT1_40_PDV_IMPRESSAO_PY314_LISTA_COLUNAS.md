# Sprint 1.40 — PDV, impressão segura no Python 3.14 e lista com colunas

## Correções

- Removido o uso de `os.startfile(pdf, "print")`, responsável por encerramento fatal do CPython 3.14 em determinadas associações de leitor PDF no Windows.
- Criado `WindowsPDFPrinter`, que delega `Print`/`PrintTo` a um processo PowerShell independente.
- Restaurado o modal pós-venda visual com três ações explícitas: imprimir cupom 80 mm, finalizar e gerar PDF.
- Lista de produtos passou a usar tabela com colunas Código, Produto / Serviço, Preço e Estoque.
- Tipografia da lista padronizada em Segoe UI 11, cabeçalho em negrito e linhas de 30 px.
- Navegação por setas, Enter, teclado numérico, clique, produto avulso e seleção por índice preservadas.

## Travas de regressão

- Proibido `os.startfile(..., "print")` no legado.
- Testado comando PowerShell para impressora padrão e impressora nomeada.
- Testado contrato visual do modal pós-venda.
- Testado contrato de colunas e fonte da lista de produtos.
