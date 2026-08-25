# Dossiê fiscal automatizado OFFLINE — resumo sanitizado

> **TESTE AUTOMATIZADO COM FAKES. NÃO É HOMOLOGAÇÃO FÍSICA, NÃO HOUVE
> COMUNICAÇÃO OU SUCESSO SEFAZ E PRODUÇÃO FISCAL CONTINUA BLOQUEADA.**

- Dossiê: `NABICODE-FISCAL-OFFLINE-TESTE-001`
- Aplicação: `2.5.1 R21`
- Harness/schema: `1.1.0` / `1.0`
- Fonte: `base:a179e791a82bc0a58c4ccccc1bccf357b6008fa8+codex/fiscal-regressao-offline`
- Perfil/ambiente: `TESTE` / `SIMULADO_OFFLINE`
- Cenários automatizados: `17`; aprovados: `17`; reprovados: `0`
- Homologação fiscal real: `NAO_EXECUTADA`
- Homologação física: `PENDENTE`
- Produção fiscal: `BLOQUEADA`
- SHA-256 do JSON: `578f61213164a998c9879bd92b514213c0c28ad215a42aad951e8af07dc28af3`
- SHA-256 do payload canônico: `3c3375cfda2007298856ed08a105c500ab566e67df1b4bcfe106b9ea9540c206`
- SHA-256 do harness: `c46ebfe3b66bf52c673e82982b373c3128090851be2697fefe1cd72df06e5993`

## Matriz executada

| Cenário | Modelo | Teste | Resultado fiscal explicitamente simulado | Evidência SHA-256 |
|---|---:|---|---|---|
| PRONTIDAO-TESTE-FAKE | 55/65 | APROVADO | APTO_SOMENTE_PARA_TESTE_AUTOMATIZADO | `5e974f2e01a988e6320afe4ec98042cf1e7c22d22fdc2eb8278761cafad9ace6` |
| PRONTIDAO-A1-AUSENTE | 55/65 | APROVADO | BLOQUEADO | `48663ffc7dffdeb035ee94a8e8faceaf56ef073c7794cf2edb58ba4ebefda9c3` |
| PRONTIDAO-NUMERACAO-AUSENTE | 55/65 | APROVADO | BLOQUEADO | `a898a0a6389b254381de894b636cd81aa18320ccb30d489411625752a9f05799` |
| AUTORIZACAO-SIMULADA | 65 | APROVADO | AUTORIZADO_SIMULADO_SEM_SEFAZ | `0ce6fd64295c4a3f488def0c616462545b87ad15753468059fffdad6996ad612` |
| REJEICAO-SIMULADA | 55 | APROVADO | REJEITADO_SIMULADO | `1194e1e5b478e16caf6571e3e5854db67c73fa922dad186ad7d22999a4e9fa4d` |
| TIMEOUT-ANTES-DESPACHO | 55/65 | APROVADO | NAO_ENVIADO_SIMULADO | `044b063cfaddc43e63cdc262ab8cf2bd154af4caf4b37f000bc498efdd5e424f` |
| TIMEOUT-APOS-DESPACHO | 65 | APROVADO | RESPOSTA_DESCONHECIDA_SIMULADA | `41e7219adc0b5f25c303b811399d3778580da5ef3f1b0846c4a06a42a7eb23ab` |
| RESPOSTA-NAO-CLASSIFICAVEL | 55 | APROVADO | RESPOSTA_DESCONHECIDA_SIMULADA | `e411bbaafe931b6ff799258cc9ac60356f54170c32070d46ded674e52c6f7cd9` |
| CONSULTA-RECONCILIACAO | 65 | APROVADO | AUTORIZADO_SIMULADO_APOS_CONSULTA | `a89472a8ffceb9b2927cb960e536b109bab2a141f5be4e01b10c500ac1776b13` |
| CANCELAMENTO-SIMULADO | 65 | APROVADO | CANCELADO_SIMULADO_SEM_SEFAZ | `d0c2c992634f856d31bf600b9fd7151ef76279845895d3370b21c67f44514b88` |
| CANCELAMENTO-BLOQUEADO-INCERTO | 55 | APROVADO | BLOQUEADO | `d6d7a0348e7998ac4caaf7cce712b112edbbc78759ed83c0c807b03e5a55d8dc` |
| INUTILIZACAO-SIMULADA | 55 | APROVADO | INUTILIZADA_SIMULADA_SEM_SEFAZ | `bc971efecba79556858ff3a085c3306c976d28a188dd6cca298ac6eb1192307d` |
| CONTINGENCIA-OFFLINE-65 | 65 | APROVADO | CONTINGENCIA_SIMULADA_PENDENTE | `4619d0af6ce76dfc7912c644688eb3089e26a3cfe275ff811d4c35a2818dde29` |
| BLOQUEIO-PRODUCAO | 55/65 | APROVADO | BLOQUEADO | `07351d29d8baea7876a5d9fc97a8e44dee16d6f1c7156480dd78d04b8920049e` |
| BLOQUEIO-PORTAO-AUSENTE | 55/65 | APROVADO | BLOQUEADO | `07351d29d8baea7876a5d9fc97a8e44dee16d6f1c7156480dd78d04b8920049e` |
| BLOQUEIO-PERMISSAO-AUSENTE | 55/65 | APROVADO | BLOQUEADO | `07351d29d8baea7876a5d9fc97a8e44dee16d6f1c7156480dd78d04b8920049e` |
| BLOQUEIO-CONTINGENCIA-55 | 55 | APROVADO | BLOQUEADO | `b31dbf810035646e720ba3925fa4bd98c5efa393050898e7916a2f02f744ec2e` |

## Prova de isolamento

- Tentativas de rede real: `0`.
- Tentativas de banco real: `0`.
- Tentativas de certificado/chave real: `0`.
- Chamadas do transporte fake roteirizado: `8`.
- Escritas no store exclusivamente em memória: `8`.
- Guards ativos durante a execução: `socket.socket`, `socket.SocketType`, `socket.create_connection`, `socket.socketpair/fromfd/fromshare`, `socket DNS resolution`, `_socket.socket`, `urllib.request.urlopen`, `http.client.HTTPConnection.connect`, `sqlite3.connect`, `sqlite3.dbapi2/_sqlite3 connect/Connection`, `builtins/io/_io/os.open(certificados/chaves)`.

## Limitações impeditivas

- Os resultados aprovam apenas as asserções do harness determinístico.
- Nenhum certificado A1, CSC, chave privada, senha ou arquivo fiscal real foi usado.
- Nenhum socket, HTTP, TLS, endpoint SEFAZ ou outra rede foi usado.
- Nenhum SQLite, banco de cliente, XML real, DANFE ou numeração real foi usado.
- cStat, mensagens e protocolos deste relatório são dados sintéticos de TESTE.
- Autorização, cancelamento e inutilização simulados não provam aceitação pela SEFAZ.
- Contingência foi exercitada apenas como estado seguro; prazo legal e calendário permanecem pendentes.
- Homologação física acompanhada, credenciamento, certificado, impressão, DANFE/QR e pacote contábil continuam pendentes.
- Produção fiscal continua bloqueada e exige evidência externa e autorização próprias.
