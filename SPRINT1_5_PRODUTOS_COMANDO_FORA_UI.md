# Sprint 1.5 — Produtos: comando de salvamento fora da UI

## Alterações realizadas

- Criado `ProductFormData` para transportar os valores brutos coletados pelo formulário.
- Criado `ProductApplicationService.criar_comando(...)` para construir `ProductSaveCommand` fora da UI.
- Criado `ProductApplicationService.converter_numero(...)` para centralizar a conversão de números com vírgula e ponto.
- Removidas do fluxo de salvamento em `nabicode_legacy.py` as conversões numéricas e a montagem manual de `ProductSaveCommand`.
- Mantida na UI apenas a coleta dos widgets, confirmação de duplicidade e apresentação do resultado.
- Adicionados testes para valores brasileiros, campos vazios e entrada numérica inválida.

## Testes executados

- Testes focados de Produtos: 27 aprovados.
- Suíte completa: 518 aprovados.
- Compilação sintática dos arquivos alterados: aprovada.

## Regressões encontradas

- Nenhuma regressão funcional encontrada.

## Próxima Sprint

Produtos — extrair o preenchimento e a leitura do estado do formulário para uma estrutura própria, reduzindo callbacks e manipulação direta de widgets no legado.
