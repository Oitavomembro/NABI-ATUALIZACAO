# Checkpoint 21 — Base NabiCode 2.5.1 DEV

Data: 08/08/2026  
Status: **APROVADO**

## Base canônica

- Arquivo: `NabiCode_v2_5_0_RELEASE.zip`
- SHA-256 esperado: `36F0BC3FDC341623E001CC88ECEC711D5B6ADBBCD3065397A9A6F3E558F89875`
- SHA-256 obtido: `36F0BC3FDC341623E001CC88ECEC711D5B6ADBBCD3065397A9A6F3E558F89875`
- Resultado: correspondência exata.
- Tamanho: 823.805 bytes.
- Entradas extraídas: 495.

A release original não foi sobrescrita nem modificada. O desenvolvimento foi iniciado em diretório independente: `NabiCode_v2_5_1_DEV`.

## Baseline

### Compilação

```text
python -m compileall -q .
```

Resultado: aprovado, código de saída 0.

### Testes

```text
python -m pytest -q
```

Resultado:

```text
902 passed, 11 subtests passed in 18.47s
```

O ambiente Linux de auditoria usou `APPDATA` apontado para diretório temporário gravável, conforme o mecanismo já suportado por `core/runtime_profile.py`. Isso evita que o smoke subprocess tente escrever em `/root`, que é somente leitura neste ambiente.

## Arquivos alterados neste checkpoint

- `CHECKPOINT_21_BASE_2_5_1.md` — relatório novo.

Nenhum arquivo funcional foi alterado.

## Decisão

Baseline idêntico ao esperado. O Checkpoint 22 está autorizado.
