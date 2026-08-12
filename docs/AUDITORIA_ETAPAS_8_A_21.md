# Auditoria técnica — Etapas 8 a 21

Data: 2026-08-02
Base auditada: NabiCode_v2_4_32_ETAPA21_FINANCEIRO_AUDITADO.zip

## Validações executadas

- `python -m compileall -q .`: concluído sem erro de sintaxe.
- `python -m unittest discover -s tests -p 'test_*.py'`: 200 testes, resultado `OK`.
- A suíte emitiu `ResourceWarning` para conexões SQLite não fechadas durante testes estruturais.
- Não foi executado teste manual da interface no Windows, leitor físico, impressão, instalador ou banco real de produção.

## Resultado por etapa

### Etapa 8 — Favoritos: NÃO CONCLUÍDA

Implementado: adicionar/remover, ordem, Alt+1 a Alt+9 e atualização imediata.

Pendências:
- Persistência usa a chave global `interface` do `CORE_CONFIG`; não é separada por usuário autenticado.
- A lista de módulos favoritados é limitada a `dashboard`, `vendas`, `clientes`, `produtos` e `configs`, não cobrindo módulos posteriores como Financeiro e ferramentas administrativas.

### Etapa 9 — Painel de atividades: NÃO CONCLUÍDA

Implementado: vendas/movimentações, clientes, produtos, XML, contas vencidas, estoque baixo, backups, logs, período, módulo e links.

Pendências:
- O serviço aceita filtro por usuário, mas a interface não possui controle de filtro por usuário.
- Não existe agendamento de atualização automática do painel; ele atualiza ao abrir ou por botão.
- O serviço agrega registros sem aplicar permissões do usuário; a abertura de alguns links chama métodos diretamente.

### Etapa 10 — Scroll global: NÃO CONCLUÍDA

Implementado: controlador percentual, roda, Shift+roda, Home/End, PageUp/PageDown e alguns frames bidirecionais.

Pendências:
- `BidirectionalScrollableFrame` aparece apenas em algumas telas; não foi aplicado a todas as telas de conteúdo.
- Não há prova automatizada de que nenhum botão fique fora da tela em todos os formulários e resoluções menores.

### Etapa 11 — Layout universal: NÃO CONCLUÍDA

Implementado: política de dimensões e aplicação nos cadastros de Produto e Cliente.

Pendências:
- A política universal não foi aplicada de forma comprovada a Fornecedores, XML, Financeiro e Compras.
- Não existe componente único de cabeçalho/rodapé/ações usado por todos os formulários exigidos.

### Etapa 12 — Notificações: NÃO CONCLUÍDA

Implementado: toast, duração configurável por configuração, histórico em memória e modais críticos preservados.

Pendências:
- Não foi encontrada notificação específica de “Estoque atualizado”.
- O histórico é somente em memória e desaparece ao reiniciar; o requisito não define persistência, mas isso limita o histórico funcional.

### Etapa 13 — XML inteligente completo: PARCIAL

Implementado: conferência, bloqueio de pendências, similaridade, vínculo/criação/atualização, quantidade, fator, unidade, custo, margem/preço, lote, colagem de Excel, progresso, transação e snapshots.

Pendências de comprovação:
- Não há teste de integração completo garantindo simultaneamente estoque, financeiro, histórico e reimportação após desfazer em um banco equivalente ao real.
- A validação da interface é majoritariamente estrutural; o fluxo completo sequencial não foi testado em GUI.

### Etapa 14 — Estoque inteligente: NÃO CONCLUÍDA

Implementado no serviço: inventário em lote, snapshot, diagnóstico e reversão auditada.

Pendências:
- `inventario_lote`, `diagnosticar_divergencias` e `reverter_movimentacao` não são chamados pela interface principal.
- Usuário não possui tela para contagem física, diferença, ajuste em lote, diagnóstico ou reversão genérica.

### Etapa 15 — Produtos: PARCIAL

Implementado: pesquisa sem caixa/acentuação, EAN, similares, duplicação e histórico de preço/custo.

