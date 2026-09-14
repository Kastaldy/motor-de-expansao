"""Trava a paridade da paleta de score entre o núcleo Python e o piloto web.

A rampa de 10 faixas existe DUAS vezes, como cópia manual — não há import nem
geração de código entre as duas linguagens:

  - Python: ``constants.RESIDUAL_SCORE_BANDS`` -> colore os PDFs que o piloto emite;
  - TypeScript: ``SCORE_BANDS_HEX`` (``web/src/lib/colors.ts``) -> colore o mapa deck.gl.

O teste de front (``web/src/lib/colors.test.ts``) repete os mesmos literais em JS,
então fica VERDE mesmo se o Python mudar. Este teste lê o ``.ts`` e compara banda a
banda com o Python: sem ele, mexer num lado só faz o mapa web e o PDF divergirem em
silêncio. Ele NÃO define a paleta — apenas trava que as duas cópias andem juntas.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from motor_expansao.dashboard.constants import RESIDUAL_SCORE_BANDS

_REPO = Path(__file__).resolve().parents[2]  # tests/unit/ -> raiz do worktree
_WEB_SRC = _REPO / "web" / "src"
_COLORS_TS = _WEB_SRC / "lib" / "colors.ts"

# `export const SCORE_BANDS_HEX = [ ... ] as const` (com ou sem anotação de tipo).
_BLOCO_RE = re.compile(
    r"export\s+const\s+SCORE_BANDS_HEX\s*(?::[^=]+)?=\s*\[(?P<corpo>[^\]]*)\]",
    re.DOTALL,
)
_HEX_RE = re.compile(r"""['"]\s*(#[0-9A-Fa-f]{6})\s*['"]""")

# O piloto web só existe na branch do piloto; sem ele não há paridade a travar.
pytestmark = pytest.mark.skipif(
    not _WEB_SRC.is_dir(),
    reason="piloto web (web/src) ausente nesta árvore — nada a comparar",
)


def _paleta_web() -> list[str]:
    """Hex de `SCORE_BANDS_HEX`, na ordem em que aparecem no colors.ts."""
    assert _COLORS_TS.is_file(), (
        f"{_COLORS_TS.relative_to(_REPO).as_posix()} não existe, mas web/src existe.\n"
        "Se o arquivo foi movido/renomeado, atualize ESTE teste — ele é a única trava "
        "entre a paleta do mapa web e a do núcleo Python (RESIDUAL_SCORE_BANDS)."
    )
    fonte = _COLORS_TS.read_text(encoding="utf-8")
    bloco = _BLOCO_RE.search(fonte)
    assert bloco is not None, (
        "não achei o array `export const SCORE_BANDS_HEX = [...]` em "
        f"{_COLORS_TS.relative_to(_REPO).as_posix()}.\n"
        "Se a constante mudou de nome/formato, atualize este teste — sem ele a paleta "
        "do mapa web e a dos PDFs divergem em silêncio."
    )
    return _HEX_RE.findall(bloco.group("corpo"))


def test_paleta_web_tem_as_mesmas_10_faixas() -> None:
    web = _paleta_web()
    nucleo = [cor for _faixa, cor in RESIDUAL_SCORE_BANDS]
    assert len(web) == len(nucleo), (
        f"a paleta do piloto web tem {len(web)} faixas e RESIDUAL_SCORE_BANDS tem "
        f"{len(nucleo)}.\n"
        "constants.RESIDUAL_SCORE_BANDS (colore o PDF) e SCORE_BANDS_HEX em "
        "web/src/lib/colors.ts (colore o mapa deck.gl) são cópias manuais: precisam "
        "andar juntas, faixa a faixa, na mesma ordem."
    )


