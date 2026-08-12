# Checkpoint 5 — auditoria de fluxos críticos

## Escopo validado

- Login, startup e splash.
- Dashboard e histórico.
- Produtos, pesquisa global, sugestões e cadastros.
- Return, KP_Enter, setas e bindings estáveis.
- PDV, venda, finalização, pagamentos e cancelamento.
- Estoque, inclusive política existente de estoque negativo.
- Clientes, recebimentos, saldo reconciliado e histórico migrado.
- Financeiro, parcelas, múltiplas compras e persistência decimal.
- Compras e integração financeira.
- Impressão, reimpressão, recibos, cupom e PDF.
- Navegação e regressão do flash já validada no Windows.

## Regras congeladas preservadas

- Cupom físico oficial permanece em 80 mm.
- `Cupom 58 mm` não pertence aos formatos válidos da interface; valores persistidos antigos são normalizados para 80 mm.
- O perfil interno de 58 mm permanece apenas para compatibilidade documental histórica explícita.
- Imprimir cupom não gera PDF automaticamente.
- PDF só é gerado por ação explícita.
- Reimpressão preserva prévia e seleção de ação.
- Return e KP_Enter permanecem equivalentes.
- Sugestões preservam setas, Enter e Escape.
- Política de estoque negativo permanece configurável por produto e sem mudança de regra.
- Saldo financeiro e recibos usam valores reconciliados, sem recálculo na UI/documental.
- Bancos usados por testes permanecem isolados.

## Resultado focado

Foram executados 70 arquivos de teste selecionados por domínio crítico.

Resultado: `360 passed, 3 subtests passed in 31.44s`.

## Achados

- CRÍTICO/ALTO: nenhuma regressão reproduzida.
- MÉDIO: a compatibilidade interna de modelos PDF 58 mm exige cuidado para não reaparecer como opção física na interface.
- BAIXO: fluxos históricos continuam concentrados no legado, porém cobertos e estáveis.

## Alterações

Nenhum código funcional foi alterado no Checkpoint 5. Navegação, flash, tema e layout aprovados foram preservados integralmente.
