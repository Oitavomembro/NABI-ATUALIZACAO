# NabiCode 2.4.93 — Enter, Pânico e aproveitamento da tela de Clientes

Base: NabiCode_v2_4_92_TESTE_SALDO_HISTORICO

## Correções

### Navegação Enter do PDV

- Corrigido o Enter no campo de produto quando a lista de sugestões está aberta.
- A causa era o evento do CTkEntry sendo repassado para a Treeview; as coordenadas do Entry eram interpretadas como coordenadas da tabela e a seleção era descartada.
- O controlador agora confirma a sugestão selecionada sem reutilizar coordenadas do campo de pesquisa.
- A rotina do legado também só interpreta coordenadas do mouse quando o evento realmente veio da Treeview.
- Fluxo: produto -> quantidade -> preço -> adicionar.
- Após adicionar, o foco volta à pesquisa.
- Com pesquisa vazia e carrinho preenchido, Enter leva ao carrinho; Enter no carrinho aciona a finalização.
- Return e KP_Enter continuam equivalentes.

### Atalho Pânico

- Removido definitivamente o gatilho por quatro setas para baixo.
- Novo atalho deliberado: Ctrl+Shift+P.
- Adicionado botão visível `Pânico [Ctrl+Shift+P]` no menu lateral.
- A seta para baixo fica livre para navegar em listas e sugestões sem risco de fechar o sistema.

### Tela de Clientes

- O conteúdo da tela de Clientes agora pode expandir até a largura disponível do viewport.
- Mantido mínimo de 1180 px para preservar todas as colunas e ações.
- Em telas maiores, o espaço livre à direita é aproveitado sem retirar espaço de botões ou informações.
- Rolagem horizontal continua disponível somente quando realmente necessária.

## Validação

Compilação:

`python -m compileall -q .` — APROVADA

Testes focados:

`23 passed`

Suíte completa:

`784 passed, 12 subtests passed`

`python main.py` foi tentado, porém o ambiente atual não possui servidor gráfico e customtkinter disponível:

- `_tkinter.TclError: couldn't connect to display ":0"`
- `ModuleNotFoundError: No module named 'customtkinter'`

A validação visual/teclado deve ser repetida no Windows.
