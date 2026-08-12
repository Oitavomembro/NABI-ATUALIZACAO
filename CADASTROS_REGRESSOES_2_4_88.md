# Cadastros — auditoria e regressões — NabiCode 2.4.88

## Escopo

Auditados exclusivamente Clientes, Produtos, Categorias e Fornecedores.
Não foram alterados Financeiro, Documental, Interface, PDV ou `nabicode_legacy.py`.

## Alterações realizadas

### Clientes
- `CustomerMaintenanceRepository.delete_fictitious()` deixou de repetir a seleção de clientes fictícios em múltiplos `DELETE`.
- Os IDs dos clientes fictícios são obtidos uma vez dentro da mesma transação e reutilizados nas exclusões relacionadas.
- Movimentações são obtidas uma vez e suas parcelas são removidas em lote.
- A exclusão continua atômica dentro de `DatabaseManager.session(write=True)`.

### Produtos
- `ProdutoService.salvar()` deixou de reentrar recursivamente em si mesmo apenas para abrir uma transação.
- A coordenação transacional foi separada em `_salvar_em_transacao()`.
- Uma transação fornecida pelo chamador continua sendo reutilizada sem abertura de transação aninhada.
- Validações, detecção de conflitos, persistência e histórico continuam na mesma transação.

### Categorias e Fornecedores
- Repositories e Services foram auditados.
- Não foram encontradas alterações seguras adicionais necessárias nesta sprint sem mudar comportamento ou contratos atuais.
- SQL permanece concentrado em `CategoriaRepository`, `FornecedorRepository` e `CadastroAuxiliarRepository`.

## Auditoria de código alterado

- SQL direto em Services alterados: nenhum.
- `commit()` manual: nenhum.
- `rollback()` manual: nenhum.
- Imports mortos nos arquivos alterados: nenhum encontrado por análise AST.
- Código morto introduzido: nenhum identificado.
- `nabicode_legacy.py`: não alterado.

## Testes adicionados/alterados

- Cobertura de exclusão em lote de múltiplos clientes fictícios e vínculos.
- Cobertura de reutilização de transação externa pelo `ProdutoService` sem abrir transação aninhada.

### Resultado focado

`23 passed`

### Regressão completa

`718 passed, 12 subtests passed`

Nenhuma regressão automatizada foi encontrada.

## python main.py

Executado após as alterações e após os testes finais.

Resultado: a aplicação não abriu neste ambiente por bloqueios externos ao escopo de cadastros:

- `_tkinter.TclError: couldn't connect to display ":0"`
- `ModuleNotFoundError: No module named 'customtkinter'`

A validação de abertura da interface permanece tecnicamente bloqueada neste ambiente. Os testes automatizados concluíram sem falhas.

## Estado

Código e regressão automatizada validados. A validação de abertura real do sistema não pode ser declarada concluída devido ao bloqueio ambiental descrito acima.
