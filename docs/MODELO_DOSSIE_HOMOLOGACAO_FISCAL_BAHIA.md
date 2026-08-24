# Modelo de dossiê de homologação fiscal — Bahia

> **Estado deste arquivo:** MODELO NÃO EXECUTADO.  A presença deste documento
> não comprova credenciamento, homologação, autorização nem aptidão para
> produção. Todo campo de evidência real permanece `PENDENTE` até ser preenchido
> pelo responsável durante uma sessão fiscal acompanhada.

## 1. Controle do dossiê

| Campo | Registro |
|---|---|
| Empresa/emitente (mascarado na cópia pública) | PENDENTE |
| CNPJ completo (anexo restrito) | PENDENTE |
| Inscrição estadual | PENDENTE |
| UF | BA |
| Responsável legal | PENDENTE |
| Responsável técnico | PENDENTE |
| Contador responsável | PENDENTE |
| Executor dos testes | PENDENTE |
| Revisor independente | PENDENTE |
| Data/hora de início (America/Bahia) | PENDENTE |
| Data/hora de término (America/Bahia) | PENDENTE |
| Versão/commit integral do NabiCode | PENDENTE |
| Perfil e banco exclusivo de teste | PENDENTE |
| Certificado A1 e validade (sem senha/chave privada) | PENDENTE |
| Credenciamento NF-e modelo 55 | PENDENTE |
| Credenciamento NFC-e modelo 65 | PENDENTE |
| Resultado final por modelo | PENDENTE |
| Aprovação do responsável legal | PENDENTE |
| Aprovação do contador | PENDENTE |

### Regras de preenchimento

- usar exclusivamente dados, certificado e credenciamento autorizados pelo
  proprietário;
- não versionar certificado, senha, chave privada, banco, XML fiscal real ou
  dados pessoais desnecessários;
- registrar horário com fuso, hash SHA-256 e origem de cada anexo;
- preservar XML de envio e resposta em repositório restrito de evidências, nunca
  neste repositório de código;
- não substituir `PENDENTE` por inferência, captura fabricada ou resultado de
  teste automatizado;
- uma aprovação em homologação não libera produção automaticamente.

## 2. Matriz de ambientes e modelos

Preencher cada célula de modo independente. Endpoints devem ser conferidos nas
fontes oficiais no dia da execução; não copiar endereços de memória.

| Modelo | Ambiente | Credenciado | Série/número exclusivos | Endpoint oficial conferido | CSC aplicável | Execução permitida | Resultado |
|---|---|---|---|---|---|---|---|
| NF-e 55 | Homologação | PENDENTE | PENDENTE | PENDENTE | Não se aplica/PENDENTE | PENDENTE | PENDENTE |
| NF-e 55 | Produção | PENDENTE | PENDENTE | PENDENTE | Não se aplica/PENDENTE | **BLOQUEADA até liberação formal** | PENDENTE |
| NFC-e 65 | Homologação | PENDENTE | PENDENTE | PENDENTE | PENDENTE | PENDENTE | PENDENTE |
| NFC-e 65 | Produção | PENDENTE | PENDENTE | PENDENTE | PENDENTE | **BLOQUEADA até liberação formal** | PENDENTE |

Para contribuinte da Bahia, os testes devem usar o ambiente de homologação da
própria SEFAZ autorizadora. O Portal Nacional registra que BA não deve testar
pelos serviços genéricos de homologação da SVAN/SVC-AN. A confirmação vigente
dos endpoints continua obrigatoriamente `PENDENTE` até o dia da sessão.

## 3. Identificação uniforme de cada caso

Copiar este bloco para cada execução:

| Campo | Evidência |
|---|---|
| ID do caso | PENDENTE |
| Modelo/ambiente | PENDENTE |
| Objetivo | PENDENTE |
| Pré-condições conferidas por | PENDENTE |
| Início/fim com fuso | PENDENTE |
| Operador e testemunha | PENDENTE |
| Commit e hash do executável/artefato | PENDENTE |
| Série, número e chave (mascarada na cópia pública) | PENDENTE |
| cStat/xMotivo e protocolo | PENDENTE |
| SHA-256 XML enviado | PENDENTE |
| SHA-256 XML retornado/processado | PENDENTE |
| SHA-256 DANFE/PDF ou imagem | PENDENTE |
| Capturas e logs sanitizados | PENDENTE |
| Resultado: APROVADO/REPROVADO/BLOQUEADO | PENDENTE |
| Desvio, chamado e reteste | PENDENTE |

