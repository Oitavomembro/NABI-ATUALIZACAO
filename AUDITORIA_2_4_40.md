# Auditoria 2.4.40

> Registro histórico da versão 2.4.40. As referências abaixo a senha mestra não
> descrevem o produto atual; a credencial universal foi removida. Consulte o
> mapa de sucessão para o contrato vigente.

- Login inicial: bloqueado por padrão em bancos novos e existentes.
- Ativação de login: exige consentimento explícito salvo na tela Segurança.
- Hotfix de banco: incluído para desligar login na instalação atual sem apagar dados.
- Senha mestra: validação centralizada, hash apenas, tolera caixa e espaços acidentais.
- Padrão de fábrica: usa o mesmo SecurityService da senha mestra.
- Restauração de configurações: desativa novamente o login inicial.
- Testes: 459 aprovados.