def test_paleta_web_bate_cor_a_cor_com_residual_score_bands() -> None:
    web = _paleta_web()
    divergencias = [
        f"  faixa {faixa} (índice {i}): RESIDUAL_SCORE_BANDS={cor_py} != SCORE_BANDS_HEX={web[i]}"
        for i, (faixa, cor_py) in enumerate(RESIDUAL_SCORE_BANDS)
        if i < len(web) and cor_py.upper() != web[i].upper()
    ]
    assert not divergencias, (
        "a paleta de score DIVERGIU entre o núcleo Python e o piloto web:\n"
        + "\n".join(divergencias)
        + "\n\nOs dois arquivos precisam andar juntos (são cópias manuais, sem import):\n"
        "  - src/motor_expansao/dashboard/constants.py -> RESIDUAL_SCORE_BANDS (PDF)\n"
        "  - web/src/lib/colors.ts -> SCORE_BANDS_HEX (mapa deck.gl do piloto)\n"
        "Ajuste o lado que ficou para trás; não mude a paleta sem decisão explícita."
    )


# ---------------------------------------------------------------------------
# Bloco D — faixas ABSOLUTAS de densidade/renda de setor (mapa de calor opcional).
# Mesma lógica de paridade acima, formato diferente: cada item é
# `[corte_superior, 'rótulo', [r, g, b, a]]`, e a última faixa usa infinito.
# ---------------------------------------------------------------------------

from motor_expansao.dashboard.constants import (  # noqa: E402
    _DENSIDADE_POP_BANDS_BR,
    _RENDA_PER_CAPITA_BANDS_BR,
    DENSIDADE_POP_BANDS,
    RENDA_PER_CAPITA_BANDS,
)

_FAIXA_ABS_ITEM_RE = re.compile(
    # O rotulo pode ser string simples ('...') ou template literal (`...`, quando
    # interpola moedaRenda() — ver RENDA_SETOR_BANDS). O teste nao checa o TEXTO do
    # rotulo, so' precisa transpor-lo para chegar no corte e na cor.
    r"\[\s*(?P<corte>[\d_]+|Infinity)\s*,\s*(?:'[^']*'|`[^`]*`)\s*,\s*"
    r"\[\s*(?P<r>\d+)\s*,\s*(?P<g>\d+)\s*,\s*(?P<b>\d+)\s*,\s*(?P<a>\d+)\s*\]\s*\]"
)


def _faixas_absolutas_web(nome_const: str) -> list[tuple[float, tuple[int, int, int, int]]]:
    """Lê `[corte, 'rotulo', [r,g,b,a]]` de uma constante TS de `colors.ts`."""
    fonte = _COLORS_TS.read_text(encoding="utf-8")
    bloco_re = re.compile(
        rf"export\s+const\s+{nome_const}\s*:[^=]*=\s*\[(?P<corpo>.*?)\n\]",
        re.DOTALL,
    )
    bloco = bloco_re.search(fonte)
    assert bloco is not None, (
        f"não achei `export const {nome_const} = [...]` em "
        f"{_COLORS_TS.relative_to(_REPO).as_posix()}."
    )
    itens = []
    for m in _FAIXA_ABS_ITEM_RE.finditer(bloco.group("corpo")):
        corte_txt = m.group("corte")
        corte = float("inf") if corte_txt == "Infinity" else float(corte_txt.replace("_", ""))
        rgba = (int(m.group("r")), int(m.group("g")), int(m.group("b")), int(m.group("a")))
        itens.append((corte, rgba))
    return itens