## 4. Trilha NF-e — modelo 55

### 4.1 Homologação

| Etapa | Critério mínimo | Evidência/resultado |
|---|---|---|
| Pré-voo | emitente, certificado, cadeia, schema, catálogo, série e ambiente conferidos | PENDENTE |
| Status do serviço | resposta oficial preservada sem transformar indisponibilidade em autorização | PENDENTE |
| Autorização | envio válido; resposta, protocolo e XML processado coerentes | PENDENTE |
| Consulta posterior | situação consultada pela chave coincide com autorização persistida | PENDENTE |
| DANFE | representa o XML autorizado, contém chave/ambiente e indicação de homologação | PENDENTE |
| Rejeição controlada | caso corrigível documentado; nenhuma venda/número duplicado | PENDENTE |
| Correção e reenvio | causa corrigida; nova resposta vinculada à tentativa correta | PENDENTE |
| Eventos aplicáveis | cancelamento, CC-e e inutilização testados apenas quando legalmente aplicáveis | PENDENTE |
| Contingência aplicável | modalidade escolhida e ativação comprovadas contra manual vigente | PENDENTE |
| Retorno da contingência | pendências reconciliadas sem autorização fictícia ou duplicada | PENDENTE |
| Reinício | fila, histórico, protocolo e estado retomados de forma consistente | PENDENTE |
| Pacote contábil | XML autorizado/eventos/DANFE/relatório íntegros e segregados por ambiente | PENDENTE |

### 4.2 Produção — portão separado

Nenhuma linha abaixo autoriza emissão. Executar somente após homologação aprovada,
credenciamento confirmado e autorização escrita do proprietário e do contador.

| Portão | Aprovação/evidência |
|---|---|
| Dossiê 55 de homologação completo e sem pendência crítica | PENDENTE |
| Endpoint de produção conferido em fonte oficial no dia | PENDENTE |
| Série/numeração de produção aprovadas | PENDENTE |
| Regras tributárias aprovadas pelo contador | PENDENTE |
| Backup e plano de retorno conferidos | PENDENTE |
| Autorização escrita do responsável | PENDENTE |
| Primeiro documento acompanhado e conciliado | PENDENTE |

## 5. Trilha NFC-e — modelo 65

### 5.1 Homologação

| Etapa | Critério mínimo | Evidência/resultado |
|---|---|---|
| Pré-voo | emitente, certificado, cadeia, schema, série, ambiente e CSC conferidos | PENDENTE |
| Status do serviço | resposta oficial preservada; falha continua sendo falha | PENDENTE |
| Autorização | envio válido; resposta, protocolo e XML processado coerentes | PENDENTE |
| Consulta posterior | situação pela chave coincide com autorização persistida | PENDENTE |
| DANFE NFC-e/QR Code | conteúdo, ambiente, chave, URL/QR e total correspondem ao XML | PENDENTE |
| Rejeição controlada | caso corrigível documentado sem venda ou numeração duplicada | PENDENTE |
| Correção e reenvio | tentativa original e corrigida permanecem rastreáveis | PENDENTE |
| Eventos aplicáveis | cancelamento e demais eventos somente quando previstos e autorizados | PENDENTE |
| Contingência offline | entrada, impressão, armazenamento e transmissão posterior seguem manual vigente | PENDENTE |
| Retorno da contingência | transmissão/reconciliação sem perda nem duplicidade | PENDENTE |
| Reinício | pendência offline, histórico e estado operacional são recuperados | PENDENTE |
| Pacote contábil | XML autorizado/eventos/DANFE/relatório íntegros e segregados por ambiente | PENDENTE |

### 5.2 Produção — portão separado

