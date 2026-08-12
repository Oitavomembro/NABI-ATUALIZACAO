# Estabilização — baseline da base recebida

## Identificação

- Base canônica: `NabiCode_v2_4_98_REFACTOR_COMPLETA.zip`.
- SHA-256 do pacote recebido: `05419D70218852536ADA2238F102CCD58EE3D9B25246C3DE2517805C01F067B5`.
- Base complementar auditada: `NabiCode_v2_4_98_CORRECAO_FLASH_WINDOWS.zip`.
- SHA-256 do pacote complementar: `5546C73268E9D4BF51B0BC953B76E943DD2CE9C13FC3C992E178E558E00CB082`.
- Versão declarada: `2.4.98`.
- Python do baseline: `3.14.6` em ambiente virtual isolado, fora da árvore do projeto.

O pacote de correção do flash não foi adotado como raiz porque omite 25 arquivos presentes na refatoração completa, inclusive services, repositories, controllers, validators e quatro arquivos de testes. Ele será tratado como delta posterior a auditar, sem substituir a base refatorada.

## Estrutura e dimensões

- Arquivos Python: 291.
- Arquivos de teste `test_*.py`: 157.
- Funções de teste encontradas estaticamente: 872.
- Resultado coletado pelo pytest: 877 testes e 11 subtestes.
- `nabicode_legacy.py`: 520.033 bytes e 9.606 linhas.
- Diretórios principais: `controllers`, `core`, `database`, `helpers`, `managers`, `repositories`, `services`, `tests`, `ui` e `validators`.
- Distribuição Python principal: 8 controllers, 15 módulos core, 9 database, 6 helpers, 3 managers, 19 repositories, 53 services, 5 módulos UI e 8 validators.

## Validação obrigatória

- `python -m compileall -q .`: aprovado, exit code 0, 0,37 s na execução registrada.
- `python -m pytest -q`: aprovado.
- Resultado: `877 passed, 11 subtests passed in 79.35s`.
- Duração total observada do comando pytest: 83,21 s.
- Primeira tentativa com o Python global: impedida porque `pytest` não estava instalado (`No module named pytest`). Foi criado ambiente isolado e instaladas as dependências declaradas mais `pytest`; nenhum banco real do usuário foi usado.

## Arquitetura atual

- Entrada e bootstrap: `main.py`, com splash opcional, configuração do runtime profile, lock do banco e criação da aplicação legada.
- Aplicação/UI principal: `FicharioMoveisApp` em `nabicode_legacy.py`.
- Controllers: callbacks e adaptação da UI legada para serviços.
- Services: regras de negócio, transações e integrações.
- Repositories: persistência por domínio; ainda há SQL fora dessa camada.
- Database: conexão SQLite, schema, migrações, manutenção e introspecção.
- UI: tema, layout, teclado e backgrounds reutilizáveis.
- Runtime: `core/runtime_profile.py` separa Produção/Teste, marca bancos e mantém lock por banco.

## Navegação e renderização

- Criação das telas: `FicharioMoveisApp.criar_telas` em `nabicode_legacy.py`.
- Troca de telas: `FicharioMoveisApp.mostrar_tela` em `nabicode_legacy.py`.
- Container principal: `container_telas`, um `CTkFrame` transparente estável.
- Telas normais: criadas antecipadamente, empilhadas e ativadas com `tkraise()`.
- PDV: exceção arquitetural; `mostrar_tela("vendas")` chama `abrir_pdv_independente()` e cria `CTkToplevel`.
- Entrada/janela: `main.py` contém `withdraw`, `deiconify`, `lift` e `update_idletasks` do fluxo inicial.
- Geometria/layout: `ui/layout_manager.py` e `ui/theme.py`.

## Tema e backgrounds

- Tema central: `NabiTheme` e helpers em `ui/theme.py`.
- Backgrounds: `BackgroundManager` e `BackgroundSettings` em `ui/background_manager.py`.
- Integração: `nabicode_legacy.py` cria o manager em `criar_telas` e o anexa a cada tela.
- Não existe classe chamada literalmente `ThemeManager`; a responsabilidade equivalente está em `NabiTheme` e funções de `ui/theme.py`.

## Runtime profile e pontos de entrada

- Runtime profile/isolamento: `core/runtime_profile.py`.
- Bootstrap principal: `main.py`.
- Aplicação legada: importação de `FicharioMoveisApp` por `main.py`.
- Utilitários executáveis: `developer_tools_cli.py`, `gerar_pacote_atualizacao.py`, `AUDITAR_SALDO_CLIENTE.py` e `CORRIGIR_LOGIN_ATUAL.py`.
- O caminho Windows do lock usa API nativa (`OpenProcess`/`GetExitCodeProcess`). `os.kill(pid, 0)` permanece somente no ramo não Windows de `DatabaseUsageLock._pid_alive`.

## Operações potencialmente pesadas na UI

- Após `tkraise()`, `mostrar_tela` chama carregamentos de dashboard, clientes, produtos, financeiro, compras ou relatórios sincronamente.
- A abertura do PDV constrói uma árvore grande de widgets em `CTkToplevel`.
- Há SQL direto e chamadas a services a partir de callbacks no arquivo legado.
- Geração documental, filesystem, subprocessos, backup, importação XML e migração aparecem em callbacks da classe principal.
- Existem usos explícitos de `update_idletasks()` durante criação e atualização de janelas.
- Há uma consulta de clientes explicitamente movida para thread; Tk deve continuar sendo atualizado somente pela thread principal.

