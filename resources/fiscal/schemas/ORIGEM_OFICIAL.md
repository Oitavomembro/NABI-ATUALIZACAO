# Schemas fiscais oficiais

Arquivos obtidos diretamente do Portal Nacional da NF-e em 18/08/2026.

- NF-e/NFC-e: Pacote `010e v1.02`, publicado em 10/07/2026.
  - URL: `https://www.nfe.fazenda.gov.br/portal/exibirArquivo.aspx?conteudo=akib2DRpJN4%3D`
  - SHA-256 do ZIP original: `D44AE5AA6A0D1CABF6235D2D2D47B75BE5DD87BC6B90A7EC3DCEC99C3D41BDA1`
- Eventos e serviços com CNPJ alfanumérico: Pacote `010d v1.03`, publicado em 10/07/2026.
  - URL: `https://www.nfe.fazenda.gov.br/portal/exibirArquivo.aspx?conteudo=%2BpBOYTXBtbk%3D`
  - SHA-256 do ZIP original: `45CEEFE4DFBBFEC93958283B650A2F1E1734784F4770D070B9907754DE081D9B`

Não editar os XSD manualmente. Uma atualização deve substituir o pacote completo,
registrar sua origem e atualizar os testes de conformidade antes do uso.

`nabicode_inutNFe_v4.00.xsd` é apenas um ponto de entrada local: inclui o
`leiauteInutNFe_v4.00.xsd` oficial e declara o elemento raiz com o tipo oficial
`TInutNFe`. Nenhum tipo ou regra publicado pela Fazenda foi alterado.
