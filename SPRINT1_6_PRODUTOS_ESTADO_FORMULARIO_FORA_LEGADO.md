# Sprint 1.6 — Produtos: estado do formulário fora do legado

## Escopo

Reduzir a responsabilidade do `nabicode_legacy.py` no preenchimento e na leitura do formulário de Produtos, sem introduzir dependência de Tkinter na camada de aplicação.

## Alterações

- Adicionado `ProductFormState` ao serviço de aplicação existente.
- Adicionado `criar_estado_formulario(...)` para converter registros de produto em valores próprios para exibição.
- Adicionado `criar_dados_formulario(...)` para resolver seleções textuais em IDs e produzir `ProductFormData`.
- Centralizada a formatação decimal usada no preenchimento do formulário.
- Removidos do legado os laços de resolução reversa de categoria, marca, fornecedor e unidades.
- Removida do callback de salvamento a resolução direta dos IDs selecionados.
- Mantida a UI responsável apenas por criar widgets, capturar valores e apresentar mensagens.

## Compatibilidade

- Nenhuma alteração de schema.
- Nenhuma alteração no formato de persistência.
- Fluxos de criação, edição, duplicidade, precificação e estoque permanecem compatíveis.
