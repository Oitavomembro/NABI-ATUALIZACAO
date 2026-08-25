from __future__ import annotations

import json
from pathlib import Path

from build_tools.supply_chain import read_locked_artifacts


START = "<!-- BEGIN GENERATED WINDOWS LOCK -->"
END = "<!-- END GENERATED WINDOWS LOCK -->"


def render_inventory(lock: Path, review: Path) -> str:
    locked = read_locked_artifacts(lock)
    reviewed = json.loads(review.read_text(encoding="utf-8"))
    expected = {item.name for item in locked}
    if set(reviewed) != expected:
        missing = sorted(expected - set(reviewed))
        extra = sorted(set(reviewed) - expected)
        raise ValueError(f"revisão de licenças divergente; ausentes={missing}; extras={extra}")
    rows = [START, "", "## Inventario do lock Windows aprovado", "", "| Componente | Versao | Licenca revisada | Artefato aprovado |", "|---|---:|---|---|"]
    for item in locked:
        data = reviewed[item.name]
        if data.get("version") != item.version or not data.get("license") or not data.get("artifact"):
            raise ValueError(f"revisão incompleta ou divergente para {item.name}")
        rows.append(f"| {item.name} | {item.version} | {data['license']} | `{data['artifact']}` |")
    rows.extend(["", "Licencas foram revisadas contra os metadados dos wheels aprovados na cerimonia de 24/08/2026. Qualquer divergencia futura exige revisao humana; a automacao nao infere licenca.", "", END])
    return "\n".join(rows)


def validate_notices(notices: Path, generated: str) -> None:
    text = notices.read_text(encoding="utf-8")
    if text.count(START) != 1 or text.count(END) != 1:
        raise ValueError("bloco gerado de avisos ausente ou duplicado")
    current = text[text.index(START) : text.index(END) + len(END)]
    if current != generated:
        raise ValueError("THIRD_PARTY_NOTICES.md diverge da revisão versionada")


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    generated = render_inventory(
        root / "build_tools" / "requirements-windows.lock",
        root / "build_tools" / "licenses-reviewed.json",
    )
    validate_notices(root / "THIRD_PARTY_NOTICES.md", generated)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
