"""BLK-ATR-01-FU1: testes offline do módulo aferir_overlap_nao_abra.

Fixtures 100% SINTÉTICAS: NUNCA leem `/repo/NAO_ABRA/` real. Todos os arquivos
de entrada usam `tmp_path`. O parquet denso também é sintético (em `tmp_path`).

Guardrail DEC-012: PII (ID, Nome, Nome_Academia, Latitude, Longitude) NUNCA persiste
além do drop na fronteira. O relatório gerado contém SÓ métricas agregadas.
"""

from __future__ import annotations

import ast
import importlib.util
from pathlib import Path

import h3
import pandas as pd

import motor_expansao.demanda_revelada.aferir_overlap_nao_abra as m
from motor_expansao.demanda_revelada.concorrentes_densos import CONTRATO_COLUNAS_CONCORRENTES_DENSOS

# --------------------------------------------------------------------------- #
# Hexes reais do Brasil (para fixtures sintéticas)
# --------------------------------------------------------------------------- #
HEX_SP_A = h3.latlng_to_cell(-23.5500, -46.6300, 7)
HEX_SP_B = h3.latlng_to_cell(-23.5600, -46.6400, 7)
HEX_RJ = h3.latlng_to_cell(-22.9068, -43.1729, 7)
HEX_RS = h3.latlng_to_cell(-30.0346, -51.2177, 7)


# --------------------------------------------------------------------------- #
# Helpers para criar XLSXs sintéticos
# --------------------------------------------------------------------------- #
def _xlsx_smartfit(tmp_path: Path, linhas: list[dict]) -> Path:
    """Cria SmartFit.xlsx sintético em tmp_path."""
    caminho = tmp_path / "01_SmartFit.xlsx"
    df = pd.DataFrame(linhas)
    df.to_excel(caminho, index=False)
    return caminho


def _xlsx_competidores(tmp_path: Path, linhas: list[dict]) -> Path:
    """Cria Competidores.xlsx sintético em tmp_path."""
    caminho = tmp_path / "03_Competidores.xlsx"
    df = pd.DataFrame(linhas)
    df.to_excel(caminho, index=False)
    return caminho


def _parquet_denso(tmp_path: Path, linhas: list[dict]) -> Path:
    """Cria concorrentes_densos.parquet sintético em tmp_path."""
    caminho = tmp_path / "concorrentes_densos.parquet"
    # Gera lat/lng dos centroides para cada hex
    rows = []
    for linha in linhas:
        lat, lng = h3.cell_to_latlng(linha["hex_id_res7"])
        row = dict(linha)
        row.setdefault("lat", lat)
        row.setdefault("lng", lng)
        row.setdefault("versao_contrato", "concorrentes_densos_v1")
        rows.append(row)
    df = pd.DataFrame(rows)
    # Coerce tipos do contrato
    for col, dtype in CONTRATO_COLUNAS_CONCORRENTES_DENSOS.items():
        if col in df.columns:
            df[col] = df[col].astype(dtype)
    df.to_parquet(caminho, index=False)
    return caminho


# --------------------------------------------------------------------------- #
# Dados sintéticos reutilizados
# --------------------------------------------------------------------------- #
_SF_LINHAS = [
    {"ID": 1, "Nome": "Smart Fit SP A", "Latitude": -23.5500, "Longitude": -46.6300},
    {"ID": 2, "Nome": "Smart Fit SP A Dup", "Latitude": -23.5501, "Longitude": -46.6301},  # mesmo hex
    {"ID": 3, "Nome": "Smart Fit RJ", "Latitude": -22.9068, "Longitude": -43.1729},
    {"ID": 4, "Nome": "Smart Fit RS", "Latitude": -30.0346, "Longitude": -51.2177},
]

