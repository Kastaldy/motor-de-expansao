"""Ponto de entrada de `python -m motor_expansao.db`. A logica vive em `cli.py`."""

from __future__ import annotations

import sys

from .cli import main

if __name__ == "__main__":
    sys.exit(main())
