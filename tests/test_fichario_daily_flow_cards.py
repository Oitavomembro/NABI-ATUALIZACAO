from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SHELL = (ROOT / "fichario/shell.py").read_text(encoding="utf-8")


def test_fichario_exposes_clickable_received_and_financed_cards():
    assert '"received_today", "RECEBIDO HOJE"' in SHELL
    assert '"credit_today", "FIADO GERADO HOJE"' in SHELL
    assert "self.open_daily_flow(current_kind)" in SHELL
    assert "VALORES RECEBIDOS HOJE" in SHELL
    assert 'dialog.resize(900, 560)' in SHELL


def test_cards_use_official_brazilian_money_formatter():
    assert "MoneyCodec.format_br(flow.received_total)" in SHELL
    assert "MoneyCodec.format_br(flow.financed_total)" in SHELL
