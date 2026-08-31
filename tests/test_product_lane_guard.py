from pathlib import Path

import pytest

from build_tools.product_lane_guard import tree_digest, validate_product_lane


def test_product_lane_accepts_the_approved_source_tree(tmp_path: Path):
    source = tmp_path / "commercial"
    source.mkdir()
    (source / "pdv.py").write_text("EDITION = 'FICHARIO'\n", encoding="utf-8")
    expected = tree_digest(tmp_path, "commercial")

    validate_product_lane(
        tmp_path,
        product="FICHARIO",
        expected_digests={"commercial": expected},
    )


@pytest.mark.parametrize("mutation", ["changed", "added", "removed"])
def test_product_lane_blocks_unreviewed_source_drift(tmp_path: Path, mutation: str):
    source = tmp_path / "ui_qt" / "commercial"
    source.mkdir(parents=True)
    pdv = source / "pdv_window.py"
    pdv.write_text("EDITION = 'FICHARIO'\n", encoding="utf-8")
    expected = tree_digest(tmp_path, "ui_qt/commercial")

    if mutation == "changed":
        pdv.write_text("EDITION = 'NABICODE'\n", encoding="utf-8")
    elif mutation == "added":
        (source / "new_nabicode_screen.py").write_text("pass\n", encoding="utf-8")
    else:
        pdv.unlink()

    with pytest.raises(RuntimeError, match="Build bloqueado.*mistura"):
        validate_product_lane(
            tmp_path,
            product="FICHARIO",
            expected_digests={"ui_qt/commercial": expected},
        )


def test_product_lane_ignores_generated_python_cache(tmp_path: Path):
    source = tmp_path / "fichario"
    source.mkdir()
    (source / "shell.py").write_text("pass\n", encoding="utf-8")
    expected = tree_digest(tmp_path, "fichario")
    cache = source / "__pycache__"
    cache.mkdir()
    (cache / "shell.pyc").write_bytes(b"generated")

    validate_product_lane(
        tmp_path,
        product="FICHARIO",
        expected_digests={"fichario": expected},
    )
