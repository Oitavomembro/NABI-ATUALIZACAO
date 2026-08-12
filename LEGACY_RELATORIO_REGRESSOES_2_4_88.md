# Relatório de regressões — NabiCode v2.4.88

## Escopo alterado
- `nabicode_legacy.py`: somente patch; nenhuma substituição integral.
- Novo `SystemInfrastructureManager` para schema, backup pré-atualização, snapshots, diagnóstico, atualização e validação pós-reinício.
- Novos helpers de conversão numérica e data, preservando `tratar_numero` e `_data_sql` como fachadas compatíveis.

## Redução do legado
- Antes: 9.983 linhas.
- Depois: 9.932 linhas.
- Redução líquida: 51 linhas.

## Código/imports mortos removidos
- `shutil`
- `json`
- `hmac`
- `tempfile`
- `zipfile`
- `heapq`
- `Counter`
- `defaultdict`
- `textwrap`

## Compatibilidade
- Nenhuma assinatura pública existente foi alterada.
- Nenhuma função/classe pública foi removida.
- Fachadas antigas continuam delegando aos módulos novos.
- `PDF_DIR` original é repassado ao manager.
- A configuração de diagnóstico continua explícita no adaptador do legado, incluindo `categorias_produtos`.

## Regressão encontrada durante a sprint
A primeira execução da suíte falhou em `test_diagnostics_uses_real_category_table`, pois `categorias_produtos` havia deixado de aparecer explicitamente no legado. O adaptador foi corrigido para repassar `required_diagnostic_tables` ao manager. Após a correção, a suíte completa passou.

## Auditoria final
- Compilação Python: aprovada.
- Assinaturas comparadas por AST: nenhuma alteração.
- Definições duplicadas no nível do módulo: nenhuma.
- Imports mortos introduzidos nos novos módulos: nenhum.
- Suíte completa: 721 passed, 12 subtests passed.

## `python main.py`
Executado após a auditoria final. A aplicação não abriu por bloqueios técnicos do ambiente:
- `ModuleNotFoundError: No module named 'customtkinter'`.
- `_tkinter.TclError: couldn't connect to display ":0"` no splash.

A validação de abertura não está concluída.
