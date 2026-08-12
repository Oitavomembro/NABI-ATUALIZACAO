# Checkpoint 8 — Resiliência e tratamento de falhas

## Base

- Base oficial: `NabiCode_v2_4_99_HOTFIX_SMOKE_WINDOWS.zip`.
- SHA-256 confirmado: `5AC375A52FB9A4C09DD48545902F4F097E81F526C564C0B52F41C1EB01C3BA84`.
- Baseline inicial: 891 testes aprovados e 11 subtests aprovados.
- Versão iniciada: 2.5.0.

## Classificação

### Alta

1. `backup_database` abria a origem antes do destino, mas o bloco de fechamento começava somente depois das duas aberturas. Falha ao abrir o destino deixava a conexão de origem ativa.
2. `DatabaseMaintenanceService.create_backup` repetia o mesmo padrão e podia deixar a conexão de origem ativa quando o destino estava indisponível.
3. `DatabaseMaintenanceService.restore` podia referenciar a conexão de destino antes de sua criação e os caminhos de recuperação repetiam o risco de vazamento ao abrir a segunda conexão.
4. A configuração de banco em rede fazia backup manual com duas conexões e sem `finally`, permitindo vazamento e arquivo parcial em falha.

### Média

- Exceções genéricas em limites de interface e integração externa. Em geral exibem mensagem ao usuário, registram diagnóstico ou protegem callbacks de widgets já destruídos.
- Callbacks periódicos da interface ignoram falhas transitórias. A alteração foi evitada porque a navegação e o comportamento visual estão congelados e validados no Windows.

### Baixa

- Exceções silenciosas em limpeza visual, restauração de foco, remoção de bindings e fechamento defensivo. São operações idempotentes e não persistem dados.

### Crítica

- Nenhuma ocorrência crítica nova foi comprovada.

## Correções

- Fechamento da origem garantido mesmo quando a abertura do destino falha.
- Fechamento condicional de destinos parcialmente inicializados.
- Remoção do backup manual da configuração de rede em favor do helper central validado.
- Remoção do destino incompleto no caminho de falha de criação de backup.
- Atualização da versão compilada e de `VERSAO.txt` para 2.5.0.

## Regressões adicionadas

- Falha ao abrir destino fecha a origem em `backup_database`.
- Falha ao abrir destino fecha a origem em `DatabaseMaintenanceService.create_backup`.

## Áreas preservadas

- Navegação, flash branco, gerenciamento visual, impressão, foco do PDV e navegação por teclado não foram modificados.
- Exceções defensivas dessas áreas não foram alteradas sem defeito objetivo.

## Validação

- Testes focados: 10 aprovados.
- `python -m compileall -q .`: aprovado.
- Suíte completa: 893 testes aprovados e 11 subtests aprovados.
