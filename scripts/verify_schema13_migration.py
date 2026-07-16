from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from english_typing_trainer.services.migration_verification import (  # noqa: E402
    MigrationVerificationError,
    verify_migration_copy,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Create a consistent SQLite copy, migrate only that copy to the latest "
            "schema, and compare non-sensitive row-count summaries."
        )
    )
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        report = verify_migration_copy(args.source, args.output)
    except (MigrationVerificationError, OSError) as exc:
        detail = (
            str(exc)
            if isinstance(exc, MigrationVerificationError)
            else "A database file could not be read or written."
        )
        print(
            f"Migration verification failed ({type(exc).__name__}): {detail}",
            file=sys.stderr,
        )
        return 1
    print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
