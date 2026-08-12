# NabiCode 2.4.89 — Relatório de Regressões

## Automatizadas

- Suíte completa: **733 passed, 12 subtests passed**.
- Falhas após correção do versionamento: **0**.
- Testes focados de Legacy/Infra, Financeiro, Cadastros, Documental e Interface: **52 passed**.
- Compilação Python: aprovada.
- Startup smoke sem abertura de UI: aprovado.

## Regressão encontrada durante integração

Após elevar a versão para `2.4.89`, `tests/test_startup_smoke_test.py` ainda esperava `2.4.88`, causando 1 falha. O teste foi corrigido para refletir a nova versão oficial. A suíte completa foi executada novamente e terminou sem falhas.

## Pendências de validação manual

Não foi possível confirmar visualmente os fluxos críticos porque o ambiente não possui servidor gráfico funcional nem `customtkinter`. Isso não é contabilizado como sucesso de smoke test manual.

Validação manual ainda necessária no Windows:

- Login sem alteração inesperada de senha no início;
- Dashboard;
- Pesquisa de produtos e lista de sugestões;
- Venda e finalização;
- Impressão 80 mm;
- PDF somente quando solicitado;
- Reimpressão;
- Financeiro;
- Cadastros.
