# Sprint 1.21 — Pesquisa global e schema fora dos repositórios

## Objetivo
Eliminar mutação de schema em construtores e padronizar pesquisas principais fora do PDV.

## Alterações
- `ProdutoRepository` deixou de executar `ALTER TABLE`, criação e remoção de índices no construtor.
- Bootstrap passou a ser a única camada responsável pelos índices e compatibilidade do EAN.
- Pesquisas de Produtos e Clientes recebem cores, seleção ao foco e consumo de Enter padronizados.
- Adicionado teste que prova que instanciar o repositório não altera o banco.
