# Auditoria final de cadastros — NabiCode 2.4.85

## Estado da sprint

**BLOQUEADA / NÃO CONCLUÍDA.**

O código e a regressão automatizada foram aprovados, mas `python main.py` não abriu no ambiente disponível. Conforme a diretriz obrigatória, a sprint não é declarada concluída.

## Escopo auditado

- Clientes
- Produtos
- Categorias
- Fornecedores
- Repositories, Services, Controllers e Validators relacionados

Não foram alterados:

- PDV
- Financeiro
- Impressão

## Alterações

### Clientes

- Persistência administrativa isolada em `CustomerMaintenanceRepository`.
- Exclusão de clientes fictícios deixou de executar consultas e exclusões por cliente.
- Remoção de parcelas, movimentações e histórico passou a usar comandos em lote dentro da mesma transação.
- Recriação de clientes de demonstração deixou de consultar o banco uma vez por registro.
- Códigos e fichas existentes são carregados uma única vez; inserções usam `executemany`.
- Duplicidades internas no próprio lote são descartadas antes da gravação.
- Exportação permanece centralizada no Repository.

### Fornecedores e categorias auxiliares

- Fornecedores permanecem isolados em `FornecedorRepository`.
- `CadastroAuxiliarRepository` delega fornecedores e mantém somente marcas/unidades genéricas.
- SQL dinâmico continua restrito à configuração interna fixa.

### Produtos

- Persistência permanece centralizada em `ProdutoRepository`.
- Compatibilidade com a coluna legada `descricao` foi preservada e validada pela regressão existente.
- Nenhuma regra de PDV, estoque transacional, financeiro ou impressão foi modificada.

## Código morto e imports mortos

Foi executada inspeção AST nos arquivos alterados. Resultado: nenhum import morto encontrado.

Não foram encontrados blocos inalcançáveis novos nos arquivos alterados. Fluxos duplicados de exclusão e consulta por item foram removidos.

## Testes criados ou ampliados

`tests/test_cadastro_repository_extraction.py` cobre:

- idempotência da recriação de clientes de demonstração;
- exportação de clientes;
- duplicidade de código dentro do lote;
- duplicidade de ficha dentro do lote;
- exclusão em cascata somente de clientes fictícios;
- preservação de clientes e vínculos reais;
- retorno zero quando não há registros fictícios;
- delegação de fornecedores ao Repository específico.

## Regressão

- Testes focados finais: 7 aprovados.
- Suíte completa: 666 aprovados.
- Falhas: 0.

Os rastros de exceções presentes no log são cenários negativos intencionais dos testes e terminaram com `OK`.

## Execução de `python main.py`

Executado antes da entrega.

Bloqueios técnicos:

```text
_tkinter.TclError: couldn't connect to display ":0"
ModuleNotFoundError: No module named 'customtkinter'
```

O sistema não abriu. A falha ocorreu na inicialização gráfica, antes da validação visual da aplicação.

## Patch do `nabicode_legacy.py`

Não aplicável nesta sprint. O arquivo não foi alterado e não está incluído no pacote.

## Conteúdo da entrega

Somente arquivos modificados, testes e relatório. Não contém projeto inteiro, `nabicode_legacy.py`, `__pycache__`, `.pyc`, `.pytest_cache`, build, dist, `.venv`, cache, `.exit` ou logs temporários.
