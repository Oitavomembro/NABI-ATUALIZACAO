from __future__ import annotations

import hashlib
import os
import re
import tempfile
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Callable
from urllib.request import Request, urlopen

try:
    from lxml import html
except ModuleNotFoundError:  # dependência fiscal opcional
    html = None


@dataclass(frozen=True)
class CESTEntry:
    code: str
    ncm_text: str
    description: str


class FiscalCESTCatalogService:
    """Referência CEST do Convênio 142/18, sem inferir incidência de ST."""

    OFFICIAL_URL = "https://www.confaz.fazenda.gov.br/legislacao/convenios/2018/CV142_18"
    MAX_DOWNLOAD_BYTES = 8 * 1024 * 1024

    def __init__(
        self, *, bundled_path: str | Path, cache_path: str | Path,
        downloader: Callable[[str], bytes] | None = None,
    ) -> None:
        self.bundled_path = Path(bundled_path)
        self.cache_path = Path(cache_path)
        self.downloader = downloader or self._download
        self._entries: tuple[CESTEntry, ...] = ()
        self._metadata: dict[str, str] = {}

    @staticmethod
    def _download(url: str) -> bytes:
        request = Request(url, headers={"User-Agent": "NabiCode/2.5.1 CEST-Official-Catalog"})
        with urlopen(request, timeout=30) as response:
            payload = response.read(FiscalCESTCatalogService.MAX_DOWNLOAD_BYTES + 1)
        if len(payload) > FiscalCESTCatalogService.MAX_DOWNLOAD_BYTES:
            raise ValueError("A publicação CEST excede o limite de segurança.")
        return payload

    @staticmethod
    def _text(value: str) -> str:
        return " ".join(str(value or "").split())

    @classmethod
    def _parse(cls, payload: bytes) -> tuple[dict[str, str], tuple[CESTEntry, ...]]:
        if html is None:
            raise RuntimeError("A leitura do catálogo CEST exige a dependência lxml.")
        if not payload or len(payload) > cls.MAX_DOWNLOAD_BYTES:
            raise ValueError("Publicação CEST vazia ou acima do limite de segurança.")
        try:
            document = html.fromstring(payload)
        except (ValueError, TypeError) as exc:
            raise ValueError("O CONFAZ não retornou HTML válido.") from exc
        consolidated: dict[str, CESTEntry] = {}
        occurrences = 0
        for row in document.xpath("//tr"):
            cells = [cls._text(cell.text_content()) for cell in row.xpath("./th|./td")]
            index = next(
                (position for position, value in enumerate(cells)
                 if re.fullmatch(r"\d{2}\.\d{3}\.\d{2}", value)),
                None,
            )
            if index is None or index + 2 >= len(cells):
                continue
            code = re.sub(r"\D", "", cells[index])
            ncm_text = cells[index + 1]
            description = cells[index + 2]
            if len(code) != 7 or not ncm_text or not description:
                continue
            occurrences += 1
            consolidated[code] = CESTEntry(code, ncm_text, description)
        if len(consolidated) < 1_000:
            raise ValueError("A publicação CEST recebida está incompleta e foi rejeitada.")
        metadata = {
            "source": "Convênio ICMS 142/18 — CONFAZ",
            "sha256": hashlib.sha256(payload).hexdigest(),
            "entries": str(len(consolidated)),
            "occurrences": str(occurrences),
        }
        return metadata, tuple(consolidated.values())

    def load(self) -> dict[str, str]:
        errors: list[str] = []
        for path in (self.cache_path, self.bundled_path):
            if not path.is_file():
                continue
            try:
                self._metadata, self._entries = self._parse(path.read_bytes())
                return dict(self._metadata)
            except (OSError, ValueError, RuntimeError) as exc:
                errors.append(f"{path.name}: {exc}")
        raise ValueError("Catálogo CEST oficial não disponível. " + "; ".join(errors))

    def update(self) -> dict[str, str]:
        payload = self.downloader(self.OFFICIAL_URL)
        metadata, entries = self._parse(payload)
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        handle, temporary_name = tempfile.mkstemp(
            prefix=".cest_", suffix=".html.tmp", dir=str(self.cache_path.parent),
        )
        os.close(handle)
        temporary = Path(temporary_name)
        try:
            temporary.write_bytes(payload)
            temporary.replace(self.cache_path)
        except Exception:
            temporary.unlink(missing_ok=True)
            raise
        self._metadata, self._entries = metadata, entries
        return dict(metadata)

    @staticmethod
    def _normalized(value: str) -> str:
        decomposed = unicodedata.normalize("NFKD", str(value or ""))
        return " ".join(
            "".join(char for char in decomposed if not unicodedata.combining(char)).lower().split()
        )

    @staticmethod
    def _ncm_prefixes(value: str) -> tuple[str, ...]:
        return tuple(re.sub(r"\D", "", token) for token in re.findall(r"\d[\d.]*", value) if 2 <= len(re.sub(r"\D", "", token)) <= 8)

    def search(self, query: str, *, ncm: str = "", limit: int = 50) -> list[CESTEntry]:
        if not self._entries:
            self.load()
        normalized = self._normalized(query)
        digits = re.sub(r"\D", "", str(query or ""))
        ncm_digits = re.sub(r"\D", "", str(ncm or ""))
        if len(normalized) < 2 and len(digits) < 2 and len(ncm_digits) != 8:
            raise ValueError("Informe CEST, descrição ou um NCM válido para pesquisar.")
        terms = normalized.split()
        result: list[CESTEntry] = []
        for entry in self._entries:
            code_match = bool(digits and entry.code.startswith(digits))
            text_match = bool(terms and all(term in self._normalized(entry.description) for term in terms))
            ncm_match = bool(
                len(ncm_digits) == 8
                and any(ncm_digits.startswith(prefix) for prefix in self._ncm_prefixes(entry.ncm_text))
            )
            if code_match or text_match or ncm_match:
                result.append(entry)
            if len(result) >= max(1, min(int(limit), 100)):
                break
        return result

    def get(self, code: str) -> CESTEntry:
        digits = re.sub(r"\D", "", str(code or ""))
        if not self._entries:
            self.load()
        entry = next((item for item in self._entries if item.code == digits), None)
        if entry is None:
            raise ValueError("CEST não encontrado na publicação oficial consolidada.")
        return entry
