# CADASTROS — REGRESSÕES E ATUALIZAÇÃO DE SALDO — NabiCode v2.4.90

## Base oficial

`NabiCode_v2_4_90_BASE_OFICIAL_INTEGRADA`

## Escopo executado

Exclusivamente Cadastros de clientes, sem alterações em Financeiro, Documental, PDV, Interface ou `nabicode_legacy.py`.

Objetivos desta correção:

- garantir atualização do saldo do cliente após recebimento;
- revisar pesquisa e ordenação;
- revisar atualização do histórico;
- revisar refresh da tabela de clientes;
- eliminar qualquer possibilidade de cache de saldo na camada de Cadastros;
- nunca recalcular saldo financeiro em Cadastros.

## Arquivos modificados

- `repositories/cliente_repository.py`
- `repositories/client_history_repository.py`
- `tests/test_cadastro_saldo_reconciliado_regression.py`
- `CADASTROS_REGRESSOES_2_4_90.md`

## Alterações

### 1. Atualização do saldo na tabela

`ClienteRepository.list_page()` continua consumindo exclusivamente `clientes.saldo_devedor`.

A contagem e a listagem agora são executadas em um snapshot de leitura curto e novo a cada chamada. Não existe estado de saldo mantido no Repository.

Consequências:

- após o commit do Financeiro, uma nova chamada de `list_page()` lê o saldo persistido atualizado;
- chamadas sucessivas não reutilizam saldo anterior;
- contagem e linhas pertencem à mesma visão do banco;
- nenhuma soma de movimentações ou parcelas é realizada pelo cadastro.

### 2. Histórico do cliente

`ClientHistoryRepository.load()` passou a carregar cliente, movimentações, estatísticas, parcelas e eventos dentro de um único snapshot de leitura.

O saldo exibido pelo histórico continua vindo exclusivamente de:

`clientes.saldo_devedor`

Não existe cálculo ou reconciliação financeira no histórico.

### 3. Pesquisa e ordenação

A regra atual foi preservada e testada:

- ficha exata permanece prioritária na pesquisa numérica;
- pesquisa textual prioriza nomes iniciados pelo termo;
- nomes contendo o termo em posição posterior permanecem depois dos prefixos;
- campos numéricos vazios não ganham prioridade em pesquisa textual.

Nenhuma regra financeira foi introduzida na busca.

### 4. Cache de saldo

Não foi encontrado cache persistente de saldo nos Repositories auditados.

A correção reforça esse contrato utilizando uma conexão/snapshot novo por leitura. O saldo não é armazenado em atributo, singleton, dicionário de cache ou variável de módulo.

### 5. Import morto

Removido o import não utilizado:

- `Decimal` em `repositories/client_history_repository.py`.

## Testes novos

`tests/test_cadastro_saldo_reconciliado_regression.py`

Coberturas adicionadas:

1. tabela reflete saldo reconciliado após pagamento;
2. tabela não recalcula saldo usando compra/parcela;
3. histórico reflete saldo e evento após pagamento;
4. histórico não deriva saldo das movimentações;
5. pesquisa textual preserva ordenação por relevância;
6. pesquisa numérica prioriza ficha exata;
7. refresh reconsulta o banco em chamadas sucessivas, sem cache.

O teste de saldo utiliza deliberadamente dados divergentes entre `clientes.saldo_devedor` e valores de compra/parcela para garantir que Cadastros consuma apenas o saldo já reconciliado e persistido pelo Financeiro.

## Validação automatizada

Testes focados:

```text
21 passed
```

Suíte completa:

```text
747 passed, 12 subtests passed
0 failures
```

Compilação dos arquivos alterados:

```text
python -m compileall -q repositories/cliente_repository.py repositories/client_history_repository.py tests/test_cadastro_saldo_reconciliado_regression.py
APROVADO
```

Auditoria de imports por AST após a remoção do import morto:

```text
repositories/cliente_repository.py: nenhum import morto
repositories/client_history_repository.py: nenhum import morto
tests/test_cadastro_saldo_reconciliado_regression.py: nenhum import morto
```

## Execução de `python main.py`

Executado antes da entrega.

Resultado: bloqueado pelo ambiente gráfico, não por regressão automatizada.

```text
_tkinter.TclError: couldn't connect to display ":0"
ModuleNotFoundError: No module named 'customtkinter'
```

A abertura gráfica não pôde ser validada neste ambiente.

## Restrições respeitadas

Não foram alterados:

- Financeiro;
- Documental;
- PDV;
- Interface;
- `nabicode_legacy.py`.

Não foi criado cálculo financeiro em Cadastros.
Não foi criado cache de saldo.
Não foi gerado EXE.
