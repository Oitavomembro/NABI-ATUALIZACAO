from __future__ import annotations

import hashlib
import os
import re
import stat
from copy import deepcopy
from dataclasses import dataclass
from enum import Enum
from pathlib import Path, PurePath
from typing import Any, Callable, Mapping

from core.sensitive_data import sanitize_text


class GreenRepair(str, Enum):
    VISUAL_PREFERENCES = "visual_preferences"
    REGISTERED_CACHE = "registered_cache"
    NABI_RUNTIME = "nabi_runtime"
    REPORT_CACHE = "report_cache"


class RepairRisk(str, Enum):
    VERDE = "VERDE"


class RepairOutcome(str, Enum):
    PROVADO = "PROVADO"
    FALHOU = "FALHOU"
    REVERTIDO = "REVERTIDO"
    INCONCLUSIVO = "INCONCLUSIVO"


class RepairPhase(str, Enum):
    PRECHECK = "PRECHECK"
    APPLY = "APPLY"
    POSTCHECK = "POSTCHECK"
    ROLLBACK = "ROLLBACK"
    FINAL = "FINAL"


@dataclass(frozen=True, slots=True)
class GreenRepairEntry:
    repair: GreenRepair
    title: str
    risk: RepairRisk = RepairRisk.VERDE


GREEN_REPAIR_CATALOG = (
    GreenRepairEntry(GreenRepair.VISUAL_PREFERENCES, "Corrigir preferências visuais inválidas"),
    GreenRepairEntry(GreenRepair.REGISTERED_CACHE, "Limpar cache e temporários registrados"),
    GreenRepairEntry(GreenRepair.NABI_RUNTIME, "Reiniciar somente o runtime local da Nabi"),
    GreenRepairEntry(GreenRepair.REPORT_CACHE, "Regenerar cache de relatórios"),
)

_CATALOG_BY_REPAIR = {entry.repair: entry for entry in GREEN_REPAIR_CATALOG}
_OPERATION_ID = re.compile(r"\A[A-Za-z0-9][A-Za-z0-9._:-]{7,127}\Z")


@dataclass(frozen=True, slots=True)
class RepairRequest:
    repair: GreenRepair
    operation_id: str

    def __post_init__(self) -> None:
        if type(self.repair) is not GreenRepair:
            raise TypeError("O reparo deve vir do catálogo tipado VERDE.")
        if not _OPERATION_ID.fullmatch(str(self.operation_id or "")):
            raise ValueError("A chave da operação deve ser técnica, opaca e possuir de 8 a 128 caracteres.")


@dataclass(frozen=True, slots=True)
class RepairAuditEvent:
    operation_fingerprint: str
    repair: GreenRepair
    phase: RepairPhase
    outcome: RepairOutcome
    changed: bool
    technical_id: str = ""


@dataclass(frozen=True, slots=True)
class RepairResult:
    entry: GreenRepairEntry
    outcome: RepairOutcome
    message: str
    operation_fingerprint: str
    changed: bool
    precheck: RepairOutcome
    postcheck: RepairOutcome
    rollback: RepairOutcome | None = None
    technical_id: str = ""


@dataclass(frozen=True, slots=True)
class VisualPreferencesCallbacks:
    snapshot: Callable[[], Mapping[str, Any]]
    is_valid: Callable[[Mapping[str, Any]], bool]
    normalize: Callable[[Mapping[str, Any]], Mapping[str, Any]]
    replace: Callable[[Mapping[str, Any]], None]


@dataclass(frozen=True, slots=True)
class NabiRuntimeSnapshot:
    generation: str
    healthy: bool


@dataclass(frozen=True, slots=True)
class NabiRestartCallbacks:
    snapshot: Callable[[], NabiRuntimeSnapshot]
    restart: Callable[[], None]
    rollback: Callable[[NabiRuntimeSnapshot], None]


@dataclass(frozen=True, slots=True)
class ReportCacheSnapshot:
    generation: str
    valid: bool


@dataclass(frozen=True, slots=True)
class ReportCacheCallbacks:
    snapshot: Callable[[], ReportCacheSnapshot]
    regenerate: Callable[[], None]
    rollback: Callable[[ReportCacheSnapshot], None]


