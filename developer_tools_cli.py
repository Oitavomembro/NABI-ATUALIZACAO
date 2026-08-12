from __future__ import annotations

import argparse
from pathlib import Path

from controllers.developer_tools_controller import DeveloperToolsController


def main() -> int:
    parser = argparse.ArgumentParser(description="Ferramentas de desenvolvimento do NabiCode")
    parser.add_argument("action", choices=("validate", "tests", "clean", "versions", "backup"))
    parser.add_argument("--database", default="fichario_moveis.db")
    args = parser.parse_args()

    root = Path(__file__).resolve().parent
    try:
        result = DeveloperToolsController(root).execute(args.action, database_name=args.database)
    except FileNotFoundError as exc:
        raise SystemExit(str(exc)) from exc
    print(result.text)
    return result.exit_code


if __name__ == "__main__":
    raise SystemExit(main())
