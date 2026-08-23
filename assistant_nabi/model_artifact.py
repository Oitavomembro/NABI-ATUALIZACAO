from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse


_SHA256 = re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True, slots=True)
class ModelArtifactManifest:
    """Evidência versionada de um peso previamente selecionado e homologado."""

    model_id: str
    filename: str
    quantization: str
    source_url: str
    source_revision: str
    license_id: str
    sha256: str
    size_bytes: int

    def __post_init__(self) -> None:
        for field_name in (
            "model_id",
            "filename",
            "quantization",
            "source_url",
            "source_revision",
            "license_id",
            "sha256",
        ):
            value = str(getattr(self, field_name) or "").strip()
            if not value:
                raise ValueError(f"Campo obrigatório ausente no manifesto: {field_name}.")
            object.__setattr__(self, field_name, value)

        filename = Path(self.filename)
        if filename.name != self.filename or filename.suffix.casefold() != ".gguf":
            raise ValueError("O manifesto deve apontar para um único arquivo GGUF local.")
        source = urlparse(self.source_url)
        if source.scheme != "https" or not source.hostname or source.username or source.password:
            raise ValueError("A origem do modelo deve ser uma URL HTTPS pública sem credenciais.")
        if self.source_revision.casefold() in {"main", "master", "latest", "head"}:
            raise ValueError("A revisão de origem do modelo deve ser imutável.")
        digest = self.sha256.casefold()
        if not _SHA256.fullmatch(digest):
            raise ValueError("O SHA-256 do modelo é inválido.")
        object.__setattr__(self, "sha256", digest)
        if int(self.size_bytes) <= 0:
            raise ValueError("O tamanho esperado do modelo deve ser positivo.")
        object.__setattr__(self, "size_bytes", int(self.size_bytes))


def verify_model_artifact(
    manifest: ModelArtifactManifest,
    *,
    model_directory: Path,
    chunk_size: int = 1024 * 1024,
) -> Path:
    """Valida localização, tamanho e conteúdo antes de liberar o peso ao runtime."""

    root = Path(model_directory).resolve(strict=True)
    candidate = (root / manifest.filename).resolve(strict=True)
    try:
        candidate.relative_to(root)
    except ValueError as error:
        raise ValueError("O arquivo do modelo está fora da área autorizada.") from error
    if not candidate.is_file():
        raise ValueError("O peso homologado não é um arquivo regular.")
    if candidate.stat().st_size != manifest.size_bytes:
        raise ValueError("O tamanho do modelo diverge do manifesto homologado.")

    digest = hashlib.sha256()
    with candidate.open("rb") as stream:
        while block := stream.read(max(4096, int(chunk_size))):
            digest.update(block)
    if not _SHA256.fullmatch(manifest.sha256) or digest.hexdigest() != manifest.sha256:
        raise ValueError("O SHA-256 do modelo diverge do manifesto homologado.")
    return candidate
