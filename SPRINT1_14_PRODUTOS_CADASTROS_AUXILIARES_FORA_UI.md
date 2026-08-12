# Sprint 1.14 — Produtos: cadastros auxiliares fora da UI

## Alterações

- ProductAuxiliaryOption e ProductAuxiliaryCatalog adicionados.
- Listagem e criação de categorias, marcas, fornecedores e unidades centralizadas no ProductApplicationService.
- Abertura do cadastro de produto usa um catálogo único tipado.
- ProductPricingController usa Decimal do início ao fim na formatação.
- EntryControl Protocol documenta o contrato mínimo dos widgets.
- Validação antecipada de controles incompatíveis.
- Proteção contra callback recursivo validada com controle falso que dispara evento durante insert.

## Testes

- 44 testes focados aprovados.
- 552 testes completos aprovados.
