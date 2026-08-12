# Relatório de código morto

## Método

Análise AST de imports e definições, busca por debug/temporários e revisão manual dos candidatos. Métodos aninhados, callbacks Tk, reexports, imports de compatibilidade e `from __future__ import annotations` foram preservados.

## Achados

- Dois imports mortos confirmados e removidos em `core/text_interactions.py`.
- Prints encontrados pertencem a utilitários CLI deliberados, não são debug abandonado.
- Nenhum `breakpoint`, instrumentação de navegação temporária ou arquivo `.tmp/.bak/.orig` foi encontrado.
- `NFeProductCandidate as NFeProductCandidate` é reexport de compatibilidade e permanece.
- Nenhuma função sem referência foi removida: callbacks podem ser alcançados por `command`, `bind`, `after`, `getattr` ou integração externa.

## Decisão

Não há evidência suficiente para remover adapters, wrappers ou arquivos históricos funcionais neste checkpoint.
