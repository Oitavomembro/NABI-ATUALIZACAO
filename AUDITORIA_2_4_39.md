# Auditoria 2.4.39

## Correções

- Migração única `login_opcional_migrado_2439` desativa o login inicial em bancos existentes antes da criação da interface.
- O proprietário pode reativar o login posteriormente em Configurações > Segurança.
- Padrão de fábrica não mantém mais o campo de senha escondido na área rolável.
- O botão `Continuar e informar senha` abre uma janela modal dedicada, visível e focada.
- A janela dedicada aceita senha administrativa ou senha mestra.
- Modos destrutivos exigem também `APAGAR TUDO`.
- Erros mantêm a janela de autorização aberta e o foco no campo correto.

## Validação

- Compilação Python.
- Suíte completa de testes.
- Validação de ferramentas.
- Integridade do ZIP.
