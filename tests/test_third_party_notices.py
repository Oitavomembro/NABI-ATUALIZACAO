from pathlib import Path

import pytest

from build_tools.third_party_notices import render_inventory, validate_notices


ROOT = Path(__file__).resolve().parents[1]


def test_notices_cover_exactly_the_transitive_lock() -> None:
    generated = render_inventory(
        ROOT / "build_tools" / "requirements-windows.lock",
        ROOT / "build_tools" / "licenses-reviewed.json",
    )
    validate_notices(ROOT / "THIRD_PARTY_NOTICES.md", generated)


def test_license_review_fails_closed_when_component_is_missing(tmp_path: Path) -> None:
    lock = tmp_path / "lock"
    lock.write_text("# artifact: demo-1-py3-none-any.whl\ndemo==1 \\\n    --hash=sha256:" + "a" * 64 + "\n", encoding="utf-8")
    review = tmp_path / "review.json"
    review.write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError, match="ausentes"):
        render_inventory(lock, review)
