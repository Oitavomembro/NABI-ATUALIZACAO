from __future__ import annotations

import ast
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from services.help_center_repair_service import (
    GREEN_REPAIR_CATALOG,
    GreenRepair,
    GreenRepairService,
    NabiRestartCallbacks,
    NabiRuntimeSnapshot,
    RegisteredCleanupTarget,
    RepairOutcome,
    RepairPhase,
    RepairRequest,
    ReportCacheCallbacks,
    ReportCacheSnapshot,
    StrictAuditError,
    UnsafeCleanupTargetError,
    VisualPreferencesCallbacks,
)
from services.ui_preferences import UIPreferencesService


class Audit:
    def __init__(self):
        self.events = []

    def __call__(self, event):
        self.events.append(event)


def request(repair: GreenRepair, suffix: str = "00000001") -> RepairRequest:
    return RepairRequest(repair, f"test-{suffix}")


def test_catalogo_verde_e_request_sao_fechados_e_imutaveis():
    assert tuple(item.repair for item in GREEN_REPAIR_CATALOG) == tuple(GreenRepair)
    assert {item.risk.value for item in GREEN_REPAIR_CATALOG} == {"VERDE"}
    with pytest.raises(TypeError, match="catálogo tipado"):
        RepairRequest("registered_cache", "test-00000001")  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="RepairRequest"):
        GreenRepairService(audit=Audit()).execute("limpe tudo")  # type: ignore[arg-type]
    with pytest.raises(FrozenInstanceError):
        GREEN_REPAIR_CATALOG[0].title = "livre"


def test_preferencias_invalidas_usam_snapshot_postcheck_e_sao_idempotentes():
    raw = {"mode": "MODO INVENTADO", "density": "gigante", "theme": "desconhecido"}
    state = {"value": raw}
    writes = []

    def valid(values):
        return dict(values) == UIPreferencesService.normalize(values)

    port = VisualPreferencesCallbacks(
        snapshot=lambda: state["value"],
        is_valid=valid,
        normalize=UIPreferencesService.normalize,
        replace=lambda values: (writes.append(dict(values)), state.__setitem__("value", dict(values)))[1],
    )
    audit = Audit()
    service = GreenRepairService(audit=audit, visual_preferences=port)
    operation = request(GreenRepair.VISUAL_PREFERENCES)
    first = service.execute(operation)
    second = service.execute(operation)

    assert first is second
    assert first.outcome is RepairOutcome.PROVADO and first.changed
    assert len(writes) == 1 and valid(state["value"])
    assert operation.operation_id not in repr(audit.events)


def test_preferencias_revertem_snapshot_quando_postcheck_falha():
    original = {"mode": "inválido"}
    state = {"value": original}
    calls = 0

    def replace(values):
        nonlocal calls
        calls += 1
        state["value"] = {"mode": "corrompido"} if calls == 1 else dict(values)

    port = VisualPreferencesCallbacks(
        snapshot=lambda: state["value"],
        is_valid=lambda values: values.get("mode") == "Intermediário",
        normalize=lambda _values: {"mode": "Intermediário"},
        replace=replace,
    )
    result = GreenRepairService(audit=Audit(), visual_preferences=port).execute(
        request(GreenRepair.VISUAL_PREFERENCES)
    )
    assert result.outcome is RepairOutcome.REVERTIDO
    assert result.rollback is RepairOutcome.PROVADO
    assert state["value"] == original and calls == 2


def test_limpeza_remove_somente_alvos_registrados_sob_raiz_explicita(tmp_path):
    root = tmp_path / "runtime"
    cache = root / "cache" / "relatorios"
    temp = root / "temp" / "preview.tmp"
    outside = tmp_path / "cliente.db"
    cache.mkdir(parents=True); (cache / "a.bin").write_bytes(b"cache")
    temp.parent.mkdir(parents=True); temp.write_bytes(b"tmp")
    outside.write_bytes(b"preservar")
    service = GreenRepairService(
        audit=Audit(),
        cleanup_targets=(
            RegisteredCleanupTarget(root, Path("cache/relatorios")),
            RegisteredCleanupTarget(root, Path("temp/preview.tmp")),
        ),
    )
    first = service.execute(request(GreenRepair.REGISTERED_CACHE))
    second = service.execute(request(GreenRepair.REGISTERED_CACHE, "00000002"))
    assert first.outcome is RepairOutcome.PROVADO and first.changed
    assert second.outcome is RepairOutcome.PROVADO and not second.changed
    assert not cache.exists() and not temp.exists() and outside.read_bytes() == b"preservar"