Pendências de comprovação:
- O layout universal do produto não foi validado manualmente em todas as resoluções.
- Não há teste de interface real para Ctrl+S, Esc e Enter em ambiente gráfico.

### Etapa 16 — Banco de dados: PARCIAL

Implementado: backup validado, restauração com backup de segurança, integridade, reindexação, compactação, diagnóstico e executor de migrações.

Pendências:
- Não há catálogo real de migrações versionadas do produto; existe a infraestrutura `Migration`, mas não uma sequência de migrações de produção auditável.
- Testes não simulam falhas de sistema/arquivo durante substituição do banco no Windows.

### Etapa 17 — Padrão de fábrica: PARCIAL

Implementado: modos, prévia, backup obrigatório, senha administrativa, confirmação e transação.

Pendências:
- A identificação de “dados de teste” depende de texto contendo `TESTE`, podendo não abranger todos os dados de demonstração.
- Não existe teste manual de recuperação completa usando o backup gerado.

### Etapa 18 — Ferramentas do desenvolvedor: PARCIAL

Implementado: scripts, spec, versão, painel técnico, diagnóstico, testes, limpeza, versões e instalador.

Pendências:
- “Verificar atualizações” não consulta uma origem oficial; apenas informa que nenhuma origem está configurada.
- Builds e instalador não foram executados/validados nesta auditoria em Windows.

### Etapa 19 — Segurança: NÃO CONCLUÍDA

Implementado: autenticação, perfis padrão, autorização, inatividade, histórico de login, auditoria e senha de gerente.

Pendências:
- Não existe interface de gerenciamento de usuários, senhas, ativação e perfis; métodos existem apenas no serviço.
- Não existe interface para criar/editar perfis e permissões por módulo/ação.
- Favoritos e preferências de interface não são persistidos por usuário.
- A cobertura de autorização em métodos diretos e janelas legadas não está centralmente garantida.

### Etapa 20 — PDV profissional: PARCIALMENTE COMPROVADA

Implementado no código: modos, busca/EAN, cliente rápido, atalhos, venda suspensa, orçamento, pré-venda, pagamento misto, troco, cancelamento transacional, F11, Del, Esc e Enter contextual.

Pendências de comprovação:
- Não foi executado teste manual com leitor físico de código de barras.
- Não foi executado teste gráfico completo de operação somente por teclado.
- Preservação ao minimizar/fechar depende do fluxo da janela e não possui teste GUI real.

### Etapa 21 — Financeiro: NÃO CONCLUÍDA

Implementado: fluxo de caixa, DRE, recorrências, centros de custo, baixas, encargos, conciliação, estorno e telas correspondentes.

Pendências:
- Integração automatizada comprovada existe para Compras; não há testes equivalentes completos para XML, cobranças e todos os fluxos de vendas.
- Relatórios não possuem exportação/impressão; essa capacidade também aparece na Etapa 22, mas “Relatórios” é requisito explícito da Etapa 21.
- Testes da interface são estruturais e não executam o fluxo gráfico real.

## Problemas transversais

1. A suíte passa, mas emite `ResourceWarning` por conexões SQLite não fechadas.
2. Muitos testes de interface analisam AST/texto e não exercitam widgets reais.
3. Nenhuma etapa de interface pode ser considerada validada em Windows somente com os testes atuais.
4. Etapas previamente marcadas como concluídas possuem serviços sem integração visual completa.

## Ordem de correção recomendada

1. Etapa 19: gestão real de usuários/perfis/permissões e preferências por usuário.
2. Etapa 8: favoritos por usuário e catálogo completo de módulos.
3. Etapa 14: integrar inventário/diagnóstico/reversão à interface.
4. Etapas 10 e 11: aplicar scroll e layout universal em todas as telas exigidas.
5. Etapa 9: filtro por usuário, atualização automática e autorização dos links.
6. Etapa 12: toast de estoque e decisão explícita sobre persistência do histórico.
7. Etapa 21: fechar integrações XML/cobranças/vendas e testes de integração.
8. Eliminar vazamentos de conexões e criar testes GUI/Windows para Etapas 13, 15, 17, 18 e 20.
