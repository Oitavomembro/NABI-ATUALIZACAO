# Continuação da missão NabiCode 2.5.0

## Estado

- Checkpoints 8 a 20 concluídos e validados automaticamente.
- Baseline final: 902 testes normais, 11 subtests e 3 testes separados.
- Próxima etapa: validação manual descrita em `VALIDACAO_MANUAL_WINDOWS_PENDENTE.md`.

## Ampliação recebida

- Executar Checkpoints 12 a 20 em sequência, sempre com validação antes/depois e ZIP recuperável.
- Não aguardar smoke manual Windows enquanto houver validações automáticas possíveis.
- Preservar todas as áreas congeladas e não criar funcionalidades comerciais.

## Pontos já identificados para o Checkpoint 12

- Revisar validação por integridade e tamanho plausível.
- Cobrir destino sem permissão, falha parcial e banco anterior preservado.
- Auditar retenção e múltiplos destinos do `BackupService`.
- Usar exclusivamente bancos temporários nos testes.
