# Backup e restauracao da edicao FICHARIO

O backup FICHARIO e uma copia consistente e validada do banco SQLite. Ele inclui
clientes e numeros de ficha, produtos usados nas vendas, movimentacoes comerciais,
parcelas, recebimentos, configuracoes operacionais e historicos/auditoria mantidos
no banco. Os itens da venda permanecem na descricao imutavel da movimentacao,
conforme o contrato comercial atual.

Nao entram no backup: executavel, arquivos de build, logs, caches, certificados,
credenciais, documentos ou filas fiscais, chave privada do emissor, arquivo
`.nabilic` e estado protegido do licenciamento. Licenca e estado protegido continuam
vinculados a maquina e nao podem ser clonados por restauracao.

Antes de restaurar, a interface exige permissao administrativa, PDV fechado,
arquivo SQLite integro, tabelas obrigatorias e schema exatamente compativel. O
operador deve digitar `RESTAURAR`. O servico cria primeiro uma copia de seguranca
do banco atual; falha durante a copia ou na validacao final aciona recuperacao
automatica dessa copia. Depois de uma restauracao concluida, o programa deve ser
reiniciado.

Dados ficam em `%APPDATA%\NabiCode\Fichario\Producao` (ou `Teste`) e nunca em
`Program Files`.
