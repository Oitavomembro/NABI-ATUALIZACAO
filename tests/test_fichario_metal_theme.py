from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_shared_commercial_theme_has_metal_focus_and_destructive_states():
    source = (ROOT / "ui_qt/commercial/customer_dialog.py").read_text(encoding="utf-8")

    assert "qlineargradient" in source
    assert "#58d5ff" in source
    assert "QPushButton#destructive" in source
    assert 'self.delete_button.setObjectName("destructive")' in source


def test_fichario_activation_uses_the_same_theme():
    source = (ROOT / "fichario/license_dialog.py").read_text(encoding="utf-8")

    assert "from ui_qt.commercial.customer_dialog import STYLE" in source
    assert "self.setStyleSheet(STYLE)" in source
    assert 'self.activate_button.setObjectName("primary")' in source


def test_commercial_exceptions_reuse_the_shared_theme():
    for relative in (
        "ui_qt/commercial/budget_dialog.py",
        "ui_qt/commercial/suspended_sale_dialog.py",
        "ui_qt/commercial/product_search_dialog.py",
        "ui_qt/commercial/post_sale_dialog.py",
    ):
        source = (ROOT / relative).read_text(encoding="utf-8")
        assert "from .customer_dialog import STYLE" in source
        assert "setStyleSheet" in source
