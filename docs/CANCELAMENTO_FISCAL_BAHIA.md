# Regras versionadas de cancelamento fiscal — Bahia

Consulta normativa realizada em 21/08/2026. Esta versão do NabiCode aplica
somente o cancelamento normal em homologação:

- NFC-e, modelo 65: até 30 minutos contados da autorização, sem circulação da
  mercadoria. Fonte: SEFAZ-BA, *NFC-e — Perguntas e Respostas*, item 31:
  https://www.sefaz.ba.gov.br/docs/inspetoria-eletronica/icms/nfce_perguntas_respostas_.pdf
- NF-e, modelo 55: até 24 horas contadas da autorização, sem circulação da
  mercadoria. Fontes: RICMS-BA/2012, art. 92, e Ato COTEPE ICMS 13/2010,
  conforme documentação oficial do CONSEF/SEFAZ-BA:
  https://mbusca.sefaz.ba.gov.br/consef/2018%20ac%C3%B3rd%C3%A3os%20juntas/A-0160-03.18.pdf
- Evento usado: `110111`, justificativa entre 15 e 255 caracteres, conforme o
  MOC 7.0 do Portal Nacional da NF-e:
  https://www.nfe.fazenda.gov.br/portal/exibirArquivo.aspx?conteudo=LrBx7WT9PuA%3D

Cancelamento por substituição (`110112`), cancelamento extemporâneo, SAT e MFe
não são automatizados por esta regra. Quando a combinação UF/modelo/ambiente
não estiver documentada no catálogo interno, o NabiCode bloqueia a operação em
vez de presumir um prazo.

Produção permanece bloqueada em todas as camadas.