def test_limpeza_recusa_escape_raiz_duplicidade_sobreposicao_e_reparse(tmp_path, monkeypatch):
    root = tmp_path / "runtime"; root.mkdir()
    with pytest.raises(ValueError, match="relativo confinado"):
        RegisteredCleanupTarget(root, Path("../fora"))
    with pytest.raises(ValueError, match="relativo confinado"):
        RegisteredCleanupTarget(root, Path("cache:stream"))
    with pytest.raises(ValueError, match="ampla demais"):
        RegisteredCleanupTarget(Path(root.anchor), Path("cache"))
    duplicate = RegisteredCleanupTarget(root, Path("cache"))
    (root / "cache" / "filho").mkdir(parents=True)
    service = GreenRepairService(audit=Audit(), cleanup_targets=(duplicate, duplicate))
    assert service.execute(request(GreenRepair.REGISTERED_CACHE)).outcome is RepairOutcome.FALHOU

    nested = RegisteredCleanupTarget(root, Path("cache/filho"))
    service = GreenRepairService(audit=Audit(), cleanup_targets=(duplicate, nested))
    assert service.execute(request(GreenRepair.REGISTERED_CACHE, "00000002")).outcome is RepairOutcome.FALHOU

    original = GreenRepairService._is_link_or_reparse
    monkeypatch.setattr(
        GreenRepairService,
        "_is_link_or_reparse",
        staticmethod(lambda path: Path(path).name == "filho" or original(Path(path))),
    )
    service = GreenRepairService(audit=Audit(), cleanup_targets=(duplicate,))
    result = service.execute(request(GreenRepair.REGISTERED_CACHE, "00000003"))
    assert result.outcome is RepairOutcome.FALHOU
    assert (root / "cache" / "filho").is_dir()


def test_limpeza_reverte_movimentos_se_postcheck_falha(tmp_path, monkeypatch):
    root = tmp_path / "runtime"; target = root / "cache"
    target.mkdir(parents=True); (target / "x").write_text("x", encoding="utf-8")
    real_lexists = __import__("os").path.lexists
    injected = {"done": False}

    def inconsistent(path):
        value = Path(path)
        if value == target and not real_lexists(path) and not injected["done"]:
            injected["done"] = True
            return True
        return real_lexists(path)

    # O postcheck enxerga o alvo como ainda presente; a quarentena precisa voltar.
    monkeypatch.setattr("services.help_center_repair_service.os.path.lexists", inconsistent)
    result = GreenRepairService(
        audit=Audit(), cleanup_targets=(RegisteredCleanupTarget(root, Path("cache")),)
    ).execute(request(GreenRepair.REGISTERED_CACHE))
    assert result.outcome is RepairOutcome.REVERTIDO
    assert target.exists()


def test_reinicio_nabi_usa_somente_callbacks_tipados_e_prova_nova_geracao():
    state = {"snapshot": NabiRuntimeSnapshot("g1", True)}
    calls = []
    port = NabiRestartCallbacks(
        snapshot=lambda: state["snapshot"],
        restart=lambda: (calls.append("restart"), state.__setitem__("snapshot", NabiRuntimeSnapshot("g2", True)))[1],
        rollback=lambda snapshot: state.__setitem__("snapshot", snapshot),
    )
    result = GreenRepairService(audit=Audit(), nabi_runtime=port).execute(
        request(GreenRepair.NABI_RUNTIME)
    )
    assert result.outcome is RepairOutcome.PROVADO and calls == ["restart"]
    assert result.technical_id == "nabi:callback"