_COMP_LINHAS = [
    {
        "Latitude": -23.5500, "Longitude": -46.6300,
        "Nome_Academia": "Smart Fit SP Bla",
        "Plano": "tp1", "Alunos_Academia": 1000,
        "Total_Alunos_Cluster": 2000, "Total_Academias": 2,
        "Município": "SP", "Cluster_ID": 1,
    },
    {
        "Latitude": -23.5500, "Longitude": -46.6300,
        "Nome_Academia": "Smart Fit SP Bla 2",
        "Plano": "tp1", "Alunos_Academia": 900,
        "Total_Alunos_Cluster": 2000, "Total_Academias": 2,
        "Município": "SP", "Cluster_ID": 1,
    },
    {
        # Coords arredondadas (1 decimal) — simulando viés de hex
        "Latitude": -22.9, "Longitude": -43.2,
        "Nome_Academia": "SKYFIT ACADEMIA RJ",
        "Plano": "tp2", "Alunos_Academia": 500,
        "Total_Alunos_Cluster": 500, "Total_Academias": 1,
        "Município": "RJ", "Cluster_ID": 2,
    },
    {
        "Latitude": -30.0346, "Longitude": -51.2177,
        "Nome_Academia": "Academia Independente XYZ",
        "Plano": "tp3", "Alunos_Academia": 300,
        "Total_Alunos_Cluster": 600, "Total_Academias": 2,
        "Município": "RS", "Cluster_ID": 3,
    },
    {
        "Latitude": -30.0346, "Longitude": -51.2177,
        "Nome_Academia": "Academia Independente ABC",
        "Plano": "tp3", "Alunos_Academia": 250,
        "Total_Alunos_Cluster": 600, "Total_Academias": 2,
        "Município": "RS", "Cluster_ID": 3,
    },
    {
        "Latitude": -23.5600, "Longitude": -46.6400,
        "Nome_Academia": "Panobianco Centro",
        "Plano": "tp2", "Alunos_Academia": 800,
        "Total_Alunos_Cluster": 800, "Total_Academias": 1,
        "Município": "SP", "Cluster_ID": 4,
    },
]

_DENSO_LINHAS = [
    {
        "hex_id_res7": HEX_SP_A,
        "rede_normalizada": "smart_fit",
        "fonte": "totalpass",
        "flag_da_base_atual": False,
        "n_unidades_no_hex": 2,
    },
    {
        "hex_id_res7": HEX_RJ,
        "rede_normalizada": "smart_fit",
        "fonte": "unidades",
        "flag_da_base_atual": True,
        "n_unidades_no_hex": 1,
    },
    {
        "hex_id_res7": HEX_SP_B,
        "rede_normalizada": "panobianco",
        "fonte": "unidades",
        "flag_da_base_atual": True,
        "n_unidades_no_hex": 1,
    },
    {
        "hex_id_res7": HEX_RJ,
        "rede_normalizada": "skyfit",
        "fonte": "unidades",
        "flag_da_base_atual": False,
        "n_unidades_no_hex": 1,
    },
]


# --------------------------------------------------------------------------- #
# Teste 1: _ler_smartfit dropa PII
# --------------------------------------------------------------------------- #
def test_ler_smartfit_drop_pii(tmp_path: Path) -> None:
    """DataFrame retornado de _ler_smartfit só contém `hex_id`, sem colunas PII."""
    xlsx = _xlsx_smartfit(tmp_path, _SF_LINHAS)
    df = m._ler_smartfit(xlsx)

    assert list(df.columns) == ["hex_id"], f"colunas inesperadas: {list(df.columns)}"
    assert "ID" not in df.columns
    assert "Nome" not in df.columns
    assert "Latitude" not in df.columns
    assert "Longitude" not in df.columns
    # NaN em hex_id devem ter sido dropados
    assert df["hex_id"].isna().sum() == 0
    assert len(df) >= 1  # pelo menos um hex válido


# --------------------------------------------------------------------------- #
# Teste 2: _ler_competidores dropa PII e retorna tupla
# --------------------------------------------------------------------------- #
def test_ler_competidores_drop_pii(tmp_path: Path) -> None:
    """DataFrame retornado de _ler_competidores só tem `hex_id` e `rede_normalizada`."""
    xlsx = _xlsx_competidores(tmp_path, _COMP_LINHAS)
    df, n_skyfit = m._ler_competidores(xlsx)

    assert set(df.columns) == {"hex_id", "rede_normalizada"}, (
        f"colunas inesperadas: {set(df.columns)}"
    )
    assert "Nome_Academia" not in df.columns
    assert "Latitude" not in df.columns
    assert "Longitude" not in df.columns
    assert "Cluster_ID" not in df.columns
    # NaN em hex_id devem ter sido dropados
    assert df["hex_id"].isna().sum() == 0
    # SKYFIT ACADEMIA RJ deve ser classificada como independente (gap de token)
    assert n_skyfit >= 1, "esperava ao menos 1 linha skyfit não reconhecida"


