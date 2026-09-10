"""Estudios boutique fora do universo de OFERTA (BLK-ESTUDIO-01).

**O defeito que o bloco corrige.** Um estudio de pilates consumia os MESMOS 2.500 alunos
de capacidade que um Smart Fit, entao a Ultra lia como saturada uma praca onde ha' tres
estudios e nenhuma academia full-service. As 9 redes que o dono classificou somam 435 das
5.386 unidades do universo de oferta (8,1%).

**O que estes testes protegem, e por que a FORMA importa mais que o numero:**

  * A exclusao acontece UMA vez, acima dos dois modelos. Filtrar so' o de 1 km (a oferta
    do residual) deixaria os estudios inflando o mercado por `calibrar_taxa_fitness_mercado`,
    que le `n_concorrentes_mapeados_2km` — o residual subiria pelas duas pontas.
  * A lista e' fechada e literal. Uma rede ambigua que o dono NAO classificou continua
    dentro: excluir academia de verdade faz a Ultra ver mercado livre onde ha' concorrente,
    e esse e' o erro caro.
  * O tripwire fala quando um slug nao casa nada. O slug vem do NOME DO ARQUIVO CSV da
    coleta (`normalizar_concorrentes`), entao um rename la' apagaria a exclusao em silencio.
  * O filtro NAO alcanca o parquet de origem — pins e Relatorio Pontual leem ele direto.
"""

from __future__ import annotations

import pandas as pd

from motor_expansao.pipelines.enriquecimento_espacial_hexagonos import (
    REDES_ESTUDIO_BOUTIQUE,
    excluir_estudios_boutique,
    unir_cadeias,
)


def _cadeias(pares: list[tuple[str, float]]) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"rede": rede, "lat": -23.5 + i * 0.001, "lng": lng, "status_registro": "valido"}
            for i, (rede, lng) in enumerate(pares)
        ]
    )


# --------------------------------------------------------------------------- #
# A lista                                                                      #
# --------------------------------------------------------------------------- #


def test_as_nove_redes_do_dono_saem() -> None:
    esperado = {
        "velocity", "my_box", "vidya_studio", "tonus_gym", "aera_pilates",
        "race_bootcamp", "kore", "nadarte", "jab_house",
    }
    assert set(REDES_ESTUDIO_BOUTIQUE) == esperado


def test_estudio_sai_e_academia_fica() -> None:
    out = excluir_estudios_boutique(
        _cadeias([("velocity", -46.6), ("smart_fit", -46.7), ("aera_pilates", -46.8)])
    )
    assert list(out["rede"]) == ["smart_fit"]


def test_rede_ambigua_nao_classificada_CONTINUA_na_oferta() -> None:
    """O custo de errar e' assimetrico, e o teste existe para travar essa assimetria.

    `allp_fit`, `26fit`, `contorno_do_corpo` e as outras 8 ambiguas ficaram DENTRO por
    decisao do dono. Excluir academia de verdade faz a Ultra ver mercado livre onde ha'
    concorrente — erro caro. Incluir um estudio a mais so' deixa o residual conservador.
    """
    ambiguas = ["allp_fit", "26fit", "contorno_do_corpo", "corpo_e_saude", "usina_do_corpo",
                "wellness_club", "evolve", "motion_fit", "marra_fit", "match_fit", "uplay"]
    out = excluir_estudios_boutique(_cadeias([(r, -46.6) for r in ambiguas]))
    assert list(out["rede"]) == ambiguas


def test_nao_ha_estudio_sobrando_no_resultado() -> None:
    out = excluir_estudios_boutique(
        _cadeias([(r, -46.6) for r in sorted(REDES_ESTUDIO_BOUTIQUE)] + [("bluefit", -46.9)])
    )
    assert out["rede"].isin(REDES_ESTUDIO_BOUTIQUE).sum() == 0
    assert len(out) == 1


