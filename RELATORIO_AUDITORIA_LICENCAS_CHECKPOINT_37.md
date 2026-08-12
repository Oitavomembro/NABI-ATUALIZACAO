# Auditoria de licenças — Checkpoint 37

## Fontes rastreadas

- defaults: `database/schema_initializer.py`;
- regras: `services/license_service.py`;
- operações administrativas: `managers/admin_operations_manager.py`;
- UI, monitor e bloqueio: `nabicode_legacy.py`.

As chaves reais são `licenca_validade`, `licenca_expira_em` e `licenca_bloqueada`. Não foram encontrados modos implementados de licença permanente nominal, arquivo de licença offline, vínculo à máquina, servidor remoto, período de tolerância ou chave externa de ativação.

## Modalidades reais

### 1. Validade diária temporária

1. Estado inicial: novas bases recebem `licenca_validade = hoje + 30 dias`, `licenca_bloqueada = 0` e `licenca_expira_em` vazio.
2. Validade: até 23:59:59 da data ISO `AAAA-MM-DD`.
3. Expiração: primeiro instante do dia seguinte.
4. Verificação: startup e monitor periódico de 1 s.
5. Ação: persiste `licenca_bloqueada = 1` e abre bloqueio modal.
6. UI: acesso operacional permanece atrás do modal; janela principal é restaurada após liberação válida.
7. Splash: no startup, `startup_modal_scope()` cria `.pause`, oculta o helper e remove o sinal ao concluir.
8. Lock: permanece adquirido pela mesma instância durante o bloqueio.
9. Desbloqueio: senha mestre validada pelo `SecurityService`.
10. Persistência: liberação grava nova validade de 30 dias, limpa expiração exata e bloqueio.
11. Reinício: reavalia as chaves persistidas.
12. Offline: toda a avaliação é local; não há consulta de rede.

Renovações administrativas existentes são de 30 ou 365 dias e estendem a maior data entre validade atual e agora. São variações de duração da mesma modalidade diária, não modalidades distintas.

### 2. Licença de teste com expiração exata

1. Estado inicial: a operação administrativa grava `agora + 1 minuto` em `licenca_expira_em` e limpa o bloqueio.
2. Validade: enquanto `agora < timestamp`.
3. Expiração: exatamente no limite (`agora >= timestamp`).
4. Verificação: startup e monitor periódico de 1 s.
5. Ação: bloqueia; o monitor também limpa a expiração exata já consumida.
6. UI: mesmo modal bloqueante da validade diária.
7. Splash: mesma coordenação por `.pause` durante startup.
8. Lock: permanece adquirido.
9. Desbloqueio: mesma senha mestre.
10. Persistência: sucesso substitui o teste por validade diária de 30 dias.
11. Reinício: antes do limite continua válida; após expirar permanece bloqueada.
12. Offline: integralmente local.

### 3. Bloqueio administrativo manual

1. Estado inicial: `licenca_bloqueada = 1`, acionado pela operação administrativa real.
2. Validade: não se aplica; o flag tem precedência.
3. Expiração: não se aplica.
4. Verificação: startup e monitor periódico de 1 s.
5. Ação: abre o bloqueio modal.
6. UI: operação protegida não fica acessível.
7. Splash: pausada/ocultada se o bloqueio ocorrer no startup.
8. Lock: preservado.
9. Desbloqueio: senha mestre no modal ou alternância administrativa já existente.
10. Persistência: o flag é persistente; desbloqueio por senha cria validade de 30 dias.
11. Reinício: flag continua sendo avaliado.
12. Offline: integralmente local.

### 4. Ausência de validade configurada

1. Estado: `licenca_validade` e `licenca_expira_em` vazios, sem bloqueio.
2. Regra atual: `SEM_VALIDADE`, acesso não bloqueado.
3. Não é rotulada no código como licença permanente.
4. Não há expiração, renovação ou chave associada.
5. Splash, UI e lock seguem o startup normal.
6. Offline: integralmente local.

Esse comportamento foi documentado, não reinterpretado. Alterá-lo seria mudança de política comercial fora do escopo.

## Desbloqueio administrativo

Senha errada retorna falso e não altera nenhuma chave. Senha correta:

1. grava `licenca_validade = agora + 30 dias`;
2. limpa `licenca_expira_em`;
3. grava `licenca_bloqueada = 0`;
4. encerra modal e libera grab;
5. o `startup_modal_scope()` remove `.pause`;
6. a mesma raiz é restaurada e recebe foco, ou continua oculta até o readiness gate se ainda estiver no startup.

Não há reinício do aplicativo nesse fluxo.

## Limites e valores inválidos

- expiração exata: antes do limite ativa; exatamente no limite e depois bloqueia;
- validade diária: ativa até 23:59:59; bloqueia a partir de 00:00:00 do dia seguinte;
- timestamp exato inválido: é removido e marcado como configuração inválida, sem bloqueio automático;
- validade diária inválida: é marcada inválida e não bloqueia automaticamente;
- ausência de validade: não bloqueia pela regra existente.

Os três últimos itens são riscos residuais de configuração já existentes. Corrigi-los exigiria uma decisão de política de licenciamento e não foi mascarado neste hotfix.

## Cobertura automatizada

Foram cobertos: antes/no/depois do limite exato; último segundo e pós-limite diário; bloqueio manual; ausência de validade; senha errada sem mutação; senha correta; persistência após reinício; bloqueio repetido até liberação; avaliação periódica de todas as modalidades; mesma raiz Tk; ausência de `mainloop` aninhado; liberação de grab; limpeza dos sinais; coleta forçada do helper; lock concorrente e contrato de segunda instância.

Alt+Tab, minimizar/restaurar, `MainWindowHandle`, PID real do executável empacotado e interação com senha no Windows são validações físicas e constam no checklist, sem aprovação presumida.

