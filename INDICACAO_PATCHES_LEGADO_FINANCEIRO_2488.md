# Indicação de patches financeiros no legado — NabiCode 2.4.88

O arquivo `nabicode_legacy.py` **não foi alterado nesta sprint**. Os pontos abaixo devem ser aplicados exclusivamente pela conversa responsável pela redução do legado.

## 1. `carregar_financeiro` — aproximadamente linhas 8153–8170

### Regra remanescente
O callback ainda normaliza manualmente os filtros `TODOS` e consulta o centro de custo título por título.

### Trecho atual
```python
tipo = None if self.fin_tipo.get() == "TODOS" else self.fin_tipo.get()
status = None if self.fin_status.get() == "TODOS" else self.fin_status.get()
titulos = FINANCEIRO_SERVICE.listar_titulos(tipo=tipo, status=status)
...
for t in titulos:
    self.tabela_financeiro.insert("", "end", iid=str(t["id"]), values=FinanceiroViewData.linha_titulo(t, FINANCEIRO_SERVICE.obter_centro_custo(t["id"])))
```

### Destino recomendado
- normalização: `FinanceiroService.normalizar_filtros_titulos`;
- centro de custo em lote: Service/Repository, evitando consulta de configuração por título.

## 2. `baixar_titulo_financeiro` — aproximadamente linhas 8194–8227

### Regras remanescentes
- acesso direto a `FINANCEIRO_SERVICE.repository`;
- conversão de saldo para `float`;
- soma manual de juros e multa;
- formatação monetária manual do resumo da baixa.

### Trecho atual
```python
titulo = FINANCEIRO_SERVICE.repository.obter_titulo(titulo_id)
saldo = float(titulo["saldo_aberto"])
...
encargos = calc["juros"] + calc["multa"]
...
f"Saldo: R$ {saldo:.2f}\nJuros: R$ {calc['juros']:.2f}\nMulta: R$ {calc['multa']:.2f}\nTotal: R$ {calc['total']:.2f}..."
```

### Destino recomendado
- título/saldo: `FinanceiroService.obter_titulo` e `FinanceiroService.saldo_titulo`;
- cálculo: `FinanceiroCalculator` via Service;
- apresentação: `FinanceiroFormatter.resumo_baixa`.

## 3. `abrir_recorrencias_financeiro` — aproximadamente linhas 8240–8300

### Regras remanescentes
- formatação monetária manual da lista;
- conversão de `Decimal` para `float` ao preencher valor de edição;
- parsing manual da competência `AAAA-MM` com `map(int, competencia.split("-"))`.

### Trecho atual
```python
resumo = "\n".join(
    f"{r['identificador']} | {r['tipo']} | R$ {r['valor']:.2f} | dia {r['dia_vencimento']} | {'ATIVA' if r.get('ativo', True) else 'INATIVA'}"
    for r in recorrencias
) or "Nenhuma recorrência cadastrada."
...
valor = simpledialog.askfloat(..., initialvalue=float(atual["valor"]), ...)
...
ano, mes = map(int, competencia.split("-"))
```

### Destino recomendado
- lista: `FinanceiroFormatter.recorrencias_para_selecao`;
- competência: `FinanceiroService.gerar_recorrencias_competencia`;
- manter `Decimal` até o limite obrigatório da API de UI.

Nenhuma dessas alterações foi aplicada nesta sprint para respeitar a proibição de modificar `nabicode_legacy.py`.
