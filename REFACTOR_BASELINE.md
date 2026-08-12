# Refatoração — baseline da base 2.4.97

## Base auditada

- Pacote: `NabiCode_v2_4_97_WORKMODE_RUNTIME_LOCK_FIX.zip`
- Diretório interno: `NabiCode_v2_4_97_WORKMODE_BASE`
- Versão declarada pelo smoke test: `2.4.97`
- Arquivos Python: **269** (`115` fora de `tests/`)
- Linhas físicas Python: **47.064** (`33.302` fora de `tests/`)
- Linhas Python não vazias: **41.699**
- `nabicode_legacy.py`: **9.889 linhas**
- Participação do legacy no Python de produção: **29,7%**

Contagem feita sobre arquivos `.py`, excluindo `.venv`, `build`, `dist`, `__pycache__` e `.pytest_cache`. Linhas físicas incluem comentários e docstrings.

## Validação inicial

- `python -m compileall -q .`: aprovado.
- `python -m pytest -q`: **863 passed, 11 subtests passed**.
- Ajuste exclusivamente ambiental: `pytest` foi instalado em diretório temporário e `APPDATA` foi apontado para `/tmp/nabicode_refactor_appdata`, porque `/root` é somente leitura neste executor. Nenhum arquivo do projeto foi alterado para viabilizar a suíte.

## Maiores módulos Python de produção

| Linhas | Módulo |
| ---: | --- |
| 9.889 | `nabicode_legacy.py` |
| 1.912 | `services/fiscal_service.py` |
| 936 | `services/financeiro_service.py` |
| 816 | `database/schema_initializer.py` |
| 772 | `repositories/financeiro_repository.py` |
| 721 | `services/product_application_service.py` |
| 717 | `services/pdf_document_service.py` |
| 654 | `services/report_service.py` |
| 620 | `services/nfe_devolucao_service.py` |
| 613 | `repositories/nfe_import_repository.py` |
| 611 | `repositories/nfe_devolucao_repository.py` |
| 505 | `services/mysql_migration_service.py` |

## Maiores funções e métodos

| Linhas | Símbolo | Local |
| ---: | --- | --- |
| 807 | `initialize_database` | `database/schema_initializer.py:10` |
| 709 | `FicharioMoveisApp.abrir_painel_admin` | `nabicode_legacy.py:9177` |
| 527 | `FicharioMoveisApp.abrir_importacao_xml` | `nabicode_legacy.py:3686` |
| 325 | `FicharioMoveisApp.abrir_historico_devolucoes` | `nabicode_legacy.py:3143` |
| 302 | `FicharioMoveisApp.abrir_pdv_independente` | `nabicode_legacy.py:4214` |
| 257 | `FicharioMoveisApp.abrir_cadastro_produto` | `nabicode_legacy.py:2651` |
| 233 | `FicharioMoveisApp.tela_configs` | `nabicode_legacy.py:8379` |
| 222 | `MySQLMigrationService.execute_summary` | `services/mysql_migration_service.py:284` |
| 217 | `FicharioMoveisApp.abrir_restauracao_fabrica` | `nabicode_legacy.py:8841` |
| 216 | `FicharioMoveisApp.abrir_historico_nfe_importadas` | `nabicode_legacy.py:3469` |
| 178 | `FicharioMoveisApp.abrir_configuracao_impressoras` | `nabicode_legacy.py:7601` |
| 168 | `PDVTransactionService.finalize_sale` | `services/pdv_transaction_service.py:36` |
| 168 | `FicharioMoveisApp.abrir_assistente_devolucao` | `nabicode_legacy.py:2974` |
| 156 | `FicharioMoveisApp.__init__` | `nabicode_legacy.py:723` |

## Acoplamento interno

O maior fan-out é `nabicode_legacy.py`, que depende diretamente de oito grupos internos: `controllers`, `core`, `database`, `helpers`, `managers`, `repositories`, `services` e `ui`. `main.py` depende de quatro grupos: `core`, `nabicode_legacy`, `services` e `splash_screen`.

Fan-in por grupo, incluindo testes:

