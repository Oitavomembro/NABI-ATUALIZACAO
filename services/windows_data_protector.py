from __future__ import annotations

import ctypes
import os
from ctypes import wintypes


class WindowsDataProtectionError(RuntimeError):
    pass


class _DataBlob(ctypes.Structure):
    _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_byte))]


class WindowsDataProtector:
    """Protege dados com DPAPI; o padrão permanece o usuário atual do Windows."""

    description = "NabiCode Fiscal A1"
    CRYPTPROTECT_LOCAL_MACHINE = 0x4

    def __init__(self, *, description: str | None = None, machine_scope: bool = False) -> None:
        self.description = str(description or self.description)
        self.machine_scope = bool(machine_scope)

    @staticmethod
    def _blob(data: bytes) -> tuple[_DataBlob, object]:
        buffer = ctypes.create_string_buffer(data)
        return _DataBlob(len(data), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_byte))), buffer

    def protect(self, data: bytes) -> bytes:
        if os.name != "nt":
            raise WindowsDataProtectionError("A proteção DPAPI exige Windows.")
        source, source_buffer = self._blob(bytes(data))
        output = _DataBlob()
        crypt32 = ctypes.windll.crypt32
        kernel32 = ctypes.windll.kernel32
        ok = crypt32.CryptProtectData(
            ctypes.byref(source), self.description, None, None, None,
            self.CRYPTPROTECT_LOCAL_MACHINE if self.machine_scope else 0,
            ctypes.byref(output),
        )
        del source_buffer
        if not ok:
            raise WindowsDataProtectionError("O Windows não conseguiu proteger a credencial fiscal.")
        try:
            return ctypes.string_at(output.pbData, output.cbData)
        finally:
            kernel32.LocalFree(output.pbData)

    def unprotect(self, data: bytes) -> bytes:
        if os.name != "nt":
            raise WindowsDataProtectionError("A proteção DPAPI exige Windows.")
        source, source_buffer = self._blob(bytes(data))
        output = _DataBlob()
        crypt32 = ctypes.windll.crypt32
        kernel32 = ctypes.windll.kernel32
        ok = crypt32.CryptUnprotectData(
            ctypes.byref(source), None, None, None, None, 0, ctypes.byref(output)
        )
        del source_buffer
        if not ok:
            raise WindowsDataProtectionError(
                "A credencial fiscal pertence a outro usuário do Windows ou foi corrompida."
            )
        try:
            return ctypes.string_at(output.pbData, output.cbData)
        finally:
            kernel32.LocalFree(output.pbData)
