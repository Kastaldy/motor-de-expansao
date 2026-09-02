"""Bloco A / commit A1 — o `perfil.json` do Brasil reproduz as constantes de hoje.

**Este e o teste que garante que declarar o pais nao muda o comportamento brasileiro.**
O `data/perfis/BR/perfil.json` nao e um perfil novo: e a transcricao de literais que
hoje vivem espalhados pelo codigo. Se um valor do perfil divergir do literal citado, e
o PERFIL que esta errado — nunca o codigo.

Ele trabalha em tres camadas, da mais forte para a mais fraca:

1. **Contra o modulo importado** (`coord.py`, `constants.py`, `relatorio_municipal.py`,
   `calibrar_renda_setor_2022.py`). E a camada forte: compara com o numero que o codigo
   de fato usa, e continua valendo DEPOIS do Bloco A, quando essas constantes passam a
   derivar do perfil — vira prova de ida e volta.
2. **Contra o texto-fonte de `web/server/app.py`**, que nao e importavel fora do
   `sys.path` do container do piloto. Aceita DUAS formas: o literal de hoje (e ele tem
   de bater com o perfil) ou a derivacao `= PERFIL.reguas.<campo>` que o commit A5
   introduz. Escrito assim de proposito: um teste que so aceita o literal quebra no A5
   longe da causa, que e exatamente o defeito que a spec §5.1 documenta.
3. **Contra os numeros escritos na spec**, como ancora final — se alguem mudar codigo e
   perfil juntos, esta camada ainda acusa.

Spec: `docs/spec_bloco_a_perfil.md` §5.9 item 2 e §7 item 3.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

from motor_expansao.api import coord
from motor_expansao.dashboard import constants as dash_constants
from motor_expansao.dashboard import relatorio_municipal
from motor_expansao.perfil import (
    PERFIL_BR_EMBARCADO,
    SUPERFICIES_VALIDAS,
    carregar_perfil,
)
from motor_expansao.pipelines import calibrar_renda_setor_2022 as calibrar

_RAIZ = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def perfil():
    return carregar_perfil(PERFIL_BR_EMBARCADO)


# --------------------------------------------------------------------------------
# Camada 1 — contra o modulo importado
# --------------------------------------------------------------------------------


def test_bbox_e_a_b1_de_coord_py(perfil) -> None:
    """B1 e a caixa que as tres copias de validacao de ENTRADA ja usam hoje. Escolher
    qualquer outra estreitaria ou alargaria o que as rotas de coordenada aceitam —
    justificativa completa na spec §1.3 e na pendencia BR-P1 do proprio perfil."""
    assert perfil.bbox.lat_min == coord.BRASIL_LAT_MIN
    assert perfil.bbox.lat_max == coord.BRASIL_LAT_MAX
    assert perfil.bbox.lng_min == coord.BRASIL_LNG_MIN
    assert perfil.bbox.lng_max == coord.BRASIL_LNG_MAX


def test_ancoras_da_regua_absoluta_batem_com_o_pipeline(perfil) -> None:
    """As quatro ancoras de `calibrar_renda_setor_2022`. Sao a regua ABSOLUTA de
    2026-08-26 (DEC-045), medidas no universo povoado em hexagono H3 res 7."""
    assert perfil.reguas.renda_abs_min == calibrar.RENDA_ABS_MIN
    assert perfil.reguas.renda_abs_max == calibrar.RENDA_ABS_MAX
    assert perfil.reguas.pop_abs_min == calibrar.POP_ABS_MIN
    assert perfil.reguas.pop_abs_max == calibrar.POP_ABS_MAX


def test_ancoras_do_perfil_reconstroem_o_ancoras_br(perfil) -> None:
    """`Perfil.ancoras()` e o objeto que o commit A8 injeta no pipeline. Aqui se prova
    que, no Brasil, injetar o perfil e injetar exatamente o default de hoje."""
    a = perfil.ancoras()
    assert (a.renda_min, a.renda_max, a.pop_min, a.pop_max) == (
        calibrar.RENDA_ABS_MIN,
        calibrar.RENDA_ABS_MAX,
        calibrar.POP_ABS_MIN,
        calibrar.POP_ABS_MAX,
    )


def test_pop_min_acionavel_bate_com_o_dashboard(perfil) -> None:
    """Segunda copia do 5.000 (`dashboard/constants.py:144`). A primeira esta no
    `app.py:154` e e checada na camada 2."""
    assert perfil.reguas.pop_min_acionavel == dash_constants.POP_MIN_ACIONAVEL


def test_capacidade_unidade_alunos_bate_com_o_dashboard(perfil) -> None:
    assert (
        perfil.reguas.capacidade_unidade_alunos
        == dash_constants.CAPACIDADE_UNIDADE_ALUNOS
    )


def test_oferta_destaque_min_bate_com_o_relatorio_municipal(perfil) -> None:
    """Segunda copia do 2.000 (`relatorio_municipal.py:61`) — a que faz desse arquivo
    o TERCEIRO CRITICO do bloco (spec §8.1), que nenhum documento listava."""
    assert perfil.reguas.oferta_destaque_min == relatorio_municipal.OFERTA_DESTAQUE_MIN


# --------------------------------------------------------------------------------
# Camada 2 — contra o texto-fonte de `web/server/app.py`
# --------------------------------------------------------------------------------

#: constante em `app.py` -> campo correspondente em `perfil.reguas`
CONSTANTES_DO_APP = {
    "SCORE_CORTE_QUENTE": "score_corte_quente",
    "OFERTA_DESTAQUE_MIN": "oferta_destaque_min",
    "POP_MIN_ACIONAVEL": "pop_min_acionavel",
    "CAPACIDADE_CONCORRENTE_PADRAO": "capacidade_concorrente",
}


@pytest.mark.parametrize(("constante", "campo"), sorted(CONSTANTES_DO_APP.items()))
def test_constante_do_app_bate_com_o_perfil(perfil, constante: str, campo: str) -> None:
    fonte = (_RAIZ / "web" / "server" / "app.py").read_text(encoding="utf-8")
    achado = re.search(rf"^{constante}\s*=\s*(.+?)(?:\s*#.*)?$", fonte, re.M)
    assert achado, f"`{constante}` nao encontrada em web/server/app.py"
    expressao = achado.group(1).strip()

    esperado = getattr(perfil.reguas, campo)
    derivado = f"PERFIL.reguas.{campo}"
    if derivado in expressao:
        # Estado pos-A5: a constante DERIVA do perfil. Nada a comparar — a igualdade
        # deixou de ser coincidencia e virou construcao.
        return
    assert float(expressao) == float(esperado), (
        f"`{constante} = {expressao}` em app.py diverge de "
        f"`reguas.{campo} = {esperado}` no perfil BR. Quem esta errado e o PERFIL."
    )


# --------------------------------------------------------------------------------
# Camada 3 — os numeros da spec, como ancora final
# --------------------------------------------------------------------------------


def test_os_treze_numeros_da_spec(perfil) -> None:
    """Os 13 valores que a spec §5.9 lista nominalmente. Esta camada existe para o caso
    de alguem mudar codigo e perfil no mesmo commit: as camadas 1 e 2 ficariam verdes."""
    assert (
        perfil.bbox.lat_min,
        perfil.bbox.lat_max,
        perfil.bbox.lng_min,
        perfil.bbox.lng_max,
    ) == (-34.0, 5.5, -74.0, -28.0)
    r = perfil.reguas
    assert r.score_corte_quente == 30.0
    assert r.pop_min_acionavel == 5000
    assert r.oferta_destaque_min == 2000.0
    assert r.capacidade_concorrente == 2500.0
    assert r.capacidade_unidade_alunos == 2500
    assert r.renda_abs_min == 300.0
    assert r.renda_abs_max == 4000.0
    assert r.pop_abs_min == 1000.0
    assert r.pop_abs_max == 100000.0


def test_identidade_e_moeda_do_brasil(perfil) -> None:
    assert perfil.pais == "BR"
    assert perfil.nome == "Brasil"
    assert perfil.locale == "pt-BR"
    assert perfil.moeda.codigo == "BRL"
    assert perfil.moeda.simbolo == "R$"
    assert perfil.geocode.countrycodes == "br"
    assert perfil.geocode.idioma == "pt-BR"


def test_fontes_saem_acentuadas(perfil) -> None:
    """Sao TEXTO DE USUARIO (CLAUDE.md §2): a rota livre `/api/metodologia` publica
    estas strings na tela. Depois do A7 elas saem DESTE arquivo — uma copia sem acento
    vira portugues errado em producao."""
    assert perfil.fontes.censo.nome == "Censo 2022 (IBGE)"
    assert "setor censitário" in perfil.fontes.censo.detalhe
    assert perfil.fontes.crescimento.nome == "CAGED, RAIS, Receita Federal e satélite"
    assert "município" in perfil.fontes.crescimento.detalhe


# --------------------------------------------------------------------------------
# O espelho do vocabulario de superficie
# --------------------------------------------------------------------------------


def test_superficies_validas_espelham_abas_validas() -> None:
    """`SUPERFICIES_VALIDAS` e uma COPIA de `ABAS_VALIDAS` (`web/server/acesso.py`),
    porque `src/motor_expansao/` nunca importa de `web/server/` — o pacote roda tambem
    na imagem da API, onde `web/server` nao esta no sys.path. Este teste e o que impede
    a copia de envelhecer: aba nova em `acesso.py` e esquecida aqui falha nomeando-a."""
    servidor = _RAIZ / "web" / "server"
    if str(servidor) not in sys.path:
        sys.path.insert(0, str(servidor))
    import acesso  # noqa: PLC0415

    assert SUPERFICIES_VALIDAS == acesso.ABAS_VALIDAS, (
        "vocabulario de aba divergiu: so em acesso.py "
        f"{sorted(acesso.ABAS_VALIDAS - SUPERFICIES_VALIDAS)}, "
        f"so em perfil.py {sorted(SUPERFICIES_VALIDAS - acesso.ABAS_VALIDAS)}"
    )


def test_brasil_habilita_todas_as_superficies(perfil) -> None:
    """E o que garante que o gate de superficie do Bloco C seja INERTE no Brasil. Se
    este campo trouxesse menos que cinco, o perfil estaria mudando o comportamento
    brasileiro — justamente o que ele existe para nao fazer."""
    assert set(perfil.superficies) == SUPERFICIES_VALIDAS


# --------------------------------------------------------------------------------
# As duas reguas de composicao familiar (Bloco B)
# --------------------------------------------------------------------------------


def test_uplift_e_moradores_batem_com_o_dashboard(perfil) -> None:
    """Os dois fallbacks nacionais passaram a vir do perfil, e no Brasil nao se moveram."""
    assert perfil.reguas.uplift_composicao == dash_constants.UPLIFT_COMPOSICAO_NACIONAL
    assert (
        perfil.reguas.moradores_por_domicilio
        == dash_constants.MORADORES_DOMICILIO_NACIONAL
    )
    assert perfil.reguas.uplift_composicao == 1.632
    assert perfil.reguas.moradores_por_domicilio == 2.79


def test_o_perfil_ARGENTINO_torna_o_uplift_IDENTIDADE() -> None:
    """**O defeito que este campo conserta, e ele foi medido.**

    A plataforma calcula `renda_media_domiciliar = renda_responsavel x uplift x temporal`.
    No Brasil aquela coluna traz a renda do RESPONSAVEL, e o uplift de 1,632 a leva ao
    domicilio. O exportador argentino escreve `renda_per_capita x moradores`, que **ja e**
    a renda domiciliar: aplicar 1,632 sobre ela poe a renda do Relatorio Pontual **63%
    acima da real** (`1.632` = +63,2%).

    O Juan resolvia com `MOTOR_PAIS=AR` no ambiente. A env NAO entra: seria o pais
    escolhendo caminho de execucao, que a DEC-047 proibe e o fio de alarme do A10 pega.
    Um multiplicador de 1,0 resolve o mesmo problema **sem ramo nenhum**.
    """
    ar = carregar_perfil(_RAIZ / "data" / "perfis" / "AR" / "perfil.json")
    assert ar.reguas.uplift_composicao == 1.0

    # A prova numerica: a mesma renda domiciliar, pelas duas reguas.
    renda_domiciliar_ar = 1_000.0
    br = carregar_perfil(PERFIL_BR_EMBARCADO)
    assert renda_domiciliar_ar * ar.reguas.uplift_composicao == 1_000.0
    assert renda_domiciliar_ar * br.reguas.uplift_composicao == pytest.approx(1_632.0)


def test_moradores_argentino_usa_HOGARES_e_nao_viviendas() -> None:
    """2,8623 e `sum(pop_total)/sum(hogares_total)` nos 42.388 hexagonos do pacote.

    A escolha da coluna nao e detalhe: `vivienda` inclui as VAGAS, e o analogo brasileiro
    (`domicilios_particulares_ocupados`, v0007) sao os OCUPADOS. Pela mesma base,
    `pop/viviendas` da 2,5781 — uns 11% abaixo. Como este numero divide a renda per capita
    para chegar a domiciliar, o 11% iria direto para a tela.
    """
    ar = carregar_perfil(_RAIZ / "data" / "perfis" / "AR" / "perfil.json")
    assert ar.reguas.moradores_por_domicilio == pytest.approx(2.8623, abs=1e-4)
    # Longe do valor que sairia de `viviendas`, e longe do brasileiro.
    assert abs(ar.reguas.moradores_por_domicilio - 2.5781) > 0.2