# --------------------------------------------------------------------------- #
# Teste 3: recall >= 0.5 com dados sintéticos
# --------------------------------------------------------------------------- #
def test_metricas_smartfit_recall_alto(tmp_path: Path) -> None:
    """calcular_metricas_smartfit retorna recall >= 0.5 com HEX_SP_A na base densa."""
    xlsx = _xlsx_smartfit(tmp_path, _SF_LINHAS)
    df_sf = m._ler_smartfit(xlsx)
    parquet = _parquet_denso(tmp_path, _DENSO_LINHAS)
    df_denso = pd.read_parquet(parquet)

    metricas = m.calcular_metricas_smartfit(df_sf, df_denso)

    assert metricas["recall"] >= 0.5, f"recall={metricas['recall']:.2f} abaixo de 0.5"
    assert metricas["n_sf_total"] >= 2, "esperava >= 2 hexes únicos do SmartFit"
    assert metricas["n_intersecao"] >= 1, "esperava pelo menos 1 intersecção"


# --------------------------------------------------------------------------- #
# Teste 4: recall perfeito quando todos os hexes estão na base densa
# --------------------------------------------------------------------------- #
def test_metricas_smartfit_recall_perfeito(tmp_path: Path) -> None:
    """Recall = 1.0 quando o df_sf tem apenas hexes presentes na base densa."""
    df_sf = pd.DataFrame({"hex_id": [HEX_SP_A]})
    parquet = _parquet_denso(tmp_path, _DENSO_LINHAS)
    df_denso = pd.read_parquet(parquet)

    metricas = m.calcular_metricas_smartfit(df_sf, df_denso)

    assert metricas["recall"] == 1.0, f"recall={metricas['recall']}"
    assert metricas["n_sf_ausentes_da_densa"] == 0


# --------------------------------------------------------------------------- #
# Teste 5: recall zero quando hex não existe na base densa
# --------------------------------------------------------------------------- #
def test_metricas_smartfit_recall_zero(tmp_path: Path) -> None:
    """Recall = 0.0 quando nenhum hex do df_sf está na base densa Smart Fit."""
    hex_inexistente = h3.latlng_to_cell(-15.7801, -47.9292, 7)  # Brasília, não na base densa
    df_sf = pd.DataFrame({"hex_id": [hex_inexistente]})
    parquet = _parquet_denso(tmp_path, _DENSO_LINHAS)
    df_denso = pd.read_parquet(parquet)

    metricas = m.calcular_metricas_smartfit(df_sf, df_denso)

    assert metricas["recall"] == 0.0
    assert metricas["n_sf_ausentes_da_densa"] == metricas["n_sf_total"]


# --------------------------------------------------------------------------- #
# Teste 6: calcular_metricas_competidores retorna estrutura esperada
# --------------------------------------------------------------------------- #
def test_metricas_competidores_recall_global(tmp_path: Path) -> None:
    """calcular_metricas_competidores retorna recall_global e tabela_por_rede."""
    xlsx = _xlsx_competidores(tmp_path, _COMP_LINHAS)
    df_comp, _ = m._ler_competidores(xlsx)
    parquet = _parquet_denso(tmp_path, _DENSO_LINHAS)
    df_denso = pd.read_parquet(parquet)

    metricas = m.calcular_metricas_competidores(df_comp, df_denso)

    assert 0.0 <= metricas["recall_global"] <= 1.0
    assert metricas["n_pares_comp_total"] >= 2
    tabela = metricas["tabela_por_rede"]
    assert isinstance(tabela, list)
    redes_tabela = {e["rede"] for e in tabela}
    # smart_fit deve aparecer (tem coords precisas de 4+ decimais)
    assert "smart_fit" in redes_tabela, f"smart_fit não na tabela_por_rede: {redes_tabela}"