@pytest.mark.parametrize(
    "nome_web,bands_py,nome_py",
    [
        ("DENSIDADE_BANDS", _DENSIDADE_POP_BANDS_BR, "_DENSIDADE_POP_BANDS_BR"),
        ("RENDA_SETOR_BANDS", _RENDA_PER_CAPITA_BANDS_BR, "_RENDA_PER_CAPITA_BANDS_BR"),
    ],
)
def test_faixas_absolutas_batem_corte_e_cor_com_o_literal_br(
    nome_web, bands_py, nome_py
) -> None:
    """O literal do `colors.ts` é o FALLBACK brasileiro — e é contra ele que compara.

    Até 2026-09-10 este teste comparava com a constante PÚBLICA
    (`RENDA_PER_CAPITA_BANDS`), que desde o perfil por país é RESOLVIDA: no Brasil ela é
    o literal BR, mas numa instância que declara `reguas.faixas_renda` ela é outra régua,
    em outra moeda. Com `MOTOR_DATA_DIR` apontando para o perfil AR, o teste ficava
    vermelho comparando as seis faixas em dólar da canasta do INDEC com cinco literais em
    real — cobrando do `colors.ts` uma paridade que ele não pode ter, porque o `.ts` é
    compilado uma vez e serve os dois países.

    A régua que de fato viaja por país sai por `/api/me` e está travada em
    `test_payload_serve_as_bandas_ja_resolvidas_pelo_nucleo` (abaixo), nos DOIS perfis. O
    que continua valendo aqui — e é o que este teste sempre existiu para pegar — é que o
    fallback compilado no front não divirja do fallback do núcleo.
    """
    web = _faixas_absolutas_web(nome_web)
    nucleo = [(corte, rgba) for corte, _rotulo, rgba in bands_py]
    assert web == nucleo, (
        f"{nome_web} (web/src/lib/colors.ts) divergiu de {nome_py} "
        "(src/motor_expansao/dashboard/constants.py) — as duas são cópias manuais que "
        "precisam andar juntas, corte e cor, na mesma ordem. "
        f"web={web!r} núcleo={nucleo!r}"
    )


# ---------------------------------------------------------------------------
# A rampa de cor da plataforma, aplicada às faixas DECLARADAS NO PERFIL.
# ---------------------------------------------------------------------------


def _faixas_como_no_perfil(bands) -> tuple:
    """Transcreve uma lista de bands para o formato que o perfil entrega (`Faixa`)."""
    from motor_expansao.perfil import Faixa

    return tuple(Faixa(ate=corte, rotulo=rotulo) for corte, rotulo, _rgba in bands)


@pytest.mark.parametrize(
    "literal_br,rampa_nome",
    [
        (_RENDA_PER_CAPITA_BANDS_BR, "_RAMPA_RENDA"),
        (_DENSIDADE_POP_BANDS_BR, "_RAMPA_DENSIDADE"),
    ],
)
def test_o_caminho_do_perfil_reproduz_o_literal_br_cor_a_cor(literal_br, rampa_nome) -> None:
    """Um país que declarasse as CINCO faixas brasileiras tem de receber as CINCO cores
    brasileiras — cor a cor, não "quase".

    Esta é a trava da ARMADILHA que existiu até 2026-09-10: a regra de atribuição era
    "as N-1 primeiras cores mais a ÚLTIMA da rampa", e com N=5 ela PULAVA o quinto
    degrau. A rampa é o literal BR (5 cores) mais um degrau escuro de topo, então sobre
    cinco faixas ela devolvia o verde-escuro `(20, 170, 80)` no topo, onde o literal
    brasileiro tem `(0, 204, 0)` — e a faixa de topo não é um caso de borda: no artefato
    de São Paulo capital ela pega 4.659 dos 26.672 setores (17,47%).

    O teste é escrito assim de propósito: em vez de repetir os números da rampa, ele
    transcreve o LITERAL BR para o formato do perfil e exige o próprio literal de volta.
    Uma rampa que deixe de reproduzi-lo falha aqui, sem precisar de terceira cópia.
    """
    from motor_expansao.dashboard import constants as c

    rampa = getattr(c, rampa_nome)
    obtido = c._bands_de_faixas(_faixas_como_no_perfil(literal_br), rampa)

    divergencias = [
        f"  faixa {i} (teto {corte}): literal BR={cor_br} != caminho do perfil={obtido[i][2]}"
        for i, (corte, _rotulo, cor_br) in enumerate(literal_br)
        if obtido[i][2] != cor_br
    ]
    assert not divergencias, (
        f"`_bands_de_faixas` com {rampa_nome} não reproduz o literal brasileiro:\n"
        + "\n".join(divergencias)
        + "\n\nA rampa é o literal BR mais UM degrau de topo, e a atribuição é por "
        "PREFIXO: N faixas tomam as N primeiras cores. Pular cor troca a cor de faixas "
        "inteiras do mapa sem mudar um corte sequer."
    )
    assert obtido == list(literal_br), (
        "cortes e rótulos também têm de sobreviver ao caminho do perfil, intactos: "
        f"{obtido!r} != {list(literal_br)!r}"
    )


