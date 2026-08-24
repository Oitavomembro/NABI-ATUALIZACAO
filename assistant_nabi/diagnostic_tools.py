from __future__ import annotations

import subprocess
import os
from dataclasses import dataclass
from pathlib import Path

from .contracts import (
    CapabilityLevel,
    ParameterDefinition,
    ParameterType,
    ToolDefinition,
    ToolKind,
    ToolRequest,
    ToolSchema,
)


SAFE_SUITES = ("ia_nabi", "commercial", "qt_commercial")

RUN_TEST_SUITE = ToolDefinition(
    "diagnostico.executar_testes",
    ToolKind.READ,
    CapabilityLevel.READ,
    "technical",
    "view",
    ToolSchema((ParameterDefinition(
        "suite", ParameterType.TEXT, required=True,
        max_length=30, allowed_values=SAFE_SUITES,
    ),)),
)


@dataclass(frozen=True, slots=True)
class SuiteExecution:
    suite: str
    return_code: int
    output: str
    timed_out: bool = False


class FixedSuiteTestRunner:
    """Executa somente comandos definidos pelo NabiCode, nunca texto do modelo."""

    def __init__(
        self,
        *,
        python_executable: Path,
        workspace: Path,
        timeout_seconds: int = 180,
    ) -> None:
        self._python = Path(python_executable).resolve()
        self._workspace = Path(workspace).resolve()
        if not self._python.is_file() or not self._workspace.is_dir():
            raise ValueError("Runtime ou workspace de testes inválido.")
        self._timeout = max(10, min(int(timeout_seconds), 900))
        self._commands = {
            "ia_nabi": ("-m", "unittest", "tests.test_assistant_nabi_phase0"),
            "commercial": ("-m", "unittest", "discover", "-s", "tests", "-p", "test_commercial_*.py"),
            "qt_commercial": ("-m", "unittest", "tests.test_ui_qt_pdv"),
        }

    def run(self, suite: str) -> SuiteExecution:
        command = self._commands.get(str(suite))
        if command is None:
            raise ValueError("Suíte de testes não autorizada.")
        try:
            environment = os.environ.copy()
            environment["QT_QPA_PLATFORM"] = "offscreen"
            completed = subprocess.run(
                (str(self._python), *command),
                cwd=self._workspace,
                capture_output=True,
                text=True,
                timeout=self._timeout,
                shell=False,
                env=environment,
                check=False,
            )
        except subprocess.TimeoutExpired as error:
            output = f"{error.stdout or ''}\n{error.stderr or ''}"[-20_000:]
            return SuiteExecution(str(suite), -1, output, True)
        output = f"{completed.stdout}\n{completed.stderr}"[-20_000:]
        return SuiteExecution(str(suite), completed.returncode, output)


class RunTestSuiteTool:
    def __init__(self, runner) -> None:
        self._runner = runner

    def execute(self, request: ToolRequest, *, actor) -> dict:
        execution = self._runner.run(request.parameters["suite"])
        return {
            "suite": execution.suite,
            "passed": execution.return_code == 0 and not execution.timed_out,
            "return_code": execution.return_code,
            "timed_out": execution.timed_out,
            "output": execution.output,
        }


def register_diagnostic_test_tool(registry, runner) -> None:
    """Registro explícito: a ferramenta não é habilitada na inicialização comum."""

    registry.register(RUN_TEST_SUITE, RunTestSuiteTool(runner))
