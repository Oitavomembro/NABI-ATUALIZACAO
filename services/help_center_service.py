from __future__ import annotations

import os
import shutil
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
                 minimum_free_mb: int = 200):
        self.dirs = tuple(Path(p).resolve() for p in persistent_dirs)
        self.probes = {HelpCheck.DATABASE: database_probe, HelpCheck.BACKUP: backup_probe,
                       HelpCheck.PRINTER: printer_probe, HelpCheck.NABI: nabi_probe}
        self.audit, self.minimum_free_mb = audit, minimum_free_mb

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