# --------------------------------------------------------------------------- #
# Tripwire do slug                                                             #
# --------------------------------------------------------------------------- #


def test_avisa_quando_um_slug_declarado_nao_casa_nada(capsys) -> None:
    """O slug vem do NOME DO ARQUIVO CSV da coleta -- um rename apaga a exclusao.

    Sem este aviso o pipeline seguiria VERDE com o estudio de volta na oferta, que e' a
    forma do defeito que este repo ja pagou caro varias vezes: nada quebra, um numero so'
    para de estar certo.
    """
    excluir_estudios_boutique(_cadeias([("velocity", -46.6), ("smart_fit", -46.7)]))
    saida = capsys.readouterr().out
    assert "AVISO" in saida
    assert "my_box" in saida  # declarado e ausente deste universo sintetico
    assert "renomeado" in saida


def test_nao_avisa_quando_todos_os_slugs_existem(capsys) -> None:
    excluir_estudios_boutique(
        _cadeias([(r, -46.6) for r in sorted(REDES_ESTUDIO_BOUTIQUE)])
    )
    assert "AVISO" not in capsys.readouterr().out


# --------------------------------------------------------------------------- #
# Fronteiras                                                                   #
# --------------------------------------------------------------------------- #


def test_frame_sem_coluna_rede_passa_intacto() -> None:
    """Defensivo: o universo pode chegar de uma fonte que nao carimba rede."""
    df = pd.DataFrame({"lat": [-23.5], "lng": [-46.6]})
    assert len(excluir_estudios_boutique(df)) == 1


def test_frame_vazio_nao_levanta() -> None:
    vazio = pd.DataFrame(columns=["rede", "lat", "lng", "status_registro"])
    assert excluir_estudios_boutique(vazio).empty


def test_nao_muta_o_frame_recebido() -> None:
    """Quem chama ainda precisa do universo COMPLETO para outras contagens."""
    entrada = _cadeias([("velocity", -46.6), ("smart_fit", -46.7)])
    antes = len(entrada)
    excluir_estudios_boutique(entrada)
    assert len(entrada) == antes


def test_a_exclusao_e_separada_da_uniao_com_o_agregador() -> None:
    """`unir_cadeias` responde QUEM EXISTE; a exclusao responde QUEM CONTA.

    Molde de `admitir_orfaos_da_malha` x `sobrepor_renda_da_malha` (DEC-055): juntar as
    duas faria a segunda mudar de resposta sempre que a primeira mudasse de fonte. O
    teste trava que a uniao NAO filtra sozinha.
    """
    comp = pd.DataFrame(
        {
            "rede": ["velocity", "smart_fit"],
            "lat": [-23.5, -23.6],
            "lng": [-46.6, -46.7],
            "status_registro": ["valido", "valido"],
        }
    )
    unido = unir_cadeias(comp, None)
    assert "velocity" in set(unido["rede"]), "unir_cadeias nao pode filtrar por conta propria"
    assert "velocity" not in set(excluir_estudios_boutique(unido)["rede"])


def test_estudio_vindo_do_feed_do_agregador_tambem_sai() -> None:
    """A DEC-048 trouxe unidades de rede do agregador para o universo de MERCADO.

    Se a exclusao rodasse ANTES da uniao, um estudio que so' existe no feed entraria pela
    porta dos fundos. Por isso ela roda DEPOIS, sobre o universo ja' unido.
    """
    comp = pd.DataFrame(
        {"rede": ["smart_fit"], "lat": [-23.6], "lng": [-46.7], "status_registro": ["valido"]}
    )
    feed = pd.DataFrame(
        {"rede": ["kore"], "lat": [-23.5], "lng": [-46.6], "tem_pin_proprio": [True]}
    )
    unido = unir_cadeias(comp, feed)
    assert "kore" in set(unido["rede"])
    assert set(excluir_estudios_boutique(unido)["rede"]) == {"smart_fit"}
