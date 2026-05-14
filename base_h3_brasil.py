"""Wrapper legado para o pipeline M1 de base H3 nacional."""

from __future__ import annotations

import sys

from motor_expansao.pipelines.m1 import base_h3_brasil as _impl

if __name__ == "__main__":
    _impl.main()
else:
    sys.modules[__name__] = _impl
