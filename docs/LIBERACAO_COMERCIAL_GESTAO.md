# NabiCode Gestão — liberação comercial

Este documento define a Etapa 1 de comercialização do NabiCode 2.5.1. Ele se
aplica ao uso administrativo e ao PDV **sem emissão fiscal oficial**.

## Escopo aprovado

- cadastros, estoque, vendas, crediário, recebimentos, Caixa e relatórios;
- importação de XML como apoio ao cadastro e à entrada de mercadorias;
- login de usuários opcional no modo não fiscal;
- senha administrativa pertencente ao cliente;
- senha mestra do fabricante restrita a suporte, recuperação e operações
  técnicas sensíveis, sempre registradas na auditoria;
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

### Login no modo não fiscal

O login não é obrigatório. Instalações de um único computador podem operar em
sessão local. Se o proprietário ativar usuários, permissões e inatividade, essas
configurações passam a ser respeitadas sem mudar as regras comerciais.

### Senha mestra de suporte

A senha mestra é uma credencial universal do fabricante. Ela não substitui a
senha cotidiana do cliente e não deve ser divulgada, impressa, registrada em
logs ou enviada junto do instalador. Seu uso deve ficar limitado a rotinas que
já exigem confirmação técnica e que produzam registro de auditoria.

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

