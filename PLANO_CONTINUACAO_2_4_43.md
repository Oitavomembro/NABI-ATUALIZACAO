# Plano de continuação — NabiCode 2.4.43

## Escopo

Este documento consolida a auditoria já realizada sobre LOGIN e PADRÃO DE FÁBRICA, sem alterar o código-fonte nem o banco. O objetivo é servir como base para a próxima etapa de implementação.

---

## 1. Contexto e análise já realizada

### Estrutura do projeto
- O projeto está organizado em módulos claramente separados:
  - interface principal: `nabicode_legacy.py`
  - serviços de negócio: `services/`
  - banco e schema: `database/`
  - repositórios: `repositories/`
  - testes: `tests/`
- A arquitetura já possui boa separação entre UI, regras de negócio, persistência e testes automatizados.

### Banco de dados
- O schema é criado/atualizado por `database/schema_initializer.py`.
- O banco atual é SQLite.
- Há mecanismos de backup e validação em `database/maintenance.py`.
- A restauração de fábrica é tratada por `services/factory_reset_service.py`.

### Login
- O fluxo de login está concentrado na interface `nabicode_legacy.py`.
- O serviço de autenticação está em `services/security_service.py`.
- Há uma janela de login customizada construída com `CTkToplevel`.
- O startup do app decide se abre a janela de login através de um `after()`.

### Padrão de fábrica
- A rotina de restauração completa é executada por `services/factory_reset_service.py`.
- O fluxo usa backup obrigatório, validação do banco e tentativa de limpar as tabelas de negócio.
- O risco principal é a ordem de exclusão e a violação das foreign keys reais do schema.

---

## 2. Arquivos já auditados

### Login
- `main.py`
- `nabicode_legacy.py`
- `services/security_service.py`
- `tests/test_login_factory_2441.py`
- `tests/test_master_and_receipt_regressions.py`

### Padrão de fábrica
- `services/factory_reset_service.py`
- `database/schema_initializer.py`
- `database/maintenance.py`
- `tests/test_login_factory_2441.py`

---

## 3. Bugs confirmados

### 3.1 Login
- O startup chama o fluxo de abertura de login via `self.after(50, self.abrir_login_usuario)` quando a condição de habilitação é satisfeita.
- O fluxo de abertura de login está acoplado à interface principal e pode ser disparado por mais de um ponto do ciclo de vida do app.
- O padrão atual permite que a janela de login seja acionada por startup, por expiração de sessão e por monitoramento de inatividade.
- O comportamento atual depende de flags de configuração e de estado persistido, o que torna a abertura do login mais complexa e vulnerável do que o necessário.

### 3.2 Padrão de fábrica
- A rotina de restauração pode quebrar por violação de foreign keys se as tabelas filhas forem apagadas antes das tabelas pai.
- A relação de dependência mais crítica identificada é a cadeia filha → pai, por exemplo:
  - `documentos_emitidos.movimentacao_id -> movimentacoes.id`
  - `parcelas.movimentacao_id -> movimentacoes.id`
- A correção precisa garantir exclusão em ordem filha → pai.
- A validação final precisa rodar `PRAGMA foreign_key_check` antes do commit.

---

## 4. Arquivos que ainda precisam ser alterados

### Prioridade alta
- `nabicode_legacy.py`
  - simplificar o fluxo de startup e remover o acionamento automático de login.
  - centralizar o ponto de entrada do acesso.

- `services/security_service.py`
  - revisar o uso da autenticação e da confirmação por senha em operações sensíveis.

- `services/factory_reset_service.py`
  - ajustar a ordem de exclusão das tabelas.
  - garantir validação de foreign keys antes do commit.
  - manter backup obrigatório.

- `database/schema_initializer.py`
  - confirmar e documentar as relações reais das foreign keys para apoiar a correção.

### Prioridade média
- `database/maintenance.py`
  - reforçar o ciclo de backup/rollback e validação.

### Testes a ampliar
- `tests/test_security_service.py`
- `tests/test_login_factory_2441.py`
- `tests/test_master_and_receipt_regressions.py`
- `tests/test_update_and_factory_integration.py`

---

## 5. Ordem recomendada das próximas tarefas

1. Remover o disparo automático de login no startup.
2. Consolidar o fluxo de autenticação em um único ponto de entrada explícito.
3. Ajustar a rotina de restauração de fábrica para apagar tabelas filhas antes das tabelas pai.
4. Inserir validação de foreign keys antes do commit e rollback seguro.
5. Expandir os testes para cobrir:
   - startup sem login automático;
   - restauração completa com foreign keys reais;
   - rollback em caso de violação estrutural.

---

## 6. Testes que precisam ser executados

### Testes de login
- verificar que o app não abre a janela de login automaticamente ao iniciar.
- verificar que o fluxo de login não é disparado por mais de um gatilho no ciclo de vida.
- verificar que operações sensíveis não dependem de senha de forma automática.

### Testes de padrão de fábrica
- testar a restauração completa com dados reais contendo dependências entre tabelas.
- verificar a ordem de exclusão filhas → pais.
- validar que `PRAGMA foreign_key_check` falha adequadamente antes do commit quando houver violação.
- validar rollback e backup obrigatório.

### Testes de regressão
- executar a suíte atual completa:
  - `python -m unittest discover -s tests -v`

---

## 7. Riscos conhecidos

- Mudar o fluxo de login pode afetar a experiência do usuário atual se houver dependência de sessões antigas ou de configuração persistida.
- Alterar a ordem de exclusão pode afetar instalações com dados já existentes e relações mais complexas.
- A restauração de fábrica é uma operação destrutiva; qualquer erro pode causar perda de dados se não houver backup e rollback corretos.
- A correção precisa ser feita com muito cuidado para não quebrar compatibilidade entre versões antigas do schema.

---

## 8. Checklist de implementação

- [ ] Remover o disparo automático de login no startup.
- [ ] Eliminar múltiplos gatilhos de abertura de login.
- [ ] Centralizar o ponto de entrada de autenticação.
- [ ] Revisar o uso de confirmação por senha em operações.
- [ ] Garantir backup obrigatório antes da restauração de fábrica.
- [ ] Implementar ordem correta de exclusão: filhas primeiro, pai depois.
- [ ] Rodar `PRAGMA foreign_key_check` antes do commit.
- [ ] Reverter transação em caso de violação.
- [ ] Adicionar testes específicos para login e padrão de fábrica.
- [ ] Validar a suíte completa após a implementação.

---

## 9. Resumo executivo

As duas áreas críticas confirmadas são:
- o fluxo de login está acoplado demais à interface e pode ser disparado por mais de um ponto do ciclo de vida;
- a restauração de fábrica precisa ser reforçada para evitar falhas por foreign keys e manter o backup/rollback seguros.

A próxima implementação deve priorizar a simplificação do login e o hardening da rotina de restauração de fábrica.
