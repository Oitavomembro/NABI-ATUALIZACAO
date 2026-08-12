# Auditoria de persistência — Checkpoint 40

## Dados operacionais

O runtime existente resolve dados mutáveis fora de Program Files. A validação física anterior comprovou preservação e recuperação de clientes, vendas, recebimentos, movimentos, configurações e banco de PRODUCAO após desinstalação/reinstalação. O `.iss` não contém exclusão de AppData, e este checkpoint não alterou banco, schema, migrations ou runtime profile.

Devem permanecer persistentes:

- banco e dados operacionais;
- configurações do cliente e rede;
- licença;
- backups, logs e PDFs conforme os caminhos já definidos;
- estado necessário à atualização/migração.

## Histórico de notificações

`core/notifications.py` define “histórico em memória” e armazena registros em `deque(maxlen=...)`. Não existe repositório, arquivo, SQLite ou caminho AppData associado. Uma nova instância de `NotificationCenter` começa vazia mesmo sem desinstalar.

Conclusão: o histórico vazio após reinstalação é coerente com o contrato atual de sessão e não evidencia remoção pelo instalador. Persisti-lo criaria nova funcionalidade e política de retenção; por isso não foi alterado. Foi acrescentado teste específico que comprova o isolamento entre sessões.

## Carrinho versus cadastro mestre

O novo editor do carrinho copia a linha e altera apenas `qtd`, `preco_original`, `desconto_percentual`, `preco` e `subtotal`. Não chama repositório de produto nem modifica nome, código/EAN, custo, categoria, marca, fornecedor ou estoque cadastral. A movimentação de estoque continua ocorrendo somente pelo fluxo já existente de venda/cancelamento.

## Risco residual

A decisão de tornar notificações persistentes, se desejada futuramente, precisa definir escopo por usuário/loja, retenção, limpeza, privacidade e migração. Isso ficou explicitamente fora do Checkpoint 40.
