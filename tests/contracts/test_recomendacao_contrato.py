"""Contrato da recomendacao unica (DEC-077): regua BR v1 ancorada, nucleo puro, empacotamento.

- A regua BR v1 e a aprovada no GATE 2 (21/10/2026): 5 vagas; renda domiciliar >= 4.500;
  residual >= 2.000 MEDIDO; score censitario >= 50; populacao >= 10.000; residual estimado
  pode ser Premium (`false`, pendente de confirmacao). Mudar QUALQUER numero exige versao nova
  do arquivo (o `VIGENTE` aponta para ela) + emenda da DEC-077 -- e este teste falha ate isso
  ser feito de proposito.
- O nucleo e PURO: nao importa I/O, env, relogio, aleatoriedade, perfil nem `dashboard`.
- Nenhum modulo do pacote importa `relatorio_municipal` (pesado e CRITICO) nem
  `dashboard.constants`.
- Os arquivos da regua viajam na imagem: `.json` + `VIGENTE` sem extensao, fora do `.gitignore`
  (o hatch empacota o que o git versiona), no mesmo molde dos fatores da renda.
"""

from __future__ import annotations

import ast
import shutil
import subprocess
from pathlib import Path

import pytest

from motor_expansao.recomendacao import carregador as carregador_mod
from motor_expansao.recomendacao import carregar_regra, limpar_cache

_REPO = Path(__file__).resolve().parents[2]
_PACOTE = _REPO / "src" / "motor_expansao" / "recomendacao"


@pytest.fixture(autouse=True)
def _sem_fixacao(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv(carregador_mod.ENV_VERSAO, raising=False)
    limpar_cache()
    yield
    limpar_cache()


def test_regua_br_v1_ancorada() -> None:
    r = carregar_regra("BR")
    assert r is not None
    assert r.versao == "2026-10_v1"
    assert r.pais == "BR"
    assert r.dec == "DEC-077"
    assert r.vagas_por_segmento == 5
    assert r.mata_virgem.renda_domiciliar_min == 4500.0
    assert r.mata_virgem.residual_min == 2000.0
    assert r.mata_virgem.populacao_min is None
    assert r.mata_virgem.exige_residual_medido is True
    assert r.premium.score_min == 50.0
    assert r.premium.populacao_min == 10000.0
    assert r.premium.exige_residual_medido is True
    assert r.fixada_por_env is False


def test_vigente_br_aponta_a_v1() -> None:
    vigente = (_PACOTE / "regra" / "BR" / "VIGENTE").read_text(encoding="utf-8").strip()
    assert vigente == "2026-10_v1"


def test_so_o_brasil_tem_regua() -> None:
    assert sorted(p.name for p in (_PACOTE / "regra").iterdir() if p.is_dir()) == ["BR"]


_PROIBIDOS_NUCLEO = (
    "os",
    "sys",
    "time",
    "datetime",
    "random",
    "pathlib",
    "io",
    "json",
    "logging",
    "motor_expansao.perfil",
    "motor_expansao.dashboard",
    "motor_expansao.renda",
    "motor_expansao.config",
)


def _imports(caminho: Path) -> set[str]:
    arvore = ast.parse(caminho.read_text(encoding="utf-8"))
    nomes: set[str] = set()
    for no in ast.walk(arvore):
        if isinstance(no, ast.Import):
            nomes |= {a.name for a in no.names}
        elif isinstance(no, ast.ImportFrom) and no.module:
            nomes.add(no.module)
    return nomes


def test_nucleo_e_puro() -> None:
    nucleo = _PACOTE / "nucleo.py"
    for nome in _imports(nucleo):
        for proibido in _PROIBIDOS_NUCLEO:
            assert not (nome == proibido or nome.startswith(proibido + ".")), (
                f"nucleo.py importa {nome}: o nucleo tem de ser puro (sem I/O/env/relogio/perfil)"
            )
    texto = nucleo.read_text(encoding="utf-8")
    for chamada in ("open(", "environ", "read_parquet", "default_rng", "now("):
        assert chamada not in texto, f"nucleo.py usa {chamada!r}"


def test_pacote_nao_importa_relatorio_municipal_nem_constants() -> None:
    for arq in sorted(_PACOTE.glob("*.py")):
        for nome in _imports(arq):
            assert "relatorio_municipal" not in nome, f"{arq.name} importa {nome}"
            assert nome != "motor_expansao.dashboard.constants", f"{arq.name} importa {nome}"
            assert not nome.startswith("motor_expansao.dashboard"), f"{arq.name} importa {nome}"


def test_regua_nao_e_ignorada_pelo_git() -> None:
    """O hatch empacota o que o git versiona: um `.gitignore` que pegasse a regua a tiraria da
    imagem em silencio (o `.csv` ja e descartado assim)."""
    git = shutil.which("git")
    if git is None:
        pytest.skip("git ausente")
    arquivos = [
        "src/motor_expansao/recomendacao/regra/BR/2026-10_v1.json",
        "src/motor_expansao/recomendacao/regra/BR/VIGENTE",
    ]
    r = subprocess.run(
        [git, "check-ignore", *arquivos], cwd=_REPO, capture_output=True, text=True, check=False
    )
    assert r.returncode == 1, f"arquivo(s) da regua ignorado(s) pelo git: {r.stdout}"


def test_hatch_empacota_o_pacote_inteiro() -> None:
    texto = (_REPO / "pyproject.toml").read_text(encoding="utf-8")
    assert 'packages = ["src/motor_expansao"]' in texto