| Portão | Aprovação/evidência |
|---|---|
| Dossiê 65 de homologação completo e sem pendência crítica | PENDENTE |
| Endpoint e URL do QR Code de produção conferidos no dia | PENDENTE |
| CSC de produção tratado como segredo e validado | PENDENTE |
| Série/numeração de produção aprovadas | PENDENTE |
| Regras tributárias aprovadas pelo contador | PENDENTE |
| Backup e plano de retorno conferidos | PENDENTE |
| Autorização escrita do responsável | PENDENTE |
| Primeiro documento acompanhado e conciliado | PENDENTE |

## 6. Roteiros adversariais obrigatórios

Cada roteiro deve ser repetido separadamente para 55 e 65 quando aplicável.

| Cenário | O sistema deve comprovar | 55 | 65 |
|---|---|---|---|
| Timeout antes da resposta | não declarar autorização; permitir consulta/reconciliação segura | PENDENTE | PENDENTE |
| Resposta rejeitada | exibir cStat/xMotivo; não criar protocolo fictício | PENDENTE | PENDENTE |
| Reenvio da mesma operação | não duplicar venda, estoque, financeiro, número ou autorização | PENDENTE | PENDENTE |
| XML/retorno adulterado | falhar fechado e preservar diagnóstico | PENDENTE | PENDENTE |
| Certificado inválido/divergente | bloquear antes da transmissão | PENDENTE | PENDENTE |
| Endpoint/ambiente divergente | impedir mistura entre homologação e produção | PENDENTE | PENDENTE |
| Queda durante persistência | recuperar ou reprocessar idempotentemente | PENDENTE | PENDENTE |
| Reinício com fila pendente | retomar sem apagar nem promover estado | PENDENTE | PENDENTE |
| Evento duplicado/fora do prazo | preservar retorno oficial e não inventar sucesso | PENDENTE | PENDENTE |
| Contingência encerrada | conciliar todas as emissões e exceções | PENDENTE | PENDENTE |

## 7. Conferência de DANFE

- [ ] modelo correto e ambiente visível — PENDENTE;
- [ ] chave, série, número, emitente, destinatário, itens e totais coincidem com
  o XML correspondente — PENDENTE;
- [ ] protocolo/situação correspondem à resposta oficial — PENDENTE;
- [ ] DANFE de homologação não pode aparentar documento de produção — PENDENTE;
- [ ] código de barras da NF-e 55 legível e coerente — PENDENTE;
- [ ] QR Code e URL da NFC-e 65 conferidos no ambiente correto — PENDENTE;
- [ ] marcações exigidas para contingência presentes — PENDENTE;
- [ ] impressão e PDF comparados, com hashes registrados — PENDENTE.

## 8. Pacote contábil e cadeia de custódia

O pacote final de cada modelo/ambiente deve conter somente arquivos autorizados
para compartilhamento e ser segregado dos segredos operacionais.

| Conteúdo | Nome/local restrito | SHA-256 | Responsável | Data/hora |
|---|---|---|---|---|
| Índice do pacote | PENDENTE | PENDENTE | PENDENTE | PENDENTE |
| XML autorizado/processado | PENDENTE | PENDENTE | PENDENTE | PENDENTE |
| XML de eventos e retornos | PENDENTE | PENDENTE | PENDENTE | PENDENTE |
| DANFE/PDF | PENDENTE | PENDENTE | PENDENTE | PENDENTE |
| Relatório de consultas | PENDENTE | PENDENTE | PENDENTE | PENDENTE |
| Relatório de rejeição/reenvio | PENDENTE | PENDENTE | PENDENTE | PENDENTE |
| Relatório de contingência/reinício | PENDENTE | PENDENTE | PENDENTE | PENDENTE |
| Aprovações assinadas | PENDENTE | PENDENTE | PENDENTE | PENDENTE |

Excluir certificado A1, senha, chave privada, CSC em claro, tokens, banco integral,
logs sensíveis e dados pessoais não necessários. A cópia pública deve mascarar
CNPJ, chaves, protocolos e identificadores conforme política do responsável.

## 9. Índice de anexos

| Anexo | Descrição | Modelo/ambiente | Local restrito | SHA-256 | Situação |
|---|---|---|---|---|---|
| A-001 | PENDENTE | PENDENTE | PENDENTE | PENDENTE | PENDENTE |
| A-002 | PENDENTE | PENDENTE | PENDENTE | PENDENTE | PENDENTE |
| A-003 | PENDENTE | PENDENTE | PENDENTE | PENDENTE | PENDENTE |