| Grupo | Arquivos importadores |
| --- | ---: |
| `services` | 94 |
| `database` | 68 |
| `repositories` | 58 |
| `core` | 19 |
| `ui` | 9 |
| `controllers` | 5 |
| `helpers` | 5 |
| `validators` | 5 |
| `managers` | 4 |

## Duplicações confirmadas por AST

Foram encontrados corpos de função estruturalmente idênticos:

- `gerar_pacote_atualizacao.sha256` e `services.update_package_service.sha256_file`.
- `database.product_decimal_migration._table_exists` e `repositories.nfe_import_repository._table_exists`.
- `services.receipt_service._date_br` e `services.pdf_document_service._date_br`.
- `repositories.client_history_repository.parse_date` e `helpers.value_parsing.parse_system_date`.
- Construtores equivalentes em `services/windows_file_opener.py` e `services/windows_pdf_printer.py`.

Duplicações em dublês de teste foram contabilizadas separadamente e não são alvo de extração de produção.

## SQL direto restante

- Chamadas diretas de `execute`, `executemany` ou `executescript` com SQL detectável em produção: **439**.
- Em `nabicode_legacy.py`: **7 detectadas por AST** e **8 chamadas totais** por busca textual.

Maiores concentrações:

| Chamadas | Módulo |
| ---: | --- |
| 98 | `database/schema_initializer.py` |
| 39 | `repositories/financeiro_repository.py` |
| 38 | `repositories/nfe_devolucao_repository.py` |
| 36 | `repositories/nfe_import_repository.py` |
| 24 | `services/pdv_transaction_service.py` |
| 19 | `services/mysql_migration_service.py` |
| 15 | `services/factory_reset_service.py` |
| 15 | `services/cash_service.py` |
| 11 | `database/maintenance.py` |
| 9 | `database/product_schema_migration.py` |
| 9 | `services/pdf_document_service.py` |
| 9 | `repositories/compra_repository.py` |
| 8 | `services/report_service.py` |
| 8 | `repositories/customer_maintenance_repository.py` |

SQL dentro de `repositories/` e inicializadores de schema é responsabilidade esperada. SQL ainda presente em `services/`, `core/` e legacy representa extração pendente, mas só pode ser movido quando a fronteira transacional e a ordem de commits forem preservadas.

## Imports mortos e variáveis sem uso

Análise com Ruff `F401/F841`:

- **111 diagnósticos totais**.
- A maioria dos `F401` em `__init__.py` representa reexportação pública e não pode ser removida como import morto sem verificar consumidores externos.
- **17 correções automáticas seguras sinalizadas** pelo analisador, distribuídas entre produção e testes.
- Imports mortos confirmados fora de arquivos de interface: `database/maintenance.py`, `database/schema_initializer.py`, `developer_tools_cli.py`, `services/backup_service.py`, `services/developer_tools.py`, `services/nfe_xml_service.py` e `services/report_service.py`.
- Variáveis atribuídas sem leitura foram sinalizadas no legacy, `repositories/dashboard_repository.py`, `services/financeiro_service.py` e `services/nfe_xml_service.py`. Cada atribuição precisa ser revisada por efeitos colaterais antes de remoção.
- Achados em arquivos protegidos (`core/global_search.py` e `core/text_interactions.py`) foram excluídos da alteração e registrados em `REFACTOR_CONFLITOS_PENDENTES.md`.

## Código morto

- Vulture com confiança mínima de 80% confirmou `io` não utilizado em `services/report_service.py`.
- Foi detectada uma condição ternária insatisfatível em `tests/test_financeiro_service.py`; por estar em teste e não afetar produção, deve ser tratada de forma conservadora.
- A varredura AST não encontrou instruções diretamente inalcançáveis após `return` ou `raise` em corpos de função.
- Métodos acionados por callbacks de Tkinter, reflexão, `command=` e bindings não podem ser classificados como mortos apenas por ausência de referência estática.

## Limites desta refatoração

Não serão modificados navegação, troca de telas, `ThemeManager`, `ScreenNavigation`, `BackgroundManager`, splash, widgets de interface nem transições visuais. Achados nesses componentes permanecem documentados para integração com a sessão dedicada ao flash branco.
