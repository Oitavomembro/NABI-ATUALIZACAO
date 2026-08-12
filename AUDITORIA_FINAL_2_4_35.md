# Auditoria final 2.4.35

- Login inicial desativado também para bancos existentes por migração única; reativação somente pela configuração de segurança.
- Credencial mestra centralizada em `SecurityService`; frase não permanece em texto puro nos fontes.
- Restauração e bloqueio técnico usam a mesma validação administrativa.
- PDV aceita venda simples sem cliente, usando o registro técnico CONSUMIDOR FINAL.
- Finalização redesenhada em três colunas horizontais, com Enter/Shift+Enter/Esc.
- Cupom é gerado depois da venda e abre ações Salvar PDF, Imprimir e Fechar.
- Código interno de produto é sugerido e gerado automaticamente; código de barras continua separado.
- Lista do carrinho possui rolagem e posiciona automaticamente no item recém-adicionado.
- Botão Suspender não é exibido; F6 permanece como atalho.
- Painel do PDV usa grade compacta de ações e mantém Finalizar Venda em destaque.
- Ações de clientes foram movidas para a faixa inferior da tela.
- Dashboard mantém Atividades do Sistema e Movimentações do Dia em áreas distintas.
- Validação do projeto: OK.
- Suíte: 447 testes, OK.
