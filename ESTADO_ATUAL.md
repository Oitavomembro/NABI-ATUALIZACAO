# NabiCode — Estado Atual

## Identificação

- **Versão:** 2.5.1 DEV
- **Base:** Checkpoint 40 Windows Validation Fixes
- **Branch planejada:** `dev/nabicode-2.5.1`
- **Status:** DESENVOLVIMENTO
- **Instalador:** frente separada — não modificar

## Testes conhecidos

- 990 passed;
- 22 subtests passed;
- suíte focada: 78 passed;
- suíte focada: 3 subtests passed;
- `compileall` aprovado;
- stress aprovado;
- benchmark aprovado;
- soak aprovado.

## Regras críticas preservadas

- A versão 2.5.0 RELEASE permanece aprovada, congelada e não deve ser modificada.
- Esta frente trabalha somente sobre o NabiCode 2.5.1 DEV.
- Não alterar regras comerciais, cálculos financeiros, persistência, licenças, impressão, corte, estoque ou banco sem missão explícita e evidência da causa.
- Antes de corrigir: localizar a implementação real, identificar a causa, registrar evidência e criar teste de regressão quando tecnicamente possível.
- Não remover testes existentes.
- Bancos reais, backups, credenciais, variáveis de ambiente e dados de clientes nunca devem ser versionados.
- Arquivos do instalador pertencem a uma frente separada e não devem ser modificados nesta branch sem missão explícita.

## Pendências externas

- validação física Windows;
- impressão e corte quando aplicável;
- VM e operação offline conforme documentação existente.

## Validação desta preparação Git

- `python -m compileall .`: aprovado.
- `python -m pytest`: não iniciado porque o ambiente atual não possui `pytest`.
- Fallback `python -m unittest discover -s tests`: 803 testes executados em 30,907 s; 796 aprovados, 1 falha e 6 erros de importação.
- Os 6 erros ocorreram pela ausência de `pytest` no ambiente.
- A falha ocorreu no smoke de startup pela ausência de `pygame` no ambiente.
- Nenhum código funcional foi alterado para mascarar essas limitações. O resultado oficial conhecido do Checkpoint 40 permanece `990 passed, 22 subtests passed`.

## Próxima missão — Módulo Caixa

Esta missão está registrada para implementação futura. **Não foi implementada nesta preparação.**

### Abertura

- Se não houver caixa aberto, perguntar como abrir.
- Oferecer `Informar saldo inicial`.
- Oferecer `Abrir sem informar`.
- Remover `Cancelar`.
- Abrir sem informar significa saldo inicial de R$ 0,00.
- Registrar o usuário.
- Registrar data e hora.
- Registrar o valor.
- Registrar o modo de abertura.
- Não perguntar novamente enquanto existir caixa aberto.

### Caixa

Criar futuramente uma aba própria contendo:

- estado aberto ou fechado;
- saldo inicial;
- vendas em dinheiro;
- PIX;
- cartão;
- recebimentos;
- sangrias;
- suprimentos;
- dinheiro esperado;
- dinheiro contado;
- diferença;
- observação;
- usuário que abriu;
- usuário que fechou;
- data e hora;
- histórico de caixas.

### Regra contábil

PIX e cartão entram no movimento do período, mas **não aumentam o dinheiro físico esperado na gaveta**.

### Múltiplos usuários

Uma sessão de caixa pertence ao terminal ou caixa físico. Cada operação registra o usuário responsável. Não criar automaticamente um caixa independente para cada usuário.
