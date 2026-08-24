# Checkpoint — recuperação visual e operacional Qt

## Contrato confirmado

O NabiCode Legacy é a referência obrigatória de organização. Melhorias Qt podem
ampliar legibilidade, DPI, desempenho e acessibilidade, mas não podem mudar a
ordem, a identidade, os atalhos ou o caminho operacional dos módulos.

Ordem canônica preservada:

1. Início — F1 — azul `#1f6feb`;
2. Vendas — F2 — verde `#2ea043`;
3. Clientes — F3 — roxo `#8957e5`;
4. Produtos — F4 — âmbar `#bf8700`;
5. Financeiro — verde-petróleo `#0f766e`;
6. Caixa — ocre `#a16207`;
7. Central Fiscal — roxo `#7c3aed`;
8. Relatórios — azul `#0369a1`;
9. Configurações — F5 — vermelho `#da3633`.

## Regressões comprovadas na composição Qt anterior

- o PDV havia se tornado a janela raiz;
- o Início deixou de ser o destino após login;
- F1 passou a abrir um hub modal;
- Vendas desapareceu do menu principal;
- ordem, cores e atalhos foram substituídos por cartões cinza;
- sidebar, indicadores, favoritos, ajuda, suporte e pânico desapareceram;
- o splash canônico não era iniciado pelo `main_qt.py`;
- o login ficou reduzido a uma caixa compacta.

## Arquitetura de recuperação

- novo shell Qt amplo e maximizado, separado do `PDVWindow`;
- Dashboard existente reutilizado como página inicial embutida;
- PDV existente aberto uma única vez por Vendas/F2;
- módulos Qt existentes preservados como diálogos, sem reescrever domínio;
- módulos adicionais ficam na lateral e não deslocam os nove slots canônicos;
- slots indisponíveis permanecem na posição original e ficam desabilitados;
- painel Nabi permanece opcional no shell, sem alteração interna;
- splash canônico existente é reutilizado, sem nova animação;
- login usa a mesma sequência do Legacy com dimensões, foco e leitura ampliados.

## Limites desta trilha

Não alterar backend Fiscal/SEFAZ, licenciamento, IA, banco, serviços centrais,
instalador ou composição pertencente à outra trilha. Não integrar nem fazer push
antes da revisão cruzada e da homologação visual do proprietário.
