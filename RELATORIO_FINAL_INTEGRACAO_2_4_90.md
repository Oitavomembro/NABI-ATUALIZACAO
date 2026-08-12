# NabiCode 2.4.90 — Integração de correções observadas no Windows

Base de origem: NabiCode_v2_4_89_BASE_OFICIAL_INTEGRADA.

## Correções integradas

- Favoritar cliente: corrigida a referência inexistente `self.cliente_repository`; a ação usa o `CLIENTE_REPOSITORY` oficial.
- Resumo lateral de clientes: todo cliente com saldo devedor positivo passa a aparecer em "Devendo", inclusive quando a primeira parcela ainda vence no futuro; clientes com atraso superior a 60 dias permanecem em "Alerta >60d".
- Busca de clientes: corrigido o ranqueamento de termos sem dígitos. O CPF vazio não pode mais receber prioridade falsa quando a pesquisa é textual. Mantida priorização por relevância e ficha.
- Histórico do cliente: saldo devedor adicionado em destaque no canto superior direito do cabeçalho.
- Tela de clientes: ao reabrir o módulo, a rolagem horizontal retorna à origem para evitar conteúdo aparecendo deslocado/cortado.
- PDF: o processo externo de abertura no Windows não usa mais `DETACHED_PROCESS`, preservando um desktop interativo válido para `Start-Process`.
- PDV/estoque: produto sem estoque é confrontado no momento da seleção; quantidade acima do saldo é novamente conferida antes da inclusão. A venda só passa com autorização explícita do operador.
- PDV/estoque: quando autorizado, o item recebe `estoque_override`, a baixa pode produzir saldo negativo e a movimentação registra que a autorização ocorreu no PDV.
- PDV: a descrição da venda registra `[ESTOQUE NEGATIVO AUTORIZADO]` quando aplicável.

## Política preservada

- Nenhum EXE foi gerado.
- Nenhum suporte de 58 mm foi reintroduzido.
- PDF continua separado da impressão física.
- Login de abertura não foi alterado.
