from __future__ import annotations

import os
import secrets
import subprocess
import time
from pathlib import Path
from urllib.request import Request, urlopen

from .local_provider import LocalOpenAICompatibleModelAdapter
from .model_artifact import ModelArtifactManifest, verify_model_artifact
from .runtime_artifact import RuntimeDirectoryManifest, verify_runtime_directory


class LocalLlamaServer:
    """Supervisiona um llama-server local autenticado, sem expor sua chave."""

    def __init__(
        self,
        *,
        runtime_manifest: RuntimeDirectoryManifest,
        runtime_directory: Path,
        manifest: ModelArtifactManifest,
        model_directory: Path,
        log_directory: Path,
        port: int = 18080,
        context_size: int = 2048,
        threads: int = 4,
    ) -> None:
        self._executable = verify_runtime_directory(
            runtime_manifest, runtime_directory=Path(runtime_directory)
        )
        self._manifest = manifest
        self._model = verify_model_artifact(
            manifest, model_directory=Path(model_directory)
        )
        self._logs = Path(log_directory).resolve()
        self._port = max(1024, min(int(port), 65535))
        self._context = max(512, min(int(context_size), 8192))
        self._threads = max(1, min(int(threads), 16))
        self._api_key = secrets.token_urlsafe(32)
        self._process: subprocess.Popen | None = None
        self._stdout = None
        self._stderr = None

    @property
    def endpoint(self) -> str:
        return f"http://127.0.0.1:{self._port}/v1/chat/completions"

    @property
    def process_id(self) -> int | None:
        return self._process.pid if self._process is not None else None

    def start(self, *, timeout_seconds: float = 30.0) -> float:
        if self._process is not None:
            raise RuntimeError("O servidor local da Nabi já foi iniciado.")
        self._logs.mkdir(parents=True, exist_ok=True)
        self._stdout = (self._logs / "llama-server.stdout.log").open("ab")
        self._stderr = (self._logs / "llama-server.stderr.log").open("ab")
        environment = dict(os.environ)
        environment["LLAMA_API_KEY"] = self._api_key
        command = [
            str(self._executable),
            "-m", str(self._model),
            "--host", "127.0.0.1",
            "--port", str(self._port),
            "-c", str(self._context),
            "-t", str(self._threads),
            "-ngl", "0",
            "--jinja",
            "--no-webui",
            "--cors-origins", "localhost",
            "--no-cors-credentials",
        ]
        creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        started = time.monotonic()
        try:
            self._process = subprocess.Popen(
                command,
                cwd=str(self._executable.parent),
                env=environment,
                stdin=subprocess.DEVNULL,
                stdout=self._stdout,
                stderr=self._stderr,
                creationflags=creationflags,
            )
            self._wait_until_ready(timeout_seconds)
            return time.monotonic() - started
        except Exception:
            self.stop()
            raise

    def create_model_adapter(self, *, timeout_seconds: float = 30.0):
        if self._process is None or self._process.poll() is not None:
            raise RuntimeError("O servidor local da Nabi não está disponível.")
        return LocalOpenAICompatibleModelAdapter(
            endpoint=self.endpoint,
            model=self._manifest.model_id,
            timeout_seconds=timeout_seconds,
            api_key=self._api_key,
        )

    def stop(self, *, timeout_seconds: float = 5.0) -> None:
        process, self._process = self._process, None
        if process is not None and process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=max(0.1, float(timeout_seconds)))
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
        for stream_name in ("_stdout", "_stderr"):
            stream = getattr(self, stream_name)
            if stream is not None:
                stream.close()
                setattr(self, stream_name, None)

    def _wait_until_ready(self, timeout_seconds: float) -> None:
        deadline = time.monotonic() + max(1.0, min(float(timeout_seconds), 120.0))
        health_url = f"http://127.0.0.1:{self._port}/health"
        while time.monotonic() < deadline:
            if self._process is None or self._process.poll() is not None:
                raise RuntimeError("O servidor local encerrou durante o carregamento.")
            try:
                request = Request(
                    health_url,
                    headers={"Authorization": f"Bearer {self._api_key}"},
                )
                with urlopen(request, timeout=1.0) as response:
                    if response.status == 200:
                        return
            except OSError:
                pass
            time.sleep(0.1)
        raise TimeoutError("O servidor local da Nabi não ficou pronto no prazo.")

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.stop()
