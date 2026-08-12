# Checkpoint 20 — Auditoria final automatizada

## Validações consolidadas

- `python -m compileall -q .`: aprovado.
- Suíte normal: 902 testes e 11 subtests aprovados.
- Stress: 1 teste aprovado.
- Benchmarks: 1 teste aprovado.
- Soak: 1 teste aprovado.
- Backup, restore, migrações, packaging e startup: 30 testes e 5 subtests focados aprovados.
- Startup smoke: versão 2.5.0.

## Volume final

- 1.000 vendas.
- 2.000 movimentos de estoque.
- 100 cancelamentos.
- 100 rollbacks injetados no stress.
- 5.000 ciclos no soak, com 1.000 commits e 4.000 rollbacks.
- 10.000 clientes, 10.000 produtos, 50.000 movimentos e 20.000 títulos nos benchmarks.

## Defeitos encontrados e corrigidos

1. Arquivo parcial de backup permanecia após falha de cópia.
2. Backups no mesmo segundo podiam colidir.
3. Inicializador confirmava schema antes de concluir toda a migração.
4. Log não possuía rotação nem sanitização de segredos.
5. Cancelar venda paga reduzia saldo devedor pertencente a outras vendas a prazo.

## Riscos restantes

- Retenção automática de backups não foi imposta sem política comercial configurada.
- Outlier isolado de dashboard deve ser acompanhado em hardware real, sem evidência atual de regressão.
- GUI, impressão, High DPI, EXE e integração física permanecem para Windows real.
