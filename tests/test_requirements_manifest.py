from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_official_runtime_dependencies_are_declared():
    requirements = (ROOT / "requirements.txt").read_text(encoding="utf-8").casefold()
    for package in (
        "customtkinter",
        "pillow",
        "requests",
        "cryptography",
        "lxml",
        "reportlab",
        "openpyxl",
        "matplotlib",
        "pyinstaller",
        "pywin32",
    ):
        assert package in requirements
