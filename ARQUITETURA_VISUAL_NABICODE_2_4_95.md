# Arquitetura visual NabiCode — 2.4.95

## Componentes

- `ui/background_manager.py`: fonte única da marca d'água. API: `attach`, `detach`, `refresh`, `set_enabled`, `set_opacity`, `set_scale`, `set_position`, `set_logo_path`.
- `ui/layout_manager.py`: políticas responsivas puras e reutilizáveis para containers, tabelas, colunas e janelas secundárias.
- `services/ui_preferences.py`: persistência/normalização das novas preferências dentro do mecanismo já existente.
- `PATCH_INTERFACE_LEGADO.md`: aplicação visual em Configurações, Clientes, Histórico e shell global, sem editar diretamente o legado.

## BackgroundManager

A origem é uma imagem configurada externamente. Não existe ativo de logo no ZIP base, portanto nenhum arquivo de imagem foi inventado ou embutido. O patch reutiliza em modo somente leitura `impressao_logo_path`, que já é o caminho configurável existente para a identidade da empresa.

A marca d'água preserva aspecto, limita opacidade a 2%–25%, mantém cache LRU máximo de quatro imagens, reutiliza a imagem quando tamanho/configuração não mudam e usa debounce de 80 ms no `<Configure>`. O label é rebaixado (`lower`) e não recebe foco (`takefocus=0`).

Escalas: automática, pequena, média e grande. Posições: centro, superior e inferior.

## LayoutManager

A regra central é: cabeçalho, filtros, ações e rodapé mantêm tamanho natural; somente a área de conteúdo/tabela recebe `weight=1` e `sticky="nsew"`.

Para Clientes, as larguras mínimas garantidas são: Ficha 90, Nome 210, Saldo 135, Limite 105, Telefone 115, CPF 120 e Favorito 46. Espaço adicional é distribuído prioritariamente a Nome, Telefone e CPF.

A política cobre 1024x768, 1280x720, 1366x768, 1600x900, 1920x1080, 2560x1440 e 3840x2160. Janelas secundárias usam geometria limitada à área útil da tela, sem impor `minsize` maior que a própria janela calculada.

## Auditoria estrutural da base

- Dashboard: usa `BidirectionalScrollableFrame` com `content_width=1180`; o conteúdo é expansível, mas largura base rígida pode induzir scroll horizontal em 1024/1280.
- Clientes: usa scroll bidirecional externo e uma tabela `pack(expand=True)` dentro de conteúdo rolável; esse desenho é a principal fonte de espaço vertical desperdiçado e botões deslocados. O patch substitui por shell `grid` expansível.
- Histórico de cliente: a área de abas já é `expand=True`; o principal problema é `geometry("980x760")` + `minsize(840,650)` fixos. O patch usa geometria responsiva.
- Produtos: tabela principal usa `Treeview` sem altura fixa; há trechos com `grid_rowconfigure(..., weight=1)`, indicando arquitetura parcialmente responsiva.
- Financeiro: auditado apenas estruturalmente; nenhuma rotina ou regra financeira foi alterada.
- Relatórios: auditado apenas estruturalmente; nenhuma rotina de relatório foi alterada.
- Configurações: usa conteúdo rolável e pode receber os novos controles sem segundo sistema de persistência.
- Janelas secundárias: há várias `Treeview`; a política nova pode ser aplicada progressivamente sem mudar comandos nem dados.

## Regras de integração

`nabicode_legacy.py` permanece byte a byte igual à base recebida. A integração do patch deve ser feita pela conversa autorizada para Legacy. Enquanto esse patch não for aplicado, os novos managers existem e são testados, porém a UI principal ainda não os instancia.
