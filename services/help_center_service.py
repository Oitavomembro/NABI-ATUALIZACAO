from __future__ import annotations

import os
import json
import shutil
import tempfile
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Callable, Mapping

from core.sensitive_data import sanitize_text


class DiagnosticState(str, Enum):
    SAUDAVEL = "SAUDAVEL"
    ALERTA = "ALERTA"
    FALHA = "FALHA"
    INCONCLUSIVO = "INCONCLUSIVO"


class HelpCheck(str, Enum):
    DISK = "disk"
    DIRECTORIES = "directories"
    DATABASE = "database"
    BACKUP = "backup"
    PRINTER = "printer"
    NABI = "nabi"


@dataclass(frozen=True)
class HelpEntry:
    check: HelpCheck
    title: str


@dataclass(frozen=True)
class DiagnosticResult:
    entry: HelpEntry
    state: DiagnosticState
    message: str
    technical_id: str = ""


CATALOG = tuple(HelpEntry(item, title) for item, title in (
    (HelpCheck.DISK, "Espaço em disco"), (HelpCheck.DIRECTORIES, "Diretórios persistentes"),
    (HelpCheck.DATABASE, "Banco de dados"), (HelpCheck.BACKUP, "Backup diário"),
    (HelpCheck.PRINTER, "Impressora"), (HelpCheck.NABI, "Runtime da Nabi"),
))


class HelpCenterDiagnosticService:
    """Diagnóstico tipado e somente leitura; não executa reparo, SQL ou shell."""

    def __init__(self, *, persistent_dirs, database_probe: Callable[[], Mapping] | None,
                 backup_probe: Callable[[], Mapping] | None, printer_probe: Callable[[], Mapping] | None,
                 nabi_probe: Callable[[], Mapping] | None, audit: Callable[..., None] | None = None,
                 minimum_free_mb: int = 200, clock: Callable[[], datetime] | None = None):
        self.dirs = tuple(Path(p).resolve() for p in persistent_dirs)
        self.probes = {HelpCheck.DATABASE: database_probe, HelpCheck.BACKUP: backup_probe,
                       HelpCheck.PRINTER: printer_probe, HelpCheck.NABI: nabi_probe}
        self.audit, self.minimum_free_mb = audit, minimum_free_mb
        self.clock = clock or datetime.now

    def run(self) -> tuple[DiagnosticResult, ...]:
        results = tuple(self._run(entry) for entry in CATALOG)
        if self.audit:
            self.audit("socorro", "DIAGNOSTICO", "central", sanitize_text(
                ";".join(f"{r.entry.check.value}={r.state.value}" for r in results)), "SUCESSO", "Sistema")
        return results

    def _run(self, entry):
        try:
            if entry.check is HelpCheck.DISK:
                free = min(shutil.disk_usage(p if p.exists() else p.parent).free for p in self.dirs) // 1048576
                state = DiagnosticState.SAUDAVEL if free >= self.minimum_free_mb else DiagnosticState.ALERTA
                return DiagnosticResult(entry, state, f"{free} MB livres", f"free_mb:{free}")
            if entry.check is HelpCheck.DIRECTORIES:
                missing = sum(not p.exists() for p in self.dirs)
                denied = sum(p.exists() and not os.access(p, os.R_OK | os.W_OK) for p in self.dirs)
                state = DiagnosticState.SAUDAVEL if not missing and not denied else DiagnosticState.FALHA
                return DiagnosticResult(entry, state, f"existentes={len(self.dirs)-missing}; ausentes={missing}; sem_acesso={denied}")
            probe = self.probes[entry.check]
            if probe is None:
                return DiagnosticResult(entry, DiagnosticState.INCONCLUSIVO, "Verificador não configurado")
            data = dict(probe())
            state = DiagnosticState(str(data.get("state", "INCONCLUSIVO")).upper())
            return DiagnosticResult(entry, state, sanitize_text(data.get("message", "Sem detalhe")), sanitize_text(data.get("technical_id", "")))
        except Exception as exc:
            return DiagnosticResult(entry, DiagnosticState.INCONCLUSIVO, sanitize_text(f"Falha segura no verificador: {type(exc).__name__}"))

    def report_bytes(self, results: tuple[DiagnosticResult, ...]) -> bytes:
        """Serializa somente o catálogo fechado e já sanitizado para suporte."""
        expected = tuple(entry.check for entry in CATALOG)
        if not isinstance(results, tuple) or tuple(item.entry.check for item in results) != expected:
            raise ValueError("O relatório exige um resultado único para cada diagnóstico conhecido.")
        payload = {
            "schema": "nabicode.help-center-report.v1",
            "generated_at": self.clock().isoformat(timespec="seconds"),
            "scope": "DIAGNOSTICO_SOMENTE_LEITURA",
            "protected": [
                "Nenhum autorreparo ou mutação operacional foi executado.",
                "Credenciais, documentos pessoais, XML fiscal e caminhos pessoais são omitidos.",
                "O relatório não comprova homologação física, fiscal ou disponibilidade externa.",
            ],
            "results": [
                {
                    "check": item.entry.check.value,
                    "title": sanitize_text(item.entry.title),
                    "state": item.state.value,
                    "message": sanitize_text(item.message),
                    "technical_id": sanitize_text(item.technical_id),
                }
                for item in results
            ],
        }
        return (json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")

    def save_report(self, destination, results: tuple[DiagnosticResult, ...]) -> Path:
        """Grava o relatório por substituição atômica; nunca modifica dados diagnosticados."""
        path = Path(destination).expanduser().resolve()
        if path.suffix.lower() != ".json":
            raise ValueError("O relatório de suporte deve usar a extensão .json.")
        if not path.parent.is_dir():
            raise ValueError("Selecione uma pasta existente para o relatório.")
        content = self.report_bytes(results)
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="wb", dir=path.parent, prefix=f".{path.name}.", suffix=".tmp", delete=False,
            ) as stream:
                temporary = Path(stream.name)
                stream.write(content); stream.flush(); os.fsync(stream.fileno())
            os.replace(temporary, path)
            return path
        except Exception:
            if temporary is not None:
                try: temporary.unlink(missing_ok=True)
                except OSError: pass
            raise