@dataclass(frozen=True, slots=True)
class RegisteredCleanupTarget:
    root: Path
    relative_path: Path

    def __post_init__(self) -> None:
        root = Path(self.root)
        relative = Path(self.relative_path)
        if not root.is_absolute():
            raise ValueError("A raiz de limpeza deve ser absoluta e explícita.")
        if root == Path(root.anchor):
            raise ValueError("A raiz do volume ou compartilhamento é ampla demais para limpeza.")
        if (
            relative.is_absolute()
            or not relative.parts
            or any(part in {"", ".", ".."} or ":" in part for part in relative.parts)
            or relative.parts[0].casefold() == ".socorro-verde"
        ):
            raise ValueError("O alvo registrado deve ser um caminho relativo confinado.")
        object.__setattr__(self, "root", root.absolute())
        object.__setattr__(self, "relative_path", relative)


class UnsafeCleanupTargetError(ValueError):
    pass


class StrictAuditError(RuntimeError):
    pass


class GreenRepairService:
    """Executor fechado de autorreparos VERDE.

    Não interpreta texto, não executa comandos e não recebe acesso a banco ou
    processo. Toda capacidade mutável entra por uma porta pequena e tipada.
    """

    def __init__(
        self,
        *,
        audit: Callable[[RepairAuditEvent], None],
        visual_preferences: VisualPreferencesCallbacks | None = None,
        cleanup_targets: tuple[RegisteredCleanupTarget, ...] = (),
        nabi_runtime: NabiRestartCallbacks | None = None,
        report_cache: ReportCacheCallbacks | None = None,
    ) -> None:
        if not callable(audit):
            raise TypeError("A auditoria estrita é obrigatória.")
        if not isinstance(cleanup_targets, tuple):
            raise TypeError("O registro de limpeza deve ser uma tupla fechada.")
        if any(type(item) is not RegisteredCleanupTarget for item in cleanup_targets):
            raise TypeError("O registro de limpeza aceita somente alvos tipados.")
        for port, expected, label in (
            (visual_preferences, VisualPreferencesCallbacks, "preferências"),
            (nabi_runtime, NabiRestartCallbacks, "Nabi"),
            (report_cache, ReportCacheCallbacks, "cache de relatórios"),
        ):
            if port is not None and type(port) is not expected:
                raise TypeError(f"A porta de {label} deve usar callbacks tipados.")
            if port is not None:
                for callback in port.__dataclass_fields__:
                    if not callable(getattr(port, callback)):
                        raise TypeError(f"Callback inválido na porta de {label}.")
        self.audit = audit
        self.visual_preferences = visual_preferences
        self.cleanup_targets = cleanup_targets
        self.nabi_runtime = nabi_runtime
        self.report_cache = report_cache
        self._results: dict[str, tuple[GreenRepair, RepairResult]] = {}

    @staticmethod
    def catalog() -> tuple[GreenRepairEntry, ...]:
        return GREEN_REPAIR_CATALOG

    def execute(self, request: RepairRequest) -> RepairResult:
        if type(request) is not RepairRequest:
            raise TypeError("A execução exige RepairRequest tipado; comandos livres são recusados.")
        fingerprint = hashlib.sha256(request.operation_id.encode("ascii")).hexdigest()[:20]
        replay = self._results.get(request.operation_id)
        if replay is not None:
            previous_repair, previous_result = replay
            if previous_repair is not request.repair:
                raise ValueError("A chave idempotente já pertence a outro reparo.")
            return previous_result

        entry = _CATALOG_BY_REPAIR[request.repair]
        self._audit(fingerprint, request.repair, RepairPhase.PRECHECK, RepairOutcome.INCONCLUSIVO, False)
        try:
            if request.repair is GreenRepair.VISUAL_PREFERENCES:
                result = self._repair_visual_preferences(entry, fingerprint)
            elif request.repair is GreenRepair.REGISTERED_CACHE:
                result = self._clean_registered_cache(entry, fingerprint)
            elif request.repair is GreenRepair.NABI_RUNTIME:
                result = self._restart_nabi(entry, fingerprint)
            elif request.repair is GreenRepair.REPORT_CACHE:
                result = self._regenerate_report_cache(entry, fingerprint)
            else:  # pragma: no cover - o Enum e o catálogo tornam o ramo inalcançável.
                raise TypeError("Reparo fora do catálogo fechado.")
        except StrictAuditError:
            raise
        except Exception as exc:
            result = self._result(
                entry, RepairOutcome.FALHOU, fingerprint, False,
                RepairOutcome.FALHOU, RepairOutcome.INCONCLUSIVO,
                message=f"Falha segura no reparo: {type(exc).__name__}",
            )
            self._audit_result(result, RepairPhase.FINAL)
        self._results[request.operation_id] = (request.repair, result)
        return result

    def _repair_visual_preferences(self, entry: GreenRepairEntry, fingerprint: str) -> RepairResult:
        port = self.visual_preferences
        if port is None:
            return self._inconclusive(entry, fingerprint, "Porta de preferências não configurada.")
        try:
            original = deepcopy(dict(port.snapshot()))
            valid = bool(port.is_valid(deepcopy(original)))
        except Exception as exc:
            return self._failed_precheck(entry, fingerprint, exc)
        if valid:
            return self._proved_unchanged(entry, fingerprint, "As preferências visuais já são válidas.")

        self._audit(fingerprint, entry.repair, RepairPhase.PRECHECK, RepairOutcome.PROVADO, False, "invalidas")
        try:
            normalized = deepcopy(dict(port.normalize(deepcopy(original))))
            if not port.is_valid(deepcopy(normalized)):
                return self._failed(entry, fingerprint, "A normalização não produziu preferências válidas.")
            self._audit(fingerprint, entry.repair, RepairPhase.APPLY, RepairOutcome.INCONCLUSIVO, False)
            port.replace(deepcopy(normalized))
            current = deepcopy(dict(port.snapshot()))
            if current != normalized or not port.is_valid(deepcopy(current)):
                raise RuntimeError("postcheck_visual_invalido")
            result = self._result(
                entry, RepairOutcome.PROVADO, fingerprint, True,
                RepairOutcome.PROVADO, RepairOutcome.PROVADO,
                message="Preferências visuais normalizadas e verificadas.", technical_id="visual:normalized",
            )
            try:
                self._audit_result(result, RepairPhase.POSTCHECK)
            except StrictAuditError:
                try:
                    port.replace(deepcopy(original))
                finally:
                    raise
            return result
        except StrictAuditError:
            raise
        except Exception:
            return self._rollback_mapping(entry, fingerprint, port.replace, port.snapshot, port.is_valid, original)

    def _clean_registered_cache(self, entry: GreenRepairEntry, fingerprint: str) -> RepairResult:
        if not self.cleanup_targets:
            return self._inconclusive(entry, fingerprint, "Nenhum cache ou temporário foi registrado.")
        try:
            targets = self._validated_cleanup_targets()
        except Exception as exc:
            return self._failed_precheck(entry, fingerprint, exc)
        existing = tuple(path for _root, path in targets if os.path.lexists(path))
        if not existing:
            return self._proved_unchanged(entry, fingerprint, "Os alvos registrados já estão limpos.")
        snapshots = {path: self._tree_fingerprint(path) for path in existing}

        self._audit(fingerprint, entry.repair, RepairPhase.PRECHECK, RepairOutcome.PROVADO, False, f"targets:{len(existing)}")
        moved: list[tuple[Path, Path, str]] = []
        try:
            for index, (root, target) in enumerate((item for item in targets if os.path.lexists(item[1]))):
                quarantine = root / ".socorro-verde" / fingerprint / str(index)
                self._assert_safe_path(root, quarantine.parent, scan_contents=False)
                quarantine.parent.mkdir(parents=True, exist_ok=True)
                self._assert_safe_path(root, quarantine.parent, scan_contents=False)
                os.replace(target, quarantine)
                moved.append((target, quarantine, snapshots[target]))
            if any(os.path.lexists(original) for original, _quarantine, _snapshot in moved):
                raise RuntimeError("postcheck_cache_presente")
            self._audit(fingerprint, entry.repair, RepairPhase.POSTCHECK, RepairOutcome.PROVADO, True, f"targets:{len(moved)}")
            for _original, quarantine, _snapshot in moved:
                self._remove_tree_without_links(quarantine)
            for root, _target in targets:
                operation_dir = root / ".socorro-verde" / fingerprint
                try:
                    operation_dir.rmdir()
                    operation_dir.parent.rmdir()
                except OSError:
                    pass
            result = self._result(
                entry, RepairOutcome.PROVADO, fingerprint, True,
                RepairOutcome.PROVADO, RepairOutcome.PROVADO,
                message=f"{len(moved)} alvo(s) registrado(s) limpo(s) e verificado(s).",
                technical_id=f"cleanup:{len(moved)}",
            )
            return result
        except StrictAuditError:
            if moved:
                try:
                    self._rollback_paths(entry, fingerprint, moved)
                except StrictAuditError:
                    pass
            raise
        except Exception:
            return self._rollback_paths(entry, fingerprint, moved)

    def _restart_nabi(self, entry: GreenRepairEntry, fingerprint: str) -> RepairResult:
        port = self.nabi_runtime
        if port is None:
            return self._inconclusive(entry, fingerprint, "Callback tipado da Nabi não configurado.")
        try:
            before = port.snapshot()
            if type(before) is not NabiRuntimeSnapshot:
                raise TypeError("Snapshot inválido da Nabi.")
        except Exception as exc:
            return self._failed_precheck(entry, fingerprint, exc)
        self._audit(fingerprint, entry.repair, RepairPhase.PRECHECK, RepairOutcome.PROVADO, False, "callback")
        try:
            self._audit(fingerprint, entry.repair, RepairPhase.APPLY, RepairOutcome.INCONCLUSIVO, False, "callback")
            port.restart()
            after = port.snapshot()
            if type(after) is not NabiRuntimeSnapshot or not after.healthy or after.generation == before.generation:
                raise RuntimeError("postcheck_nabi_invalido")
            result = self._result(
                entry, RepairOutcome.PROVADO, fingerprint, True,
                RepairOutcome.PROVADO, RepairOutcome.PROVADO,
                message="Runtime local da Nabi reiniciado e saúde comprovada.", technical_id="nabi:callback",
            )
            try:
                self._audit_result(result, RepairPhase.POSTCHECK)
            except StrictAuditError:
                try:
                    port.rollback(before)
                finally:
                    raise
            return result
        except StrictAuditError:
            raise
        except Exception:
            return self._rollback_typed(entry, fingerprint, lambda: port.rollback(before), lambda: port.snapshot() == before)

    def _regenerate_report_cache(self, entry: GreenRepairEntry, fingerprint: str) -> RepairResult:
        port = self.report_cache
        if port is None:
            return self._inconclusive(entry, fingerprint, "Porta de cache de relatórios não configurada.")
        try:
            before = port.snapshot()
            if type(before) is not ReportCacheSnapshot:
                raise TypeError("Snapshot inválido do cache de relatórios.")
        except Exception as exc:
            return self._failed_precheck(entry, fingerprint, exc)
        self._audit(fingerprint, entry.repair, RepairPhase.PRECHECK, RepairOutcome.PROVADO, False, "port")
        try:
            self._audit(fingerprint, entry.repair, RepairPhase.APPLY, RepairOutcome.INCONCLUSIVO, False, "port")
            port.regenerate()
            after = port.snapshot()
            if type(after) is not ReportCacheSnapshot or not after.valid or after.generation == before.generation:
                raise RuntimeError("postcheck_report_cache_invalido")
            result = self._result(
                entry, RepairOutcome.PROVADO, fingerprint, True,
                RepairOutcome.PROVADO, RepairOutcome.PROVADO,
                message="Cache de relatórios regenerado pela porta e verificado.", technical_id="reports:port",
            )
            try:
                self._audit_result(result, RepairPhase.POSTCHECK)
            except StrictAuditError:
                try:
                    port.rollback(before)
                finally:
                    raise
            return result
        except StrictAuditError:
            raise
        except Exception:
            return self._rollback_typed(entry, fingerprint, lambda: port.rollback(before), lambda: port.snapshot() == before)

    def _validated_cleanup_targets(self) -> tuple[tuple[Path, Path], ...]:
        validated: list[tuple[Path, Path]] = []
        for registered in self.cleanup_targets:
            root = registered.root
            target = root.joinpath(registered.relative_path)
            self._assert_safe_path(root, target, scan_contents=True)
            validated.append((root, target))
        normalized = tuple(os.path.normcase(str(target)) for _root, target in validated)
        if len(set(normalized)) != len(normalized):
            raise UnsafeCleanupTargetError("O registro de limpeza contém alvo duplicado.")
        for index, first in enumerate(normalized):
            for second in normalized[index + 1:]:
                if os.path.commonpath((first, second)) in {first, second}:
                    raise UnsafeCleanupTargetError("Alvos de limpeza sobrepostos são recusados.")
        return tuple(validated)

    @classmethod
    def _assert_safe_path(cls, root: Path, target: Path, *, scan_contents: bool) -> None:
        root_text = os.path.abspath(root)
        target_text = os.path.abspath(target)
        if not root.is_dir():
            raise UnsafeCleanupTargetError("A raiz explícita de limpeza deve existir e ser uma pasta.")
        if os.path.commonpath((root_text, target_text)) != root_text or target_text == root_text:
            raise UnsafeCleanupTargetError("Alvo fora da raiz explícita ou igual à raiz.")
        current = Path(root.anchor)
        for part in PurePath(root_text).parts[1:]:
            current /= part
            if os.path.lexists(current) and cls._is_link_or_reparse(current):
                raise UnsafeCleanupTargetError("Raiz com symlink/reparse point recusada.")
        relative = Path(os.path.relpath(target_text, root_text))
        current = Path(root_text)
        for part in relative.parts:
            current /= part
            if os.path.lexists(current) and cls._is_link_or_reparse(current):
                raise UnsafeCleanupTargetError("Alvo com symlink/reparse point recusado.")
        if scan_contents and os.path.lexists(target):
            if target.is_dir():
                for base, directories, files in os.walk(target, topdown=True, followlinks=False):
                    for name in tuple(directories) + tuple(files):
                        if cls._is_link_or_reparse(Path(base) / name):
                            raise UnsafeCleanupTargetError("Conteúdo com symlink/reparse point recusado.")
            elif not target.is_file():
                raise UnsafeCleanupTargetError("Tipo de alvo de limpeza não suportado.")

    @staticmethod
    def _is_link_or_reparse(path: Path) -> bool:
        metadata = os.lstat(path)
        attributes = int(getattr(metadata, "st_file_attributes", 0))
        reparse_flag = int(getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400))
        return stat.S_ISLNK(metadata.st_mode) or bool(attributes & reparse_flag)

    @classmethod
    def _remove_tree_without_links(cls, path: Path) -> None:
        if cls._is_link_or_reparse(path):
            raise UnsafeCleanupTargetError("Quarentena com link/reparse recusada.")
        if path.is_file():
            path.unlink()
            return
        for base, directories, files in os.walk(path, topdown=False, followlinks=False):
            for name in files:
                child = Path(base) / name
                if cls._is_link_or_reparse(child):
                    raise UnsafeCleanupTargetError("Link/reparse encontrado durante limpeza.")
                child.unlink()
            for name in directories:
                child = Path(base) / name
                if cls._is_link_or_reparse(child):
                    raise UnsafeCleanupTargetError("Link/reparse encontrado durante limpeza.")
                child.rmdir()
        path.rmdir()

    @classmethod
    def _tree_fingerprint(cls, path: Path) -> str:
        """Resume tipo, nomes e conteúdo para provar um rollback sem expor dados."""
        digest = hashlib.sha256()
        if cls._is_link_or_reparse(path):
            raise UnsafeCleanupTargetError("Link/reparse recusado no snapshot.")
        if path.is_file():
            digest.update(b"F\0")
            with path.open("rb") as stream:
                for block in iter(lambda: stream.read(1024 * 1024), b""):
                    digest.update(block)
            return digest.hexdigest()
        digest.update(b"D\0")
        for base, directories, files in os.walk(path, topdown=True, followlinks=False):
            directories.sort(); files.sort()
            relative_base = Path(base).relative_to(path)
            for name in directories:
                child = Path(base) / name
                if cls._is_link_or_reparse(child):
                    raise UnsafeCleanupTargetError("Link/reparse recusado no snapshot.")
                digest.update(b"D\0" + str(relative_base / name).encode("utf-8") + b"\0")
            for name in files:
                child = Path(base) / name
                if cls._is_link_or_reparse(child):
                    raise UnsafeCleanupTargetError("Link/reparse recusado no snapshot.")
                digest.update(b"F\0" + str(relative_base / name).encode("utf-8") + b"\0")
                with child.open("rb") as stream:
                    for block in iter(lambda: stream.read(1024 * 1024), b""):
                        digest.update(block)
        return digest.hexdigest()

    def _rollback_mapping(self, entry, fingerprint, replace, snapshot, is_valid, original) -> RepairResult:
        return self._rollback_typed(
            entry, fingerprint,
            lambda: replace(deepcopy(original)),
            lambda: dict(snapshot()) == original,
        )

    def _rollback_paths(self, entry, fingerprint, moved) -> RepairResult:
        if not moved:
            return self._failed(entry, fingerprint, "A limpeza falhou antes de alterar os alvos.")
        audit_error = None
        try:
            self._audit(fingerprint, entry.repair, RepairPhase.ROLLBACK, RepairOutcome.INCONCLUSIVO, True)
        except StrictAuditError as exc:
            audit_error = exc
        try:
            for original, quarantine, _snapshot in reversed(moved):
                if os.path.lexists(quarantine) and not os.path.lexists(original):
                    original.parent.mkdir(parents=True, exist_ok=True)
                    os.replace(quarantine, original)
            proved = all(
                os.path.lexists(original)
                and not os.path.lexists(quarantine)
                and self._tree_fingerprint(original) == snapshot
                for original, quarantine, snapshot in moved
            )
        except Exception:
            proved = False
        if audit_error is not None:
            raise audit_error
        return self._rolled_back_or_inconclusive(entry, fingerprint, proved)

    def _rollback_typed(self, entry, fingerprint, rollback, proved) -> RepairResult:
        audit_error = None
        try:
            self._audit(fingerprint, entry.repair, RepairPhase.ROLLBACK, RepairOutcome.INCONCLUSIVO, True)
        except StrictAuditError as exc:
            audit_error = exc
        try:
            rollback()
            restored = bool(proved())
        except Exception:
            restored = False
        if audit_error is not None:
            raise audit_error
        return self._rolled_back_or_inconclusive(entry, fingerprint, restored)

    def _rolled_back_or_inconclusive(self, entry, fingerprint, restored) -> RepairResult:
        outcome = RepairOutcome.REVERTIDO if restored else RepairOutcome.INCONCLUSIVO
        result = self._result(
            entry, outcome, fingerprint, True,
            RepairOutcome.PROVADO, RepairOutcome.FALHOU,
            rollback=RepairOutcome.PROVADO if restored else RepairOutcome.INCONCLUSIVO,
            message=("Falha após alteração; snapshot restaurado e verificado." if restored
                     else "Falha após alteração; não foi possível provar a restauração."),
        )
        self._audit_result(result, RepairPhase.FINAL)
        return result

    def _proved_unchanged(self, entry, fingerprint, message) -> RepairResult:
        result = self._result(
            entry, RepairOutcome.PROVADO, fingerprint, False,
            RepairOutcome.PROVADO, RepairOutcome.PROVADO, message=message,
        )
        self._audit_result(result, RepairPhase.POSTCHECK)
        return result

    def _failed_precheck(self, entry, fingerprint, error) -> RepairResult:
        return self._failed(entry, fingerprint, f"Precheck falhou com {type(error).__name__}.")

    def _failed(self, entry, fingerprint, message) -> RepairResult:
        result = self._result(
            entry, RepairOutcome.FALHOU, fingerprint, False,
            RepairOutcome.FALHOU, RepairOutcome.INCONCLUSIVO, message=message,
        )
        self._audit_result(result, RepairPhase.FINAL)
        return result

    def _inconclusive(self, entry, fingerprint, message) -> RepairResult:
        result = self._result(
            entry, RepairOutcome.INCONCLUSIVO, fingerprint, False,
            RepairOutcome.INCONCLUSIVO, RepairOutcome.INCONCLUSIVO, message=message,
        )
        self._audit_result(result, RepairPhase.FINAL)
        return result

    @staticmethod
    def _result(entry, outcome, fingerprint, changed, precheck, postcheck, *, rollback=None, message, technical_id=""):
        return RepairResult(
            entry=entry, outcome=outcome, message=sanitize_text(message),
            operation_fingerprint=fingerprint, changed=changed,
            precheck=precheck, postcheck=postcheck, rollback=rollback,
            technical_id=sanitize_text(technical_id),
        )

    def _audit_result(self, result: RepairResult, phase: RepairPhase) -> None:
        self._audit(
            result.operation_fingerprint, result.entry.repair, phase,
            result.outcome, result.changed, result.technical_id,
        )

    def _audit(self, fingerprint, repair, phase, outcome, changed, technical_id="") -> None:
        event = RepairAuditEvent(
            operation_fingerprint=fingerprint, repair=repair, phase=phase,
            outcome=outcome, changed=bool(changed),
            technical_id=sanitize_text(technical_id),
        )
        try:
            self.audit(event)
        except Exception as exc:
            raise StrictAuditError("A auditoria estrita falhou; o autorreparo foi bloqueado.") from exc
