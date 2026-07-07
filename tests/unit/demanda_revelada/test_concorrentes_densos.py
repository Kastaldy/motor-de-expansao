"""BLK-ATR-01: testes offline da base DENSA de concorrentes do Huff.

Fixtures 100% SINTETICAS (nunca `concorrentes/` real nem parquet real): CSVs pequenos em
`tmp_path` (`sep=";"`, `encoding="utf-8-sig"`) com coords reais do Brasil, uma `concorrentes_
mapeados` fake e um `df_join` sintetico. Cobre: ingestao/volume, dedup intra-fonte, dedup
inter-fonte (precedencia), dedup contra base atual, schema/contrato, centroide, isolamento de
import (AST), rede pelo nome do arquivo de Unidades, e o smoke da re-validacao Huff.
"""

from __future__ import annotations

import ast
import inspect
from pathlib import Path

import h3
import numpy as np
import pandas as pd
import pytest

from motor_expansao.demanda_revelada import concorrentes_densos as m


# --------------------------------------------------------------------------- #
# Fixtures sinteticas
# --------------------------------------------------------------------------- #
def _escrever_csv(caminho: Path, df: pd.DataFrame) -> None:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(caminho, sep=";", encoding="utf-8-sig", index=False)


@pytest.fixture
def dirs_sinteticos(tmp_path: Path) -> tuple[Path, Path, Path]:
    """3 pastas de CSVs sinteticos com casos de dedup embutidos."""
    tp = tmp_path / "totalpass"
    wh = tmp_path / "wellhub"
    un = tmp_path / "unidades"

    # TotalPass: 2 Smart Fit no MESMO hex (dup intra-fonte) + 1 nome que cai em `independente`.
    _escrever_csv(
        tp / "unidades_totalpass_sp.csv",
        pd.DataFrame(
            {
                "slug": ["a", "b", "c"],
                "nome": ["Smart Fit Centro", "Smart Fit Anexo", "Padaria do Ze"],
                "latitude": [-23.5500, -23.5501, -23.6000],
                "longitude": [-46.6300, -46.6301, -46.7000],
                "cidade": ["SP", "SP", "SP"],
                "uf": ["SP", "SP", "SP"],
                "cep": ["01000-000", "01000-000", "02000-000"],
                "endereco_formatado": ["Rua A", "Rua B", "Rua C"],
                "modalidades": ["Musc", "Musc", "Pao"],
                "data_coleta": ["2026-06-01", "2026-06-01", "2026-06-01"],
            }
        ),
    )
    # WellHub: mesma Smart Fit no MESMO hex do TP (dup inter-fonte) + Bluefit distinta.
    _escrever_csv(
        wh / "unidades_wellhub_sp.csv",
        pd.DataFrame(
            {
                "slug": ["d", "e"],
                "nome": ["Smart Fit Filial", "Bluefit Sul"],
                "latitude": [-23.5500, -23.8000],
                "longitude": [-46.6300, -46.9000],
                "cidade": ["SP", "SP"],
                "uf": ["SP", "SP"],
                "cep": ["01000-000", "03000-000"],
                "endereco_formatado": ["Rua D", "Rua E"],
                "atividades": ["Musc", "Musc"],
                "data_coleta": ["2026-05-29", "2026-05-29"],
            }
        ),
    )
    # Unidades: rede vem do nome do arquivo (`unidades_selfit.csv` -> `selfit`).
    _escrever_csv(
        un / "unidades_selfit.csv",
        pd.DataFrame(
            {
                "nome_unidade": ["Selfit Norte"],
                "latitude": [-23.4000],
                "longitude": [-46.5000],
                "data_coleta": ["2026-05-25"],
            }
        ),
    )
    return tp, wh, un


@pytest.fixture
def base_atual_fake(tmp_path: Path) -> Path:
    """`concorrentes_mapeados` fake: 1 Smart Fit no MESMO hex do TP (dedup contra base atual)."""
    hex_sf = h3.latlng_to_cell(-23.5500, -46.6300, 7)
    hex_outro = h3.latlng_to_cell(-22.9000, -43.2000, 7)  # RJ, so na base atual
    df = pd.DataFrame(
        {
            "hex_id_res7": [hex_sf, hex_outro],
            "rede": ["smart_fit", "panobianco"],
        }
    )
    p = tmp_path / "concorrentes_mapeados.parquet"
    df.to_parquet(p, index=False)
    return p


