# Startup baseline — NabiCode 2.5.1 DEV

Checkpoint 23  
Data: 08/08/2026  
Status: **INSTRUMENTAÇÃO APROVADA; MEDIÇÃO GRÁFICA WINDOWS PENDENTE**

## Instrumentação

Foi adicionada instrumentação opt-in em `core/startup_metrics.py`. Ela permanece inativa no uso normal e somente grava JSON quando `NABICODE_STARTUP_TRACE` contém um caminho de saída.

Marcos disponíveis:

1. `process_imports_ready`;
2. `main_entered`;
3. `runtime_profile_imported`;
4. `runtime_profile_ready`;
5. `splash_started`;
6. `legacy_import_started` / `legacy_import_ready`;
7. `theme_manager_configured`;
8. `database_path_ready`;
9. `database_lock_acquired`;
10. `main_window_created`;
11. `database_migrations_started` / `database_migrations_ready`;
12. `ui_build_started`;
13. `ui_modules_created`;
14. `dashboard_ready`;
15. `application_created`;
16. `mainloop_entered`;
17. `first_screen_usable`.

Cada evento registra tempo acumulado e delta desde o evento anterior usando `time.perf_counter()`. A saída é substituída atomicamente.

## Medições realizadas neste ambiente

### Caminho de smoke de source

Comando funcional equivalente:

```text
NABICODE_STARTUP_TRACE=<arquivo> python main.py --startup-smoke-test --smoke-output <arquivo>
```

| Marco | Acumulado | Delta |
| --- | ---: | ---: |
| imports mínimos prontos | 0,029 ms | 0,029 ms |
| entrada em `main()` | 2,391 ms | 2,362 ms |
| runtime profile importado | 4,556 ms | 2,166 ms |
| runtime profile configurado | 6,175 ms | 1,619 ms |
| smoke concluído | 8,611 ms | 2,436 ms |

Versão carregada: `2.5.0`.

### Import do legado sem criação da janela

O ambiente recebeu dependências temporárias fora do projeto e um AppData isolado. O import completo de `nabicode_legacy` foi medido com `-X importtime`:

| Marco | Acumulado | Delta |
| --- | ---: | ---: |
| import do legado iniciado | 0,029 ms | 0,029 ms |
| ThemeManager/CustomTkinter configurado | 138,068 ms | 138,040 ms |
| import do legado concluído | 144,873 ms | 6,805 ms |

Principais custos cumulativos observados no processo de import:

| Grupo | Tempo cumulativo aproximado |
| --- | ---: |
| `services.fiscal_service` e dependências | 80,756 ms |
| `requests` | 39,901 ms |
| `urllib3` | 24,312 ms |
| `tkinter` | 21,872 ms |
| `customtkinter` | 18,406 ms |
| `reportlab.pdfgen.canvas` | 18,159 ms |
| `cryptography.x509` | 15,733 ms |
| `lxml.etree` | 3,532 ms próprios/cumulativos do módulo |

O custo próprio de `nabicode_legacy` foi aproximadamente 111,196 ms; isso inclui criação antecipada de objetos de repositório/serviço e configuração global.

## Gargalos candidatos encontrados

### Com evidência de import

- O pacote `services` importa módulos fiscais antecipadamente.
- Requests, urllib3, Cryptography, lxml e ReportLab são carregados antes de o usuário abrir funções fiscais/documentais.
- CustomTkinter/Tk é inevitável para a criação da UI, mas precisa ser distinguido do custo fiscal.

### Evidência estrutural, ainda sem tempo gráfico real

- `FicharioMoveisApp.__init__()` cria todas as telas antecipadamente: Dashboard, Vendas, Clientes, Produtos, Financeiro, Compras, Relatórios e Configurações.
- Após criar as telas, `mostrar_tela("dashboard")` executa consultas do resumo/histórico antes da primeira tela.
- Migrações e validação de atualização são síncronas antes da janela utilizável, o que é correto para integridade, mas precisa ser medido em base real.
- Vários repositórios/serviços são instanciados no import do legado.
- ThemeManager não mostrou custo isolado relevante; o marco inclui o import do legado até a configuração do tema.

## Limitação obrigatória

Este contêiner Linux não possui servidor gráfico (`DISPLAY`) nem Windows. Portanto, não foi possível obter tempos honestos de:

- criação real da janela;
- migrações em base Windows real;
- criação de todos os módulos visuais;
- Dashboard renderizado;
- primeira tela utilizável;
- startup do onedir/instalado.

Esses tempos não foram inventados. A instrumentação entregue permite medi-los no build Windows e no protocolo de máquina limpa.

## Decisão para o Checkpoint 31

Não será feita otimização funcional de startup neste ambiente. O import total observado (~145 ms) não justifica, sozinho, uma alteração ampla no grafo de imports. A criação antecipada das telas pode ser um gargalo, mas alterá-la sem medir a UI Windows violaria a regra de não otimizar por intuição e poderia afetar a navegação/flash já aprovados.

## Validação

```text
4 passed, 3 subtests passed
```

Cobertura: instrumentação habilitada/desabilitada e smoke de startup existente.

## Arquivos alterados neste checkpoint

- `core/startup_metrics.py` — novo, instrumentação opt-in;
- `main.py` — marcos de processo, perfil, lock, app e primeira tela;
- `nabicode_legacy.py` — marcos de tema, janela, migrações, UI e Dashboard;
- `tests/test_startup_metrics.py` — novos testes;
- `STARTUP_BASELINE_2_5_1.md` — relatório.

Nenhuma regra comercial, financeira, de PDV, impressão, corte, navegação ou flash foi alterada.
