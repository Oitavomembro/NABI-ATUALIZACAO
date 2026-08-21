# Etapa 2 - homologacao fiscal controlada na Bahia

Esta etapa prepara NF-e modelo 55 e NFC-e modelo 65 para testes no ambiente de
homologacao. Os documentos gerados nao possuem valor fiscal e a producao
continua bloqueada.

## Protecoes obrigatorias

- ambiente configurado como `HOMOLOGACAO`;
- perfil de execucao `NABICODE_PROFILE=TESTE` durante testes internos;
- somente certificado A1 pertencente ao CNPJ configurado;
- nenhuma numeracao de producao e reutilizada;
- destinatario identificado e anonimizado antes de gerar o XML;
- CNPJ de teste `99999999000191`, nome oficial de homologacao e ausencia de
  endereco, IE e e-mail reais;
- DANFE e interface identificam claramente `SEM VALOR FISCAL`;
- exportacao contabil exclui homologacao por padrao;
- nenhuma liberacao de producao faz parte deste roteiro.

## Ordem do teste acompanhado

1. Confirmar credenciamento do CNPJ no ambiente de homologacao da Bahia.
2. Abrir Configuracao Fiscal e manter `TESTE FISCAL - HOMOLOGACAO`.
3. Importar os dados do emitente por XML proprio autorizado ou conferi-los manualmente.
4. Instalar e validar o certificado A1.
5. Conferir modelos habilitados, series exclusivas de teste e catalogo fiscal.
6. Cadastrar somente regras tributarias aprovadas pelo contador.
7. Executar `Pre-voo fiscal local - nao transmite`.
8. Testar a conexao com a SEFAZ separadamente para NF-e e NFC-e habilitadas.
9. Emitir um documento minimo de cada modelo habilitado.
10. Registrar chave, retorno, codigo de status, protocolo, XML e DANFE.
11. Testar rejeicao corrigivel e reenvio sem duplicar numero ou venda.
12. Testar cancelamento, CC-e, inutilizacao e contingencia aplicaveis.
13. Reiniciar o NabiCode e confirmar recuperacao da fila e do historico.
14. Gerar pacote contabil incluindo homologacao somente para conferencia.

## Criterio de aprovacao

O teste e aprovado somente quando cada modelo habilitado possui autorizacao de
homologacao, consulta posterior consistente, DANFE correspondente e historico
persistido. Cancelamento/eventos devem retornar os codigos oficiais esperados.
Falha de rede nao pode congelar a interface nem transformar pendencia em autorizacao.

## Evidencia a registrar

- CNPJ e UF do emitente (mascarar na documentacao publica);
- versao e commit do NabiCode;
- data/hora e responsavel;
- modelos, series e numeros usados exclusivamente no teste;
- codigo e mensagem de cada retorno;
- chaves e protocolos de homologacao;
- resultado do cancelamento, CC-e, inutilizacao e contingencia;
- localizacao do backup e confirmacao de restauracao;
- pendencias do contador ou da SEFAZ.

## Bloqueios

- nao executar teste online sem acompanhamento do proprietario;
- nao versionar certificado, senha, XML real ou banco do cliente;
- nao transmitir se o CNPJ do certificado divergir do emitente;
- nao cadastrar aliquota presumida para apenas passar no teste;
- nao mudar para producao ao finalizar a homologacao.

