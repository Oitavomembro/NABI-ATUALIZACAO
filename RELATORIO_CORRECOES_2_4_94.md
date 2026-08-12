# NabiCode 2.4.94 — Setas, layout de Clientes e corte térmico

## Correções
- Tela Clientes deixa de impor largura mínima de 1180 px; usa mínimo seguro de 900 px e cresce até o viewport.
- Setas navegam entre opções/botões globalmente sem roubar setas de Entry, ComboBox, Treeview, listas, sliders ou textos.
- Removido default conflitante que podia persistir corte automático desligado.
- Migração 2.4.94 habilita corte automático uma única vez em bases antigas; depois o usuário pode desligá-lo normalmente.
- Pânico permanece em Ctrl+Shift+P e não usa setas.
- Financeiro/recebimento não foi alterado.

## Validação automatizada
- `python -m compileall -q .`: aprovado.
- Testes focados: 27 passed + 5 subtests.
- Suíte completa: 788 passed + 12 subtests, 0 falhas.
- `python main.py`: tentativa realizada; bloqueada neste ambiente por ausência de display `:0` e `customtkinter`.

## Teste Windows pendente
- confirmar que a tabela Clientes não corta CPF/Histórico nem exige rolagem horizontal em resolução equivalente à captura enviada;
- confirmar navegação por setas em botões/opções sem interferir em campos e tabelas;
- confirmar corte físico da impressora térmica após a migração que habilita o corte automático.
