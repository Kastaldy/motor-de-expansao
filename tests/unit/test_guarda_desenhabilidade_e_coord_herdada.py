"""Regen de 2026-11-01: guarda de desenhabilidade com margem e coordenada herdada da semana anterior.

Naquele domingo o regen reprovou por 4.736 -> 4.734 pins desenhaveis: a regra era "nao pode cair
nenhum", e a queda era rotacao normal (1 academia saiu do site, 10 vieram sem coordenada, 8
entraram). Duas correcoes:

- a guarda passa a reprovar so' o COLAPSO por rede ou a queda grande do total (regua da DEC-061);
- a academia que continua listada mas veio sem coordenada herda a da semana anterior.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from motor_expansao.pipelines import guarda_desenhabilidade as guarda
from motor_expansao.pipelines import normalizar_concorrentes as nc
from motor_expansao.pipelines.guarda_desenhabilidade import desenhaveis, quedas_de_desenhaveis
from motor_expansao.pipelines.normalizar_concorrentes import (
    COORD_AUSENTE,
    COORD_DA_COLETA,
    COORD_DA_SEMANA_ANTERIOR,
    herdar_coordenadas_da_semana_anterior,
    normalizar,
)

ROOT = Path(__file__).resolve().parents[2]
WRAPPER = ROOT / "scripts" / "cron" / "run_regen_mercado.sh"


# ---------------------------------------------------------------------------
# Guarda de desenhabilidade
# ---------------------------------------------------------------------------


def _pins(contagem: dict[str, int]) -> pd.DataFrame:
    linhas = []
    for rede, n in contagem.items():
        for i in range(n):
            linhas.append(
                {"rede": rede, "lat": -23.0 - i * 1e-3, "lng": -46.0, "status_registro": "valido"}
            )
    return pd.DataFrame(linhas)


def test_rotacao_normal_da_semana_aprova() -> None:
    """O caso de 01/11: algumas redes perdem 1-3 pins, outras ganham; total -2. Tem de passar."""
    antes = _pins(
        {"26fit": 66, "live": 28, "redfit": 24, "panobianco": 534, "skyfit": 449, "outras": 3635}
    )
    agora = _pins(
        {"26fit": 63, "live": 26, "redfit": 22, "panobianco": 536, "skyfit": 450, "outras": 3637}
    )
    assert len(antes) - len(agora) == 2
    assert quedas_de_desenhaveis(antes, agora) == []


def test_colapso_de_uma_rede_reprova_mesmo_com_total_quase_igual() -> None:
    """O caso de 13/09: o lote morreu no meio, a Selfit caiu 48% e o total so' 2,6%."""
    antes = _pins({"selfit": 231, "outras": 4358})
    agora = _pins({"selfit": 119, "outras": 4351})
    motivos = quedas_de_desenhaveis(antes, agora)
    assert len(motivos) == 1
    assert "selfit" in motivos[0] and "231 -> 119" in motivos[0]


def test_rede_que_some_inteira_reprova() -> None:
    antes = _pins({"selfit": 10, "outras": 500})
    agora = _pins({"outras": 500})
    assert any("selfit" in m for m in quedas_de_desenhaveis(antes, agora))


def test_rede_pequena_nao_reprova_por_uma_academia() -> None:
    """Abaixo do piso de 5 pins, 1 academia a menos ja' passa de 30%: seria ruido."""
    antes = _pins({"pequena": 4, "outras": 500})
    agora = _pins({"pequena": 2, "outras": 500})
    assert quedas_de_desenhaveis(antes, agora) == []


def test_queda_difusa_do_total_reprova() -> None:
    """Muitas redes perdendo pouco (nenhuma acima de 30%) ainda reprova pelo total (> 10%)."""
    antes = _pins({f"r{i}": 10 for i in range(20)})
    agora = _pins({f"r{i}": 8 for i in range(20)})
    motivos = quedas_de_desenhaveis(antes, agora)
    assert len(motivos) == 1 and "no total" in motivos[0]


def test_crescimento_aprova() -> None:
    assert quedas_de_desenhaveis(_pins({"a": 10}), _pins({"a": 12})) == []


def test_desenhavel_exige_status_valido_e_coordenada() -> None:
    df = pd.DataFrame(
        {
            "rede": ["a", "a", "a"],
            "lat": [-23.0, None, -23.1],
            "lng": [-46.0, -46.0, -46.1],
            "status_registro": ["valido", "valido", "descartado_coord"],
        }
    )
    assert len(desenhaveis(df)) == 1


