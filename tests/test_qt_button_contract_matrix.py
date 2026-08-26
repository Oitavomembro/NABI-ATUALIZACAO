import csv
import ast
from pathlib import Path

from build_tools.audit_qt_buttons import EXEMPTIONS, inventory, write_csv


def test_todo_botao_qt_tem_acao_ou_excecao_explicita():
    records = inventory()
    assert records
    missing = [
        f"{item.file}:{item.line} {item.scope} {item.target} {item.label}"
        for item in records if item.status == "SEM_ACAO"
    ]
    assert not missing, "Botões sem ação ou justificativa:\n" + "\n".join(missing)


def test_excecoes_sao_reais_e_nao_ficam_obsoletas():
    records = inventory()
    actual = {(item.file, item.scope, item.target) for item in records if item.exemption}
    assert actual == set(EXEMPTIONS)


def test_matriz_nao_inventa_evidencia_operacional(tmp_path):
    output = write_csv(tmp_path / "matrix.csv")
    with output.open(encoding="utf-8-sig", newline="") as stream:
        rows = tuple(csv.DictReader(stream, delimiter=";"))
    assert rows
    criteria = (
        "abriu", "executou", "bloqueou_corretamente", "preservou_dados", "retornou_foco",
    )
    assert all(row[field] == "NAO_COMPROVADO" for row in rows for field in criteria)


def test_f6_e_f9_sao_exclusivos_do_pdv_qt():
    root = Path(__file__).parents[1]
    offenders = []
    for path in root.joinpath("ui_qt").rglob("*.py"):
        if path.as_posix().endswith("ui_qt/commercial/pdv_window.py"):
            continue
        with __import__("tokenize").open(path) as stream:
            tree = ast.parse(stream.read(), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and node.value in {"F6", "F9"}:
                offenders.append(f"{path.relative_to(root)}:{node.lineno}={node.value}")
    assert not offenders, "F6/F9 devem permanecer exclusivos do PDV Qt:\n" + "\n".join(offenders)
