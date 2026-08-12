# Checkpoint 27 — Teste do aplicativo empacotado

Data: 08/08/2026  
Status: **PENDENTE DE BUILD E VALIDAÇÃO WINDOWS**

## Resultado honesto

Não existe distribuição Windows neste ambiente Linux. PyInstaller não faz cross-build, e o pipeline recusou a operação com código de saída 2. Portanto, startup e fluxos do onedir não foram declarados aprovados.

## Validações realizadas no código-fonte

- smoke de versão 2.5.1;
- runtime profile e lock;
- separação programa/dados;
- build audit e spec onedir;
- manifesto/hashes em distribuição simulada;
- recusa de banco/caches;
- projeto do instalador offline.

Os testes focados dos Checkpoints 23–28 passaram. A suíte completa será executada no Checkpoint 32.

## Matriz obrigatória para o onedir Windows

| Item | Estado |
| --- | --- |
| smoke do EXE e versão | automatizado no pipeline; pendente de execução Windows |
| runtime profile `PRODUCAO` | pendente |
| lock/segunda instância | pendente no novo onedir |
| banco e migrações | pendente no novo onedir |
| Dashboard e navegação | pendente |
| Produtos, Clientes e Histórico | pendente |
| Financeiro e PDV | pendente |
| cupom RAW, corte e A4 | pendente com hardware |
| PDF e reimpressão | pendente |
| assets/fontes | pendente |
| fechamento e persistência | pendente |
| manifesto e SHA-256 | gerados automaticamente após build |

## Arquivos alterados

- `CHECKPOINT_27_TESTE_APLICATIVO_EMPACOTADO.md`.

Nenhum código funcional foi alterado neste checkpoint.
