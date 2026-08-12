# NabiCode v2.4.45 — Sprint 1.4

## Objetivo

Retirar do `nabicode_legacy.py` a regra de avaliação de possíveis produtos duplicados e corrigir a identificação de versão da base oficial.

## Alterações realizadas

- Criado `ProductDuplicateAssessment` em `services/product_application_service.py`.
- Criado `ProductApplicationService.avaliar_duplicidade(...)` para centralizar:
  - quando a busca de similares deve ocorrer;
  - consulta de produtos semelhantes;
  - armazenamento imutável do resultado;
  - formatação do resumo apresentado ao usuário.
- A edição de produto não dispara avaliação de duplicidade, preservando o comportamento anterior.
- `nabicode_legacy.py` deixou de consultar e formatar diretamente produtos semelhantes.
- Exportação do novo tipo adicionada em `services/__init__.py`.
- Adicionados testes unitários para avaliação e resumo de duplicidade.
- `VERSAO.txt` corrigido para `2.4.45`; a base recebida estava nomeada como 2.4.44, mas mantinha internamente 2.4.43.

## Testes executados

- Testes focados em Produtos/Estoque: 24 testes, todos aprovados.
- Suíte completa: 515 testes, todos aprovados.
- Compilação sintática dos arquivos alterados: aprovada.

## Regressões encontradas

- Nenhuma regressão funcional encontrada.
- Inconsistência de versão da base anterior corrigida nesta sprint.

## Próxima Sprint

Produtos — extrair do legado a preparação dos dados do formulário e a conversão dos campos para `ProductSaveCommand`, mantendo a UI apenas como coleta e apresentação.
