from __future__ import annotations

import hashlib
import tempfile
import unittest
from pathlib import Path

from assistant_nabi.runtime_artifact import (
    RuntimeDirectoryManifest,
    verify_runtime_directory,
)


class RuntimeArtifactTests(unittest.TestCase):
    def test_arvore_adulterada_falha_fechada(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            executable = root / "llama-server.exe"
            executable.write_bytes(b"runtime")
            digest = hashlib.sha256(b"llama-server.exe\0runtime").hexdigest()
            manifest = RuntimeDirectoryManifest(
                version="test",
                source_commit="commit",
                archive_url="https://github.com/ggml-org/llama.cpp/releases/test.zip",
                archive_sha256="a" * 64,
                file_count=1,
                tree_sha256=digest,
            )
            self.assertEqual(
                verify_runtime_directory(manifest, runtime_directory=root),
                executable.resolve(),
            )
            executable.write_bytes(b"alterado")
            with self.assertRaisesRegex(ValueError, "integridade"):
                verify_runtime_directory(manifest, runtime_directory=root)


if __name__ == "__main__":
    unittest.main()
