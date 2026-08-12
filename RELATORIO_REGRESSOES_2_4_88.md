# NabiCode 2.4.88 — Relatório de regressões

## Resultado automatizado

- 716 testes aprovados.
- 12 subtestes aprovados.
- Compilação Python aprovada.
- Nenhuma falha automatizada detectada.

## Política documental

- 80 mm permanece como único formato térmico oferecido na interface.
- PDF continua separado da impressão física e somente é gerado quando solicitado.
- Configurações históricas de 58 mm são normalizadas/rejeitadas pelo serviço documental.
- O renderizador histórico interno não foi reintroduzido na interface.

## Bloqueio técnico

A abertura real da aplicação não foi validada porque o ambiente não contém `customtkinter` e não possui display gráfico acessível. Portanto, não se declara validação manual completa dos fluxos críticos.

## Risco residual

Risco residual moderado nos fluxos gráficos e de impressão física, pois exigem Windows, impressora configurada e sessão gráfica. Não há evidência automatizada de regressão após a integração.
