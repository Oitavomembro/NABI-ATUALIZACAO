from __future__ import annotations

from datetime import datetime
from tkinter import messagebox, simpledialog
from typing import Any


class FinanceiroCallbackController:
    """Orquestra callbacks financeiros de UI sem conter regras financeiras."""

    def __init__(self, app: Any, service: Any, view_data: Any) -> None:
        self.app = app
        self.service = service
        self.view_data = view_data

    def _autorizar(self, action: str) -> bool:
        return bool(self.app._autorizar("financeiro", action))

    def _usuario(self) -> str:
        return self.app._usuario_financeiro()

    def _ator_mutacao(self, action: str) -> str | None:
        """Revalida sessão e permissão imediatamente antes da escrita."""

        try:
            return self.app.security.require_actor("financeiro", action)
        except PermissionError as exc:
            messagebox.showerror("Acesso negado", str(exc), parent=self.app)
            return None

    def carregar(self) -> None:
        if not hasattr(self.app, "tabela_financeiro"):
            return
        inicio, fim = self.app.fin_inicio.get().strip(), self.app.fin_fim.get().strip()
        try:
            fluxo = self.service.fluxo_caixa(inicio, fim)
            dre = self.service.dre(inicio, fim)
            self.app.fin_lbl_fluxo.configure(text=self.view_data.resumo_fluxo(fluxo))
            self.app.fin_lbl_dre.configure(text=self.view_data.resumo_dre(dre))
        except ValueError as exc:
            messagebox.showerror("Financeiro", str(exc), parent=self.app)
            return
        tipo = None if self.app.fin_tipo.get() == "TODOS" else self.app.fin_tipo.get()
        status = None if self.app.fin_status.get() == "TODOS" else self.app.fin_status.get()
        titulos = self.service.listar_titulos(tipo=tipo, status=status)
        for item in self.app.tabela_financeiro.get_children():
            self.app.tabela_financeiro.delete(item)
        for titulo in titulos:
            self.app.tabela_financeiro.insert(
                "", "end", iid=str(titulo["id"]),
                values=self.view_data.linha_titulo(
                    titulo, self.service.obter_centro_custo(titulo["id"])
                ),
            )

    def titulo_selecionado(self):
        sel = self.app.tabela_financeiro.selection() if hasattr(self.app, "tabela_financeiro") else ()
        if not sel:
            messagebox.showwarning("Financeiro", "Selecione um título.", parent=self.app)
            return None
        return int(sel[0])

    def novo_titulo(self) -> None:
        if not self._autorizar("create"):
            return
        tipo = simpledialog.askstring("Novo título", "Tipo: PAGAR ou RECEBER", parent=self.app)
        if tipo is None: return
        valor = simpledialog.askfloat("Novo título", "Valor:", minvalue=0.01, parent=self.app)
        if valor is None: return
        venc = simpledialog.askstring("Novo título", "Vencimento (AAAA-MM-DD):", parent=self.app)
        if venc is None: return
        desc = simpledialog.askstring("Novo título", "Descrição:", parent=self.app) or ""
        pessoa = simpledialog.askstring("Novo título", "Pessoa/fornecedor/cliente:", parent=self.app) or ""
        actor = self._ator_mutacao("create")
        if actor is None: return
        try:
            self.service.criar_titulo(
                tipo=tipo, valor=valor, data_vencimento=venc, descricao=desc,
                pessoa_nome=pessoa, usuario=actor,
            )
            self.carregar()
        except ValueError as exc:
            messagebox.showerror("Financeiro", str(exc), parent=self.app)

    def baixar_titulo(self) -> None:
        if not self._autorizar("pay"):
            return
        titulo_id = self.titulo_selecionado()
        if titulo_id is None: return
        titulo = self.service.repository.obter_titulo(titulo_id)
        saldo = float(titulo["saldo_aberto"])
        juros = simpledialog.askfloat("Baixa", "Juros mensal (%):", initialvalue=0.0, minvalue=0.0, parent=self.app)
        if juros is None: return
        multa = simpledialog.askfloat("Baixa", "Multa (%):", initialvalue=0.0, minvalue=0.0, parent=self.app)
        if multa is None: return
        calc = self.service.calcular_juros_multa(titulo_id, juros_mensal_percentual=juros, multa_percentual=multa)
        encargos = calc["juros"] + calc["multa"]
        forma = simpledialog.askstring("Baixa", "Forma de pagamento:", parent=self.app) or ""
        actor = self._ator_mutacao("pay")
        if actor is None: return
        try:
            if encargos > 0:
                confirmar = messagebox.askyesno(
                    "Baixa com encargos",
                    f"Saldo: R$ {saldo:.2f}\nJuros: R$ {calc['juros']:.2f}\nMulta: R$ {calc['multa']:.2f}\nTotal: R$ {calc['total']:.2f}\n\nAplicar encargos ao título e realizar a baixa total?",
                    parent=self.app,
                )
                if not confirmar:
                    return
                self.service.baixar_com_encargos(
                    titulo_id, juros_mensal_percentual=juros, multa_percentual=multa,
                    forma_pagamento=forma, usuario=actor,
                )
            else:
                valor = simpledialog.askfloat(
                    "Baixa", f"Saldo R$ {saldo:.2f}.\nValor a baixar no título:",
                    initialvalue=saldo, minvalue=0.01, maxvalue=saldo, parent=self.app,
                )
                if valor is None:
                    return
                self.service.baixar(titulo_id, valor, forma_pagamento=forma, usuario=actor)
            self.carregar()
        except ValueError as exc:
            messagebox.showerror("Financeiro", str(exc), parent=self.app)

    def definir_centro_custo(self) -> None:
        if not self._autorizar("create"):
            return
        titulo_id = self.titulo_selecionado()
        if titulo_id is None: return
        atual = self.service.obter_centro_custo(titulo_id)
        centro = simpledialog.askstring("Centro de custo", "Centro de custo:", initialvalue=atual, parent=self.app)
        if centro is None: return
        actor = self._ator_mutacao("create")
        if actor is None: return
        self.service.definir_centro_custo(titulo_id, centro, usuario=actor)
        self.carregar()

    def abrir_recorrencias(self) -> None:
        if not self._autorizar("create"):
            return
        recorrencias = self.service.listar_recorrencias()
        resumo = "\n".join(
            f"{r['identificador']} | {r['tipo']} | R$ {r['valor']:.2f} | dia {r['dia_vencimento']} | {'ATIVA' if r.get('ativo', True) else 'INATIVA'}"
            for r in recorrencias
        ) or "Nenhuma recorrência cadastrada."
        acao = simpledialog.askstring(
            "Recorrências", resumo + "\n\nAções: NOVA, EDITAR, ATIVAR, DESATIVAR, EXCLUIR ou GERAR", parent=self.app,
        )
        if acao is None: return
        acao = acao.strip().upper()
        try:
            if acao == "NOVA":
                ident = simpledialog.askstring("Recorrência", "Identificador único:", parent=self.app)
                if ident is None: return
                tipo = simpledialog.askstring("Recorrência", "Tipo: PAGAR ou RECEBER", parent=self.app)
                if tipo is None: return
                valor = simpledialog.askfloat("Recorrência", "Valor:", minvalue=0.01, parent=self.app)
                if valor is None: return
                dia = simpledialog.askinteger("Recorrência", "Dia do vencimento:", minvalue=1, maxvalue=31, parent=self.app)
                if dia is None: return
                desc = simpledialog.askstring("Recorrência", "Descrição:", parent=self.app) or ""
                actor = self._ator_mutacao("create")
                if actor is None: return
                self.service.criar_recorrencia(
                    identificador=ident, tipo=tipo, valor=valor, dia_vencimento=dia,
                    descricao=desc, usuario=actor,
                )
            elif acao == "EDITAR":
                ident = simpledialog.askstring("Recorrências", "Identificador:", parent=self.app)
                if ident is None: return
                atual = next((r for r in self.service.listar_recorrencias() if r["identificador"] == ident), None)
                if not atual: raise ValueError("Recorrência não encontrada.")
                tipo = simpledialog.askstring("Recorrência", "Tipo: PAGAR ou RECEBER", initialvalue=atual["tipo"], parent=self.app)
                if tipo is None: return
                valor = simpledialog.askfloat("Recorrência", "Valor:", initialvalue=float(atual["valor"]), minvalue=0.01, parent=self.app)
                if valor is None: return
                dia = simpledialog.askinteger("Recorrência", "Dia do vencimento:", initialvalue=int(atual["dia_vencimento"]), minvalue=1, maxvalue=31, parent=self.app)
                if dia is None: return
                desc = simpledialog.askstring("Recorrência", "Descrição:", initialvalue=atual.get("descricao", ""), parent=self.app)
                if desc is None: return
                pessoa = simpledialog.askstring("Recorrência", "Pessoa:", initialvalue=atual.get("pessoa_nome", ""), parent=self.app)
                if pessoa is None: return
                actor = self._ator_mutacao("create")
                if actor is None: return
                self.service.editar_recorrencia(
                    ident, tipo=tipo, valor=valor, dia_vencimento=dia, descricao=desc,
                    pessoa_nome=pessoa, usuario=actor,
                )
            elif acao in {"ATIVAR", "DESATIVAR", "EXCLUIR"}:
                ident = simpledialog.askstring("Recorrências", "Identificador:", parent=self.app)
                if ident is None: return
                actor = self._ator_mutacao("create")
                if actor is None: return
                if acao == "EXCLUIR":
                    self.service.excluir_recorrencia(ident, usuario=actor)
                else:
                    self.service.ativar_recorrencia(ident, acao == "ATIVAR", usuario=actor)
            elif acao == "GERAR":
                competencia = simpledialog.askstring(
                    "Recorrências", "Competência AAAA-MM:",
                    initialvalue=datetime.now().strftime("%Y-%m"), parent=self.app,
                )
                if competencia is None: return
                ano, mes = map(int, competencia.split("-"))
                actor = self._ator_mutacao("create")
                if actor is None: return
                self.service.gerar_recorrencias(ano, mes, usuario=actor)
                self.carregar()
            else:
                raise ValueError("Ação de recorrência inválida.")
        except (ValueError, TypeError) as exc:
            messagebox.showerror("Recorrência", str(exc), parent=self.app)

    def conciliar_pagamento(self) -> None:
        if not self._autorizar("reconcile"): return
        titulo_id = self.titulo_selecionado()
        if titulo_id is None: return
        pagamentos = self.service.listar_pagamentos(titulo_id)
        if not pagamentos:
            messagebox.showwarning("Conciliação", "O título não possui pagamentos.", parent=self.app); return
        linhas = self.view_data.pagamentos_para_selecao(pagamentos)
        pagamento_id = simpledialog.askinteger("Conciliação", f"Informe o ID do pagamento:\n\n{linhas}", parent=self.app)
        if pagamento_id is None: return
        referencia = simpledialog.askstring("Conciliação", "Referência do extrato/comprovante:", parent=self.app)
        if referencia is None: return
        actor = self._ator_mutacao("reconcile")
        if actor is None: return
        try:
            self.service.conciliar_pagamento(pagamento_id, referencia, usuario=actor)
            messagebox.showinfo("Conciliação", "Pagamento conciliado.", parent=self.app)
        except ValueError as exc:
            messagebox.showerror("Conciliação", str(exc), parent=self.app)

    def cancelar_titulo(self) -> None:
        if not self._autorizar("create"): return
        titulo_id = self.titulo_selecionado()
        if titulo_id is None: return
        if not messagebox.askyesno("Cancelar título", "Cancelar o título selecionado?", parent=self.app): return
        actor = self._ator_mutacao("create")
        if actor is None: return
        try:
            self.service.cancelar(titulo_id, usuario=actor)
            self.carregar()
        except ValueError as exc:
            messagebox.showerror("Financeiro", str(exc), parent=self.app)

    def abrir_conciliacoes(self) -> None:
        if not self._autorizar("reconcile"): return
        registros = self.service.listar_conciliacoes()
        linhas = self.view_data.conciliacoes_para_selecao(registros)
        acao = simpledialog.askstring("Conciliações", linhas + "\n\nDigite CONCILIAR ou DESFAZER:", parent=self.app)
        if acao is None: return
        try:
            acao = acao.strip().upper()
            pagamento_id = simpledialog.askinteger("Conciliações", "ID do pagamento:", parent=self.app)
            if pagamento_id is None: return
            actor = self._ator_mutacao("reconcile")
            if actor is None: return
            if acao == "CONCILIAR":
                referencia = simpledialog.askstring("Conciliações", "Referência:", parent=self.app)
                if referencia is None: return
                self.service.conciliar_pagamento(pagamento_id, referencia, usuario=actor)
            elif acao == "DESFAZER":
                self.service.desfazer_conciliacao(pagamento_id, usuario=actor)
            else:
                raise ValueError("Ação de conciliação inválida.")
        except ValueError as exc:
            messagebox.showerror("Conciliações", str(exc), parent=self.app)

    def abrir_relatorio_centros_custo(self) -> None:
        if not self._autorizar("view"): return
        try:
            dados = self.service.relatorio_centros_custo(self.app.fin_inicio.get().strip(), self.app.fin_fim.get().strip())
            texto = self.view_data.relatorio_centros_custo(dados)
            messagebox.showinfo("Relatório por centro de custo", texto, parent=self.app)
        except ValueError as exc:
            messagebox.showerror("Financeiro", str(exc), parent=self.app)

    def abrir_detalhes(self) -> None:
        if not self._autorizar("view"): return
        try:
            inicio, fim = self.app.fin_inicio.get().strip(), self.app.fin_fim.get().strip()
            fluxo = self.service.fluxo_caixa(inicio, fim)
            dre = self.service.dre(inicio, fim)
            messagebox.showinfo("Detalhes financeiros", self.view_data.detalhes_financeiros(fluxo, dre), parent=self.app)
        except ValueError as exc:
            messagebox.showerror("Financeiro", str(exc), parent=self.app)

    def estornar_pagamento(self) -> None:
        if not self._autorizar("pay"): return
        titulo_id = self.titulo_selecionado()
        if titulo_id is None: return
        pagamentos = self.service.listar_pagamentos(titulo_id)
        if not pagamentos:
            messagebox.showwarning("Estorno", "O título não possui pagamentos.", parent=self.app); return
        linhas = self.view_data.pagamentos_para_selecao(pagamentos)
        pagamento_id = simpledialog.askinteger("Estorno", f"Informe o ID do pagamento a estornar:\n\n{linhas}", parent=self.app)
        if pagamento_id is None: return
        if not messagebox.askyesno("Estorno", "Confirmar estorno desta baixa?", parent=self.app): return
        actor = self._ator_mutacao("pay")
        if actor is None: return
        try:
            self.service.estornar_pagamento(pagamento_id, usuario=actor)
            self.carregar()
        except ValueError as exc:
            messagebox.showerror("Estorno", str(exc), parent=self.app)
