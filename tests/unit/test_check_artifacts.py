"""`scripts/check_artifacts.py` nao pode discordar do `/api/health`.

POR QUE ESTE ARQUIVO EXISTE. Sao dois verificadores da MESMA pergunta — "os artefatos que
nao viajam com o codigo estao no lugar?" — em dois ambientes: o `check_artifacts` olha o
disco LOCAL, o `/api/health` olha o ambiente PUBLICADO. O proprio docstring do script ja
registrava o risco em prosa (*"um verificador que discorda do programa verificado e' pior
que nenhum: manda procurar o problema no lugar errado"*), mas nada impedia a divergencia —
e ela aconteceu.

O DEFEITO QUE ELE TRAVA (BLK-MA-19, medido em 2026-08-24). Os pins de M&A (BLK-MA-15 +
DEC-035) entraram no `/api/health` quando o codigo foi escrito, mas ninguem acrescentou os
dois parquets ao `check_artifacts`. Resultado: numa maquina — e num servidor — sem eles, o
script imprimia **"OK: todos os artefatos criticos e de staging presentes"** enquanto a
camada estava morta na tela. A camada ficou fora do ar de 2026-08-19 a 2026-08-24 sem que
nada acusasse.

O INVARIANTE. Todo artefato que o health observa **sob `staging/`** tem de ser nomeado pelo
`check_artifacts`. O recorte e' deliberado e nao e' preguica:

  - `staging/` e' exatamente a classe que **nao vem do git nem da imagem** e so' chega por
    `scp` + bind mount — a classe que some em silencio num deploy.
  - `enriquecido` (sob `outputs/`) fica de fora porque o piloto **nao abre** sem ele: a falta
    e' estrondosa, nao silenciosa, e o script ja cobre `outputs/` pelos CRITICOS.
  - `oportunidades_imobiliarias` fica de fora porque nao mora sob `staging/` nem `outputs/`:
    tem mount PROPRIO (`/app/data/oportunidades`), vem de outro repositorio e tem cadencia de
    coleta propria (DEC-037). Cobri-lo aqui e' assunto de bloco proprio, nao deste teste.

Sem escrita: so' importa os dois modulos e compara listas.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[2]  # tests/unit/ -> raiz do worktree
_SERVER = _REPO / "web" / "server"
if str(_SERVER) not in sys.path:
    sys.path.insert(0, str(_SERVER))

import app as pilot_app  # noqa: E402  (backend do piloto; web/server no sys.path acima)


def _carregar_check_artifacts():
    """Importa o script por caminho — `scripts/` nao e' pacote e nao esta no `sys.path`.

    O modulo guarda o `main()` atras de `if __name__ == "__main__"`, entao importar nao
    executa verificacao nenhuma nem imprime nada.
    """
    caminho = _REPO / "scripts" / "check_artifacts.py"
    spec = importlib.util.spec_from_file_location("_check_artifacts_sob_teste", caminho)
    if spec is None or spec.loader is None:  # pragma: no cover — so' se o arquivo sumir
        pytest.fail(f"nao consegui importar {caminho}")
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


def _relativos_do_verificador(modulo) -> set[str]:
    """Todos os caminhos relativos que o script conhece, em qualquer grupo."""
    grupos = ("CRITICOS", "STAGING_OPCIONAL", "PILOTO_CRESCIMENTO", "PILOTO_MA")
    conhecidos: set[str] = set()
    for nome in grupos:
        for rel, _desc in getattr(modulo, nome):
            conhecidos.add(rel)
    return conhecidos


def _staging_observados_pelo_health() -> dict[str, str]:
    """`{nome no health: caminho relativo posix}` para o que o health observa sob `staging/`."""
    fora: dict[str, str] = {}
    for nome, caminho, _para_que in pilot_app._artefatos_observados():
        try:
            rel = Path(caminho).resolve().relative_to(Path(pilot_app.DATA_DIR).resolve())
        except ValueError:
            # Artefato com mount proprio (imobiliaria) — fora do DATA_DIR, fora do recorte.
            continue
        posix = rel.as_posix()
        if posix.startswith("staging/"):
            fora[nome] = posix
    return fora


def test_todo_artefato_de_staging_do_health_esta_no_check_artifacts() -> None:
    """O invariante. Quebra no dia em que alguem poe um parquet novo no health e esquece aqui."""
    modulo = _carregar_check_artifacts()
    conhecidos = _relativos_do_verificador(modulo)
    observados = _staging_observados_pelo_health()

    # Guarda contra o teste virar vacuo: se o health parar de observar staging, o `<=` passa
    # com o conjunto vazio e o invariante evapora sem ninguem notar.
    assert observados, "o health deixou de observar qualquer artefato de staging — invariante vazio"

    faltando = {nome: rel for nome, rel in observados.items() if rel not in conhecidos}
    assert not faltando, (
        "artefato(s) que o /api/health observa e o check_artifacts ignora: "
        f"{faltando}. Um verificador que diz 'OK' com a camada morta manda o operador "
        "procurar o problema no lugar errado — acrescente ao grupo certo em "
        "scripts/check_artifacts.py."
    )


def test_os_dois_parquets_de_ma_estao_nos_dois_lados() -> None:
    """Trava DIRETA do BLK-MA-19, sem depender do invariante generico acima.

    O teste anterior falharia se alguem removesse a camada do health E do script ao mesmo
    tempo — os dois lados voltariam a concordar, sobre nada. Este aqui nomeia os arquivos.
    """
    modulo = _carregar_check_artifacts()
    conhecidos = _relativos_do_verificador(modulo)
    nomes_no_health = {nome for nome, _c, _p in pilot_app._artefatos_observados()}

    for rel, nome_health in (
        ("staging/vulnerabilidade_ma_nomeadas.parquet", "independentes_nomeadas"),
        ("staging/vulnerabilidade_ma_redes.parquet", "redes_nomeadas"),
    ):
        assert rel in conhecidos, f"{rel} sumiu do scripts/check_artifacts.py"
        assert nome_health in nomes_no_health, f"{nome_health} sumiu do /api/health"


def test_a_variante_sem_identidade_nao_e_verificada() -> None:
    """`vulnerabilidade_ma_academias.parquet` NAO entra — nenhuma superficie o le.

    Verificar artefato que ninguem consome treina o operador a ignorar `[FALTA]`, que e'
    exatamente como um aviso real passa despercebido. Se um dia alguma tela passar a le-lo,
    este teste e' o lugar de registrar a mudanca.
    """
    modulo = _carregar_check_artifacts()
    conhecidos = _relativos_do_verificador(modulo)
    assert "staging/vulnerabilidade_ma_academias.parquet" not in conhecidos
