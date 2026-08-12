# Auditoria de estabilização 2.4.99 — Checkpoint 1

## Escopo

Análise estática e dinâmica da base refatorada, sem alteração de código funcional. A suíte completa foi executada antes desta auditoria e permaneceu verde.

## Visão arquitetural

A base possui separação real em controllers, services, repositories, database, managers, helpers, validators e UI, mas mantém `nabicode_legacy.py` como composição principal e ponte de compatibilidade. As telas normais são pré-construídas e empilhadas no mesmo container; o PDV e diversos históricos usam janelas independentes. Services e repositories cobrem boa parte dos domínios, porém as fronteiras ainda não são uniformes.

## Achados classificados

### CRÍTICO — divergência entre os dois pacotes recebidos

O pacote `CORRECAO_FLASH_WINDOWS` não é um superseto da refatoração completa. Ele omite 25 arquivos da base refatorada, incluindo componentes de persistência, serviços, validators e quatro testes, e altera dezenas de arquivos compartilhados. Substituir a refatoração pelo pacote de flash causaria regressão estrutural silenciosa. Decisão: preservar `REFACTOR_COMPLETA` como raiz e auditar/integrar somente o delta de navegação compatível.

### ALTO — caminho de PDV fora da navegação estável

`mostrar_tela("vendas")` não usa a pilha de frames. Ele chama `abrir_pdv_independente()`, que cria um `CTkToplevel` e monta centenas de linhas de UI. O pacote complementar documenta que `state("zoomed")` durante a montagem pode mapear a janela prematuramente no Windows. Este é o principal candidato à causa do flash grande observado e deve ser investigado no Checkpoint 2 sem copiar cegamente a implementação anterior.

### ALTO — trabalho síncrono imediatamente após a troca visual

Depois de `tela.tkraise()`, a navegação chama carregamentos de histórico, clientes, produtos, financeiro, compras e relatórios. Esses caminhos podem executar SQL e reconstrução de widgets na thread Tk. Mesmo com o container estável, isso aumenta latência e pode produzir desenho parcial ou congelamento. A correção deve preservar consistência dos dados e não introduzir manipulação de Tk em threads secundárias.

### ALTO — SQL e transações atravessando camadas

Foi detectado SQL fora de repositories/database em `nabicode_legacy.py`, managers, core e diversos services. Nem toda ocorrência é defeito: vários services coordenam transações atômicas e recebem conexão externa. Mover SQL mecanicamente poderia introduzir commits internos e quebrar rollback global. A propriedade de `commit`, `rollback` e `close` deve ser auditada por fluxo nos Checkpoints 3 e 4.

### MÉDIO — concentração excessiva no legado

`nabicode_legacy.py` possui 9.606 linhas e 105 handlers amplos (`except Exception` ou bare except). As maiores funções restantes incluem painel administrativo (709 linhas), importação XML (527), histórico de devoluções (325), PDV independente (302), cadastro de produto (257) e configurações (233). Não se recomenda nova reescrita geral; somente extrações ligadas a risco concreto.

### MÉDIO — funções muito grandes fora do legado

`database/schema_initializer.py::initialize_database` possui cerca de 807 linhas. Também há funções extensas em migração MySQL, transação do PDV, fiscal e financeiro. O inicializador de schema merece auditoria específica de idempotência e migrações, mas não deve ser dividido durante estabilização sem benefício funcional comprovado.

### MÉDIO — tratamento amplo de exceções

Foram encontrados 244 handlers amplos, 105 no legado. Alguns são limites de UI deliberados, mas podem ocultar falhas de persistência, fechamento de recursos ou renderização. A revisão deve priorizar callbacks de venda, financeiro, migração, backup, importação e navegação; não há justificativa para substituição global.

### MÉDIO — dependência de desenvolvimento incompleta

`requirements.txt` descreve dependências de execução, mas não declara `pytest`. O baseline falhou inicialmente por ausência da ferramenta. Deve-se decidir no pacote final entre um arquivo de dependências de desenvolvimento existente/novo e instruções explícitas, sem transformar dependências de teste em requisito de produção desnecessário.

### BAIXO — referências legítimas a `os.kill`

`core/runtime_profile.py` contém `os.kill(pid, 0)`, porém apenas no ramo não Windows; o Windows usa API nativa e o teste confirma que `os.kill` não é chamado nesse ramo. Há outra referência em `services/update_package_service.py`, fora do lock de runtime, que deverá ser auditada separadamente para comportamento Windows, mas não constitui reintrodução comprovada no `DatabaseUsageLock`.

### BAIXO — artefatos históricos numerosos

A raiz contém muitos relatórios e patches históricos. Eles ajudam rastreabilidade, mas aumentam ruído e risco de empacotar material desnecessário. A limpeza só deverá ocorrer no Checkpoint 7 e apenas com prova de que nenhum arquivo é necessário ao funcionamento ou atualização.

## Dependências e fronteiras

- UI principal chama controllers e services, mas ainda acessa conexão/SQL diretamente em trechos legados.
- Controllers adaptam callbacks e evitam parte do acoplamento com Tk.
- Services contêm regras e, em vários domínios, coordenam transações.
- Repositories concentram persistência, mas a migração está incompleta.
- Database centraliza conexão, schema, manutenção e migração.
- Não foi demonstrado ciclo de importação que impeça startup ou testes; a suíte completa importa e valida os módulos cobertos.

## Recursos, callbacks e bloqueios

- Há callbacks que abrem arquivos, subprocessos, geram documentos, fazem backup e importam dados.
- Há criação de thread para consulta, mas a auditoria do retorno seguro à UI fica para o Checkpoint 6.
- Conexões abertas diretamente no legado devem ser verificadas quanto a `close` em todos os caminhos de exceção.
- `update_idletasks()` aparece em vários fluxos e pode forçar renderização intermediária; cada uso ligado a navegação será analisado no Checkpoint 2.

## Decisões deliberadas

- Não reiniciar a refatoração.
- Não substituir a base completa pelo pacote de flash.
- Não mover SQL mecanicamente.
- Não remover código legado apenas por tamanho.
- Não introduzir delays, splash, overlay ou frame de mascaramento.
- Não declarar o flash resolvido sem validação visual posterior no Windows.

## Próximo passo

Checkpoint 2: reconstruir a sequência exata de navegação e comparar o delta do pacote de flash com a base refatorada, criar regressões compatíveis e implementar apenas a correção de causa raiz que preserve todos os módulos e testes da refatoração completa.

