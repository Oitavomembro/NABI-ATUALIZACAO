# Relatório de estabilização final 2.4.99

## Base e baseline

Base refatorada 2.4.98 preservada; pacote antigo de flash usado somente como fonte de diff. Baseline inicial: 877 testes e 11 subtestes. Baseline final esperado: 886 testes e 11 subtestes.

## Problemas e causas

- CRÍTICO: pacote de flash incompleto; descartada substituição integral.
- ALTO: PDV maximizava `Toplevel` durante construção, permitindo mapeamento branco no Windows.
- ALTO: históricos eram construídos visíveis; telas eram levantadas antes da preparação.
- ALTO: lacunas de regressão após efeitos intermediários de estoque/financeiro.
- MÉDIO: operações potencialmente bloqueantes na thread Tk, mantidas sem mudança especulativa.
- BAIXO: dois imports mortos.

## Alterações

- Revelação estrutural de Toplevel somente após montagem, sem overlay, alpha, sleep ou atraso artificial.
- Preparação de telas persistentes antes de `tkraise`.
- Três regressões bancárias novas e seis regressões de flash.
- Remoção de dois imports mortos.
- Versão final atualizada para 2.4.99.

## Integridade e fluxos

Venda, estoque, financeiro, recebimento, compras, NF-e, cadastros, migração, restore e perfis Produção/Teste foram auditados. Conexão externa não recebe commit/rollback/close interno. Impressão oficial 80 mm, PDF sob demanda, reimpressão, teclado, estoque negativo e saldo reconciliado foram preservados.

## Flash

Validação manual aprovada pelo usuário no Windows via `python main.py`: abertura normal, navegação fluida e ausência do flash branco. A implementação está congelada contra mudanças sem regressão comprovada.

## Arquivos principais modificados

`nabicode_legacy.py`, `ui/window_reveal.py`, `ui/__init__.py`, testes de flash/PDV/transação/propriedade de conexão, `core/text_interactions.py`, `VERSAO.txt` e relatórios dos checkpoints.

## Riscos restantes

- Backup, restore, importação e geração documental podem bloquear UI em bases grandes; exigem medição real antes de threading.
- `schema_initializer.py` e funções administrativas/fiscais permanecem extensos.
- Compatibilidade interna de PDF 58 mm não pode reaparecer como opção física de interface.

## Itens deliberadamente não alterados

Regras de negócio, schema, navegação aprovada, tema/layout, SQL transacional e dependências de runtime.

## Instalação Windows

```cmd
py -3.14 -m venv .venv
.venv\Scripts\activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python main.py
```

Para testes:

```cmd
python -m pip install pytest
python -m compileall -q .
python -m pytest -q
```

## Validação manual recomendada

Abrir Dashboard, Clientes, Produtos, Financeiro, PDV e históricos; finalizar uma venda de teste em banco de Teste; confirmar impressão 80 mm e PDF somente por ação explícita.
