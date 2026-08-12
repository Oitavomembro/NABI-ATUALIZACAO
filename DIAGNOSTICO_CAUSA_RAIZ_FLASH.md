# Diagnóstico da causa raiz do flash

## Escopo observado

Foram auditados o callback de menu, `mostrar_tela`, a pilha de telas, o container, os carregamentos executados durante navegação, a abertura do PDV e os históricos em `CTkToplevel`. Também foram comparados os mecanismos exclusivos do pacote anterior de flash.

## Fluxo das telas normais

`clique/menu -> mostrar_tela(nome) -> preparar dados/widgets do destino -> tkraise() -> tela destino`

As telas normais já são criadas uma única vez em `criar_telas`, compartilham `container_telas` e permanecem empilhadas. Não há `destroy`, `pack_forget`, `grid_forget`, `grid_remove` ou `place_forget` em `mostrar_tela`. Antes desta correção, `tkraise()` ocorria antes dos carregamentos síncronos, permitindo que o usuário visse o destino sendo reconstruído. A preparação agora ocorre enquanto a origem continua levantada; somente depois o destino recebe `tkraise()`.

## Fluxo do PDV e causa raiz

`clique Vendas -> mostrar_tela("vendas") -> abrir_pdv_independente() -> CTkToplevel -> withdraw() -> state("zoomed") durante construção -> montagem dos widgets -> after_idle -> deiconify()`

No Windows, `state("zoomed")` pode mapear o `Toplevel` mesmo depois de `withdraw()`. Como a chamada ocorria antes da criação dos filhos CustomTkinter, o sistema podia apresentar o fundo nativo branco da janela. O `withdraw()` inicial e o `deiconify()` posterior não garantiam ocultação porque a maximização intermediária alterava o estado de mapeamento.

## Históricos

Histórico de cliente e histórico de notificações criavam `CTkToplevel` visível e só depois adicionavam widgets. Isso permitia um retângulo branco menor durante o primeiro desenho. Ambos agora são retirados imediatamente e revelados via `after_idle` após a montagem completa.

## Correção aplicada

- Adicionado `ui/window_reveal.py` com contrato público de retirar, concluir layout/geometria e revelar.
- O helper não usa `alpha`, overlay, splash, `sleep`, temporizador ou atributo privado do CustomTkinter.
- A maximização do PDV ocorre somente depois de todos os widgets existirem e após `update_idletasks()`.
- A revelação usa `after_idle`, que agenda para o ciclo ocioso atual sem atraso temporal artificial.
- Históricos seguem o mesmo contrato e aplicam `grab_set()` somente na revelação.
- Telas normais são carregadas antes de `tkraise()`, mantendo a origem visível durante a preparação.

## Por que remove a causa

A correção elimina o estado em que uma janela mapeada ainda não possui conteúdo. Não tenta cobrir o branco com outra superfície: impede o mapeamento prematuro. Na navegação empilhada, impede que o destino incompleto seja levantado.

## Validação manual Windows

Validação concluída pelo usuário em Windows com `python main.py`: inicialização normal, navegação funcional e fluida, sem ocorrência do flash/tela branca anteriormente observado. A correção estrutural está validada no Windows e sua arquitetura deve ser preservada enquanto não houver regressão comprovada.
