# Auditoria de persistência — Checkpoint 8

## Escopo

Revisão estática das camadas `database`, `repositories`, `services`, `controllers`, `helpers` e `validators`, complementada pela suíte integral de regressão. Arquivos de navegação, tema, splash, widgets e transições visuais permaneceram fora do escopo de modificação.

## SQL direto

- Foram identificadas 388 chamadas literais a `execute`, `executemany` ou `executescript` no backend auditado.
- A maior concentração está em inicialização/migração de schema e repositórios, onde SQL é responsabilidade esperada da camada.
- SQL de aplicação foi mantido em serviços transacionais quando a operação coordena múltiplos agregados em uma única transação, especialmente PDV, NF-e, estoque, fiscal e migração.
- O SQL ainda acoplado ao fluxo visual `editar_cliente_selecionado` foi registrado em `REFACTOR_CONFLITOS_PENDENTES.md` e não foi alterado.

## Transações, commit e rollback

- `DatabaseManager.session(write=True)` e `connection_session(write=True)` continuam sendo os limites preferenciais: commit no sucesso, rollback na exceção e fechamento garantido.
- Fluxos atômicos de NF-e, estoque, financeiro e compras continuam compartilhando a mesma conexão entre serviço e repositórios.
- Operações que recebem uma conexão externa não executam commit próprio, preservando a atomicidade do chamador.
- Foram adicionados rollbacks explícitos ao registro administrativo de migração e à persistência de estado do PDV; antes, o fechamento da conexão fazia rollback implícito em caso de erro.
- Rotinas de manutenção, migração e reset mantêm transações manuais por precisarem controlar `BEGIN IMMEDIATE`, cópias, validação e recuperação.

## Duplicações eliminadas

- Estado e escape de argumentos PowerShell, antes repetidos nos adaptadores de abertura e impressão de arquivos, foram centralizados em `WindowsShellDispatcher`.
- A auditoria AST final não encontrou corpos funcionais duplicados relevantes; os pares restantes são construtores mínimos equivalentes e funções locais de biblioteca, sem justificativa para acoplamento adicional.

## Resultado

A persistência permanece compatível com o comportamento anterior, com limites transacionais explícitos e cobertura de regressão preservada. Nenhuma alteração foi feita em áreas protegidas da interface.
