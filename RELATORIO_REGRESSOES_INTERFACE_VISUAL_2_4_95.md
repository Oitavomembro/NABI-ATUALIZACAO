# Relatório de regressões — Interface visual 2.4.95

## Escopo modificado

- `ui/background_manager.py` — novo.
- `ui/layout_manager.py` — novo.
- `ui/__init__.py` — exportação da infraestrutura visual.
- `services/ui_preferences.py` — novas preferências visuais normalizadas.
- `tests/test_background_manager.py` — novo.
- `tests/test_layout_manager.py` — novo.
- `tests/test_ui_preferences.py` — novos testes de preferências.
- `PATCH_INTERFACE_LEGADO.md` — novo; instruções, sem alteração direta no legado.
- `ARQUITETURA_VISUAL_NABICODE_2_4_95.md` — novo.

## Regras não alteradas

Nenhum arquivo de Financeiro, PDV, Documental, banco, schema, migração, estoque ou regras de Cadastros foi modificado. `nabicode_legacy.py` não foi modificado.

## Cobertura visual automatizada

- ativação/desativação do BackgroundManager;
- opacidade e limites seguros;
- preservação da proporção;
- sete resoluções obrigatórias;
- debounce de resize;
- cache limitado;
- crescimento de memória durante múltiplos resizes;
- tempo de renderização em sequência de resoluções;
- áreas centrais com `weight=1`;
- colunas de Clientes preservando CPF/Favorito;
- ausência de scroll horizontal quando as colunas mínimas cabem;
- geometria responsiva para Histórico;
- persistência/normalização das preferências visuais.

## Limitações objetivas

O ZIP base não contém arquivo de logo. O BackgroundManager fica inativo visualmente até receber um caminho existente; isso evita inventar identidade visual ou embutir ativo não fornecido.

A aplicação concreta do BackgroundManager e da nova estrutura de Clientes/Histórico depende da aplicação de `PATCH_INTERFACE_LEGADO.md` pela conversa autorizada a alterar `nabicode_legacy.py`. Por isso, esta entrega não deve ser declarada como integração visual final antes dessa aplicação.

## Execução obrigatória

- `python -m compileall -q .`: concluído sem erro.
- `pytest -q`: o comando único excedeu o limite operacional do ambiente sem apresentar falha até o ponto executado. A coleção completa foi então executada em 6 lotes, cobrindo os 144 arquivos e os 809 testes: **809 passed + 12 subtests passed**.
- Testes focados finais da infraestrutura visual: **53 passed**.
- `python main.py`: **não abriu neste ambiente**. Bloqueios observados e preservados integralmente:
  1. `_tkinter.TclError: couldn't connect to display ":0"` ao inicializar o splash.
  2. `ModuleNotFoundError: No module named 'customtkinter'` ao importar `nabicode_legacy.py`.

Nenhum desses bloqueios foi mascarado como sucesso de abertura gráfica.

## Auditoria final

- `nabicode_legacy.py`: SHA-256 idêntico ao ZIP base (`0ee9dfe00bf7e34eb795ac888278b791b16aaf47ef27932324e08ea574c21028`).
- cache de imagens do BackgroundManager limitado a 4 itens;
- resize com debounce de 80 ms;
- sem `PhotoImage` órfão no desenho arquitetural: cada alvo guarda uma única referência ativa e o cache é limitado;
- nenhum import novo morto identificado nos arquivos modificados;
- nenhuma dimensão rígida nova foi adicionada a telas funcionais;
- nenhum binding de resize duplicado foi criado fora do gerenciador central;
- nenhuma alteração em Financeiro, PDV, Documental, Cadastros/regras, banco, schema, migração ou estoque.