def test_constantes_iguais_as_da_guarda_do_snapshot() -> None:
    """As duas guardas medem o mesmo feed: a regua nao pode divergir em silencio (DEC-061)."""
    from motor_expansao.vulnerabilidade import contrato

    assert guarda.TOLERANCIA_QUEDA_REDE_PCT == contrato.TOLERANCIA_QUEDA_REDE_PCT
    assert guarda.TOLERANCIA_QUEDA_TOTAL_PCT == contrato.TOLERANCIA_QUEDA_TOTAL_PCT
    assert guarda.MIN_UNIDADES_GUARDA_REDE == contrato.MIN_UNIDADES_GUARDA_REDE
    assert guarda.MIN_UNIDADES_GUARDA_TOTAL == contrato.MIN_UNIDADES_GUARDA_TOTAL


def test_wrapper_usa_a_guarda_do_pacote_e_nao_a_regra_sem_margem() -> None:
    texto = WRAPPER.read_text(encoding="utf-8")
    assert "from motor_expansao.pipelines.guarda_desenhabilidade import" in texto
    assert "quedas_de_desenhaveis(conc_vivo, conc_novo)" in texto
    assert "len(conc_novo) < len(conc_vivo)" not in texto


# ---------------------------------------------------------------------------
# Coordenada herdada da semana anterior
# ---------------------------------------------------------------------------


def _coleta(linhas: list[tuple[str, str, float | None, float | None]]) -> pd.DataFrame:
    df = pd.DataFrame(linhas, columns=["rede", "nome_unidade", "lat", "lng"])
    df["data_coleta"] = "2026-11-01"
    df["arquivo_origem"] = "unidades_" + df["rede"] + ".csv"
    df["lat"] = df["lat"].astype("float64")
    df["lng"] = df["lng"].astype("float64")
    return df


def _anterior(linhas: list[tuple[str, str, float | None, float | None]]) -> pd.DataFrame:
    df = pd.DataFrame(linhas, columns=["rede", "nome_unidade", "lat", "lng"])
    df["lat"] = df["lat"].astype("float64")
    df["lng"] = df["lng"].astype("float64")
    return df


def test_academia_sem_coordenada_herda_a_da_semana_anterior() -> None:
    agora = _coleta(
        [("26fit", "26FIT-PANAMBI", None, None), ("26fit", "26FIT-CENTRO", -28.0, -53.0)]
    )
    ant = _anterior(
        [("26fit", "26FIT-PANAMBI", -28.2951, -53.5011), ("26fit", "26FIT-CENTRO", -28.0, -53.0)]
    )
    out = normalizar([agora], anterior=ant)
    panambi = out[out["nome_unidade"] == "26FIT-PANAMBI"].iloc[0]
    assert panambi["status_registro"] == "valido"
    assert (panambi["lat"], panambi["lng"]) == (-28.2951, -53.5011)
    assert panambi["coord_origem"] == COORD_DA_SEMANA_ANTERIOR
    assert panambi["hex_id_res7"] is not None and panambi["concorrente_id"] is not None
    assert out.loc[out["nome_unidade"] == "26FIT-CENTRO", "coord_origem"].iloc[0] == COORD_DA_COLETA


def test_concorrente_id_herdado_e_o_mesmo_da_semana_anterior() -> None:
    """O id e' hash de rede|nome|lat|lng: herdando a coordenada, a academia mantem a identidade."""
    com = normalizar([_coleta([("live", "FRANCESES", -3.07425, -60.031724)])])
    sem = normalizar([_coleta([("live", "FRANCESES", None, None)])], anterior=com)
    assert sem["concorrente_id"].iloc[0] == com["concorrente_id"].iloc[0]


def test_coordenada_da_coleta_nunca_e_sobrescrita() -> None:
    agora = _coleta([("cristal", "Cristal Guarulhos", -23.40, -46.50)])
    ant = _anterior([("cristal", "Cristal Guarulhos", -23.46, -46.51)])
    out = herdar_coordenadas_da_semana_anterior(agora, ant)
    assert (out["lat"].iloc[0], out["lng"].iloc[0]) == (-23.40, -46.50)
    assert out["coord_origem"].iloc[0] == COORD_DA_COLETA


def test_casa_nome_com_caixa_e_espaco_diferentes() -> None:
    agora = _coleta([("power_fit", "Power Fit  Matriz ", None, None)])
    ant = _anterior([("power_fit", "POWER FIT MATRIZ", -15.587, -56.053)])
    out = herdar_coordenadas_da_semana_anterior(agora, ant)
    assert out["coord_origem"].iloc[0] == COORD_DA_SEMANA_ANTERIOR


