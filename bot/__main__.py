"""Allow ``python -m bot`` to work."""

from bot.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
