# Distribuição de DF-e

Implementação baseada no serviço nacional `NFeDistribuicaoDFe`, leiaute
`distDFeInt` 1.01 e no Pacote de Liberação Distribuição de DF-e v1.04,
publicado pelo Portal Nacional da NF-e em 03/07/2026.

Fontes oficiais consultadas em 19/08/2026:

- https://www.nfe.fazenda.gov.br/portal/listaConteudo.aspx?tipoConteudo=BMPFMBoln3w=
- https://www.nfe.fazenda.gov.br/portal/WebServices.aspx?tipoConteudo=OUC/YVNWZfo=

O NabiCode consome o NSU de forma incremental, valida Base64/GZip/XML, limita
tamanhos e só avança o último NSU após uma resposta aceita. A consulta exige o
A1 do próprio interessado, cadeia ICP-Brasil e CRL válidas. Nenhum certificado
ou documento real é usado nos testes automatizados.

O prazo para manifestação conclusiva passou a 90 dias a partir de 01/06/2026,
conforme aviso oficial do Portal Nacional e Ajuste SINIEF 14/26. A interface não
deve sugerir prazo maior.