def test_a_rampa_de_seis_sai_inteira_e_a_de_cinco_nao_pula_degrau() -> None:
    """A outra metade da regra de prefixo: com 6 faixas a rampa sai inteira.

    Junto, os dois casos fixam a regra por completo — 5 = literal BR (teste acima),
    6 = rampa inteira — e é o que impede uma "correção" futura de trocar o prefixo por
    uma amostragem espaçada, que voltaria a pular degrau no meio.
    """
    from motor_expansao.dashboard import constants as c
    from motor_expansao.perfil import Faixa

    for rampa in (c._RAMPA_RENDA, c._RAMPA_DENSIDADE):
        seis = tuple(
            Faixa(ate=float(i + 1) if i < 5 else float("inf"), rotulo=f"f{i}")
            for i in range(6)
        )
        assert [cor for _t, _r, cor in c._bands_de_faixas(seis, rampa)] == rampa
        cinco = seis[:4] + (Faixa(ate=float("inf"), rotulo="topo"),)
        assert [cor for _t, _r, cor in c._bands_de_faixas(cinco, rampa)] == rampa[:5]


# ---------------------------------------------------------------------------
# O PAYLOAD de `/api/me` contra as constantes do núcleo — nos DOIS perfis.
#
# É esta a trava que substitui, para a régua que viaja por país, a comparação com o
# literal do `colors.ts`: o front lê as bandas do payload, e o payload tem de ser as
# MESMAS bandas que o PDF pinta. Um único ponto de resolução (o Python), servido.
# ---------------------------------------------------------------------------

import json  # noqa: E402
import os  # noqa: E402
import subprocess  # noqa: E402
import sys  # noqa: E402

_WEB_SERVER = _REPO / "web" / "server"

#: Roda DENTRO do processo alvo e imprime o payload e o esperado, já em JSON. Existe
#: como texto porque o ramo AR precisa de um processo NOVO: o perfil é resolvido no
#: import e memoizado (`@lru_cache(maxsize=1)` em `perfil.py`), então trocar
#: `MOTOR_DATA_DIR` no processo do pytest não trocaria país nenhum — ele leria o perfil
#: que já está carregado e o teste passaria a provar o contrário do que promete.
_SONDA = """
import json, sys
sys.path.insert(0, {web_server!r})
import app
from motor_expansao.dashboard.constants import DENSIDADE_POP_BANDS, RENDA_PER_CAPITA_BANDS

payload = app._perfil_do_cliente()["reguas"]
print("<<<JSON>>>" + json.dumps({{
    "pais": app.PERFIL.pais,
    "servido": {{
        "renda": payload["bandas_renda_setor"],
        "densidade": payload["bandas_densidade_setor"],
    }},
    "esperado": {{
        "renda": app._bandas_para_o_cliente(RENDA_PER_CAPITA_BANDS),
        "densidade": app._bandas_para_o_cliente(DENSIDADE_POP_BANDS),
    }},
}}))
"""


def _sondar(motor_data_dir: Path | None) -> dict:
    """Roda a sonda num processo novo, opcionalmente com outro `MOTOR_DATA_DIR`."""
    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join(
        [str(_REPO / "src"), env.get("PYTHONPATH", "")]
    ).rstrip(os.pathsep)
    if motor_data_dir is not None:
        env["MOTOR_DATA_DIR"] = str(motor_data_dir)
    proc = subprocess.run(  # noqa: S603
        [sys.executable, "-c", _SONDA.format(web_server=str(_WEB_SERVER))],
        cwd=str(_REPO),
        env=env,
        capture_output=True,
        text=True,
        timeout=300,
    )
    assert proc.returncode == 0, (
        "a sonda do payload não rodou "
        f"(MOTOR_DATA_DIR={motor_data_dir}):\n{proc.stdout}\n{proc.stderr}"
    )
    marca = proc.stdout.rfind("<<<JSON>>>")
    assert marca >= 0, f"sonda não imprimiu o JSON:\n{proc.stdout}\n{proc.stderr}"
    return json.loads(proc.stdout[marca + len("<<<JSON>>>") :])


