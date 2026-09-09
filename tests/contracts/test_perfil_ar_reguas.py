"""O `oferta_destaque_min` do perfil AR e' ancorado na regua nativa do pipeline argentino.

**Este e' o teste que impede a regua brasileira de apagar o funil argentino.** O passo 2
do funil ("Demanda nao atendida", `web/server/app.py::_com_residual`) corta por
`PERFIL.reguas.oferta_destaque_min`, e o passo 3 ("Pressao concorrencial") deriva do 2.
Com o 2.000 brasileiro copiado para o perfil AR, 398 de 434 municipios argentinos com
hexagono quente saiam com as DUAS camadas vazias (medido na base exportada de 2026-09-04:
o residual argentino tem p95 = 1.538 entre os quentes — o piso era inalcancavel por
construcao, a classe de defeito das DEC-038/DEC-042: valor legitimo que, na escala
errada, apaga uma superficie inteira sem erro).

A ancora e' a leitura que o proprio pipeline do pais declara
(`juancalu/motor-argentina`, `pipelines/sam_mercado_argentina.py`):

    score_oportunidade_residual = 100 * residual_membros / capacidade_concorrente  # 1.070
    prioridade_mercado "alta"   = score >= 75  =>  residual >= 0,75 * 1.070 = 802,5

"Destaque" no piloto = onde comeca a prioridade ALTA do pipeline argentino. Por isso o
teste trava a DERIVACAO (0,75 x `capacidade_concorrente` do proprio perfil), nao so o
literal — um 802.5 magico solto envelhece calado quando a capacidade recalibrar.

Decisao de Juan em 2026-09-08 (pendencia P9 do perfil, "decide: Bloco A/B (dev)").
Molde do PR #320: regua de pais mora no perfil, numero ancorado na base do proprio pais.
"""

from __future__ import annotations

from pathlib import Path

from motor_expansao.perfil import carregar_perfil

_REPO = Path(__file__).resolve().parents[2]


def _perfil_ar():
    return carregar_perfil(_REPO / "data" / "perfis" / "AR" / "perfil.json")


def test_oferta_destaque_min_ar_e_o_piso_da_prioridade_alta_nativa() -> None:
    reguas = _perfil_ar().reguas
    assert reguas.oferta_destaque_min == 802.5


def test_oferta_destaque_min_ar_deriva_da_capacidade_do_proprio_perfil() -> None:
    """A relacao, alem do numero: 0,75 x capacidade da academia argentina vista.

    Se `capacidade_concorrente` recalibrar (400 socios x 2,675 de cobertura hoje),
    este teste aponta que o piso do destaque tem de ser recalculado JUNTO — em vez
    de deixar os dois divergirem em silencio.
    """
    reguas = _perfil_ar().reguas
    assert reguas.oferta_destaque_min == 0.75 * reguas.capacidade_concorrente
