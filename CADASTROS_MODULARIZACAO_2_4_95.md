# CADASTROS — MODULARIZAÇÃO 2.4.95

Base: `NabiCode_v2_4_95_TESTE_REIMPRESSAO_LAYOUT`

## Escopo

Alterações limitadas à camada de Cadastros. Nenhum arquivo de Interface, layout, BackgroundManager, ThemeManager, Financeiro, Documental, PDV ou `nabicode_legacy.py` foi alterado.

## Alterações

### Repositories

- `ProductsRepository` é alias público de `ProdutoRepository`.
- `CustomersRepository` é alias público de `ClienteRepository`.
- Não foram criadas classes paralelas nem SQL duplicado.
- Persistência e transações existentes permanecem centralizadas nos Repositories já consolidados.

### Validators

Criados:
- `CustomerValidator`: nome, número de ficha e limite de crédito.
- `ProductValidator`: nome, tipo/filtro e regras numéricas compartilhadas de produto.
- `AuxiliaryRegistrationValidator`: tipos auxiliares e normalização de nome/sigla.

Validações anteriormente repetidas nos Services foram delegadas aos Validators mantendo mensagens e contratos cobertos pelos testes existentes.

### Services

- `CustomerRegistrationService`: removidos parsers internos duplicados; usa `CustomerValidator`.
- `ProdutoService`: centraliza validações compartilhadas em `ProductValidator` e `AuxiliaryRegistrationValidator`.
- `ProductApplicationService`: passa a reutilizar os mesmos Validators, eliminando validações duplicadas entre Application Service e Service de domínio.
- Removido import morto de `UnitConversionService` em `ProductApplicationService`.

### Controllers

Criados sem integração com widgets/telas nesta sprint:
- `CustomerRegistrationController`;
- `ProductRegistrationController`.

Os Controllers apenas orquestram Services e não contêm SQL, regra de layout ou persistência.

## Commits / rollback

Revisados os fluxos alterados:
- cadastro de cliente continua usando `ClienteRepository.transaction()` e uma única transação para validação de ficha + INSERT;
- cadastro de produto continua reutilizando transação externa quando fornecida e abrindo uma única transação via `ProdutoRepository` quando necessário;
- Controllers e Validators não executam `commit()` ou `rollback()`;
- nenhuma nova transação aninhada foi introduzida.

## Auditoria de código

- código morto introduzido: nenhum;
- import morto encontrado e removido: `UnitConversionService` em `services/product_application_service.py`;
- reexports em `__init__.py` foram preservados deliberadamente como API pública;
- nenhuma alteração visual foi implementada.

## Testes

Bateria focada final:

`68 passed`

Suíte completa executada antes do ajuste final de import:

`798 passed, 12 subtests passed`

Após a remoção do único import morto, a bateria focada foi repetida:

`68 passed`

## python main.py

Executado antes da entrega.

A aplicação não abriu neste ambiente por bloqueios externos ao código de Cadastros:

- `_tkinter.TclError: couldn't connect to display ":0"`
- `ModuleNotFoundError: No module named 'customtkinter'`

A validação gráfica permanece bloqueada pelo ambiente. A regressão automatizada de Cadastros está aprovada.
