from __future__ import annotations

import argparse
import sys
from pathlib import Path

from controllers.release_package_controller import ReleasePackageController
from helpers.file_hashing import sha256_file

ROOT = Path(__file__).resolve().parent
VERSION = (ROOT / "VERSAO.txt").read_text(encoding="utf-8").strip()


sha256 = sha256_file


def locate_release() -> Path:
    try:
        return ReleasePackageController(ROOT, VERSION).locate_release()
    except FileNotFoundError as exc:
        raise SystemExit(str(exc)) from exc


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--minimum-source", required=True)
    parser.add_argument("--accepted-source", action="append", default=[])
    parser.add_argument("--remove", action="append", default=[])
    args = parser.parse_args()

    try:
        output = ReleasePackageController(ROOT, VERSION).create(
            minimum_source=args.minimum_source,
            accepted_sources=args.accepted_source,
            remove=args.remove,
        )
    except (FileNotFoundError, ValueError, RuntimeError) as exc:
        raise SystemExit(str(exc)) from exc
    print(output)
    return 0


if __name__ == "__main__":
    sys.exit(main())
