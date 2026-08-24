# NabiCode Gestão — liberação comercial

Este documento define a Etapa 1 de comercialização do NabiCode 2.5.1. Ele se
aplica ao uso administrativo e ao PDV **sem emissão fiscal oficial**.

## Escopo aprovado

- cadastros, estoque, vendas, crediário, recebimentos, Caixa e relatórios;
- importação de XML como apoio ao cadastro e à entrada de mercadorias;
- login obrigatório com usuário ativo antes de liberar os módulos;
- credenciais individuais pertencentes ao cliente, com primeiro acesso e
  migração assistida para instalações antigas;
- nenhuma senha mestra, credencial universal ou fallback do fabricante;
- backup diário e backup manual, restauração validada e atualização com
  snapshot/retorno à versão anterior;
- emissão fiscal de produção permanece bloqueada.

## Portas obrigatórias antes de entregar uma versão ao cliente

1. A suíte automatizada, compilação, smoke sem GUI e `git diff --check` passam.
2. O instalador de teste é validado em máquina limpa e não cria duas versões.
3. Instalar, atualizar, reparar e desinstalar são testados.
4. As opções de desinstalação preservando dados e remoção total são testadas.
5. Um backup criado pela versão entregue é restaurado em banco temporário.
6. Perfis TESTE e PRODUÇÃO usam pastas e bancos diferentes.
7. Nenhuma credencial, certificado, banco real ou dado de cliente integra o
   pacote.
8. O modo fiscal de produção continua bloqueado.
9. O cliente recebe a Política de Privacidade, os Termos de Licença e o roteiro
   de backup/suporte preenchidos com os dados da empresa fornecedora.
10. O responsável pela entrega registra versão, hash do instalador, data e
    resultado da validação manual.

Qualquer item reprovado impede chamar o pacote de versão comercial. Uma versão
assim ainda pode ser distribuída somente como TESTE.

## Decisões do produto

### Login e autoria no modo não fiscal

O login é obrigatório antes de liberar os módulos da edição Gestão. Instalações
novas concluem o primeiro acesso criando uma credencial administrativa do
cliente; instalações antigas passam pela migração assistida e depois usam o
login normal. Permissões, inatividade e autoria são sempre vinculadas à sessão.

### Suporte sem credencial universal

O NabiCode não possui senha mestra ou credencial universal do fabricante.
Suporte e recuperação exigem autorização por uma conta ativa do cliente com a
permissão necessária e registro de auditoria. Licença assinada não autentica
operador e nenhuma senha pode fabricar, prolongar ou contornar uma licença.

### Fiscal

Importar XML não transforma o sistema em emissor fiscal. NF-e/NFC-e em produção
só podem ser liberadas na Etapa 3, após homologação real e validação contábil.

## Evidências da entrega

Preencher para cada pacote:

- versão e revisão:
- commit Git:
- instalador e SHA-256:
- perfil testado:
- banco temporário utilizado:
- resultado da suíte:
- teste em máquina limpa:
- teste de backup/restauração:
- teste de atualização/retorno:
- responsável e data:

