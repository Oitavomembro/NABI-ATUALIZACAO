# Sprint 1.17 — Persistência monetária exata

- Mantém colunas REAL legadas para compatibilidade.
- Adiciona colunas TEXT canônicas para preços, custos, percentuais e fator de conversão.
- Migração idempotente preenche as novas colunas a partir dos valores legados.
- O repositório grava simultaneamente a representação legada e a decimal exata.
- Leitura pública retorna Decimal.
- Histórico de preços também possui representação decimal exata.
- Testes reais em SQLite comprovam tipo TEXT e preservação de escala arbitrária.
- Teste integrado cobre formulário, comando, transação, persistência, reconstrução e histórico.