# --------------------------------------------------------------------------- #
# 1. Ingestao / volume
# --------------------------------------------------------------------------- #
def test_ingestao_volume(dirs_sinteticos: tuple[Path, Path, Path]) -> None:
    tp, wh, un = dirs_sinteticos
    cons = m.ingerir_csvs_concorrentes(tp, wh, un)
    assert not cons.empty
    assert set(cons.columns) == {"hex_id_res7", "rede_normalizada", "fonte", "n_unidades_no_hex"}
    assert set(cons["fonte"].unique()) <= {"totalpass", "wellhub", "unidades"}


@pytest.mark.skipif(
    not m.DIR_TOTALPASS_DEFAULT.exists(),
    reason="CSVs reais de concorrentes/ ausentes (sanity so roda localmente)",
)
def test_volume_real_maior_que_10k() -> None:
    """Sanity de volume REAL (>10.000 unidades) -- so local, nunca no CI."""
    cons = m.ingerir_csvs_concorrentes()
    assert int(cons["n_unidades_no_hex"].sum()) > 10_000


# --------------------------------------------------------------------------- #
# 2. Dedup intra-fonte
# --------------------------------------------------------------------------- #
def test_dedup_intra_fonte(dirs_sinteticos: tuple[Path, Path, Path]) -> None:
    tp, wh, un = dirs_sinteticos
    cons = m.ingerir_csvs_concorrentes(tp, wh, un)
    sf_tp = cons[
        (cons["rede_normalizada"] == "smart_fit") & (cons["fonte"] == "totalpass")
    ]
    assert len(sf_tp) == 1  # 2 linhas brutas colapsaram em 1
    assert int(sf_tp["n_unidades_no_hex"].iloc[0]) >= 2


# --------------------------------------------------------------------------- #
# 3. Dedup inter-fonte + precedencia
# --------------------------------------------------------------------------- #
def test_dedup_inter_fonte(dirs_sinteticos: tuple[Path, Path, Path]) -> None:
    tp, wh, un = dirs_sinteticos
    final = m.materializar(tp, wh, un, escrever=False, incluir_base_atual=False)
    sf = final[final["rede_normalizada"] == "smart_fit"]
    assert len(sf) == 1  # TP + WH mesma (hex, rede) -> 1 linha
    assert sf["fonte"].iloc[0] == "totalpass"  # precedencia unidades>totalpass>wellhub


# --------------------------------------------------------------------------- #
# 4. Dedup contra a base atual
# --------------------------------------------------------------------------- #
def test_dedup_contra_base_atual(
    dirs_sinteticos: tuple[Path, Path, Path], base_atual_fake: Path
) -> None:
    tp, wh, un = dirs_sinteticos
    final = m.materializar(
        tp, wh, un, escrever=False, concorrentes_path=base_atual_fake, incluir_base_atual=True
    )
    sf = final[final["rede_normalizada"] == "smart_fit"]
    # A Smart Fit ja esta na base atual (mesmo hex) -> so aparece como base_atual, nao como fonte nova.
    assert len(sf) == 1
    assert bool(sf["flag_da_base_atual"].iloc[0]) is True
    assert sf["fonte"].iloc[0] == "base_atual"
    # A base atual inteira e anexada (panobianco do RJ so existe na base atual).
    assert (final["rede_normalizada"] == "panobianco").any()
    # Chave unica no total.
    assert final.duplicated(subset=["hex_id_res7", "rede_normalizada"]).sum() == 0


# --------------------------------------------------------------------------- #
# 5. Schema / contrato
# --------------------------------------------------------------------------- #
def test_schema_parquet(
    dirs_sinteticos: tuple[Path, Path, Path], base_atual_fake: Path
) -> None:
    tp, wh, un = dirs_sinteticos
    final = m.materializar(
        tp, wh, un, escrever=False, concorrentes_path=base_atual_fake, incluir_base_atual=True
    )
    assert list(final.columns) == list(m.CONTRATO_COLUNAS_CONCORRENTES_DENSOS.keys())
    assert not final["hex_id_res7"].isna().any()
    assert not final["rede_normalizada"].isna().any()
    assert (final["rede_normalizada"].astype(str).str.len() > 0).all()
    for hid in final["hex_id_res7"].astype(str):
        assert h3.is_valid_cell(hid) and h3.get_resolution(hid) == 7
    assert (final["versao_contrato"] == "concorrentes_densos_v1").all()
    # _assert_schema nao deve levantar sobre o frame final.
    m._assert_schema(final)


# --------------------------------------------------------------------------- #
# 6. lat/lng = centroide do hex (nao coord GPS bruta)
# --------------------------------------------------------------------------- #
def test_lat_lng_centroide(dirs_sinteticos: tuple[Path, Path, Path]) -> None:
    tp, wh, un = dirs_sinteticos
    final = m.materializar(tp, wh, un, escrever=False, incluir_base_atual=False)
    linha = final.iloc[0]
    lat_c, lng_c = h3.cell_to_latlng(str(linha["hex_id_res7"]))
    assert linha["lat"] == pytest.approx(lat_c)
    assert linha["lng"] == pytest.approx(lng_c)
    # E NAO a coord GPS bruta (-23.55/-46.63) na maioria dos casos: o centroide difere.
    assert not (linha["lat"] == pytest.approx(-23.5500) and linha["lng"] == pytest.approx(-46.6300))