def test_reinicio_nabi_reverte_quando_nao_comprova_saude():
    before = NabiRuntimeSnapshot("g1", True)
    state = {"snapshot": before}
    port = NabiRestartCallbacks(
        snapshot=lambda: state["snapshot"],
        restart=lambda: state.__setitem__("snapshot", NabiRuntimeSnapshot("g2", False)),
        rollback=lambda snapshot: state.__setitem__("snapshot", snapshot),
    )
    result = GreenRepairService(audit=Audit(), nabi_runtime=port).execute(
        request(GreenRepair.NABI_RUNTIME)
    )
    assert result.outcome is RepairOutcome.REVERTIDO and state["snapshot"] == before


def test_cache_relatorios_regenera_exclusivamente_pela_porta_e_reverte():
    before = ReportCacheSnapshot("r1", True)
    state = {"snapshot": before}
    calls = []
    port = ReportCacheCallbacks(
        snapshot=lambda: state["snapshot"],
        regenerate=lambda: (calls.append("regenerate"), state.__setitem__("snapshot", ReportCacheSnapshot("r2", False)))[1],
        rollback=lambda snapshot: state.__setitem__("snapshot", snapshot),
    )
    result = GreenRepairService(audit=Audit(), report_cache=port).execute(
        request(GreenRepair.REPORT_CACHE)
    )
    assert calls == ["regenerate"] and result.outcome is RepairOutcome.REVERTIDO
    assert state["snapshot"] == before


def test_falha_da_auditoria_estrita_bloqueia_qualquer_mutacao():
    calls = []

    def broken_audit(_event):
        raise RuntimeError("indisponível")

    port = NabiRestartCallbacks(
        snapshot=lambda: NabiRuntimeSnapshot("g1", True),
        restart=lambda: calls.append("restart"),
        rollback=lambda _snapshot: calls.append("rollback"),
    )
    with pytest.raises(StrictAuditError, match="bloqueado"):
        GreenRepairService(audit=broken_audit, nabi_runtime=port).execute(
            request(GreenRepair.NABI_RUNTIME)
        )
    assert calls == []


def test_falha_da_auditoria_no_postcheck_reverte_preferencias():
    original = {"mode": "inválido"}
    state = {"value": original}

    def audit(event):
        if event.phase is RepairPhase.POSTCHECK:
            raise RuntimeError("auditoria indisponível")

    port = VisualPreferencesCallbacks(
        snapshot=lambda: state["value"],
        is_valid=lambda values: values.get("mode") == "Intermediário",
        normalize=lambda _values: {"mode": "Intermediário"},
        replace=lambda values: state.__setitem__("value", dict(values)),
    )
    with pytest.raises(StrictAuditError):
        GreenRepairService(audit=audit, visual_preferences=port).execute(
            request(GreenRepair.VISUAL_PREFERENCES)
        )
    assert state["value"] == original


def test_falha_da_auditoria_no_postcheck_reverte_quarentena(tmp_path):
    root = tmp_path / "runtime"; target = root / "cache"
    target.mkdir(parents=True); (target / "x").write_text("conteúdo", encoding="utf-8")

    def audit(event):
        if event.phase in {RepairPhase.POSTCHECK, RepairPhase.ROLLBACK}:
            raise RuntimeError("auditoria indisponível")

    with pytest.raises(StrictAuditError):
        GreenRepairService(
            audit=audit, cleanup_targets=(RegisteredCleanupTarget(root, Path("cache")),)
        ).execute(request(GreenRepair.REGISTERED_CACHE))
    assert (target / "x").read_text(encoding="utf-8") == "conteúdo"


def test_servico_nao_importa_ia_shell_banco_processo_ou_dominios_proibidos():
    source_path = Path(__file__).parents[1] / "services" / "help_center_repair_service.py"
    source = source_path.read_text(encoding="utf-8")
    modules = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            modules.extend(alias.name.lower() for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            modules.append(str(node.module or "").lower())
    forbidden = (
        "assistant_nabi", "main_qt", "subprocess", "sqlite", "database", "backup",
        "update", "licensing", "fiscal", "sefaz", "caixa", "estoque", "venda",
    )
    assert not any(word in module for module in modules for word in forbidden)
    assert "kill(" not in source.lower() and "system(" not in source.lower()
