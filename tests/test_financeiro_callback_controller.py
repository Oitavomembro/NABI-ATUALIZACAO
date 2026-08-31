from unittest.mock import patch

from controllers.financeiro_callback_controller import FinanceiroCallbackController


class Value:
    def __init__(self, value): self.value = value
    def get(self): return self.value


class Label:
    def __init__(self): self.text = None
    def configure(self, **kwargs): self.text = kwargs.get("text")


class Table:
    def __init__(self): self.rows = {"old": ()}; self.selected = ("7",)
    def get_children(self): return tuple(self.rows)
    def delete(self, item): self.rows.pop(item, None)
    def insert(self, _parent, _where, iid, values): self.rows[str(iid)] = values
    def selection(self): return self.selected


class FakeRepository:
    def obter_titulo(self, titulo_id): return {"id": titulo_id, "saldo_aberto": 100.0}


class FakeService:
    def __init__(self):
        self.repository = FakeRepository()
        self.calls = []
    def fluxo_caixa(self, inicio, fim): self.calls.append(("fluxo", inicio, fim)); return {"x": 1}
    def dre(self, inicio, fim): self.calls.append(("dre", inicio, fim)); return {"y": 2}
    def listar_titulos(self, **kwargs): self.calls.append(("listar", kwargs)); return [{"id": 7}]
    def obter_centro_custo(self, titulo_id): return "ADM"
    def criar_titulo(self, **kwargs): self.calls.append(("criar", kwargs))


class FakeViewData:
    @staticmethod
    def resumo_fluxo(_): return "Fluxo OK"
    @staticmethod
    def resumo_dre(_): return "DRE OK"
    @staticmethod
    def linha_titulo(titulo, centro): return (titulo["id"], centro)


class FakeApp:
    def __init__(self):
        self.tabela_financeiro = Table()
        self.fin_inicio = Value("2026-08-01")
        self.fin_fim = Value("2026-08-31")
        self.fin_tipo = Value("TODOS")
        self.fin_status = Value("ABERTO")
        self.fin_lbl_fluxo = Label()
        self.fin_lbl_dre = Label()
        self.authorized = True
        self.actor = "tester"
        self.security = self
    def _autorizar(self, module, action): return self.authorized and module == "financeiro"
    def _usuario_financeiro(self): return "tester"
    def require_actor(self, module, action):
        if not self.authorized or module != "financeiro":
            raise PermissionError("Sessão ou permissão revogada.")
        return self.actor


def test_carregar_orquestra_service_sem_regra_financeira_local():
    app, service = FakeApp(), FakeService()
    controller = FinanceiroCallbackController(app, service, FakeViewData)
    controller.carregar()
    assert app.fin_lbl_fluxo.text == "Fluxo OK"
    assert app.fin_lbl_dre.text == "DRE OK"
    assert app.tabela_financeiro.rows == {"7": (7, "ADM")}
    assert ("listar", {"tipo": None, "status": "ABERTO"}) in service.calls


def test_titulo_selecionado_preserva_id_inteiro():
    app, service = FakeApp(), FakeService()
    controller = FinanceiroCallbackController(app, service, FakeViewData)
    assert controller.titulo_selecionado() == 7


def test_novo_titulo_delega_ao_service_e_recarrega():
    app, service = FakeApp(), FakeService()
    controller = FinanceiroCallbackController(app, service, FakeViewData)
    respostas = ["RECEBER", "2026-08-20", "Venda", "Cliente"]
    with patch("controllers.financeiro_callback_controller.simpledialog.askstring", side_effect=respostas), \
         patch("controllers.financeiro_callback_controller.simpledialog.askfloat", return_value=20.0), \
         patch.object(controller, "carregar") as carregar:
        controller.novo_titulo()
    criar = next(call for call in service.calls if call[0] == "criar")
    assert criar[1]["valor"] == 20.0
    assert criar[1]["usuario"] == "tester"
    carregar.assert_called_once_with()


def test_callback_financeiro_respeita_autorizacao():
    app, service = FakeApp(), FakeService()
    app.authorized = False
    controller = FinanceiroCallbackController(app, service, FakeViewData)
    with patch("controllers.financeiro_callback_controller.simpledialog.askstring") as ask:
        controller.novo_titulo()
    ask.assert_not_called()
    assert not service.calls


def test_novo_titulo_revalida_sessao_depois_dos_dialogos_e_nao_grava():
    app, service = FakeApp(), FakeService()
    controller = FinanceiroCallbackController(app, service, FakeViewData)
    respostas = iter(["RECEBER", "2026-08-20", "Venda", "Cliente"])

    def answer(*_args, **_kwargs):
        value = next(respostas)
        if value == "Cliente":
            app.authorized = False
        return value

    with patch("controllers.financeiro_callback_controller.simpledialog.askstring", side_effect=answer), \
         patch("controllers.financeiro_callback_controller.simpledialog.askfloat", return_value=20.0), \
         patch("controllers.financeiro_callback_controller.messagebox.showerror") as error:
        controller.novo_titulo()
    assert not any(call[0] == "criar" for call in service.calls)
    error.assert_called_once()


def test_novo_titulo_usa_usuario_corrente_apos_troca_com_janela_aberta():
    app, service = FakeApp(), FakeService()
    controller = FinanceiroCallbackController(app, service, FakeViewData)
    respostas = iter(["RECEBER", "2026-08-20", "Venda", "Cliente"])

    def answer(*_args, **_kwargs):
        value = next(respostas)
        if value == "Cliente":
            app.actor = "novo-operador"
        return value

    with patch("controllers.financeiro_callback_controller.simpledialog.askstring", side_effect=answer), \
         patch("controllers.financeiro_callback_controller.simpledialog.askfloat", return_value=20.0), \
         patch.object(controller, "carregar"):
        controller.novo_titulo()
    criar = next(call for call in service.calls if call[0] == "criar")
    assert criar[1]["usuario"] == "novo-operador"
