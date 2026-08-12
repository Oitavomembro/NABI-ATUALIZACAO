from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LEGACY = (ROOT / "nabicode_legacy.py").read_text(encoding="utf-8")


def test_panic_does_not_use_down_arrow_navigation():
    assert 'self.bind("<Down>", self.ativar_modo_panico)' not in LEGACY
    assert 'self.bind("<Control-Shift-P>", self.ativar_modo_panico)' in LEGACY
    assert '[Ctrl+Shift+P] ➔ Pânico' in LEGACY


def test_clients_content_expands_to_available_viewport():
    bloco = LEGACY.split('def tela_clientes(self, parent)', 1)[1].split('def carregar_clientes', 1)[0]
    assert 'LayoutManager.configure_vertical_shell(frame, expandable_row=1)' in bloco
    assert 'conteudo_cli.pack(fill="both", expand=True' in bloco
    assert 'conteudo_cli.grid(' not in bloco
    assert 'LayoutManager.apply_client_treeview' in bloco

def test_product_suggestion_only_uses_mouse_coordinates_from_table():
    assert 'getattr(event, "widget", None) is tabela' in LEGACY
