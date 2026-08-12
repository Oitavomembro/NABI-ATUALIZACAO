# Sprint 1.2 — Produtos: testes, desempenho e regressões

Base: `NabiCode_v2_4_44_SPRINT1_1_TESTES_CORRIGIDOS.zip`

## Correções

- Edição de produto inexistente agora é rejeitada antes de qualquer gravação.
- Código de barras não vazio passou a ser único entre produtos.
- Vários produtos continuam podendo permanecer sem código de barras.
- Bancos antigos recebem índice único parcial no código de barras quando não existem duplicidades legadas.
- Bancos que já possuem EANs duplicados continuam abrindo; novos conflitos são bloqueados pela camada de serviço.

## Desempenho

- Pesquisas comuns de produtos agora são filtradas primeiro pelo SQLite.
- O catálogo completo não é mais carregado em memória a cada tecla quando o termo possui correspondência direta.
- A busca sem acentos permanece compatível por meio de fallback apenas quando necessário.
- Adicionados índices para nome e combinação tipo/ativo.

## Qualidade

- Corrigidos arquivos abertos sem fechamento em testes de regressão.
- Adicionados testes para EAN único, EAN vazio repetido, edição inexistente e caminho rápido de pesquisa.

## Validação

- Testes focados: 20 OK.
- Suíte completa: 511 testes OK.
