from __future__ import annotations

from dataclasses import dataclass

from services.document_rendering import normalize_newlines, wrap_lines


@dataclass(frozen=True)
class ReceiptTemplate:
    name: str
    top: str
    divider: str
    accent: str
    left: str = ""
    right: str = ""
    title_left: str = ""
    title_right: str = ""


class ReceiptTemplateService:
    """Galeria offline de estilos estruturais para cupons térmicos de 80 mm."""

    PRESETS = (
        ReceiptTemplate("Clássico", "=", "-", "="),
        ReceiptTemplate("Minimalista", "-", " ", "-"),
        ReceiptTemplate("Elegante", "~", ".", "~", title_left="< ", title_right=" >"),
        ReceiptTemplate("Moderno", "#", "-", "#", title_left="[ ", title_right=" ]"),
        ReceiptTemplate("Ticket", "-", "-", "=", "|", "|", "> ", " <"),
        ReceiptTemplate("Moldura dupla", "=", "=", "#", "||", "||"),
        ReceiptTemplate("Pontilhado", ".", ".", ":"),
        ReceiptTemplate("Compacto", "-", "-", "-", title_left=":: "),
        ReceiptTemplate("Total em destaque", "*", "-", "*", title_left="*** ", title_right=" ***"),
        ReceiptTemplate("Faixas", "#", "=", "#", title_left="# ", title_right=" #"),
        ReceiptTemplate("Cantos", "+", "-", "+", "/", "\\"),
        ReceiptTemplate("Blocos", "#", "#", "=", "[", "]"),
        ReceiptTemplate("Linha fina", "_", "-", "_"),
        ReceiptTemplate("Industrial", "=", ":", "#", title_left="// ", title_right=" //"),
        ReceiptTemplate("Premium", "*", "~", "*", title_left="<* ", title_right=" *>"),
        ReceiptTemplate("Retrô", "-", ".", "=", title_left="<< ", title_right=" >>"),
        ReceiptTemplate("Contábil", "=", "-", "=", "|", "|"),
        ReceiptTemplate("Loja rápida", ">", "-", ">", title_left=">> "),
        ReceiptTemplate("Assinatura", "~", "-", "~", title_left="{ ", title_right=" }"),
        ReceiptTemplate("Nabi exclusivo", "*", "=", "*", "<", ">", "NABI | ", " | NABI"),
    )
    DEFAULT = "Clássico"

    @classmethod
    def names(cls) -> list[str]:
        return [preset.name for preset in cls.PRESETS]

    @classmethod
    def resolve(cls, name: str | None) -> ReceiptTemplate:
        normalized = str(name or "").strip().casefold()
        return next((item for item in cls.PRESETS if item.name.casefold() == normalized), cls.PRESETS[0])

    @classmethod
    def render(cls, text: str, name: str | None, *, width: int = 42) -> str:
        preset = cls.resolve(name)
        inner_width = width - len(preset.left) - len(preset.right)
        inner_width = max(24, inner_width)
        source = normalize_newlines(text).strip("\n").splitlines()
        rendered: list[str] = [preset.top * width]
        for index, line in enumerate(source):
            stripped = line.strip()
            if stripped and set(stripped) <= {"=", "-"}:
                char = preset.accent if "=" in stripped else preset.divider
                rendered.append(char * width)
                continue
            if index < 2 and stripped:
                stripped = f"{preset.title_left}{stripped}{preset.title_right}"
                pieces = [stripped[:inner_width].center(inner_width)]
            else:
                pieces = wrap_lines(stripped, inner_width, preserve_separators=True) or [""]
            rendered.extend(
                f"{preset.left}{piece[:inner_width].ljust(inner_width)}{preset.right}"
                for piece in pieces
            )
        rendered.append(preset.top * width)
        return "\n".join(rendered) + "\n\n\n"
