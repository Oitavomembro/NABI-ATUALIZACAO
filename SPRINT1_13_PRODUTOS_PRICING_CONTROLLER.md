# Sprint 1.13 — Controlador de formação de preço

## Alterações

- Criado `ProductPricingController` e `ProductPricingControls`.
- Removido `_calculando_preco` do `nabicode_legacy.py`.
- Removidas funções locais de leitura, escrita e sincronização de preço e margem.
- Eventos da UI agora delegam ao controlador independente de Tkinter.
- Cálculo manual continua exibindo erro na UI; eventos automáticos ignoram entrada temporariamente inválida.
- API pública de Produtos atualizada em `services.__all__`.
- Status consolidado da Sprint 1 atualizado até a Sprint 1.13.

## Limites

Cadastros auxiliares não foram alterados nesta sprint para preservar o recorte funcional.
