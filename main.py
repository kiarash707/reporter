#!/usr/bin/env python3
"""Backwards-compatible entry point.

Prefer ``python -m bot run``; this file stays so existing services, scripts and
muscle memory keep working.
"""

from __future__ import annotations

from bot.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
