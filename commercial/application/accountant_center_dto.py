from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class AccountantPackagePlan:
    cnpj: str
    competence: str
    profile: str
    output_path: str
    reviewed_by: str
    fingerprint: str

    @classmethod
    def create(cls, *, cnpj: str, competence: str, profile: str,
               output_path: str, reviewed_by: str) -> "AccountantPackagePlan":
        payload = {
            "cnpj": cnpj, "competence": competence, "profile": profile,
            "output_path": output_path, "reviewed_by": reviewed_by,
        }
        fingerprint = hashlib.sha256(
            json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        return cls(**payload, fingerprint=fingerprint)


@dataclass(frozen=True, slots=True)
class AccountantPackageOutcome:
    path: str
    cnpj: str
    competence: str
    profile: str
    status: str
    files: int
    movements: int
    pendencies: int
    package_sha256: str = ""

