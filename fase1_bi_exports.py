"""Wrapper legado para exports executivos/BI do M1."""

from __future__ import annotations

import sys

from motor_expansao.pipelines.m1 import fase1_bi_exports as _impl

if __name__ == "__main__":
    _impl.main()
else:
    sys.modules[__name__] = _impl
