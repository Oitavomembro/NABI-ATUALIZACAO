from __future__ import annotations

import textwrap
from dataclasses import dataclass
from typing import Any


_TRUE_VALUES = frozenset({"1", "true", "sim", "yes", "on"})


@dataclass(frozen=True)
class DocumentProfile:
    name: str
    paper_width_mm: float | None
    pdf_width_chars: int
    raw_width_chars: int


A4_PROFILE = DocumentProfile("A4", None, 100, 100)
THERMAL_58_PROFILE = DocumentProfile("58 mm", 58.0, 30, 32)
THERMAL_80_PROFILE = DocumentProfile("80 mm", 80.0, 44, 42)
LEGACY_58_PDF_MODELS = frozenset({
    "térmica 58 mm econômica",
    "termica 58 mm economica",
    "58 mm",
})


def config_bool(value: Any, default: bool = False) -> bool:
    if value in (None, ""):
        return default
    return str(value).strip().casefold() in _TRUE_VALUES


def profile_for_pdf_model(model: str) -> DocumentProfile:
    normalized = str(model or "").strip().casefold()
    if normalized == "a4":
        return A4_PROFILE
    if normalized in LEGACY_58_PDF_MODELS:
        return THERMAL_58_PROFILE
    return THERMAL_80_PROFILE



def normalize_newlines(text: Any) -> str:
    return str(text or "").replace("\r\n", "\n").replace("\r", "\n")


def wrap_lines(
    text: Any,
    width: int,
    *,
    preserve_separators: bool = False,
    break_long_words: bool = True,
) -> list[str]:
    if width < 16:
        raise ValueError("A largura do cupom deve ser de pelo menos 16 caracteres.")

    output: list[str] = []
    for line in normalize_newlines(text).split("\n"):
        if not line:
            output.append("")
            continue
        if preserve_separators and set(line) <= {"=", "-"}:
            output.append(line[0] * width)
            continue
        output.extend(
            textwrap.wrap(
                line,
                width=width,
                break_long_words=break_long_words,
                break_on_hyphens=False,
                replace_whitespace=False,
            )
            or [""]
        )
    return output


def bold_font_name(font: str) -> str:
    """Resolve a variação em negrito das fontes PDF padrão sem duplicar regras."""
    normalized = str(font or "Helvetica").strip()
    known = {
        "Helvetica": "Helvetica-Bold",
        "Helvetica-Bold": "Helvetica-Bold",
        "Times-Roman": "Times-Bold",
        "Times-Bold": "Times-Bold",
        "Courier": "Courier-Bold",
        "Courier-Bold": "Courier-Bold",
    }
    return known.get(normalized, normalized)


def wrap_pdf_lines(text: Any, font: str, size: float, width: float) -> list[str]:
    """Quebra pelo tamanho real da fonte, inclusive palavras sem espaços."""
    from reportlab.pdfbase.pdfmetrics import stringWidth

    result: list[str] = []
    for paragraph in normalize_newlines(text).split("\n"):
        remaining = paragraph
        while remaining and stringWidth(remaining, font, size) > width:
            end = 1
            while end < len(remaining) and stringWidth(remaining[:end + 1], font, size) <= width:
                end += 1
            space = remaining.rfind(" ", 0, end + 1)
            if space > 0:
                end = space
            result.append(remaining[:end])
            remaining = remaining[end:].lstrip()
        result.append(remaining)
    return result


class PDFLineRenderer:
    """Renderiza linhas quebradas em um canvas ReportLab mantendo o cursor Y."""

    def __init__(
        self,
        *,
        canvas: Any,
        margin: float,
        y: float,
        font: str,
        size: float,
        width_chars: int,
        step: float,
    ) -> None:
        self.canvas = canvas
        self.margin = float(margin)
        self.y = float(y)
        self.font = str(font or "Helvetica")
        self.size = float(size)
        self.width_chars = int(width_chars)
        self.step = float(step)

    def draw(
        self,
        text: Any = "",
        *,
        bold: bool = False,
        centered: bool = False,
        center_x: float | None = None,
        indent: int = 0,
        break_long_words: bool = True,
    ) -> float:
        prefix = " " * max(0, int(indent))
        lines = wrap_lines(
            f"{prefix}{normalize_newlines(text)}",
            self.width_chars,
            break_long_words=break_long_words,
        )
        selected_font = bold_font_name(self.font) if bold else self.font
        page_size = getattr(self.canvas, "_pagesize", None)
        if isinstance(page_size, (tuple, list)) and isinstance(page_size[0], (int, float)):
            available = max(1.0, page_size[0] - 2 * self.margin)
            lines = [part for line in lines for part in wrap_pdf_lines(line, selected_font, self.size, available)]
        self.canvas.setFont(selected_font, self.size)
        for line in lines:
            if centered:
                page_width = getattr(self.canvas, "_pagesize", (0, 0))[0]
                resolved_center = float(center_x) if center_x is not None else (page_width / 2 if page_width else 0)
                if resolved_center:
                    self.canvas.drawCentredString(resolved_center, self.y, line)
                else:
                    self.canvas.drawString(self.margin, self.y, line)
            else:
                self.canvas.drawString(self.margin, self.y, line)
            self.y -= self.step
        return self.y