# --------------------------------------------------------------------------- #
# 7. Isolamento de imports (AST)
# --------------------------------------------------------------------------- #
def test_isolamento_imports() -> None:
    # AST sobre os IMPORTS reais (nao a prosa do docstring, que cita os paths proibidos como
    # guardrail): nenhum import de topo nem interno pode casar M1/dashboard/censo/api/config raiz.
    src = inspect.getsource(m)
    tree = ast.parse(src)
    nomes: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            nomes.append(node.module)
        elif isinstance(node, ast.Import):
            nomes.extend(a.name for a in node.names)
    for n in nomes:
        assert "pipelines.m1" not in n, n
        assert not n.startswith("motor_expansao.dashboard"), n
        assert not n.startswith("motor_expansao.api"), n
        assert "censo" not in n, n
        # `dimensionamento.config` e paralelo/permitido; so o `config.py` raiz do M1 e proibido.
        assert n not in ("motor_expansao.config", "config"), n


# --------------------------------------------------------------------------- #
# 8. Rede pelo nome do arquivo de Unidades
# --------------------------------------------------------------------------- #
def test_unidades_rede_do_nome_arquivo(tmp_path: Path) -> None:
    un = tmp_path / "unidades"
    _escrever_csv(
        un / "unidades_smart_fit.csv",
        pd.DataFrame(
            {"nome_unidade": ["X"], "latitude": [-23.5], "longitude": [-46.6], "data_coleta": ["2026"]}
        ),
    )
    df = m._ler_csv_unidades(un / "unidades_smart_fit.csv")
    assert (df["rede_normalizada"] == "smart_fit").all()
    assert (df["fonte"] == "unidades").all()


# --------------------------------------------------------------------------- #
# 9. Sem CSV -> frame vazio bem-formado
# --------------------------------------------------------------------------- #
def test_ingestao_vazia(tmp_path: Path) -> None:
    vazio = tmp_path / "nada"
    vazio.mkdir()
    cons = m.ingerir_csvs_concorrentes(vazio, vazio, vazio)
    assert cons.empty
    final = m.materializar(vazio, vazio, vazio, escrever=False, incluir_base_atual=False)
    assert list(final.columns) == list(m.CONTRATO_COLUNAS_CONCORRENTES_DENSOS.keys())
    assert final.empty


# --------------------------------------------------------------------------- #
# 10. Smoke da re-validacao Huff (fiacao, nao o numero)
# --------------------------------------------------------------------------- #
def test_revalidacao_smoke(dirs_sinteticos: tuple[Path, Path, Path]) -> None:
    tp, wh, un = dirs_sinteticos
    final = m.materializar(tp, wh, un, escrever=False, incluir_base_atual=False)

    # df_join sintetico: hexes reais + membros crescente (N suficiente p/ o harness).
    rng = np.random.default_rng(42)
    hexes: list[str] = []
    seen: set[str] = set()
    lat0, lng0 = -23.55, -46.63
    passo = 0.02
    lado = 8
    for i in range(lado):
        for j in range(lado):
            hh = h3.latlng_to_cell(lat0 + i * passo, lng0 + j * passo, 7)
            if hh not in seen:
                seen.add(hh)
                hexes.append(hh)
    membros = (np.arange(len(hexes)) * 3 + rng.integers(0, 5, len(hexes))).astype(int)
    df_join = pd.DataFrame({"hex_id": hexes, "membros": membros})

    result, cobertura = m.revalidar_huff_densa(final, df_join=df_join)
    assert result.veredito in {"GO", "NO-GO"}
    assert "n_concorrentes" in cobertura
    assert "pct_hex_competitivo" in cobertura
    assert result.n_join == len(hexes)

    # gerar_relatorio_huff_densa nao levanta e passa a rede anti-PII (escrever=False).
    consolidado = m.ingerir_csvs_concorrentes(tp, wh, un)
    dedup = m.deduplicar(consolidado, incluir_base_atual=False)
    base_atual = pd.DataFrame(columns=["hex_id_res7", "rede_normalizada"])
    texto = m.gerar_relatorio_huff_densa(
        result, result, cobertura, cobertura, consolidado, dedup, base_atual, escrever=False
    )
    assert "BLK-ATR-01" in texto
    assert "DEDUP" in texto
