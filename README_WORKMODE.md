# NabiCode v2.4.97 — WORKMODE BASE

## Finalidade

Base completa consolidada para continuidade do desenvolvimento no Work Mode/Codex.

## Origem

Base estável usada como origem física:

`NabiCode_v2_4_96_TESTE_INTEGRADO_HOTFIX_CLIENTES`

Integração aplicada na ordem:

1. Legacy
2. Financeiro
3. Cadastros
4. Documental
5. Interface

Os protótipos novos de Splash Matrix e o `background_manager(1)(2).py` experimental enviados separadamente **não foram integrados** nesta base.

## Estado dos testes desta integração

- `python -m compileall -q .`: APROVADO
- testes focados dos cinco módulos: `36 passed`
- suíte completa: `863 passed, 11 subtests passed`
- startup smoke: APROVADO, versão `2.4.97`
- `python main.py`: tentativa realizada, bloqueada neste ambiente por ausência de display Tk e `customtkinter`
- EXE: não gerado

## Missão inicial no Work Mode

Antes de implementar qualquer funcionalidade nova:

1. Auditar toda a árvore do projeto.
2. Identificar maiores arquivos e funções.
3. Localizar SQL repetido, transações duplicadas, imports mortos e código morto.
4. Mapear dependências circulares e alto acoplamento.
5. Não alterar comportamento funcional durante a auditoria.
6. Executar `python -m compileall -q .` e `pytest -q` antes e depois de qualquer refatoração.
7. Preservar os fluxos críticos: Login, Dashboard, Pesquisa, lista de sugestões, Enter/KP_Enter, Venda, Finalização, Financeiro, Impressão 80 mm, PDF sob demanda, Reimpressão e Cadastros.
8. Não integrar Splash/Watermark/Background experimental sem uma sprint isolada e aprovação posterior.

## Política de desenvolvimento

- estabilidade antes de funcionalidade nova;
- não substituir `nabicode_legacy.py` inteiro;
- mudanças no legado devem ser pequenas e testáveis;
- 80 mm é o formato documental oficial;
- imprimir cupom não pode gerar PDF automaticamente;
- não gerar EXE durante desenvolvimento;
- não incluir bancos operacionais, caches, `.venv`, `build` ou `dist` em pacotes de desenvolvimento.
