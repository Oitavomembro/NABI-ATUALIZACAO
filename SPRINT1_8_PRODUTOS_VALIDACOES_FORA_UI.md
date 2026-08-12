# Sprint 1.8 — Produtos: validações fora da UI

## Alterações

- Centralizada a validação do nome do produto em `ProductApplicationService.validar_nome_formulario`.
- Centralizada a validação dos campos numéricos usados na navegação do formulário em `validar_numero_formulario`.
- Adicionada validação integral de `ProductSaveCommand` antes de acessar repositórios.
- O serviço agora rejeita nome vazio, preço de venda negativo, custo/percentuais inválidos, fator de conversão inválido, estoque mínimo negativo e estoque negativo sem autorização.
- Callbacks Tkinter passaram a apenas exibir as mensagens produzidas pela camada de aplicação.
- Adicionados testes unitários para validações de campo e consistência do comando.

## Validação

- Testes focados: 24 aprovados.
- Suíte completa: 529 testes e 4 subtestes aprovados.
- Compilação sintática completa aprovada.
