# Auditoria comercial e fiscal — NabiCode 2.5.1

Data técnica: 18/08/2026  
Base auditada: `dev/nabicode-2.5.1` após o Checkpoint 42.68.

## Resultado executivo

O núcleo administrativo, Caixa, PDV não fiscal, atualização segura, migração e a base fiscal em homologação possuem cobertura automatizada ampla. O módulo fiscal, porém, ainda não pode ser vendido como emissor fiscal completo de produção. O próprio serviço bloqueia `PRODUCAO` deliberadamente e diversas rotinas legais dependem de homologação, dados oficiais ou prestadores externos ainda não integrados.

Nenhuma dessas restrições deve ser contornada com valores tributários presumidos, endpoints improvisados ou botões que aparentem uma função legal ainda inexistente.

## Implementado e ligado ao fluxo oficial

- configuração do emitente, modelos 55/65, séries e numeração inicial auditada;
- certificado A1 `.pfx/.p12`, validação de senha, CNPJ, validade, cofre DPAPI e alerta de vencimento;
- geração XML, assinatura XMLDSig, validação XSD local e comunicação em fila;
- consulta de status, recibo, reenvio idempotente e recuperação de falhas;
- cancelamento, CC-e e inutilização com retorno da SEFAZ;
- importação de NF-e de compra e reaproveitamento da ficha fiscal do produto;
- devolução integral/parcial vinculada à nota original;
- pré-visualização fiscal sem reservar número;
- armazenamento de XML autorizado, histórico de documentos e eventos;
- exportação ZIP e CSV para a contabilidade;
- retransmissão em lote de NFC-e já identificadas como contingência;
- DANFE oficial da NF-e modelo 55 e DANFE NFC-e térmico de 80 mm para documentos autorizados;
- contingência offline da NFC-e ativada explicitamente no PDV, com assinatura, QR Code, DANFE, fila e prazo controlado;
- catálogo NCM vigente da Receita Federal, com pesquisa offline e atualização gratuita pela fonte oficial;
- referência CEST consolidada do Convênio ICMS 142/18, com conferência obrigatória de descrição e UF;
- preparação estrutural das 27 UFs, com Bahia como perfil atualmente validado;
- controles básicos de ICMS, PIS, COFINS e primeira matriz regular de IBS/CBS.

## Bloqueadores para comercialização fiscal em produção

1. Homologação fiscal real do contribuinte e retirada controlada do bloqueio de produção.
2. Motor tributário completo para situações especiais: ST integral, DIFAL, IPI, benefícios, reduções, monofasia, créditos e demais classificações IBS/CBS aplicáveis.
3. Integração licenciada da tabela IBPT. NCM e referência CEST já usam publicações oficiais gratuitas; a incidência de ST continua submetida à matriz tributária e à legislação da UF.
4. Validação da cadeia ICP-Brasil contra repositório de confiança atualizado. A assinatura e o certificado incorporado são validados, mas isso não substitui a cadeia oficial.
5. Distribuição DF-e e manifestação do destinatário.
6. Envio de XML e documento auxiliar por e-mail com fila, consentimento e configuração segura.
7. Consulta automática de CNPJ e IE por provedor oficial/contratado, com tratamento de indisponibilidade e limites de uso.
8. NFS-e, que exige arquitetura separada por padrão nacional/provedor municipal e não deve ser simulada pelo motor de NF-e.
9. Política automatizada de retenção, cópia externa e restauração dos documentos fiscais pelo prazo legal aplicável.
10. Homologação estadual além da Bahia, incluindo endpoints, QR Code, regras e testes por UF.

## Funções solicitadas que ainda não existem

- atualização IBPT;
- consulta Receita/Sintegra e validação online de IE;
- duplicação controlada de nota para novo rascunho;
- envio fiscal por e-mail;
- distribuição/manifestação DF-e;
- emissão NFS-e;

## Regra de liberação

O NabiCode pode continuar sendo validado em `HOMOLOGACAO`. A identificação como emissor fiscal comercial de produção somente deve ocorrer depois que os bloqueadores aplicáveis ao cliente forem implementados, revisados pela contabilidade responsável e homologados com a SEFAZ/provedor competente. Até lá, o bloqueio de produção é uma proteção obrigatória de dados e do cliente.
