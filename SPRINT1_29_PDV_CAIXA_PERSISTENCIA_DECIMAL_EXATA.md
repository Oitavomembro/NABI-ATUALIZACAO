# Sprint 1.29 — PDV e Caixa: persistência decimal exata

- Colunas canônicas TEXT adicionadas por migração para movimentações, parcelas, saldo de clientes, abertura e fechamento de caixa.
- PDV e Caixa gravam simultaneamente REAL legado e TEXT canônico quando o schema está migrado.
- Compatibilidade preservada com schemas antigos sem migração em construtores ou serviços.
- Leituras de Caixa priorizam Decimal canônico com fallback legado.
- Cancelamentos sincronizam valores canônicos quando disponíveis.
- Testes SQLite reais validam precisão extensa e tipo TEXT.
