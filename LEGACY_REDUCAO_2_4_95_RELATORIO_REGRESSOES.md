# Relatório de regressões — redução do nabicode_legacy.py

Base: `NabiCode_v2_4_95_TESTE_REIMPRESSAO_LAYOUT`

## Alterações

- Removidos helpers privados sem qualquer chamada: `_pastas_backup_configuradas`, `_criar_backup_em_pasta` e `_hash_senha_admin`.
- Removidas duas funções locais mortas dentro da importação XML: `obter_ou_criar_fornecedor` e `obter_ou_criar_unidade`. O fluxo ativo já usa `NFeImportService`/`NFeImportRepository` para essas responsabilidades.
- Removido import morto `hashlib`.
- Extraída lógica pura para `helpers/legacy_reduction_helpers.py`:
  - parsing numérico não negativo;
  - formatação numérica brasileira;
  - formatação do relatório de manutenção do banco;
  - formatação do relatório de simulação da migração MySQL.
- Nenhum layout, `grid`, `pack`, `sticky`, `rowconfigure`, `columnconfigure`, fonte, botão, scrollbar, `BackgroundManager` ou `ThemeManager` foi alterado.
- Nenhuma regra de Financeiro ou Documental foi alterada.

## Redução

- `nabicode_legacy.py` antes: 9.963 linhas.
- `nabicode_legacy.py` depois: 9.890 linhas.
- Redução líquida: 73 linhas.

A meta de 1.000 linhas não foi atingida. As maiores funções restantes são predominantemente construtoras de Interface ou pertencem aos domínios explicitamente bloqueados. Mover esses blocos para outro módulo apenas para cumprir a métrica violaria o escopo da sprint.

## Auditoria estática

- Imports mortos após a alteração: nenhum detectado por AST.
- Métodos duplicados diretamente em `FicharioMoveisApp`: nenhum.
- Compilação de `nabicode_legacy.py`, helper novo e teste novo: aprovada.

## Testes

- `pytest -q tests/test_legacy_reduction_helpers.py`: **5 passed**.
- `pytest -q`: **797 passed, 12 subtests passed**.
- Regressões automatizadas detectadas: nenhuma.

## Execução de `python main.py`

Executada. A aplicação não abriu devido ao ambiente:

- `_tkinter.TclError: couldn't connect to display ":0"` no splash;
- `ModuleNotFoundError: No module named 'customtkinter'` ao importar o legado.

A validação gráfica não é considerada concluída.
