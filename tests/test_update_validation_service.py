from services.update_validation_service import UpdateValidationService


class Package:
    def __init__(self, state): self.state = state; self.calls = []
    def load_state(self): return self.state
    def validate_installed_files(self, state): return state.get("file_errors", [])
    def mark_success(self, state, report): self.calls.append(("success", report))
    def restore_files(self, state): self.calls.append(("restore", state))
    def mark_failure(self, state, error, rolled_back=False): self.calls.append(("failure", error, rolled_back))


class Diagnostics:
    def __init__(self, result): self.result = result
    def run(self, save_report=True): return self.result


def build(package, result, restored):
    return UpdateValidationService(package, lambda: Diagnostics(result), restored.append, "2.4.85")


def test_returns_none_without_pending_update():
    assert build(Package(None), {}, []).validate_after_restart() is None


def test_marks_success_after_files_and_diagnostics_pass():
    package = Package({"status": "ARQUIVOS_APLICADOS", "target_version": "2.4.85", "manifest": {"files": [1]}})
    result = build(package, {"aprovado": True, "arquivo": "diag.json"}, []).validate_after_restart()
    assert result["ok"] is True
    assert package.calls[0][0] == "success"


def test_rolls_back_files_and_snapshot_on_failure():
    package = Package({"status": "ARQUIVOS_APLICADOS", "target_version": "2.4.85", "snapshot_id": "snap-1", "file_errors": ["hash inválido"]})
    restored = []
    result = build(package, {"aprovado": True}, restored).validate_after_restart()
    assert result["ok"] is False
    assert restored == ["snap-1"]
    assert [call[0] for call in package.calls] == ["restore", "failure"]
