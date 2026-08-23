from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse


_SHA256 = re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True, slots=True)
class RuntimeDirectoryManifest:
    version: str
    source_commit: str
    archive_url: str
    archive_sha256: str
    file_count: int
    tree_sha256: str
    executable_name: str = "llama-server.exe"

    def __post_init__(self) -> None:
        source = urlparse(str(self.archive_url))
        if source.scheme != "https" or source.hostname != "github.com":
            raise ValueError("O runtime deve vir de um artefato HTTPS oficial no GitHub.")
        for name in ("version", "source_commit", "executable_name"):
            if not str(getattr(self, name) or "").strip():
                raise ValueError(f"Campo obrigatório ausente no runtime: {name}.")
        for name in ("archive_sha256", "tree_sha256"):
            value = str(getattr(self, name) or "").strip().casefold()
            if not _SHA256.fullmatch(value):
                raise ValueError(f"SHA-256 inválido no runtime: {name}.")
            object.__setattr__(self, name, value)
        if int(self.file_count) <= 0:
            raise ValueError("A quantidade de arquivos do runtime é inválida.")
        object.__setattr__(self, "file_count", int(self.file_count))


def verify_runtime_directory(
    manifest: RuntimeDirectoryManifest, *, runtime_directory: Path
) -> Path:
    root = Path(runtime_directory).resolve(strict=True)
    files = sorted(
        (path for path in root.rglob("*") if path.is_file()),
        key=lambda path: path.relative_to(root).as_posix(),
    )
    if len(files) != manifest.file_count:
        raise ValueError("A quantidade de arquivos do runtime diverge do manifesto.")
    digest = hashlib.sha256()
    for path in files:
        relative = path.relative_to(root).as_posix()
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        with path.open("rb") as stream:
            while block := stream.read(1024 * 1024):
                digest.update(block)
    if digest.hexdigest() != manifest.tree_sha256:
        raise ValueError("A integridade do runtime local diverge do manifesto.")
    executable = (root / manifest.executable_name).resolve(strict=True)
    if not executable.is_file():
        raise ValueError("O executável homologado do runtime não foi encontrado.")
    return executable


LLAMA_CPP_B10537_CPU_X64 = RuntimeDirectoryManifest(
    version="b10537",
    source_commit="bf0040e15fd5b716262658f4d652c9cee959cf91",
    archive_url=(
        "https://github.com/ggml-org/llama.cpp/releases/download/b10537/"
        "llama-b10537-bin-win-cpu-x64.zip"
    ),
    archive_sha256="48d02dfdc5a715d1f58e06b9c9622bb548eb214b021af027808c9e8c124c4dec",
    file_count=52,
    tree_sha256="8d32024aab57571fd10931d50626b0000d39f5e9040f8cc568c98d5466dd931c",
)
