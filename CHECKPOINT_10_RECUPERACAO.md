# Checkpoint 10 — Recuperação e diagnóstico

## Resultado da auditoria

- Banco indisponível ou bloqueado: erros são propagados para os limites de interface; transações revertem antes do fechamento.
- Segunda instância: lock exclusivo por banco, validação conservadora de PID no Windows e liberação em `finally`/`atexit`.
- Produção e teste: perfil, diretório, marcador e lock são separados e validados.
- Inicialização: splash, lock e arquivo temporário são liberados em `finally`.
- Impressão: falha externa permanece separada da persistência da venda e não desfaz uma venda já confirmada.
- Atualização e snapshot: pacotes e bancos são validados antes da substituição, com recuperação por snapshot.
- Dados inválidos: validações de domínio e banco impedem commit parcial.

## Decisão

- Nenhum defeito crítico ou alto adicional foi comprovado.
- Não foram adicionados popups técnicos nem logs temporários.
- Implementações congeladas de navegação, impressão e foco não foram modificadas.

## Validação

- Testes focados: 32 aprovados e 3 subtests aprovados.
- `python -m compileall -q .`: aprovado.
- Suíte completa: 893 testes aprovados e 11 subtests aprovados.
