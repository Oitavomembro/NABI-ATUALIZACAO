# Cadastros — Modularização e Robustez — NabiCode 2.4.96

Base obrigatória auditada: `NabiCode_v2_4_96_TESTE_INTEGRADO_HOTFIX_CLIENTES`.

## Escopo

Auditados exclusivamente Clientes, Produtos, Categorias e Fornecedores nas camadas Repository, Service, Validator e Controller. Não foram alterados Financeiro, Documental, PDV, Interface ou `nabicode_legacy.py`.

## Alterações realizadas

### `repositories/customer_maintenance_repository.py`

- removida consulta `SELECT COUNT(*)` redundante antes da seleção dos clientes fictícios;
- a quantidade removida passa a ser derivada da própria lista de IDs já necessária para a exclusão;
- mantida a transação única existente para exclusão de parcelas, movimentações, histórico e clientes fictícios;
- nenhuma regra financeira foi criada ou recalculada.

### `services/produto_service.py`

Removidos três wrappers privados sem uso em todo o projeto:

- `_normalizar_nome_cadastro`;
- `_normalizar_tipo`;
- `_normalizar_tipo_filtro`.

As validações continuam centralizadas em `ProductValidator`, sem mudança de comportamento.

### `tests/test_cadastros_2496_robustez.py`

Cobertura adicionada para:

- pesquisa por nome;
- ficha;
- CPF;
- telefone;
- relevância;
- ordenação;
- favoritos;
- refresh após atualização financeira já commitada;
- consumo exclusivo do saldo persistido em `clientes.saldo_devedor`;
- rollback cadastral após falha posterior ao INSERT;
- dados migrados com campos opcionais nulos;
- exclusão de clientes fictícios após remoção da consulta duplicada.

## Auditoria das camadas

### Clientes

- `ClienteRepository`: pesquisa, paginação, favoritos e leitura do saldo permanecem centralizados no Repository.
- saldo não é calculado em Cadastros; `list_page()` apenas consome `clientes.saldo_devedor` persistido pelo Financeiro.
- ordenação atual da busca foi preservada.
- `CustomerRegistrationService`: transação de criação continua delegada ao Repository/DatabaseManager.
- `CustomerMaintenanceRepository`: consulta redundante removida.

### Produtos

- `ProdutoRepository`: persistência e histórico permanecem dentro da mesma transação quando coordenados por `ProdutoService`.
- `ProdutoService`: wrappers mortos removidos; validações continuam delegadas a `ProductValidator`, `PricingService` e `UnitConversionService`.
- não foi criado Repository paralelo; `ProductsRepository` continua alias da implementação consolidada `ProdutoRepository`.

### Categorias

- `CategoriaRepository` permanece como Repository único para categorias.
- criação/listagem não apresentaram SQL duplicado seguro para remoção nesta sprint.
- validação de nome permanece centralizada em `ProductValidator`.

### Fornecedores

- `FornecedorRepository` permanece Repository exclusivo de fornecedores.
- `CadastroAuxiliarRepository` delega fornecedores ao `FornecedorRepository`, sem duplicar SQL.
- validações de cadastros auxiliares permanecem em `AuxiliaryRegistrationValidator`.

### Controllers

- `CustomerRegistrationController` e `ProductRegistrationController` foram auditados.
- ambos apenas orquestram/delegam e não contêm SQL, commit ou rollback.
- nenhuma alteração foi necessária.

## SQL e transações

Auditoria confirmou:

- nenhum SQL em Services, Validators ou Controllers do escopo;
- nenhum `commit()` ou `rollback()` manual nessas camadas;
- transações permanecem centralizadas em Repository/`DatabaseManager.session(write=True)`;
- rollback de criação de cliente foi testado com falha simulada após INSERT e não deixou registro parcial.

## Código morto e imports mortos

- removidos os três métodos privados mortos de `ProdutoService`;
- análise AST dos arquivos de Clientes, Produtos, Categorias e Fornecedores não encontrou candidatos a imports mortos;
- não foram removidos reexports públicos usados como contratos de compatibilidade.

## Testes

Testes focados finais:

`109 passed, 3 subtests passed`

Suíte completa:

`835 passed, 11 subtests passed, 0 falhas`

## Execução de `python main.py`

Executada antes da entrega.

A abertura gráfica foi bloqueada pelo ambiente de execução:

- `_tkinter.TclError: couldn't connect to display ":0"`
- `ModuleNotFoundError: No module named 'customtkinter'`

O bloqueio é ambiental. A abertura gráfica não é declarada validada nesta sprint.

## Regressões

Nenhuma regressão automatizada detectada.

Preservados:

- ordenação da busca de clientes;
- favoritos;
- paginação;
- atualização após pagamento por nova leitura do saldo persistido;
- histórico;
- dados migrados;
- saldo vindo exclusivamente do Financeiro;
- comportamento de Produtos, Categorias e Fornecedores.
