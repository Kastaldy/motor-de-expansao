"""Wrapper legado para enriquecimento e priorizacao oficial do M1."""

from __future__ import annotations

import sys

from motor_expansao.pipelines.m1 import hex_enrichment as _impl

if __name__ == "__main__":
    _impl.main()
else:
    sys.modules[__name__] = _impl
