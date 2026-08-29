from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
import hashlib
import json
from pathlib import Path
import sys
from typing import Any, Callable
from urllib.parse import urlsplit

from services.fiscal_state_catalog import BA_ENDPOINTS, BA_NFCE_URLS


CATALOG_SCHEMA = "nabicode.fiscal-regulatory-catalog.v1"
CATALOG_SHA256 = "0EA7F18AA3372C3BF80E5C21CF580F4C03CFF59589A22F9B21575791760A3B0E"
OFFICIAL_HOSTS = {
    "www.nfe.fazenda.gov.br",
    "hom.nfe.fazenda.gov.br",
    "www.sefaz.ba.gov.br",
}


@dataclass(frozen=True, slots=True)
class FiscalRegulatoryReport:
    jurisdiction: str
    reviewed_at: str
    review_due_at: str
    production_approved: bool
    artifact_versions: tuple[tuple[str, str], ...]
    supported_operations: tuple[str, ...]
    unsupported_operations: tuple[str, ...]
    problems: tuple[str, ...]
    warnings: tuple[str, ...]

    @property
    def ready(self) -> bool:
        return not self.problems


class FiscalRegulatoryCatalogService:
    """Verifica a base normativa instalada sem consultar rede nem inferir tributos."""

    def __init__(
        self,
        *,
        runtime_root: str | Path | None = None,
        catalog_path: str | Path | None = None,
        today_provider: Callable[[], date] = date.today,
        expected_sha256: str = CATALOG_SHA256,
    ) -> None:
        root = Path(
            runtime_root
            or getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[1])
        )
        self.runtime_root = root
        self.catalog_path = Path(
            catalog_path or root / "resources" / "fiscal" / "regulatory_catalog.json"
        )
        self.today_provider = today_provider
        self.expected_sha256 = str(expected_sha256).strip().upper()

    @staticmethod
    def _parse_date(value: Any, label: str) -> date:
        try:
            return datetime.strptime(str(value), "%Y-%m-%d").date()
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{label} do catálogo regulatório é inválida.") from exc

    def _load(self) -> dict[str, Any]:
        try:
            raw = self.catalog_path.read_bytes()
        except OSError as exc:
            raise ValueError("Catálogo regulatório fiscal não está instalado.") from exc
        digest = hashlib.sha256(raw).hexdigest().upper()
        if not self.expected_sha256 or digest != self.expected_sha256:
            raise ValueError(
                "Catálogo regulatório fiscal foi alterado ou não pertence a esta versão."
            )
        try:
            payload = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError("Catálogo regulatório fiscal é inválido.") from exc
        if not isinstance(payload, dict) or payload.get("schema") != CATALOG_SCHEMA:
            raise ValueError("Schema do catálogo regulatório fiscal não é reconhecido.")
        return payload

    @staticmethod
    def _tree_sha256(path: Path) -> str:
        rows = [
            (
                file.relative_to(path).as_posix(),
                hashlib.sha256(file.read_bytes()).hexdigest().upper(),
            )
            for file in sorted(path.rglob("*"))
            if file.is_file()
        ]
        canonical = json.dumps(rows, separators=(",", ":")).encode("utf-8")
        return hashlib.sha256(canonical).hexdigest().upper()

    @staticmethod
    def _endpoint_catalog_sha256() -> str:
        canonical = json.dumps(
            {"endpoints": BA_ENDPOINTS, "nfce_urls": BA_NFCE_URLS},
            sort_keys=True, separators=(",", ":"),
        ).encode("utf-8")
        return hashlib.sha256(canonical).hexdigest().upper()

    def audit(self, *, environment: str = "HOMOLOGACAO") -> FiscalRegulatoryReport:
        try:
            payload = self._load()
        except ValueError as exc:
            return FiscalRegulatoryReport(
                "", "", "", False, (), (), (), (str(exc),), ()
            )
        problems: list[str] = []
        warnings: list[str] = []
        jurisdiction = str(payload.get("jurisdiction") or "").strip().upper()
        if jurisdiction != "BR-BA":
            problems.append("Catálogo regulatório não corresponde à Bahia.")
        expected_endpoint_hash = str(
            payload.get("endpoint_catalog_sha256") or ""
        ).strip().upper()
        if (
            len(expected_endpoint_hash) != 64
            or expected_endpoint_hash != self._endpoint_catalog_sha256()
        ):
            problems.append(
                "Catálogo de endpoints Bahia diverge da revisão regulatória instalada."
            )
        try:
            reviewed_at = self._parse_date(payload.get("reviewed_at"), "Data de revisão")
            review_due_at = self._parse_date(payload.get("review_due_at"), "Prazo de revisão")
            if review_due_at < reviewed_at:
                problems.append("Prazo regulatório termina antes da revisão registrada.")
            if self.today_provider() > review_due_at:
                problems.append(
                    "Revisão regulatória vencida; confira NTs, schemas, tabelas e endpoints oficiais."
                )
        except ValueError as exc:
            problems.append(str(exc))
            reviewed_at = review_due_at = None

        artifacts = payload.get("artifacts")
        versions: list[tuple[str, str]] = []
        seen_ids: set[str] = set()
        if not isinstance(artifacts, list) or not artifacts:
            problems.append("Catálogo regulatório não possui artefatos oficiais.")
            artifacts = []
        for artifact in artifacts:
            if not isinstance(artifact, dict):
                problems.append("Catálogo regulatório contém artefato inválido.")
                continue
            identifier = str(artifact.get("id") or "").strip()
            version = str(artifact.get("version") or "").strip()
            source_url = str(artifact.get("source_url") or "").strip()
            host = (urlsplit(source_url).hostname or "").casefold()
            if not identifier or identifier in seen_ids:
                problems.append("Catálogo regulatório possui identificador ausente ou duplicado.")
            else:
                seen_ids.add(identifier)
            if not version:
                problems.append(f"Artefato {identifier or '?'} não informa versão.")
            if urlsplit(source_url).scheme != "https" or host not in OFFICIAL_HOSTS:
                problems.append(f"Artefato {identifier or '?'} não aponta para fonte oficial permitida.")
            installed_path = str(artifact.get("installed_path") or "").strip()
            if installed_path:
                resolved = (self.runtime_root / installed_path).resolve()
                try:
                    resolved.relative_to(self.runtime_root.resolve())
                except ValueError:
                    problems.append(f"Artefato {identifier or '?'} aponta para fora do runtime.")
                else:
                    if not resolved.is_file():
                        problems.append(f"Artefato fiscal instalado ausente: {identifier or '?'}.")
            source_hash = str(artifact.get("source_sha256") or "").strip().upper()
            if source_hash and (
                len(source_hash) != 64
                or any(character not in "0123456789ABCDEF" for character in source_hash)
            ):
                problems.append(f"Hash de origem inválido no artefato {identifier or '?'}.")
            versions.append((identifier, version))

        installed_trees = payload.get("installed_trees")
        if not isinstance(installed_trees, dict) or not installed_trees:
            problems.append("Catálogo regulatório não protege as árvores de schemas instaladas.")
        else:
            for relative_path, expected_hash in installed_trees.items():
                resolved = (self.runtime_root / str(relative_path)).resolve()
                try:
                    resolved.relative_to(self.runtime_root.resolve())
                except ValueError:
                    problems.append("Árvore fiscal aponta para fora do runtime.")
                    continue
                if not resolved.is_dir():
                    problems.append(f"Árvore de schemas ausente: {relative_path}.")
                    continue
                actual_hash = self._tree_sha256(resolved)
                if actual_hash != str(expected_hash).strip().upper():
                    problems.append(
                        f"Árvore de schemas alterada ou incompleta: {relative_path}."
                    )

        operations = payload.get("supported_operations")
        supported: list[str] = []
        unsupported: list[str] = []
        if not isinstance(operations, dict) or not operations:
            problems.append("Catálogo regulatório não declara a cobertura operacional.")
        else:
            for name, enabled in sorted(operations.items()):
                (supported if enabled is True else unsupported).append(str(name))
            if not unsupported:
                warnings.append(
                    "Catálogo declara cobertura total; exige revisão humana antes de produção."
                )

        production_approved = payload.get("production_approved") is True
        if str(environment).strip().upper() == "PRODUCAO" and not production_approved:
            problems.append("Catálogo regulatório não autoriza operação em produção.")
        return FiscalRegulatoryReport(
            jurisdiction=jurisdiction,
            reviewed_at=reviewed_at.isoformat() if reviewed_at else "",
            review_due_at=review_due_at.isoformat() if review_due_at else "",
            production_approved=production_approved,
            artifact_versions=tuple(versions),
            supported_operations=tuple(supported),
            unsupported_operations=tuple(unsupported),
            problems=tuple(dict.fromkeys(problems)),
            warnings=tuple(dict.fromkeys(warnings)),
        )

    def require_current(self, *, environment: str) -> FiscalRegulatoryReport:
        report = self.audit(environment=environment)
        if not report.ready:
            raise ValueError("; ".join(report.problems))
        return report
