# Componentes de terceiros

## BrazilFiscalReport

- versão integrada: 1.0.1;
- projeto: https://github.com/Engenere/BrazilFiscalReport;
- licença: GNU Lesser General Public License v3.0 (LGPL-3.0);
- uso no NabiCode: geração do DANFE oficial da NF-e modelo 55 a partir do XML autorizado;
- o componente é usado como biblioteca separada e não teve seu código incorporado ou alterado no NabiCode;
- texto e código-fonte correspondente: https://github.com/Engenere/BrazilFiscalReport/tree/1.0.1.

As demais dependências continuam declaradas em `requirements.txt` e no lock canônico de build.

## cryptography

- versão validada nesta implementação: 46.0.7;
- projeto: https://github.com/pyca/cryptography;
- licença declarada pelo pacote: `Apache-2.0 OR BSD-3-Clause`;
- uso no NabiCode: verificação Ed25519 das licenças e leitura da chave privada
  somente na ferramenta externa de emissão;
- nenhuma chave privada é distribuída com o aplicativo.
