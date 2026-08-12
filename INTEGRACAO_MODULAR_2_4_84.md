# Integração modular 2.4.84

Base: NabiCode 2.4.83.

Pacotes integrados:
- Interface e Cadastros: tema centralizado, geometria responsiva e serviço de cadastro de clientes.
- Documental: cálculo seguro da altura de cupons térmicos.
- Financeiro: apresentação financeira extraída para FinanceiroViewData e APIs públicas de listagem.

Conflitos resolvidos manualmente:
- nabicode_legacy.py: preservados CustomerRegistrationService e FinanceiroViewData.
- services/__init__.py: exportados ambos os serviços.

Não alterado:
- pesquisa de produtos do PDV;
- finalização de vendas;
- fluxo de reimpressão nativo estabilizado;
- schema do banco de dados.
