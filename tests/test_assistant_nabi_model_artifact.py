from __future__ import annotations

import hashlib
import tempfile
import unittest
from pathlib import Path

from assistant_nabi import ModelArtifactManifest, verify_model_artifact


class NabiModelArtifactTests(unittest.TestCase):
    def manifest(self, content: bytes, **changes) -> ModelArtifactManifest:
        values = {
            "model_id": "qwen3-1.7b-instruct-q4",
            "filename": "qwen3-1.7b-instruct-q4.gguf",
            "quantization": "Q4",
            "source_url": "https://example.invalid/model.gguf",
            "source_revision": "0123456789abcdef",
            "license_id": "Apache-2.0",
            "sha256": hashlib.sha256(content).hexdigest(),
            "size_bytes": len(content),
        }
        values.update(changes)
        return ModelArtifactManifest(**values)

    def test_libera_somente_arquivo_com_tamanho_e_hash_exatos(self):
        content = b"GGUF-peso-sintetico"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "qwen3-1.7b-instruct-q4.gguf"
            path.write_bytes(content)
            verified = verify_model_artifact(
                self.manifest(content), model_directory=Path(directory), chunk_size=4
            )
            self.assertEqual(verified, path.resolve())

    def test_adulteracao_e_truncamento_falham_fechados(self):
        original = b"GGUF-original"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "qwen3-1.7b-instruct-q4.gguf"
            manifest = self.manifest(original)
            for changed in (b"GGUF-alterado", b"GGUF"):
                with self.subTest(changed=changed):
                    path.write_bytes(changed)
                    with self.assertRaisesRegex(ValueError, "tamanho|SHA-256"):
                        verify_model_artifact(manifest, model_directory=Path(directory))

    def test_arquivo_ausente_nao_e_baixado_nem_criado(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with self.assertRaises(FileNotFoundError):
                verify_model_artifact(self.manifest(b"peso"), model_directory=root)
            self.assertEqual(tuple(root.iterdir()), ())

    def test_manifesto_recusa_caminho_origem_revisao_hash_e_tamanho_invalidos(self):
        content = b"peso"
        invalid = (
            {"filename": "../modelo.gguf"},
            {"filename": "modelo.bin"},
            {"source_url": "http://example.invalid/model.gguf"},
            {"source_url": "https://user:secret@example.invalid/model.gguf"},
            {"source_revision": "main"},
            {"sha256": "0" * 63},
            {"size_bytes": 0},
            {"license_id": ""},
        )
        for changes in invalid:
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                self.manifest(content, **changes)


if __name__ == "__main__":
    unittest.main()
