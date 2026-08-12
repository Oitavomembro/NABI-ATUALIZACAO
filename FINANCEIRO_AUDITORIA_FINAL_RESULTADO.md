# Auditoria final — módulo Financeiro

## Escopo auditado

- Decimal;
- consultas SQL;
- transações;
- rollback;
- commits;
- filtros;
- código morto;
- imports mortos;
- duplicações;
- regressões.

## Alterações

- `FinanceiroRepository` passou a concentrar todas as consultas e atualizações do recebimento de crediário legado.
- `FinanceiroService` passou a preparar os alvos e executar o pagamento em uma única sessão transacional.
- `FinanceiroCalculator` passou a validar limites e aplicar pagamentos exclusivamente com `Decimal` quantizado.
- `FinanceiroFormatter.moeda` passou a normalizar valores pelo calculador antes da apresentação.
- O callback `receber_pagamento_cliente_selecionado` perdeu SQL, controle transacional e cálculos financeiros.
- Nenhuma funcionalidade nova foi criada.
- PDV, pesquisa, impressão e estrutura da interface não foram alterados.

## Transações

- O fluxo usa `DatabaseManager.session(write=True)`.
- Commit ocorre apenas no encerramento bem-sucedido do contexto.
- Exceções provocam rollback automático.
- Nenhum `commit()` ou `rollback()` manual foi adicionado.

## Auditoria estática

- Compilação de `services`, `repositories`, testes e legado: aprovada.
- Métodos novos sem duplicação de nomes.
- Imports adicionados são utilizados.
- Nenhum cache ou artefato temporário incluído no pacote.

## Testes

- Conjunto focado: 16 testes aprovados.
- Suíte completa monolítica avançou além de 90% sem nova falha, mas excedeu o limite operacional do ambiente antes do resumo final.
- Execução por arquivos também foi interrompida pelo limite global do ambiente; os arquivos processados não apresentaram falhas nem timeouts individuais.
- Regressão textual de pagamento direcionado preservada.
- Testes novos cobrem pagamento parcial e rollback integral por valor excedente.

## `python main.py`

Executado antes da entrega.

Bloqueios técnicos do ambiente:

```text
_tkinter.TclError: couldn't connect to display ":0"
ModuleNotFoundError: No module named 'customtkinter'
```

A aplicação não abriu neste ambiente. A sprint não é declarada concluída.