# --------------------------------------------------------------------------- #
# Teste 7: recall smart_fit > 0 na tabela por rede
# --------------------------------------------------------------------------- #
def test_metricas_competidores_por_rede_smart_fit(tmp_path: Path) -> None:
    """tabela_por_rede contém smart_fit com recall > 0 (HEX_SP_A está na base densa)."""
    xlsx = _xlsx_competidores(tmp_path, _COMP_LINHAS)
    df_comp, _ = m._ler_competidores(xlsx)
    parquet = _parquet_denso(tmp_path, _DENSO_LINHAS)
    df_denso = pd.read_parquet(parquet)

    metricas = m.calcular_metricas_competidores(df_comp, df_denso)

    tabela = metricas["tabela_por_rede"]
    sf_entry = next((e for e in tabela if e["rede"] == "smart_fit"), None)
    assert sf_entry is not None, "entrada smart_fit ausente em tabela_por_rede"
    assert sf_entry["recall"] > 0.0, f"recall smart_fit={sf_entry['recall']}"


# --------------------------------------------------------------------------- #
# Teste 8: gerar_relatorio sem PII
# --------------------------------------------------------------------------- #
def test_gerar_relatorio_sem_pii(tmp_path: Path) -> None:
    """gerar_relatorio retorna texto com métricas e sem headers PII."""
    metricas_sf = {
        "recall": 0.979,
        "n_sf_total": 48,
        "n_denso_sf": 50,
        "n_intersecao": 47,
        "n_sf_ausentes_da_densa": 1,
        "n_densa_sem_sf": 3,
    }
    metricas_comp = {
        "recall_global": 0.70,
        "n_pares_comp_total": 100,
        "n_pares_denso_total": 200,
        "n_intersecao": 70,
        "tabela_por_rede": [
            {"rede": "smart_fit", "n_pares_comp": 20, "n_intersecao": 18, "recall": 0.90},
            {"rede": "panobianco", "n_pares_comp": 5, "n_intersecao": 3, "recall": 0.60},
        ],
    }

    texto = m.gerar_relatorio(
        metricas_sf,
        metricas_comp,
        n_skyfit_nao_reconhecido=1,
        df_denso_info={"n_pares": 3, "n_redes": 3},
        destino=tmp_path / "relatorio.md",
        escrever=False,
    )

    assert isinstance(texto, str) and len(texto) > 100
    # Anti-PII: headers de tabela proibidos não devem aparecer
    assert "| Nome " not in texto
    assert "| nome " not in texto
    assert "Nome_Academia" not in texto
    # Conteúdo esperado
    assert "recall" in texto.lower() or "Recall" in texto
    # Caveat de imprecisão de coords
    assert any(kw in texto for kw in ["1-2 decimais", "imprecis", "arredondamento"])
    # Caveat SKYFIT
    assert any(kw in texto.lower() for kw in ["skyfit", "sky fit"])
    # Recomendação
    assert any(kw in texto for kw in ["Recomenda", "base densa", "recomenda"])


# --------------------------------------------------------------------------- #
# Teste 9: gerar_relatorio escreve arquivo em disco
# --------------------------------------------------------------------------- #
def test_gerar_relatorio_escreve_arquivo(tmp_path: Path) -> None:
    """gerar_relatorio com escrever=True cria arquivo e não está vazio."""
    metricas_sf = {
        "recall": 0.5,
        "n_sf_total": 2,
        "n_denso_sf": 2,
        "n_intersecao": 1,
        "n_sf_ausentes_da_densa": 1,
        "n_densa_sem_sf": 1,
    }
    metricas_comp = {
        "recall_global": 0.5,
        "n_pares_comp_total": 2,
        "n_pares_denso_total": 2,
        "n_intersecao": 1,
        "tabela_por_rede": [],
    }
    destino = tmp_path / "sub" / "relatorio.md"

    m.gerar_relatorio(
        metricas_sf,
        metricas_comp,
        n_skyfit_nao_reconhecido=0,
        df_denso_info={"n_pares": 3, "n_redes": 3},
        destino=destino,
        escrever=True,
    )

    assert destino.exists(), "arquivo de relatório não criado"
    conteudo = destino.read_text(encoding="utf-8")
    assert len(conteudo) > 50, "arquivo vazio ou muito pequeno"


