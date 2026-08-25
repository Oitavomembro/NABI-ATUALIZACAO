from __future__ import annotations

import base64
import hashlib
import json
import os
import struct
from dataclasses import dataclass
from pathlib import Path

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt


MAGIC = b"NABICODE-BACKUP\x00"
VERSION = 1
MAX_HEADER_SIZE = 4096
MAX_PLAINTEXT_SIZE = 2 * 1024 * 1024 * 1024
TAG_SIZE = 16
CHUNK_SIZE = 1024 * 1024
SCRYPT_N = 2**15
SCRYPT_R = 8
SCRYPT_P = 1


@dataclass(frozen=True, slots=True)
class BackupEnvelopeInfo:
    format: str
    encrypted: bool
    version: int
    plaintext_size: int


def _password_bytes(password: str) -> bytes:
    if not isinstance(password, str) or len(password) < 12:
        raise ValueError("A senha do backup deve possuir ao menos 12 caracteres.")
    if len(password) > 1024:
        raise ValueError("A senha do backup excede o limite permitido.")
    return password.encode("utf-8")


def _derive_key(password: str, salt: bytes) -> bytes:
    return Scrypt(salt=salt, length=32, n=SCRYPT_N, r=SCRYPT_R, p=SCRYPT_P).derive(
        _password_bytes(password)
    )


def _canonical_header(*, salt: bytes, nonce: bytes, plaintext_size: int) -> bytes:
    header = {
        "cipher": "AES-256-GCM",
        "kdf": {"name": "scrypt", "n": SCRYPT_N, "p": SCRYPT_P, "r": SCRYPT_R},
        "nonce": base64.b64encode(nonce).decode("ascii"),
        "plaintext_size": int(plaintext_size),
        "salt": base64.b64encode(salt).decode("ascii"),
        "version": VERSION,
    }
    return json.dumps(header, sort_keys=True, separators=(",", ":")).encode("ascii")


def encrypt_database(source: Path, destination: Path, password: str) -> BackupEnvelopeInfo:
    size = source.stat().st_size
    if size <= 0 or size > MAX_PLAINTEXT_SIZE:
        raise ValueError("O banco excede o limite seguro do backup criptografado.")
    salt, nonce = os.urandom(16), os.urandom(12)
    header = _canonical_header(salt=salt, nonce=nonce, plaintext_size=size)
    encryptor = Cipher(algorithms.AES(_derive_key(password, salt)), modes.GCM(nonce)).encryptor()
    encryptor.authenticate_additional_data(header)
    with destination.open("xb") as stream:
        stream.write(MAGIC)
        stream.write(struct.pack(">I", len(header)))
        stream.write(header)
        with source.open("rb") as plain:
            for chunk in iter(lambda: plain.read(CHUNK_SIZE), b""):
                stream.write(encryptor.update(chunk))
        stream.write(encryptor.finalize())
        stream.write(encryptor.tag)
        stream.flush()
        os.fsync(stream.fileno())
    return BackupEnvelopeInfo("NABICODE_ENCRYPTED_V1", True, VERSION, size)


def inspect_envelope(path: Path) -> BackupEnvelopeInfo:
    with path.open("rb") as stream:
        if stream.read(len(MAGIC)) != MAGIC:
            return BackupEnvelopeInfo("SQLITE_LEGACY_UNENCRYPTED", False, 0, path.stat().st_size)
        raw_length = stream.read(4)
        if len(raw_length) != 4:
            raise ValueError("Cabeçalho do backup criptografado está truncado.")
        header_length = struct.unpack(">I", raw_length)[0]
        if not 1 <= header_length <= MAX_HEADER_SIZE:
            raise ValueError("Tamanho do cabeçalho do backup é inválido.")
        header = stream.read(header_length)
        if len(header) != header_length:
            raise ValueError("Cabeçalho do backup criptografado está truncado.")
    parsed = _parse_header(header)
    expected = len(MAGIC) + 4 + header_length + parsed["plaintext_size"] + TAG_SIZE
    if path.stat().st_size != expected:
        raise ValueError("Tamanho do backup criptografado é divergente.")
    return BackupEnvelopeInfo(
        "NABICODE_ENCRYPTED_V1", True, VERSION, parsed["plaintext_size"]
    )


def decrypt_database(source: Path, destination: Path, password: str) -> BackupEnvelopeInfo:
    info = inspect_envelope(source)
    if not info.encrypted:
        raise ValueError("O arquivo informado é um backup legado não criptografado.")
    stream = source.open("rb")
    try:
        stream.read(len(MAGIC))
        header_length = struct.unpack(">I", stream.read(4))[0]
        header = stream.read(header_length)
        ciphertext_size = info.plaintext_size
        stream.seek(-TAG_SIZE, os.SEEK_END)
        tag = stream.read(TAG_SIZE)
        stream.seek(len(MAGIC) + 4 + header_length)
        parsed = _parse_header(header)
        decryptor = Cipher(
            algorithms.AES(_derive_key(password, parsed["salt"])),
            modes.GCM(parsed["nonce"], tag),
        ).decryptor()
        decryptor.authenticate_additional_data(header)
        written = 0
        with destination.open("xb") as output:
            remaining = ciphertext_size
            while remaining:
                chunk = stream.read(min(CHUNK_SIZE, remaining))
                if not chunk:
                    raise ValueError("Conteúdo criptografado está truncado.")
                decrypted = decryptor.update(chunk)
                output.write(decrypted)
                written += len(decrypted)
                remaining -= len(chunk)
            output.write(decryptor.finalize())
            output.flush()
            os.fsync(output.fileno())
    except InvalidTag as exc:
        destination.unlink(missing_ok=True)
        raise ValueError("Senha incorreta ou backup criptografado adulterado.") from exc
    except Exception:
        destination.unlink(missing_ok=True)
        raise
    finally:
        stream.close()
    if written != info.plaintext_size:
        destination.unlink(missing_ok=True)
        raise ValueError("Conteúdo descriptografado possui tamanho divergente.")
    return info


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _parse_header(raw: bytes) -> dict:
    try:
        header = json.loads(raw.decode("ascii"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("Cabeçalho do backup criptografado é inválido.") from exc
    if not isinstance(header, dict) or set(header) != {
        "cipher", "kdf", "nonce", "plaintext_size", "salt", "version"
    }:
        raise ValueError("Campos do cabeçalho do backup são inválidos.")
    if header["version"] != VERSION or header["cipher"] != "AES-256-GCM":
        raise ValueError("Versão ou cifra do backup não é suportada.")
    if header["kdf"] != {"name": "scrypt", "n": SCRYPT_N, "p": SCRYPT_P, "r": SCRYPT_R}:
        raise ValueError("Parâmetros de derivação do backup são inválidos.")
    size = header["plaintext_size"]
    if type(size) is not int or not 1 <= size <= MAX_PLAINTEXT_SIZE:
        raise ValueError("Tamanho declarado do backup é inválido.")
    try:
        salt = base64.b64decode(header["salt"], validate=True)
        nonce = base64.b64decode(header["nonce"], validate=True)
    except (TypeError, ValueError) as exc:
        raise ValueError("Salt ou nonce do backup é inválido.") from exc
    if len(salt) != 16 or len(nonce) != 12:
        raise ValueError("Salt ou nonce do backup possui tamanho inválido.")
    return {"salt": salt, "nonce": nonce, "plaintext_size": size}
