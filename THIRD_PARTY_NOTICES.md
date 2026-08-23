# Componentes de terceiros

## BrazilFiscalReport

- versão integrada: 1.0.1;
- projeto: https://github.com/Engenere/BrazilFiscalReport;
- licença: GNU Lesser General Public License v3.0 (LGPL-3.0);
- uso no NabiCode: geração do DANFE oficial da NF-e modelo 55 a partir do XML autorizado;
- o componente é usado como biblioteca separada e não teve seu código incorporado ou alterado no NabiCode;
- texto e código-fonte correspondente: https://github.com/Engenere/BrazilFiscalReport/tree/1.0.1.

As demais dependências continuam declaradas em `requirements.txt` e no lock canônico de build.

## llama.cpp

- versão homologada localmente: build `b10537`, commit `bf0040e15fd5b716262658f4d652c9cee959cf91`;
- projeto: https://github.com/ggml-org/llama.cpp;
- licença: MIT;
- uso no NabiCode: runtime local opcional da assistente Nabi;
- o binário permanece fora do Git e ainda não foi incorporado ao instalador;
- uma distribuição futura deverá acompanhar o texto de licença aplicável.

## Qwen3-1.7B GGUF Q4_K_M

- modelo-base: Qwen3-1.7B;
- conversão GGUF homologada inicialmente: `ggml-org/Qwen3-1.7B-GGUF`, revisão `daeb8e2d528a760970442092f6bf1e55c3b659eb`;
- licença declarada no repositório do artefato: Apache-2.0;
- uso no NabiCode: peso local opcional da assistente Nabi;
- o peso permanece fora do Git e ainda não foi incorporado ao instalador;
- redistribuição futura exige preservar licença, avisos, origem e hash do artefato exato.