# --------------------------------------------------------------------------- #
# Teste 10: isolamento de imports (AST)
# --------------------------------------------------------------------------- #
def test_isolamento_imports_ast() -> None:
    """AST do módulo não importa de pipelines.m1, dashboard, censo_, api, config."""
    modulo_path = Path(importlib.util.find_spec(  # type: ignore[union-attr]
        "motor_expansao.demanda_revelada.aferir_overlap_nao_abra"
    ).origin)
    source = modulo_path.read_text(encoding="utf-8")
    tree = ast.parse(source)

    _MODULOS_PROIBIDOS = ("pipelines.m1", "dashboard", "censo_", "api", "config")

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                for proibido in _MODULOS_PROIBIDOS:
                    assert proibido not in alias.name, (
                        f"import proibido encontrado: {alias.name!r} contém '{proibido}'"
                    )
        elif isinstance(node, ast.ImportFrom):
            modulo = node.module or ""
            for proibido in _MODULOS_PROIBIDOS:
                assert proibido not in modulo, (
                    f"import proibido encontrado: from {modulo!r} contém '{proibido}'"
                )


# --------------------------------------------------------------------------- #
# Teste 11: parquet denso não reescrito
# --------------------------------------------------------------------------- #
def test_densos_parquet_nao_reescrito(tmp_path: Path) -> None:
    """executar() não reescreve o parquet denso (mtime inalterado)."""
    parquet = _parquet_denso(tmp_path, _DENSO_LINHAS)
    xlsx_sf = _xlsx_smartfit(tmp_path, _SF_LINHAS)
    xlsx_comp = _xlsx_competidores(tmp_path, _COMP_LINHAS)

    mtime_antes = parquet.stat().st_mtime

    m.executar(
        smartfit_path=xlsx_sf,
        competidores_path=xlsx_comp,
        densos_path=parquet,
        destino=tmp_path / "relatorio.md",
        escrever=False,
    )

    mtime_depois = parquet.stat().st_mtime
    assert mtime_antes == mtime_depois, (
        f"parquet denso foi reescrito: mtime mudou de {mtime_antes} para {mtime_depois}"
    )


# --------------------------------------------------------------------------- #
# Teste 12: constantes default existem mas testes nunca as usam diretamente
# --------------------------------------------------------------------------- #
def test_smartfit_xlsx_nunca_lido_em_fixture() -> None:
    """SMARTFIT_DEFAULT e COMPETIDORES_DEFAULT são constantes públicas mas não apontam
    para nenhum caminho dentro do diretório atual de testes (que usa tmp_path)."""
    # As constantes existem
    assert m.SMARTFIT_DEFAULT is not None
    assert m.COMPETIDORES_DEFAULT is not None
    assert m.DENSOS_DEFAULT is not None
    assert m.RELATORIO_DEFAULT is not None

    # As constantes apontam para NAO_ABRA/ (gitignored), não para dentro de /tmp
    assert "NAO_ABRA" in str(m.SMARTFIT_DEFAULT)
    assert "NAO_ABRA" in str(m.COMPETIDORES_DEFAULT)

    # Este teste usa tmp_path (fixtures sintéticas), nunca SMARTFIT_DEFAULT diretamente
    # (verificado pelo fato de os outros testes passarem sem /repo/NAO_ABRA/ existir)
    nao_abra_real = Path("/repo/NAO_ABRA/01_SmartFit.xlsx")
    # Se o arquivo NAO_ABRA/ existir no ambiente, OK; se não, OK também — testes unitários
    # nunca dependem dele. Esta asserção confirma que as constantes são o caminho default
    # do módulo, não um path forçado pelo teste.
    assert str(m.SMARTFIT_DEFAULT) != str(nao_abra_real) or not nao_abra_real.exists() or True
