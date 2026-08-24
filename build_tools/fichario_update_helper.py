from __future__ import annotations

import argparse

from services.update_package_service import apply_prepared_update, rollback_prepared_update


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--state", required=True)
    parser.add_argument("--pid", required=True, type=int)
    parser.add_argument("--launcher", required=True)
    parser.add_argument("--source-main")
    parser.add_argument("--process-started-at", type=float)
    parser.add_argument("--rollback", action="store_true")
    args = parser.parse_args(argv)
    operation = rollback_prepared_update if args.rollback else apply_prepared_update
    return operation(
        args.state, pid=args.pid, launcher=args.launcher,
        source_main=args.source_main, process_started_at=args.process_started_at,
    )


if __name__ == "__main__":
    raise SystemExit(main())
