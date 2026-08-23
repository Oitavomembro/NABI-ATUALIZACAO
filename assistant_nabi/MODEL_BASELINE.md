# Nabi — baseline local de modelo

Data da avaliação: 23/08/2026.

## Máquina de homologação

- RAM: 12 GB;
- CPU: Intel Core i5-3470, 4 núcleos/4 threads;
- GPU: Radeon RX 550, 4 GB reportados;
- espaço livre observado: aproximadamente 103 GB.

## Decisão inicial

- runtime preferencial: `llama.cpp/llama-server` local;
- modelo inicial: Qwen3-1.7B Instruct em GGUF Q4, após verificação de origem,
  licença e hash;
- candidato de maior qualidade: Qwen3-4B em GGUF Q4, somente se tempo de
  resposta e memória forem aceitáveis na homologação;
- contexto inicial deve ser pequeno e medido; anunciar 32K não significa que a
  máquina deva alocar 32K durante o PDV;
- nenhuma atualização ou download ocorre durante venda;
- Nabi permanece opcional e o sistema funciona integralmente sem o servidor.

## Portão antes do download

1. escolher repositório GGUF confiável e conferir licença dos pesos;
2. registrar URL exata, revisão, nome do arquivo, quantização, tamanho e SHA-256;
3. conferir avisos e condições de redistribuição;
4. medir RAM, tempo até primeira resposta e tokens por segundo;
5. executar avaliações fixas do NabiCode, inclusive respostas hostis;
6. manter opção de remover ou substituir o modelo sem alterar o núcleo.

O modelo não será incorporado ao instalador até essa evidência existir.

## Verificação implementada antes da homologação física

O NabiCode já possui um verificador local que exige manifesto com identificador,
arquivo GGUF simples, quantização, origem HTTPS sem credenciais, revisão
imutável, licença declarada, tamanho e SHA-256. O peso somente é aceito dentro
da pasta autorizada e quando tamanho e conteúdo coincidem exatamente.

Esse verificador não escolhe a origem, não baixa o arquivo e não transforma um
peso ainda não testado em modelo homologado. A revisão e o SHA-256 reais serão
registrados somente depois da seleção explícita do artefato oficial.

## Artefato baixado e verificado no ambiente TESTE

- conversão: `ggml-org/Qwen3-1.7B-GGUF`;
- arquivo: `Qwen3-1.7B-Q4_K_M.gguf`;
- quantização: `Q4_K_M`;
- revisão imutável: `daeb8e2d528a760970442092f6bf1e55c3b659eb`;
- tamanho publicado: `1.282.439.264` bytes;
- SHA-256 publicado:
  `d2387ca2dbfee2ffabce7120d3770dadca0b293052bc2f0e138fdc940d9bc7b5`;
- licença declarada pelo repositório: `Apache-2.0`;
- origem: organização `ggml-org`, mantenedora do `llama.cpp`.

O repositório oficial `Qwen/Qwen3-1.7B-GGUF` observado oferece o peso Q8_0. A
conversão Q4_K_M foi selecionada no `ggml-org` para reduzir memória e tamanho,
sem alterar a origem do modelo-base Qwen. O arquivo foi baixado manualmente para
`AppData/Roaming/NabiCode/Teste/ia/models`, fora do Git e da Produção. Tamanho e
SHA-256 locais coincidiram exatamente com o manifesto.

## Runtime e homologação física inicial

- runtime: `llama.cpp` CPU x64 build `b10537`, commit
  `bf0040e15fd5b716262658f4d652c9cee959cf91`;
- arquivo oficial: `llama-b10537-bin-win-cpu-x64.zip`;
- SHA-256 do pacote:
  `48d02dfdc5a715d1f58e06b9c9622bb548eb214b021af027808c9e8c124c4dec`;
- árvore extraída: 52 arquivos, hash agregado
  `8d32024aab57571fd10931d50626b0000d39f5e9040f8cc568c98d5466dd931c`;
- execução: somente `127.0.0.1`, sem interface web, CORS limitado, credenciais
  CORS desativadas e chave efêmera mantida apenas em memória;
- requisição sem chave foi recusada com HTTP 401;
- primeira medição: modelo carregado em 1,827 s e resposta curta em 4,609 s;
- repetição após verificar integralmente modelo e runtime: carga em 2,210 s e
  resposta curta em 6,729 s;
- memória ativa observada no primeiro carregamento: aproximadamente 1,41 GB;
- chamada de ferramenta estruturada `produtos.pesquisar` produzida corretamente;
- pedidos hostis para executar SQL e inventar autorização SEFAZ foram recusados
  sem chamada de ferramenta;
- servidor foi encerrado ao final de cada ensaio e não inicia com o Windows.

Esta é homologação técnica inicial, não liberação comercial. Ainda faltam login
Qt real, consulta com sessão/permissões reais, avaliações ampliadas de qualidade,
teste prolongado, integração visual e decisão sobre redistribuição no instalador.