def test_payload_serve_as_bandas_ja_resolvidas_pelo_nucleo() -> None:
    """No processo do pytest (perfil BR, o do repositório): payload == constantes."""
    if str(_WEB_SERVER) not in sys.path:
        sys.path.insert(0, str(_WEB_SERVER))
    import app as pilot  # noqa: PLC0415

    servido = pilot._perfil_do_cliente()["reguas"]
    assert servido["bandas_renda_setor"] == pilot._bandas_para_o_cliente(
        RENDA_PER_CAPITA_BANDS
    )
    assert servido["bandas_densidade_setor"] == pilot._bandas_para_o_cliente(
        DENSIDADE_POP_BANDS
    )
    # O topo aberto sai como `null`: `float('inf')` derruba a rota inteira no
    # serializador do FastAPI ("Out of range float values are not JSON compliant").
    assert servido["bandas_renda_setor"][-1][0] is None
    assert servido["bandas_densidade_setor"][-1][0] is None
    # E o JSON tem de ser de fato serializável — `json.dumps` aceita `inf` com
    # `allow_nan`, então a checagem só vale desligando-o, que é o que o FastAPI faz.
    json.dumps(servido, allow_nan=False)


@pytest.mark.parametrize("sigla", ["BR", "AR"])
def test_payload_bate_com_as_constantes_em_processo_do_pais(sigla: str) -> None:
    """A mesma igualdade, num processo cujo `MOTOR_DATA_DIR` é o perfil do país.

    O ramo AR é o que prova que a régua VIAJA: lá as bandas de renda são as seis faixas
    em dólar da canasta do INDEC, e é isso que tem de sair no payload. Payload e
    constantes vêm da mesma fonte, então isto fica verde desde o primeiro dia — se
    algum dia divergir, o mapa web e o PDF pintaram réguas diferentes.
    """
    perfil_dir = _REPO / "data" / "perfis" / sigla
    if not (perfil_dir / "perfil.json").is_file():
        pytest.skip(f"perfil {sigla} ausente nesta árvore")

    resultado = _sondar(perfil_dir)
    assert resultado["pais"] == sigla, (
        f"a sonda subiu com o país {resultado['pais']!r}, não {sigla!r} — "
        "MOTOR_DATA_DIR não pegou e o teste provaria outra coisa"
    )
    assert resultado["servido"] == resultado["esperado"], (
        f"no perfil {sigla} o payload de /api/me divergiu das bandas do núcleo:\n"
        f"  servido={resultado['servido']!r}\n  esperado={resultado['esperado']!r}"
    )


def test_no_perfil_ar_as_bandas_de_renda_nao_sao_as_brasileiras() -> None:
    """Guarda de eficácia do teste acima: sem isto, um payload que ignorasse o perfil
    (servindo sempre o literal BR) passaria nos dois ramos, porque o "esperado" seria
    calculado do mesmo jeito errado."""
    perfil_ar = _REPO / "data" / "perfis" / "AR"
    if not (perfil_ar / "perfil.json").is_file():
        pytest.skip("perfil AR ausente nesta árvore")

    ar = _sondar(perfil_ar)["servido"]
    br_renda = [
        [None if corte == float("inf") else corte, rotulo, list(rgba)]
        for corte, rotulo, rgba in _RENDA_PER_CAPITA_BANDS_BR
    ]
    assert ar["renda"] != br_renda, (
        "o payload argentino saiu com a régua BRASILEIRA de renda — o perfil não foi "
        "lido, e os outros testes deste arquivo ficariam verdes provando nada."
    )