## 10. Decisão e assinaturas

| Decisão | NF-e 55 | NFC-e 65 |
|---|---|---|
| Homologação técnica | PENDENTE | PENDENTE |
| Homologação fiscal/contábil | PENDENTE | PENDENTE |
| Pendências impeditivas | PENDENTE | PENDENTE |
| Produção liberada formalmente | PENDENTE | PENDENTE |

| Papel | Nome | Decisão | Data/hora/fuso | Assinatura ou referência |
|---|---|---|---|---|
| Responsável legal | PENDENTE | PENDENTE | PENDENTE | PENDENTE |
| Responsável técnico | PENDENTE | PENDENTE | PENDENTE | PENDENTE |
| Contador | PENDENTE | PENDENTE | PENDENTE | PENDENTE |
| Revisor | PENDENTE | PENDENTE | PENDENTE | PENDENTE |

## 11. Fontes oficiais e documentos internos de apoio

As URLs devem ser revalidadas no dia da homologação. Mudança normativa ou
técnica posterior exige nova revisão; este modelo não substitui orientação da
SEFAZ-BA nem do contador.

1. SEFAZ-BA, **Nota Fiscal Eletrônica** — página oficial com relação de serviços
   e orientações estaduais:
   <https://www.sefaz.ba.gov.br/inspetoria-eletronica/icms/documentos-fiscais/nota-fiscal-eletronica/>.
2. SEFAZ-BA, **NFC-e — Perguntas e Respostas**:
   <https://www.sefaz.ba.gov.br/docs/inspetoria-eletronica/icms/nfce_perguntas_respostas_.pdf>.
3. SEFAZ-BA, **Nota Fiscal de Consumidor Eletrônica** — orientações e serviços
   estaduais do modelo 65:
   <https://www.sefaz.ba.gov.br/inspetoria-eletronica/icms/documentos-fiscais/nota-fiscal-de-consumidor-eletronica/>.
4. Portal Nacional da NF-e, **Manuais** — MOC 7.0, anexos de leiaute, DANFE e
   contingência, além dos manuais próprios da NFC-e:
   <https://www.nfe.fazenda.gov.br/portal/listaConteudo.aspx?tipoConteudo=ndIjl+iEFdE%3D>.
5. Portal Nacional da NF-e, **Notas Técnicas**:
   <https://www.nfe.fazenda.gov.br/portal/listaConteudo.aspx?tipoConteudo=04BIflQt1aY%3D>.
6. Portal Nacional da NF-e, **Relação de Serviços Web**:
   <https://www.nfe.fazenda.gov.br/portal/webServices.aspx?tipoConteudo=OUC%2FYVNWZfo%3D>.
7. Portal Nacional da NF-e, aviso de que contribuintes da BA devem testar no
   ambiente de homologação da própria SEFAZ autorizadora:
   <https://hom.nfe.fazenda.gov.br/portal/informe.aspx?Informe=WlPWPrd2Yp0%3D&ehCTG=false>.
8. Referências internas já versionadas, usadas apenas como roteiro auxiliar:
   `docs/HOMOLOGACAO_FISCAL_BAHIA.md`,
   `docs/CANCELAMENTO_FISCAL_BAHIA.md`, `docs/FISCAL_DFE.md`,
   `resources/fiscal/schemas/ORIGEM_OFICIAL.md` e
   `resources/fiscal/icp_brasil/ORIGEM.md`.

## 12. Validação deste modelo documental

- [ ] todas as evidências de execução continuam `PENDENTE` antes da sessão;
- [ ] modelos 55 e 65 possuem trilhas separadas;
- [ ] homologação e produção possuem portões separados;
- [ ] autorização, consulta, DANFE, rejeição/reenvio, eventos, contingência,
  reinício e pacote contábil estão cobertos;
- [ ] responsáveis, data/hora, hashes e anexos são obrigatórios;
- [ ] nenhuma URL não oficial foi usada como fonte normativa;
- [ ] nenhum segredo ou dado fiscal real foi incorporado ao Git.
