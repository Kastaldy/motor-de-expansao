"""Movimentação da concorrência pela série semanal (`motor_expansao.dashboard.movimentacao_semanal`).

Trava as regras da emenda 1 da DEC-064 com séries sintéticas gravadas como na VPS
(`snapshots_concorrentes/semana=S/fonte=F/` e `ponte_identidade_concorrentes/...`): abertura só de
chave inédita, fechamento só com duas semanas de ausência, troca de cadastro casada, recalibração e
saltos de cobertura fora da conta, "Em breve" pelo nome, e o laudo do que ficou de fora.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd
import pytest

from motor_expansao.dashboard import movimentacao_semanal as ms

SEMANAS = ["2026-38", "2026-39", "2026-40", "2026-41", "2026-42"]
DATAS = {s: f"2026-09-{20 + 7 * i:02d}" if 20 + 7 * i <= 30 else f"2026-10-{20 + 7 * i - 30:02d}" for i, s in enumerate(SEMANAS)}
LAT, LNG = -23.0, -46.0


def _linha(semana: str, chave: str, rede: str | None, nome: str, dlat: float = 0.0, fonte: str = "unidades") -> dict[str, Any]:
    return {"semana": semana, "fonte": fonte, "chave": chave, "rede": rede, "nome": nome, "lat": LAT + dlat, "lng": LNG}


def _gravar(base: Path, linhas: list[dict[str, Any]], *, ponte_desde: str = "2026-38") -> Path:
    quadro = pd.DataFrame(linhas)
    for (semana, fonte), g in quadro.groupby(["semana", "fonte"]):
        snap = base / ms.DIR_SNAPSHOTS / f"semana={semana}" / f"fonte={fonte}"
        snap.mkdir(parents=True, exist_ok=True)
        pd.DataFrame(
            {"chave_snapshot": g["chave"], "rede": g["rede"], "snapshot_date": DATAS[str(semana)]}
        ).to_parquet(snap / "part-0.parquet", index=False)
        if str(semana) >= ponte_desde:
            ponte = base / ms.DIR_PONTE / f"semana={semana}" / f"fonte={fonte}"
            ponte.mkdir(parents=True, exist_ok=True)
            pd.DataFrame(
                {"chave_snapshot": g["chave"], "nome": g["nome"], "lat": g["lat"], "lng": g["lng"]}
            ).to_parquet(ponte / "part-0.parquet", index=False)
    return base


def _estaveis(rede: str, n: int, semanas: list[str] = SEMANAS, fonte: str = "unidades", dlat0: float = 0.0) -> list[dict[str, Any]]:
    """`n` unidades paradas a 2 km umas das outras, presentes em todas as semanas."""
    return [
        _linha(s, f"{rede}-{k}", rede, f"{rede} {k}", dlat0 + 0.02 * k, fonte) for s in semanas for k in range(n)
    ]


def _rodar(tmp_path: Path, linhas: list[dict[str, Any]], **kw: Any) -> tuple[pd.DataFrame, dict[str, Any]]:
    return ms.eventos_da_serie(ms.ler_serie(_gravar(tmp_path, linhas, **kw)))


def _tipos(eventos: pd.DataFrame) -> list[tuple[str, str]]:
    return sorted(zip(eventos["tipo"].astype(str), eventos["nome"].astype(str), strict=True))


def test_sem_serie_ou_sem_ponte_devolve_none_e_vazio(tmp_path: Path) -> None:
    assert ms.ler_serie(tmp_path) is None
    eventos, laudo = ms.eventos_da_serie(None)
    assert eventos.empty and list(eventos.columns) == list(ms.COLUNAS)
    assert laudo["janela"] == {}


def test_abertura_inedita_fechamento_confirmado_e_pendente(tmp_path: Path) -> None:
    linhas = _estaveis("pratique", 4)
    linhas += [_linha(s, "nova", "pratique", "Pratique Nova", 0.5) for s in SEMANAS[2:]]  # nasce na 40
    linhas += [_linha(s, "fechou", "pratique", "Pratique Fechou", 0.6) for s in SEMANAS[:2]]  # última na 39
    linhas += [_linha(s, "pendente", "pratique", "Pratique Pendente", 0.7) for s in SEMANAS[:4]]  # última na 41
    eventos, laudo = _rodar(tmp_path, linhas)
    assert _tipos(eventos) == [("abertura", "Pratique Nova"), ("fechamento", "Pratique Fechou")]
    abertura = eventos[eventos["tipo"] == "abertura"].iloc[0]
    assert (abertura["de"], abertura["ate"], abertura["confianca"]) == (DATAS["2026-39"], DATAS["2026-40"], "semanal")
    assert laudo["pendentes"]["unidades"] == {"pratique": 1}
    assert laudo["janela"]["unidades"] == {"de": DATAS["2026-38"], "ate": DATAS["2026-42"], "semanas": 5}


def test_quem_some_e_volta_nao_abre_nem_fecha_e_pisca_nao_conta(tmp_path: Path) -> None:
    linhas = _estaveis("pratique", 4)
    linhas += [_linha(s, "volta", "pratique", "Pratique Volta", 0.5) for s in ("2026-38", "2026-39", "2026-41", "2026-42")]
    linhas += [_linha("2026-40", "pisca", "pratique", "Pratique Pisca", 0.6)]
    eventos, laudo = _rodar(tmp_path, linhas)
    assert eventos.empty
    assert laudo["pendentes"]["unidades"] == {}


def test_troca_de_cadastro_da_mesma_rede_a_ate_1km_nao_e_movimento(tmp_path: Path) -> None:
    linhas = _estaveis("pratique", 6) + _estaveis("bluefit", 6, dlat0=1.0)
    # Mesma rede, 330 m adiante, chave nova: troca de cadastro.
    linhas += [_linha(s, "antiga", "pratique", "Pratique Centro", 0.5) for s in SEMANAS[:2]]
    linhas += [_linha(s, "renomeada", "pratique", "Pratique - Centro", 0.503) for s in SEMANAS[2:]]
    # Rede DIFERENTE no mesmo ponto: uma fecha, a outra abre (é mercado, não cadastro).
    linhas += [_linha(s, "saiu", "pratique", "Pratique Sul", 0.8) for s in SEMANAS[:2]]
    linhas += [_linha(s, "entrou", "bluefit", "Bluefit Sul", 0.8) for s in SEMANAS[2:]]
    eventos, _ = _rodar(tmp_path, linhas)
    assert _tipos(eventos) == [("abertura", "Bluefit Sul"), ("fechamento", "Pratique Sul")]


def test_recalibracao_da_rede_tira_a_semana_dela_inteira(tmp_path: Path) -> None:
    linhas = _estaveis("pratique", 5)
    # A Velocity troca as 10 chaves na 41, cada uma a 5 km da antiga (fora do casamento de 1 km).
    linhas += [_linha(s, f"v-{k}", "velocity", f"Velocity {k}", 2 + 0.1 * k) for s in SEMANAS[:3] for k in range(10)]
    linhas += [_linha(s, f"v2-{k}", "velocity", f"VELOCITY {k}", 2.05 + 0.1 * k) for s in SEMANAS[3:] for k in range(10)]
    eventos, laudo = _rodar(tmp_path, linhas)
    assert eventos.empty
    assert [(r["rede"], r["trocas"], r["unidades"]) for r in laudo["recalibracoes"]] == [("velocity", 10, 10)]


def test_salto_de_cobertura_da_rede_tira_as_entradas_e_rede_grande_segue_contando(tmp_path: Path) -> None:
    linhas = _estaveis("selfit", 20) + _estaveis("smart_fit", 200, dlat0=5.0)
    linhas += [_linha(s, f"sf-nova-{k}", "selfit", f"Selfit Nova {k}", 0.3 + 0.02 * k) for s in SEMANAS[3:] for k in range(5)]
    linhas += [_linha(s, f"sm-nova-{k}", "smart_fit", f"Smart Nova {k}", 9.3 + 0.02 * k) for s in SEMANAS[3:] for k in range(5)]
    eventos, laudo = _rodar(tmp_path, linhas)
    assert sorted(eventos["rede"].astype(str).unique()) == ["smart_fit"]
    assert int((eventos["tipo"] == "abertura").sum()) == 5
    assert [(c["rede"], c["entradas"], c["unidades"]) for c in laudo["cobertura_redes"]] == [("selfit", 5, 20)]


def test_rede_que_estreia_na_coleta_nao_abre_unidades(tmp_path: Path) -> None:
    linhas = _estaveis("pratique", 4)
    linhas += [_linha(s, f"estreante-{k}", "estreante", f"Estreante {k}", 3 + 0.02 * k) for s in SEMANAS[2:] for k in range(3)]
    eventos, _ = _rodar(tmp_path, linhas)
    assert eventos.empty


def test_em_breve_anuncio_inauguracao_pipeline_e_anuncio_que_some(tmp_path: Path) -> None:
    linhas = _estaveis("corpo", 6)
    # Mesma chave perde o sufixo na 41: inauguração.
    linhas += [_linha(s, "h", "corpo", "Corpo - Norte (Em breve)", 0.5) for s in SEMANAS[2:3]]
    linhas += [_linha(s, "h", "corpo", "Corpo - Norte", 0.5) for s in SEMANAS[3:]]
    # Anunciada na 40 e ainda "Em breve" na última: pipeline, não abertura.
    linhas += [_linha(s, "i", "corpo", "Corpo - Leste (EM BREVE)", 0.6) for s in SEMANAS[2:]]
    # Anúncio que some não é fechamento.
    linhas += [_linha(s, "j", "corpo", "Corpo - Oeste (Em breve)", 0.7) for s in SEMANAS[:2]]
    # Inaugura com a chave TROCADA (sufixo some e a coordenada anda 100 m): inauguração, não troca.
    linhas += [_linha(s, "k", "corpo", "Corpo - Sul (Em breve)", 0.8) for s in SEMANAS[:3]]
    linhas += [_linha(s, "k2", "corpo", "Corpo - Sul", 0.801) for s in SEMANAS[3:]]
    eventos, laudo = _rodar(tmp_path, linhas)
    assert _tipos(eventos) == [
        ("em_breve", "Corpo - Leste (EM BREVE)"),
        ("inauguracao", "Corpo - Norte"),
        ("inauguracao", "Corpo - Sul"),
    ]
    pipeline = eventos[eventos["tipo"] == "em_breve"].iloc[0]
    assert (pipeline["fonte"], pipeline["de"], pipeline["ate"]) == ("em_breve", DATAS["2026-40"], DATAS["2026-42"])
    assert laudo["pendentes"]["unidades"] == {}


def test_wellhub_renomeacao_sai_troca_de_dono_fica_e_independente_vira_rede_vazia(tmp_path: Path) -> None:
    base = _estaveis("independente", 150, fonte="wellhub")
    linhas = list(base)
    # Renomeada no mesmo ponto (termo próprio "braves" em comum): cadastro.
    linhas += [_linha(s, "braves", "independente", "Braves Gym Club - Xaxim", 0.5, "wellhub") for s in SEMANAS[:2]]
    linhas += [_linha(s, "braves2", "independente", "Braves - Xaxim", 0.5, "wellhub") for s in SEMANAS[2:]]
    # Outro operador no mesmo endereço (nenhum termo próprio em comum): mercado.
    linhas += [_linha(s, "baby", "independente", "Baby Gym Paulinia", 0.7, "wellhub") for s in SEMANAS[:2]]
    linhas += [_linha(s, "brinca", "independente", "Brinca e Voa", 0.7, "wellhub") for s in SEMANAS[2:]]
    # Unidade de rede credenciada: a rede vem preenchida.
    linhas += [_linha(s, "pano", "panobianco", "Panobianco Centro", 0.9, "wellhub") for s in SEMANAS[3:]]
    eventos, _ = _rodar(tmp_path, linhas)
    assert _tipos(eventos) == [
        ("entrou_agregador", "Brinca e Voa"),
        ("entrou_agregador", "Panobianco Centro"),
        ("saiu_agregador", "Baby Gym Paulinia"),
    ]
    redes = dict(zip(eventos["nome"].astype(str), eventos["rede"], strict=True))
    assert pd.isna(redes["Brinca e Voa"]) and redes["Panobianco Centro"] == "panobianco"


def test_salto_de_cobertura_do_wellhub_casa_as_trocas_antes_de_cortar(tmp_path: Path) -> None:
    linhas = _estaveis("independente", 150, fonte="wellhub")
    # Na 41 entram 3 academias de uma vez (2% da base de 150): ampliação de cobertura.
    linhas += [_linha(s, f"novo-{k}", "independente", f"Academia Nova {k}", 4 + 0.02 * k, "wellhub") for s in SEMANAS[3:] for k in range(3)]
    # Na mesma semana o coletor renomeia uma academia: a saída casa com a entrada e NÃO sobra solta.
    linhas += [_linha(s, "forca", "independente", "Forca Total", 0.5, "wellhub") for s in SEMANAS[:3]]
    linhas += [_linha(s, "forca2", "independente", "Forca Total Fitness", 0.5, "wellhub") for s in SEMANAS[3:]]
    eventos, laudo = _rodar(tmp_path, linhas)
    assert eventos.empty
    assert [(c["sentido"], c["n"], c["base"]) for c in laudo["cobertura_agregador"]] == [("entradas", 3, 151)]


def test_ponte_le_so_as_linhas_que_a_conta_usa(tmp_path: Path) -> None:
    linhas = _estaveis("independente", 50, fonte="wellhub") + _estaveis("pratique", 5)
    linhas += [_linha(s, "w-nova", "independente", "Nova", 0.5, "wellhub") for s in SEMANAS[2:]]
    serie = ms.ler_serie(_gravar(tmp_path, linhas))
    assert serie is not None
    wellhub = serie.ponte[serie.ponte["fonte"] == "wellhub"]
    assert set(wellhub["chave_snapshot"]) == {"w-nova"}
    assert serie.inicio == {"unidades": "2026-38", "wellhub": "2026-38"}
    assert serie.tamanho_fonte[("wellhub", "2026-40")] == 51


def test_janela_comeca_na_primeira_semana_com_ponte_e_usa_a_serie_inteira_para_o_inedito(tmp_path: Path) -> None:
    linhas = _estaveis("pratique", 4)
    # Vista na 38 (sem ponte), some e volta na 41: NÃO é inédita, então não abre.
    linhas += [_linha("2026-38", "antiga", "pratique", "Pratique Antiga", 0.5)]
    linhas += [_linha(s, "antiga", "pratique", "Pratique Antiga", 0.5) for s in SEMANAS[3:]]
    eventos, laudo = _rodar(tmp_path, linhas, ponte_desde="2026-39")
    assert eventos.empty
    assert laudo["janela"]["unidades"]["de"] == DATAS["2026-39"]


def test_resumo_por_rede_e_bloco_do_card(tmp_path: Path) -> None:
    linhas = _estaveis("pratique", 4) + _estaveis("independente", 150, fonte="wellhub")
    linhas += [_linha(s, "nova", "pratique", "Pratique Nova", 0.5) for s in SEMANAS[2:]]
    linhas += [_linha(s, "eb", "pratique", "Pratique Leste (Em breve)", 0.6) for s in SEMANAS[3:]]
    linhas += [_linha(s, "aera", "aera_pilates", "Aera", 0.9) for s in SEMANAS]
    linhas += [_linha(s, "w", "independente", "Academia W", 0.5, "wellhub") for s in SEMANAS[1:]]
    serie = ms.ler_serie(_gravar(tmp_path, linhas))
    eventos, laudo = ms.eventos_da_serie(serie)
    assert ms.resumo_por_rede(eventos) == {"pratique": {"aberturas": 1, "fechamentos": 0, "saldo": 1, "em_breve": 1}}
    bloco = ms.bloco_do_card(eventos, laudo, ms.redes_da_serie(serie))
    assert bloco["disponivel"] is True
    assert (bloco["de"], bloco["ate"], bloco["semanas"]) == (DATAS["2026-38"], DATAS["2026-42"], 5)
    assert bloco["redes_observadas"] == ["aera_pilates", "pratique"]
    independentes = [a for a in bloco["agregadores"] if a["grupo"] == "independentes"][0]
    assert (independentes["entradas"], independentes["saidas"], independentes["de"]) == (1, 0, DATAS["2026-38"])
    assert ms.bloco_do_card(None, {}, []) == {"disponivel": False}


@pytest.mark.parametrize("rede", ["independente", "Independente", " ", None])
def test_rede_independente_ou_vazia_vira_none(rede: Any) -> None:
    assert ms._rede_da_linha(rede) is None


def test_assinatura_muda_quando_chega_semana_nova(tmp_path: Path) -> None:
    assert ms.assinatura_da_serie(tmp_path) == ()
    linhas = _estaveis("pratique", 2, SEMANAS[:3])
    _gravar(tmp_path, linhas)
    antes = ms.assinatura_da_serie(tmp_path)
    assert len(antes) == 6 and all(str(tmp_path) in caminho for caminho, *_ in antes)
    _gravar(tmp_path, _estaveis("pratique", 2, SEMANAS[3:4]))
    assert ms.assinatura_da_serie(tmp_path) != antes


def test_anexar_ao_card_poe_a_serie_em_cada_linha_sem_mexer_no_pacote(tmp_path: Path) -> None:
    linhas = _estaveis("pratique", 4) + _estaveis("selfit", 4, dlat0=1.0)
    linhas += [_linha(s, "nova", "pratique", "Pratique Nova", 0.5) for s in SEMANAS[2:]]
    linhas += [_linha(s, f"bt-{k}", "bodytech", f"Bodytech {k}", 2 + 0.02 * k) for s in SEMANAS for k in range(2)]
    linhas += [_linha(s, "bt-nova", "bodytech", "Bodytech Nova", 2.5) for s in SEMANAS[2:]]
    serie = ms.ler_serie(_gravar(tmp_path, linhas))
    eventos, laudo = ms.eventos_da_serie(serie)
    pacote = {
        "disponivel": True,
        "tem_cadastro": True,
        "redes": [
            {"rede": "pratique", "aberturas": 3, "fechamentos": 1, "saldo": 2, "unidades": 190},
            {"rede": "selfit", "aberturas": 0, "fechamentos": 0, "saldo": 0, "unidades": 231},
            {"rede": "skyfit", "aberturas": 2, "fechamentos": 0, "saldo": 2, "unidades": 400},
        ],
    }
    card = ms.anexar_ao_card(pacote, {"eventos": eventos, "laudo": laudo, "redes": ms.redes_da_serie(serie)})
    por_rede = {linha["rede"]: linha for linha in card["redes"]}
    assert por_rede["pratique"]["aberturas"] == 3, "o histórico do pacote fica como estava"
    assert por_rede["pratique"]["semanal"] == {"aberturas": 1, "fechamentos": 0, "saldo": 1, "em_breve": 0}
    assert por_rede["selfit"]["semanal"] == {"aberturas": 0, "fechamentos": 0, "saldo": 0, "em_breve": 0}
    assert por_rede["skyfit"]["semanal"] is None, "a série não enxerga a rede: '—', nunca 0"
    assert por_rede["bodytech"]["sem_cadastro"] == "fora_da_cobertura"
    assert por_rede["bodytech"]["semanal"]["aberturas"] == 1
    assert card["semanal"]["disponivel"] is True
    assert pacote["redes"][0].get("semanal") is None, "o payload de entrada não é mutado"
    sem_serie = ms.anexar_ao_card(pacote, None)
    assert sem_serie["semanal"] == {"disponivel": False}
    assert all(linha["semanal"] is None for linha in sem_serie["redes"])


# ---------------------------------------------------------------------------
# Achados da revisão de 19/11 (antes do PR)
# ---------------------------------------------------------------------------


def test_anuncio_pela_regra_da_chave_pre_lancamento_e_inauguracao(tmp_path: Path) -> None:
    """A AD3 anuncia com "(Pré-Lançamento)", não com "Em breve": é a regra de `nome_base`."""
    linhas = _estaveis("ad3", 6)
    linhas += [_linha(s, "gaspar", "ad3", "AD3 Gaspar (Pré-Lançamento)", 0.5) for s in SEMANAS[2:4]]
    linhas += [_linha(s, "gaspar", "ad3", "AD3 Gaspar", 0.5) for s in SEMANAS[4:]]
    linhas += [_linha(s, "blumenau", "ad3", "AD3 Blumenau - Pré-venda", 0.6) for s in SEMANAS[2:]]
    linhas += [_linha(s, "itajai", "ad3", "AD3 Itajaí (Inauguração em dezembro)", 0.7) for s in SEMANAS[1:4]]
    eventos, laudo = _rodar(tmp_path, linhas)
    assert _tipos(eventos) == [("em_breve", "AD3 Blumenau - Pré-venda"), ("inauguracao", "AD3 Gaspar")]
    assert laudo["pendentes"]["unidades"] == {}, "anúncio que some na última coleta não é pendente"
    assert ms.anunciada("Smart Fit Centro (Em breve)") and not ms.anunciada("Smart Fit Centro")


def test_troca_de_chave_em_duas_semanas_seguidas_nao_vira_movimento(tmp_path: Path) -> None:
    """K1 -> K2 (uma semana só) -> K3: a chave do meio desfaz os dois pares."""
    linhas = _estaveis("pratique", 4, dlat0=3.0)
    for k in range(3):
        base = 0.03 * k
        linhas += [_linha(s, f"k1-{k}", "rede_x", f"Rede X {k}", base) for s in SEMANAS[:2]]
        linhas += [_linha("2026-40", f"k2-{k}", "rede_x", f"Rede X {k} Centro", base + 0.002)]
        linhas += [_linha(s, f"k3-{k}", "rede_x", f"Rede X - {k}", base + 0.004) for s in SEMANAS[3:]]
    eventos, laudo = _rodar(tmp_path, linhas)
    assert eventos.empty
    assert laudo["pendentes"]["unidades"] == {}


def test_troca_desfeita_depois_de_duas_semanas_nao_abre_nem_fecha(tmp_path: Path) -> None:
    """K1 some por duas coletas (o coletor trocou para K2) e volta: K2 casa com a ausência e com a volta."""
    linhas = _estaveis("pratique", 4, dlat0=3.0)
    linhas += [_linha(s, "k1", "rede_y", "Rede Y Sul", 0.5) for s in ("2026-38", "2026-39", "2026-42")]
    linhas += [_linha(s, "k2", "rede_y", "Rede Y - Sul", 0.502) for s in ("2026-40", "2026-41")]
    linhas += [_linha(s, f"y-{k}", "rede_y", f"Rede Y {k}", 1 + 0.02 * k) for s in SEMANAS for k in range(2)]
    eventos, _ = _rodar(tmp_path, linhas)
    assert eventos.empty


def test_salto_de_cobertura_olha_o_crescimento_liquido(tmp_path: Path) -> None:
    """Rede de 100 que abre 6 e fecha 3 de verdade na mesma semana: não é o coletor achando páginas."""
    linhas = _estaveis("grande", 97, dlat0=5.0)
    linhas += [_linha(s, f"sai-{k}", "grande", f"Grande Sai {k}", 8.0 + 0.03 * k) for s in SEMANAS[:2] for k in range(3)]
    linhas += [_linha(s, f"novo-{k}", "grande", f"Grande Novo {k}", 0.1 + 0.03 * k) for s in SEMANAS[2:] for k in range(6)]
    eventos, laudo = _rodar(tmp_path, linhas)
    assert int((eventos["tipo"] == "abertura").sum()) == 6
    assert int((eventos["tipo"] == "fechamento").sum()) == 3
    assert laudo["cobertura_redes"] == []


def test_bloco_do_card_tira_estudios_e_ultra_do_laudo() -> None:
    laudo = {
        "janela": {"unidades": {"de": "2026-09-20", "ate": "2026-11-15", "semanas": 9}},
        "pendentes": {"unidades": {"velocity": 2, "pratique": 1, "ultra": 1}, "wellhub": {"": 4}},
        "recalibracoes": [
            {"rede": "velocity", "de": "a", "ate": "b", "trocas": 9, "unidades": 9},
            {"rede": "evoque", "de": "a", "ate": "b", "trocas": 9, "unidades": 9},
        ],
        "cobertura_redes": [{"rede": "kore", "de": "a", "ate": "b", "entradas": 5, "unidades": 20}],
        "cobertura_agregador": [],
    }
    bloco = ms.bloco_do_card(None, laudo, ["velocity", "pratique"], excluir={"velocity", "kore"})
    assert bloco["pendentes"] == {"unidades": 1, "wellhub": 4}
    assert [r["rede"] for r in bloco["recalibracoes"]] == ["evoque"]
    assert bloco["cobertura_redes"] == []
    assert bloco["redes_observadas"] == ["pratique"]


def test_rede_que_estreia_no_meio_da_janela_fica_sem_leitura_ate_mexer(tmp_path: Path) -> None:
    linhas = _estaveis("pratique", 4) + _estaveis("tardia", 3, SEMANAS[3:], dlat0=2.0)
    serie = ms.ler_serie(_gravar(tmp_path, linhas))
    eventos, laudo = ms.eventos_da_serie(serie)
    card = ms.anexar_ao_card(
        {"tem_cadastro": True, "redes": [{"rede": "pratique"}, {"rede": "tardia"}]},
        {"eventos": eventos, "laudo": laudo, "redes": ms.redes_da_serie(serie)},
    )
    por_rede = {linha["rede"]: linha["semanal"] for linha in card["redes"]}
    assert por_rede["pratique"] == {"aberturas": 0, "fechamentos": 0, "saldo": 0, "em_breve": 0}
    assert por_rede["tardia"] is None, "zero afirmaria que ela ficou parada antes de ser coletada"


def test_assinatura_ve_a_escrita_do_arquivo_e_nao_so_a_pasta(tmp_path: Path) -> None:
    _gravar(tmp_path, _estaveis("pratique", 2, SEMANAS[:2]))
    antes = ms.assinatura_da_serie(tmp_path)
    arquivo = tmp_path / ms.DIR_PONTE / "semana=2026-39" / "fonte=unidades" / "part-0.parquet"
    pd.DataFrame({"chave_snapshot": ["a", "b", "c"], "nome": ["x", "y", "z"], "lat": [1.0, 2.0, 3.0], "lng": [1.0, 2.0, 3.0]}).to_parquet(
        arquivo, index=False
    )
    assert ms.assinatura_da_serie(tmp_path) != antes


@pytest.mark.parametrize(
    ("nome", "esperado"),
    [
        ("Smart Fit Centro (Em breve)", True),
        ("AD3 Gaspar (Pré-Lançamento)", True),
        ("Bluefit Maracaju - Pré-venda", True),
        ("AD3 Itajaí (Inauguração em dezembro)", True),
        ("Pedroso de Morais - Inaugurada", False),
        ("Academia Inaugurado", False),
        ("Smart Fit Centro", False),
        (None, False),
    ],
)
def test_anuncio_reconhece_o_marcador_da_chave_menos_inaugurada(nome: Any, esperado: bool) -> None:
    assert ms.anunciada(nome) is esperado
