from __future__ import annotations

from .cli import main as run_main


def main() -> None:
    raise SystemExit(run_main())


if __name__ == "__main__":
    main()
