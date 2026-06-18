"""Configuracao compartilhada da suite de testes.

Contem fixtures de ISOLAMENTO/DETERMINISMO que valem para toda a suite. Nada aqui
toca producao (`src/`): sao apenas garantias de reprodutibilidade do ambiente de teste.

## Determinismo do timestamp de PDF (BLK-FIX-14)

`fpdf2` (>=2.8) carimba em CADA instancia de `FPDF` um `/CreationDate` derivado de
`datetime.now(timezone.utc)` capturado no `__init__`, e um `/ID` derivado desse
timestamp. Como `gerar_pdf_relatorio_pontual_censitario` constroi uma instancia nova
de `_UltraPDF` por chamada, dois PDFs gerados com os MESMOS inputs em segundos de
relogio diferentes divergem em alguns bytes (campo de segundos do `/CreationDate` e o
hash `/ID`). Isso tornava `test_classico_template_recente_inalterado` (que compara
`antes == depois` de dois PDFs do template recente) flaky quando as duas geracoes
cruzavam a virada de um segundo — falha de DETERMINISMO de ambiente, nao de logica.

A fixture abaixo congela `datetime.now()` SO dentro dos modulos do `fpdf2` durante os
testes, mantendo todo o resto do `datetime` intacto. Nao mascara o teste: a assercao
`antes == depois` continua validando que gerar o template classico no meio nao mutou
estado compartilhado que afete os bytes do template recente. Apenas remove a unica
fonte de nao-determinismo legitima (o relogio de parede) que nao tem relacao com o que
o teste pretende verificar. Producao (`censo_report.py`) fica INTOCADA.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

# Instante fixo usado para congelar o relogio do fpdf2 nos testes.
_FROZEN_NOW = datetime(2026, 1, 1, 0, 0, 0, tzinfo=UTC)


class _FrozenDateTime(datetime):
    """`datetime` cujo `.now()` e deterministico; demais comportamentos preservados."""

    @classmethod
    def now(cls, tz=None):  # type: ignore[override]
        if tz is not None:
            return _FROZEN_NOW.astimezone(tz)
        return _FROZEN_NOW.replace(tzinfo=None)


@pytest.fixture(autouse=True)
def _freeze_fpdf_clock(monkeypatch):
    """Congela `datetime.now()` dentro do fpdf2 para PDFs reprodutiveis nos testes.

    Patcha o simbolo `datetime` nos modulos do fpdf2 que carimbam timestamp
    (`fpdf.fpdf` para o `/CreationDate` do `__init__`; `fpdf.output` para o `now` do
    XMP), tornando os bytes do PDF independentes do relogio de parede. Se o fpdf2 nao
    estiver instalado/importavel, a fixture e um no-op gracioso.
    """
    try:
        import fpdf.fpdf as _fpdf_mod
        import fpdf.output as _output_mod
    except Exception:  # pragma: no cover - fpdf2 e dependencia base; defensivo
        yield
        return

    if hasattr(_fpdf_mod, "datetime"):
        monkeypatch.setattr(_fpdf_mod, "datetime", _FrozenDateTime)
    if hasattr(_output_mod, "datetime"):
        monkeypatch.setattr(_output_mod, "datetime", _FrozenDateTime)
    yield
