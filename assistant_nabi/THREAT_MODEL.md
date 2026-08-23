# Nabi — modelo de ameaças da Fase 0

## Escopo

Esta fase cria somente contratos, classificação de capacidades e um catálogo de
consultas. Não há modelo de linguagem conectado, interface de conversa, acesso
direto a banco, execução de comandos, ferramenta mutável ou integração fiscal.

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
| Ação mutável prematura | Registro da Fase 0 aceita apenas `READ` de nível 1 |
| Ausência de trilha | Toda tentativa, inclusive negada ou desconhecida, é enviada à porta de auditoria |
| Indisponibilidade da IA | Núcleo do NabiCode não depende deste pacote para operar |
| Falsa evidência fiscal | Nenhuma ferramenta ou porta Fiscal/SEFAZ nesta fase |

## Regras de evolução

Uma fase futura que introduza rascunhos ou mutações deve usar contratos novos e
não enfraquecer `ReadOnlyToolRegistry`. Antes de qualquer mutação serão exigidos:

1. schema fechado e validação recursiva dos parâmetros;
2. permissão vinculada à sessão atual;
3. prévia determinística;
4. confirmação humana vinculada ao hash exato da prévia e com expiração;
5. chave idempotente;
6. auditoria persistida antes da execução;
7. resultado real retornado pelo backend;
8. testes adversariais e homologação manual no Windows.

Fiscal/SEFAZ permanece fora da autoridade da Nabi. Uma integração futura poderá
apenas solicitar o fluxo oficial e relatar o estado comprovado pelo pipeline.

## Provedor local recomendado para homologação

- runtime preferencial: `llama.cpp/llama-server`, sob MIT;
- API: OpenAI-compatible exclusivamente em loopback;
- modelo-base candidato: Qwen3-4B, sob Apache 2.0;
- nenhum peso de modelo é incorporado ou baixado automaticamente nesta fase;
- origem, licença, hash e quantização do arquivo GGUF deverão ser registrados
  antes de distribuição;
- o adaptador rejeita endpoint remoto, não recebe token e usa temperatura zero;
- trocar o modelo não altera ferramentas, schemas, permissões ou políticas.

Fontes oficiais consultadas em 23/08/2026:

- `https://github.com/ggml-org/llama.cpp` e seu arquivo `LICENSE`;
- `https://qwenlm.github.io/blog/qwen3/`;
- `https://huggingface.co/Qwen/Qwen3-4B`.
