# Relatório de duplicações finais

## Análise

A busca AST por nomes repetidos encontrou principalmente funções locais com nomes genéricos (`salvar`, `fechar`, `carregar`, `confirmar`) em janelas diferentes e métodos homônimos em classes diferentes. Isso não representa duplicação semântica removível.

Helpers locais de PDF, fiscal, financeiro e UI preservam contexto próprio. Consolidá-los exigiria acoplamento artificial ou reabertura de fluxos aprovados.

## Resultado

- Duplicações consolidadas: 0.
- Duplicações comprovadamente seguras pendentes: 0.
- Refatorações deliberadamente recusadas: callbacks visuais, transações, adapters e helpers contextuais.
