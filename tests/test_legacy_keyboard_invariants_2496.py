from pathlib import Path

LEGACY=Path('nabicode_legacy.py').read_text(encoding='utf-8')
CONTROLLER=Path('controllers/pdv_enter_controller.py').read_text(encoding='utf-8')


def test_panic_shortcut_preserved():
    assert 'self.bind("<Control-Shift-P>", self.ativar_modo_panico)' in LEGACY


def test_enter_and_kp_enter_remain_owned_by_controller():
    assert 'PDVEnterController(' in LEGACY
    assert 'widget.bind("<Return>", callback)' in CONTROLLER
    assert 'widget.bind("<KP_Enter>", callback)' in CONTROLLER
    assert 'win.bind("<Return>", self._enter_contexto_pdv' not in LEGACY


def test_arrow_navigation_preserved():
    assert 'install_global_arrow_navigation(self)' in LEGACY
    assert 'self.entry_item_venda.bind("<Down>", self.navegar_sugestoes_produto)' in LEGACY
    assert 'self.entry_item_venda.bind("<Up>", self.navegar_sugestoes_produto)' in LEGACY
