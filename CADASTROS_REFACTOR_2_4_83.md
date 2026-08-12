# Refatoração de cadastros — base 2.4.83

## Escopo alterado
- Cadastro de clientes: regras extraídas da janela para `CustomerRegistrationService`.
- Persistência de clientes: criação e verificação de ficha centralizadas em `ClienteRepository`.
- Produtos, categorias, marcas e fornecedores: preservados; suíte focada executada para bloquear regressões.

## Regras extraídas
- nome obrigatório e normalização de espaços;
- geração do código automático de cliente;
- validação e unicidade do número da ficha;
- conversão e validação do limite de crédito;
- atualização de `proxima_ficha`;
- criação do histórico de cadastro;
- persistência do cliente.

## Arquivos modificados
- `nabicode_legacy.py`
- `repositories/cliente_repository.py`
- `services/__init__.py`
- `services/customer_registration_service.py`
- `tests/test_customer_registration_service.py`

## Testes
- 64 testes focados aprovados.
- Suíte completa iniciada, mas excedeu o limite operacional de 120 segundos antes do resumo final. Nenhuma falha apareceu no trecho executado.
