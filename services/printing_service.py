from __future__ import annotations

import os
import subprocess
from collections.abc import Callable
from typing import Any

from services.document_rendering import config_bool, normalize_newlines, wrap_lines
from services.receipt_template_service import ReceiptTemplateService


class PrintingService:
    """Infraestrutura de impressão independente da interface gráfica.

    O serviço mantém pywin32 opcional e concentra descoberta, validação,
    formatação de cupom e envio direto ao spooler do Windows.
    """

    OFFICIAL_THERMAL_FORMAT = "Cupom 80 mm"
    LEGACY_THERMAL_FORMAT = "Cupom 58 mm"
    VALID_FORMATS = {OFFICIAL_THERMAL_FORMAT, "A4", "PDF virtual"}
    DEFAULT_FORMATS = {
        "recibo": OFFICIAL_THERMAL_FORMAT,
        "entrega": OFFICIAL_THERMAL_FORMAT,
        "ficha": "A4",
        "historico": "A4",
        "fechamento": "A4",
    }

    def __init__(self, get_config: Callable[[str], Any] | None = None) -> None:
        self._get_config = get_config or (lambda _key: "")
        self.last_warning = ""

    def list_printers(self) -> list[str]:
        names: list[str] = []
        self.last_warning = ""
        if os.name == "nt":
            try:
                import win32print  # type: ignore

                flags = win32print.PRINTER_ENUM_LOCAL | win32print.PRINTER_ENUM_CONNECTIONS
                names = sorted(
                    {item[2] for item in win32print.EnumPrinters(flags) if item[2]},
                    key=str.casefold,
                )
            except (ImportError, OSError, RuntimeError) as primary_error:
                try:
                    command = [
                        "powershell",
                        "-NoProfile",
                        "-Command",
                        "Get-CimInstance Win32_Printer | Select-Object -ExpandProperty Name",
                    ]
                    result = subprocess.run(
                        command,
                        capture_output=True,
                        text=True,
                        timeout=12,
                        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                        check=False,
                    )
                    if result.returncode != 0:
                        raise RuntimeError(result.stderr.strip() or "PowerShell não retornou as impressoras.")
                    names = sorted(
                        {line.strip() for line in result.stdout.splitlines() if line.strip()},
                        key=str.casefold,
                    )
                except (OSError, subprocess.SubprocessError, RuntimeError) as fallback_error:
                    self.last_warning = f"Falha ao listar impressoras: {fallback_error or primary_error}"
                    names = []
        return ["Padrão do Sistema"] + [name for name in names if name != "Padrão do Sistema"]

    def is_available(self, name: str | None) -> bool:
        normalized = str(name or "").strip()
        return not normalized or normalized == "Padrão do Sistema" or normalized in self.list_printers()

    @classmethod
    def normalize_output_format(cls, value: Any, default: str = "A4") -> str:
        """Normaliza formatos persistidos sem remover a compatibilidade histórica de 58 mm."""
        normalized = str(value or default).strip()
        if normalized == cls.LEGACY_THERMAL_FORMAT:
            return cls.OFFICIAL_THERMAL_FORMAT
        return normalized if normalized in cls.VALID_FORMATS else default

    def output_format(self, category: str) -> str:
        normalized = "recibo" if category == "movimento" else str(category or "").strip().lower()
        default = self.DEFAULT_FORMATS.get(normalized, "A4")
        persisted = self._get_config(f"formato_impressao_{normalized}")
        return self.normalize_output_format(persisted, default)

    def _config_bool(self, key: str, default: bool = False) -> bool:
        return config_bool(self._get_config(key), default)

    _ESC_POS_CUT_TOTAL = b"\x1d\x56\x00"
    _ESC_POS_CUT_PARTIAL = b"\x1d\x56\x01"

    def _cut_payload(self) -> bytes:
        """Retorna avanço e um único comando ESC/POS GS V quando configurado."""
        if not self._config_bool("impressao_corte_automatico", True):
            return b""
        try:
            feed_lines = int(self._get_config("impressao_linhas_antes_corte") or 4)
        except (TypeError, ValueError):
            feed_lines = 4
        feed_lines = max(0, min(12, feed_lines))
        cut_type = str(self._get_config("impressao_tipo_corte") or "PARCIAL").strip().upper()
        cut_command = (
            self._ESC_POS_CUT_TOTAL
            if cut_type == "TOTAL"
            else self._ESC_POS_CUT_PARTIAL
        )
        return (b"\r\n" * feed_lines) + cut_command

    def _raw_payload(self, text: str) -> bytes:
        """Monta o trabalho RAW uma vez: texto CP850, avanço e corte opcional."""
        styled = ReceiptTemplateService.render(
            text, self._get_config("modelo_cupom_visual") or ReceiptTemplateService.DEFAULT,
        )
        body = normalize_newlines(styled).replace("\n", "\r\n").encode(
            "cp850", errors="replace"
        )
        return body + self._cut_payload()

    @staticmethod
    def wrap_receipt_text(text: str, width: int) -> str:
        if width < 16:
            raise ValueError("A largura do cupom deve ser de pelo menos 16 caracteres.")
        output = wrap_lines(text, width, preserve_separators=True)
        return "\n".join(output) + "\n\n\n"

    def _resolve_printer_name(self, printer: str, win32print: Any) -> str:
        """Resolve e valida a impressora uma única vez por backend."""
        name = win32print.GetDefaultPrinter() if not printer or printer == "Padrão do Sistema" else printer
        flags = win32print.PRINTER_ENUM_LOCAL | win32print.PRINTER_ENUM_CONNECTIONS
        installed = {item[2] for item in win32print.EnumPrinters(flags) if item[2]}
        if name not in installed:
            raise RuntimeError(f"A impressora '{name}' não está instalada ou está desconectada.")
        return name

    def print_text(
        self,
        text: str,
        *,
        output_format: str,
        printer: str = "Padrão do Sistema",
        title: str = "NabiCode",
    ) -> str:
        """Ponto único de envio documental para impressão física."""
        if output_format == "A4":
            return self.print_a4_text(text, printer, title)
        if output_format == self.OFFICIAL_THERMAL_FORMAT:
            return self.print_raw_text(text, printer, title)
        raise ValueError(f"Formato de impressão não suportado: {output_format!r}")

    def print_raw_text(self, text: str, printer: str = "Padrão do Sistema", title: str = "NabiCode") -> str:
        if os.name != "nt":
            raise RuntimeError("A seleção direta de impressoras está disponível na versão para Windows.")
        try:
            import win32print  # type: ignore
        except ImportError as exc:
            raise RuntimeError(
                "O componente de impressão do Windows não foi encontrado. Instale 'pywin32' e gere o executável novamente."
            ) from exc

        name = self._resolve_printer_name(printer, win32print)

        handle = win32print.OpenPrinter(name)
        try:
            win32print.StartDocPrinter(handle, 1, (title, None, "RAW"))
            try:
                win32print.StartPagePrinter(handle)
                win32print.WritePrinter(handle, self._raw_payload(text))
                win32print.EndPagePrinter(handle)
            finally:
                win32print.EndDocPrinter(handle)
        finally:
            win32print.ClosePrinter(handle)
        return name

    def print_a4_text(self, text: str, printer: str = "Padrão do Sistema", title: str = "Documento") -> str:
        if os.name != "nt":
            raise RuntimeError("A impressão A4 direta está disponível apenas no Windows.")
        try:
            import win32con  # type: ignore
            import win32print  # type: ignore
            import win32ui  # type: ignore
        except ImportError as exc:
            raise RuntimeError(
                "O componente de impressão A4 do Windows não foi encontrado. Instale 'pywin32' e gere o executável novamente."
            ) from exc

        name = self._resolve_printer_name(printer, win32print)

        dc = win32ui.CreateDC()
        dc.CreatePrinterDC(name)
        try:
            dc.StartDoc(title)
            dc.StartPage()
            page_width = dc.GetDeviceCaps(win32con.HORZRES)
            page_height = dc.GetDeviceCaps(win32con.VERTRES)
            dpi_y = max(96, dc.GetDeviceCaps(win32con.LOGPIXELSY))
            margin_x = int(page_width * 0.07)
            margin_y = int(page_height * 0.06)
            content_width = page_width - (margin_x * 2)
            font = win32ui.CreateFont({"name": "Arial", "height": -int(dpi_y * 10 / 72), "weight": 400})
            title_font = win32ui.CreateFont({"name": "Arial", "height": -int(dpi_y * 15 / 72), "weight": 700})
            y = margin_y
            for index, line in enumerate(normalize_newlines(text).split("\n")):
                line = line.expandtabs(4)
                is_title = index < 2 and bool(line.strip())
                dc.SelectObject(title_font if is_title else font)
                line_height = int(dpi_y * (0.28 if is_title else 0.22))
                max_chars = max(45, int(content_width / max(6, dpi_y * 0.07)))
                for part in wrap_lines(line, max_chars):
                    if y + line_height > page_height - margin_y:
                        dc.EndPage()
                        dc.StartPage()
                        y = margin_y
                    dc.TextOut(margin_x, y, part)
                    y += line_height
            dc.EndPage()
            dc.EndDoc()
        finally:
            dc.DeleteDC()
        return name
