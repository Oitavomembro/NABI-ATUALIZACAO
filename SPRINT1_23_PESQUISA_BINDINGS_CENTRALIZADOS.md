# Sprint 1.23 — Bindings de pesquisa centralizados

## Objetivo
Eliminar bindings duplicados e inconsistentes nos campos de pesquisa, garantindo o mesmo comportamento para foco, cores, Enter normal e Enter do teclado numérico.

## Alterações
- Adicionado `SearchEntryBehavior.attach(...)`.
- Configuração visual centralizada: texto branco e placeholder cinza.
- Seleção automática do conteúdo anterior ao receber foco.
- Consumo obrigatório de `<Return>` e `<KP_Enter>`.
- Migração das pesquisas de Produtos, Clientes, PDV, Relatórios, Central de Ajuda e paleta global.
- Remoção dos bindings manuais redundantes de Enter e foco.
- Testes independentes de Tkinter para os eventos centralizados.

## Resultado
Ações globais não recebem Enter originado em campos de pesquisa e o comportamento é consistente em todos os fluxos migrados.
