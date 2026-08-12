# Checkpoint 15 — Stress test automatizado

- Suíte separada em `stress_tests/`; `pytest.ini` mantém o pytest normal restrito a `tests/`.
- 1 teste de stress, 1.000 vendas, 2.000 movimentos e 100 rollbacks.
- Um bug de saldo em cancelamento de venda paga foi encontrado e corrigido.
- Regressão normal adicionada para impedir retorno do defeito.
- Stress final: aprovado em 24,13 segundos.
- `python -m compileall -q .`: aprovado.
- Suíte normal: 901 testes aprovados e 11 subtests aprovados.
- Total automatizado nesta etapa: 902 testes, sendo 1 teste de stress separado.
