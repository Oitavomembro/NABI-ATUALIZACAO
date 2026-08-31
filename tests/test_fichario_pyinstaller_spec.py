from pathlib import Path


SPEC = Path("build_tools/pyinstaller/nabicode_fichario.spec")


def test_fichario_spec_rejects_foreign_icu_binaries():
    source = SPEC.read_text(encoding="utf-8")

    assert 'foreign_icu_names = {"icuuc.dll"}' in source
    assert 'startswith("icudt")' in source
    assert "item in a.binaries" in source
