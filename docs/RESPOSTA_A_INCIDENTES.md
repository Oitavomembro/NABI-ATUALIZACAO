# Roteiro de resposta a incidentes

## Ao receber um relato

1. Registrar data, versão, computador, usuário e descrição, sem solicitar senha.
2. Orientar o cliente a interromper somente a operação afetada.
3. Preservar banco, logs e backups; não apagar nem sobrescrever evidências.
4. Classificar: indisponibilidade, integridade financeira, perda de dados,
   acesso indevido, privacidade ou segurança fiscal.
5. Criar backup validado antes de qualquer correção.

## Contenção e correção

- reproduzir com `NABICODE_PROFILE=TESTE` e banco temporário;
- remover credenciais e dados pessoais dos materiais de diagnóstico;
- localizar a causa raiz e criar teste de regressão;
- produzir atualização oficial assinada/validada e manter retorno seguro;
- não usar banco real, certificado real, SEFAZ ou impressora sem autorização
  específica e acompanhamento do proprietário.

## Incidente com dados pessoais

O responsável pelo tratamento deve avaliar natureza, volume, pessoas afetadas,
consequências e medidas adotadas. Se houver risco ou dano relevante confirmado,
a organização responsável decide e realiza as comunicações legais aplicáveis.

## Encerramento

Registrar causa, arquivos/versão afetados, correção, testes, orientação ao
cliente e confirmação de restauração do serviço. Segredos nunca entram no Git,
no diagnóstico ou no relatório entregue.

