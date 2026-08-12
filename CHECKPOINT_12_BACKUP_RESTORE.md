# Checkpoint 12 — Backup e restauração

## Correções

- Nomes únicos com microssegundos.
- Remoção de arquivo parcial quando a cópia falha.
- Rejeição explícita de arquivo ausente ou vazio.

## Testes novos

- Falha após escrita parcial remove o arquivo incompleto.
- Dois backups no mesmo segundo mantêm arquivos distintos.
- Arquivo vazio é rejeitado.

## Validação

- Testes focados: 16 aprovados.
- `python -m compileall -q .`: aprovado.
- Suíte completa: 896 testes aprovados e 11 subtests aprovados.
