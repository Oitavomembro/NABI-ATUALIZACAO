# Nabi — modelo de ameaças operacional

## Escopo

A Nabi possui conversa local, consultas, rascunhos e duas operações comerciais
confirmadas: recebimento de pedido e entrada local de NF-e com vínculo exato.
Não há acesso direto a banco, terminal, URL, SEFAZ ou ferramenta mutável genérica.
Toda gravação passa por serviço oficial, permissão atual, prévia imutável,
confirmação humana reforçada e chave idempotente.

## Fronteiras de confiança

- A mensagem do operador é entrada não confiável.
- Dados de produtos, clientes, documentos e integrações também são conteúdo não
  confiável; nunca se tornam instruções.
- O provedor de linguagem futuro será não confiável e substituível.
- Somente ferramentas registradas pelo NabiCode podem ser chamadas.
- Permissões são decididas pelo serviço de segurança do NabiCode, não pelo
  modelo, pelo texto da conversa ou pela interface.
- Serviços de aplicação e backend continuam sendo a fonte de verdade.

## Ameaças prioritárias e controles

| Ameaça | Controle obrigatório |
| --- | --- |
| Ferramenta inventada pelo modelo | Catálogo fechado e falha fechada |
| Acesso sem permissão | Verificação por usuário, módulo e ação a cada chamada |
| Prompt injection em dados consultados | Dados nunca habilitam ferramentas ou alteram permissões |
| SQL, terminal, URL ou código emitido pelo modelo | Não existem ferramentas genéricas para essas operações |
| Vazamento de erro ou segredo | Resultado externo usa mensagem segura e não inclui exceção interna |
| Alteração dos parâmetros após autorização | Requisições e resultados imutáveis |
| Ação mutável prematura | Registro aceita apenas leitura/rascunho; execução existe fora do catálogo e exige confirmação vinculada |
| Ausência de trilha | Toda tentativa, inclusive negada ou desconhecida, é enviada à porta de auditoria |
| Indisponibilidade da IA | Núcleo do NabiCode não depende deste pacote para operar |
| Falsa evidência fiscal | `cStat` é apenas dado local; a Nabi não autentica XML nem consulta SEFAZ |
| XML de terceiro ou rejeitado | Automação exige destinatário documentado e evidência local literal `cStat=100`; demais casos vão para conferência humana |
| Produto ambíguo ou inventado | Entrada automática aceita somente um ID real ligado inequivocamente por EAN/código exato |
| Conversão de unidade presumida | Fator positivo deve ser informado para cada item e aparece na prévia |
| Repetição após resposta desconhecida | Diário idempotente é confirmado na mesma transação de nota, estoque e financeiro |

## Regras de evolução

Novas mutações devem usar contratos próprios e não enfraquecer
`ReadOnlyToolRegistry` nem `DraftToolRegistry`. Para toda mutação são exigidos:

1. schema fechado e validação recursiva dos parâmetros;
2. permissão vinculada à sessão atual;
3. prévia determinística;
4. confirmação humana vinculada ao hash exato da prévia e com expiração;
5. chave idempotente;
6. auditoria persistida antes da execução;
7. resultado real retornado pelo backend;
8. testes adversariais e homologação manual no Windows.

Fiscal/SEFAZ permanece fora da autoridade da Nabi. A entrada assistida lê um XML
local escolhido pelo operador e chama o importador transacional já existente;
não transmite, consulta, autoriza, cancela nem interpreta resposta da SEFAZ.

## Provedor local recomendado para homologação

- runtime preferencial: `llama.cpp/llama-server`, sob MIT;
- API: OpenAI-compatible exclusivamente em loopback;
- modelo-base inicial: Qwen3-1.7B Instruct em GGUF Q4; Qwen3-4B permanece
  somente candidato posterior, condicionado à homologação de memória e velocidade;
- nenhum peso de modelo é incorporado ou baixado automaticamente nesta fase;
- origem, licença, hash e quantização do arquivo GGUF deverão ser registrados
  antes de distribuição;
- o adaptador rejeita endpoint remoto, não recebe token e usa temperatura zero;
- trocar o modelo não altera ferramentas, schemas, permissões ou políticas.

Fontes oficiais consultadas em 23/08/2026:

- `https://github.com/ggml-org/llama.cpp` e seu arquivo `LICENSE`;
- `https://qwenlm.github.io/blog/qwen3/`;
- `https://huggingface.co/Qwen/Qwen3-4B`.
