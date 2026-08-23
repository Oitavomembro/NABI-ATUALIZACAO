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