def test_nao_cruza_redes() -> None:
    agora = _coleta([("tonus_gym", "AMERICANA", None, None)])
    ant = _anterior([("vidya_studio", "AMERICANA", -22.75, -47.34)])
    out = herdar_coordenadas_da_semana_anterior(agora, ant)
    assert pd.isna(out["lat"].iloc[0]) and out["coord_origem"].iloc[0] == COORD_AUSENTE


def test_chave_ambigua_na_semana_anterior_nao_herda() -> None:
    """Duas coordenadas para o mesmo nome: escolher uma seria inventar endereco."""
    agora = _coleta([("smart_fit", "Centro", None, None)])
    ant = _anterior([("smart_fit", "Centro", -23.0, -46.0), ("smart_fit", "Centro", -22.0, -43.0)])
    out = herdar_coordenadas_da_semana_anterior(agora, ant)
    assert out["coord_origem"].iloc[0] == COORD_AUSENTE


def test_nome_repetido_na_coleta_nao_herda() -> None:
    agora = _coleta([("smart_fit", "Centro", None, None), ("smart_fit", "Centro", None, None)])
    ant = _anterior([("smart_fit", "Centro", -23.0, -46.0)])
    out = herdar_coordenadas_da_semana_anterior(agora, ant)
    assert (out["coord_origem"] == COORD_AUSENTE).all()


def test_academia_que_saiu_do_site_nao_volta() -> None:
    """Herdar so' completa quem esta' NESTA coleta; quem fechou sai do CSV e some do mapa."""
    agora = _coleta([("redfit", "Tatuape", -23.54, -46.56)])
    ant = _anterior(
        [("redfit", "Tatuape", -23.54, -46.56), ("redfit", "Aricanduva", -23.555, -46.517)]
    )
    out = normalizar([agora], anterior=ant)
    assert list(out["nome_unidade"]) == ["Tatuape"]


def test_coordenada_invalida_da_semana_anterior_nao_e_herdada() -> None:
    agora = _coleta([("a", "X", None, None)])
    ant = _anterior([("a", "X", 0.0, 0.0)])
    out = herdar_coordenadas_da_semana_anterior(agora, ant)
    assert out["coord_origem"].iloc[0] == COORD_AUSENTE


def test_sem_semana_anterior_nada_muda() -> None:
    agora = _coleta([("a", "X", None, None), ("a", "Y", -23.0, -46.0)])
    out = normalizar([agora])
    assert list(out["status_registro"]) == ["descartado_coord", "valido"]
    assert list(out["coord_origem"]) == [COORD_AUSENTE, COORD_DA_COLETA]


def test_funcao_nao_muta_a_entrada() -> None:
    agora = _coleta([("a", "X", None, None)])
    copia = agora.copy()
    herdar_coordenadas_da_semana_anterior(agora, _anterior([("a", "X", -23.0, -46.0)]))
    pd.testing.assert_frame_equal(agora, copia)


def test_main_herda_do_parquet_publicado(tmp_path: Path, monkeypatch) -> None:
    """No regen, OUT_PATH guarda a copia REAL do publicado: e' de la' que vem a coordenada."""
    conc_dir = tmp_path / "concorrentes"
    conc_dir.mkdir()
    (conc_dir / "unidades_live.csv").write_text(
        "nome_unidade;latitude;longitude;data_coleta\nFRANCESES;;;2026-11-01\nMARGARITA;-3.0;-59.98;2026-11-01\n",
        encoding="utf-8",
    )
    out_path = tmp_path / "staging" / "concorrentes_mapeados.parquet"
    out_path.parent.mkdir()
    normalizar([_coleta([("live", "FRANCESES", -3.07425, -60.031724)])]).to_parquet(
        out_path, index=False
    )
    monkeypatch.setattr(nc, "CONCORRENTES_DIR", conc_dir)
    monkeypatch.setattr(nc, "OUT_PATH", out_path)

    nc.main()

    salvo = pd.read_parquet(out_path).set_index("nome_unidade")
    assert salvo.loc["FRANCESES", "status_registro"] == "valido"
    assert salvo.loc["FRANCESES", "coord_origem"] == COORD_DA_SEMANA_ANTERIOR
    assert salvo.loc["MARGARITA", "coord_origem"] == COORD_DA_COLETA
