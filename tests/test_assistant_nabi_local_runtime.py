from __future__ import annotations

import hashlib
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from assistant_nabi.local_runtime import LocalLlamaServer
from assistant_nabi.model_artifact import ModelArtifactManifest
from assistant_nabi.runtime_artifact import RuntimeDirectoryManifest


class LocalRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.runtime_directory = self.root / "runtime"
        self.model_directory = self.root / "models"
        self.runtime_directory.mkdir()
        self.model_directory.mkdir()
        self.executable = self.runtime_directory / "llama-server.exe"
        self.executable.write_bytes(b"runtime")
        self.model = self.model_directory / "model.gguf"
        self.model.write_bytes(b"GGUF-model")
        self.manifest = ModelArtifactManifest(
            model_id="qwen-local",
            filename=self.model.name,
            quantization="Q4_K_M",
            source_url="https://example.invalid/model.gguf",
            source_revision="0123456789abcdef",
            license_id="Apache-2.0",
            sha256=hashlib.sha256(self.model.read_bytes()).hexdigest(),
            size_bytes=self.model.stat().st_size,
        )
        tree = hashlib.sha256()
        for path in sorted(
            (item for item in self.runtime_directory.rglob("*") if item.is_file()),
            key=lambda item: item.relative_to(self.runtime_directory).as_posix(),
        ):
            tree.update(path.relative_to(self.runtime_directory).as_posix().encode("utf-8"))
            tree.update(b"\0")
            tree.update(path.read_bytes())
        self.runtime_manifest = RuntimeDirectoryManifest(
            version="test",
            source_commit="0123456789abcdef",
            archive_url="https://github.com/ggml-org/llama.cpp/releases/test.zip",
            archive_sha256="a" * 64,
            file_count=1,
            tree_sha256=tree.hexdigest(),
        )

    def runtime(self):
        return LocalLlamaServer(
            runtime_manifest=self.runtime_manifest,
            runtime_directory=self.runtime_directory,
            manifest=self.manifest,
            model_directory=self.model_directory,
            log_directory=self.root / "logs",
            port=18081,
        )

    @patch("assistant_nabi.local_runtime.urlopen")
    @patch("assistant_nabi.local_runtime.subprocess.Popen")
    def test_inicia_oculto_loopback_sem_webui_e_com_chave_em_memoria(
        self, popen, urlopen
    ):
        process = Mock(pid=91)
        process.poll.return_value = None
        process.wait.return_value = 0
        popen.return_value = process
        response = Mock(status=200)
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=False)
        urlopen.return_value = response
        runtime = self.runtime()
        runtime.start()
        command = popen.call_args.args[0]
        environment = popen.call_args.kwargs["env"]
        self.assertIn("--no-webui", command)
        self.assertIn("--no-cors-credentials", command)
        self.assertEqual(command[command.index("--host") + 1], "127.0.0.1")
        self.assertNotIn(environment["LLAMA_API_KEY"], command)
        self.assertNotIn(environment["LLAMA_API_KEY"], runtime.endpoint)
        adapter = runtime.create_model_adapter()
        self.assertTrue(adapter._api_key)
        runtime.stop()
        process.terminate.assert_called_once()

    @patch("assistant_nabi.local_runtime.urlopen", side_effect=OSError("offline"))
    @patch("assistant_nabi.local_runtime.subprocess.Popen")
    def test_falha_de_carga_encerra_processo_e_fecha_logs(self, popen, _urlopen):
        process = Mock(pid=92)
        process.poll.return_value = 1
        popen.return_value = process
        runtime = self.runtime()
        with self.assertRaisesRegex(RuntimeError, "encerrou"):
            runtime.start(timeout_seconds=1)
        self.assertIsNone(runtime.process_id)
        self.assertIsNone(runtime._stdout)
        self.assertIsNone(runtime._stderr)

    def test_recusa_peso_adulterado_antes_de_iniciar_runtime(self):
        self.model.write_bytes(b"GGUF-adulterado")
        with self.assertRaisesRegex(ValueError, "tamanho|SHA-256"):
            self.runtime()


if __name__ == "__main__":
    unittest.main()
