from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable
from urllib.request import Request, urlopen


@dataclass(frozen=True)
class NCMEntry:
    code: str
    description: str
    start_date: str
    end_date: str


class FiscalNCMCatalogService:
    """Catálogo NCM oficial da RFB, com snapshot offline e atualização atômica."""

    OFFICIAL_URL = "https://portalunico.siscomex.gov.br/classif/api/publico/nomenclatura/download/json"
    MAX_DOWNLOAD_BYTES = 15 * 1024 * 1024

    def __init__(
        self, *, bundled_path: str | Path, cache_path: str | Path,
        downloader: Callable[[str], bytes] | None = None,
    ) -> None:
        self.bundled_path = Path(bundled_path)
        self.cache_path = Path(cache_path)
        self.downloader = downloader or self._download
        self._loaded_path: Path | None = None
        self._metadata: dict[str, str] = {}
        self._entries: tuple[NCMEntry, ...] = ()

    @staticmethod
    def _download(url: str) -> bytes:
        request = Request(url, headers={"User-Agent": "NabiCode/2.5.1 NCM-Official-Catalog"})
        with urlopen(request, timeout=30) as response:
            payload = response.read(FiscalNCMCatalogService.MAX_DOWNLOAD_BYTES + 1)
        if len(payload) > FiscalNCMCatalogService.MAX_DOWNLOAD_BYTES:
            raise ValueError("A tabela NCM excede o limite de segurança.")
        return payload

    @staticmethod
    def _parse(payload: bytes) -> tuple[dict[str, str], tuple[NCMEntry, ...]]:
        if not payload or len(payload) > FiscalNCMCatalogService.MAX_DOWNLOAD_BYTES:
            raise ValueError("Arquivo NCM vazio ou acima do limite de segurança.")
        try:
            raw = json.loads(payload.decode("utf-8-sig"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError("A fonte NCM não retornou JSON válido.") from exc
        rows = raw.get("Nomenclaturas") if isinstance(raw, dict) else None
        if not isinstance(rows, list):
            raise ValueError("A fonte NCM não possui a estrutura oficial esperada.")
        entries: list[NCMEntry] = []
        seen: set[str] = set()
        for row in rows:
            if not isinstance(row, dict):
                continue
            code = re.sub(r"\D", "", str(row.get("Codigo") or ""))
            description = re.sub(r"\s+", " ", str(row.get("Descricao") or "")).strip()
            if len(code) != 8 or not description or code in seen:
                continue
            seen.add(code)
            entries.append(NCMEntry(
                code, description, str(row.get("Data_Inicio") or ""), str(row.get("Data_Fim") or ""),
            ))
        if len(entries) < 5_000:
            raise ValueError("A tabela NCM recebida está incompleta e foi rejeitada.")
        metadata = {
            "updated": str(raw.get("Data_Ultima_Atualizacao_NCM") or "").strip(),
            "legal_act": str(raw.get("Ato") or "").strip(),
            "sha256": hashlib.sha256(payload).hexdigest(),
            "entries": str(len(entries)),
        }
        return metadata, tuple(entries)

    def load(self) -> dict[str, str]:
        candidates = [path for path in (self.cache_path, self.bundled_path) if path.is_file()]
        errors: list[str] = []
        for path in candidates:
            try:
                metadata, entries = self._parse(path.read_bytes())
                self._loaded_path, self._metadata, self._entries = path, metadata, entries
                return dict(metadata)
            except (OSError, ValueError) as exc:
                errors.append(f"{path.name}: {exc}")
        raise ValueError("Tabela NCM oficial não disponível. " + "; ".join(errors))

    def update(self) -> dict[str, str]:
        payload = self.downloader(self.OFFICIAL_URL)
        metadata, entries = self._parse(payload)
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        handle, temporary_name = tempfile.mkstemp(
            prefix=".ncm_", suffix=".json.tmp", dir=str(self.cache_path.parent)
        )
        os.close(handle)
        temporary = Path(temporary_name)
        try:
            temporary.write_bytes(payload)
            temporary.replace(self.cache_path)
        except Exception:
            temporary.unlink(missing_ok=True)
            raise
        self._loaded_path, self._metadata, self._entries = self.cache_path, metadata, entries
        return dict(metadata)

    @staticmethod
    def _search_text(value: str) -> str:
        normalized = unicodedata.normalize("NFKD", str(value or ""))
        return " ".join("".join(char for char in normalized if not unicodedata.combining(char)).lower().split())

    def search(self, query: str, *, limit: int = 50) -> list[NCMEntry]:
        if not self._entries:
            self.load()
        normalized = self._search_text(query)
        digits = re.sub(r"\D", "", str(query or ""))
        if len(normalized) < 2 and len(digits) < 2:
            raise ValueError("Informe ao menos dois caracteres para pesquisar a NCM.")
        terms = normalized.split()
        matches = [
            entry for entry in self._entries
            if (digits and entry.code.startswith(digits))
            or (terms and all(term in self._search_text(entry.description) for term in terms))
        ]
        return matches[:max(1, min(int(limit), 100))]

    def validate_code(self, code: str) -> NCMEntry:
        digits = re.sub(r"\D", "", str(code or ""))
        matches = self.search(digits, limit=100) if len(digits) == 8 else []
        entry = next((item for item in matches if item.code == digits), None)
        if entry is None:
            raise ValueError("NCM não encontrada na tabela oficial vigente.")
        return entry
