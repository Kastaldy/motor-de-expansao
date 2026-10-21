"""`python -m motor_expansao.renda.atualizar_fatores` com microdados SINTETICOS (sem rede).

Cobre: fatores corretos (mesma visita, media geometrica, nacional do Brasil inteiro), regra de
excecao, `--aprovar-uf` invalida, conferencia de NIVEL contra a 7531 (falha com a visita
trocada) e o pedido do Felipe (2026-10-20) de provar que o fator NAO vem da 7531:
(a) 7531 adulterada (2025 x 1,0049) ainda passa e os fatores saem IDENTICOS;
(b) fator nacional != 7531(2025)/7531(2022);
(c) nenhuma chave com '7531'/'sidra' nos blocos de fator;
(d) o modulo de calculo nao importa o modulo da SIDRA (AST).

Ha' ainda um teste de REPRODUCAO com os microdados reais em cache, pulado sem
`MOTOR_PNAD_CACHE_DIR`.
"""

from __future__ import annotations

import ast
import json
import math
import os
import re
import shutil
import zipfile
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from motor_expansao.renda import atualizar_fatores as af
from motor_expansao.renda import pnad, sidra

ANO_BASE, ANO_ALVO = 2022, 2025
HOJE = date(2026, 10, 20)

# Posicoes 1-based por visita: a visita 5 tem as variaveis de renda em OUTRO lugar, como no IBGE.
LAYOUTS = {
    1: {"Ano": (1, 4, "$"), "UF": (5, 2, "$"), "V1032": (7, 15, ""), "V2005": (22, 2, "$"),
        "VD2003": (24, 2, ""), "VD5007": (26, 8, ""), "VD5008": (34, 8, "")},
    5: {"Ano": (1, 4, "$"), "UF": (5, 2, "$"), "V1032": (7, 15, ""), "V2005": (22, 2, "$"),
        "VD2003": (30, 2, ""), "VD5007": (40, 8, ""), "VD5008": (52, 8, "")},
}  # fmt: skip
LARGURA = {1: 45, 5: 64}

# Crescimento real por UF (igual nas duas visitas) e o "artefato de visita": v1 mede 6% a mais.
CRESC = {"35": 1.30, "26": 1.55, "50": 1.10}
NIVEL_VISITA = {1: 1.06, 5: 1.00}
NOMES_ZIP = {
    (2022, 1): "PNADC_2022_visita1_20250822.zip",
    (2025, 1): "PNADC_2025_visita1_20260923.zip",
    (2022, 5): "PNADC_2022_visita5_20250822.zip",
    (2025, 5): "PNADC_2025_visita5_20261016.zip",
}
NOMES_LAYOUT = {
    (2022, 1): "input_PNADC_2022_visita1_20231129.txt",
    (2025, 1): "input_PNADC_2025_visita1_20260923.txt",
    (2022, 5): "input_PNADC_2022_visita5_20231222.txt",
    (2025, 5): "input_PNADC_2025_visita5_20261016.txt",
}


# ---------------------------------------------------------------------------
# Gerador de microdados sinteticos
# ---------------------------------------------------------------------------


def _domicilios() -> list[dict]:
    """Estrutura FIXA de domicilios (mesmos pesos e tamanhos nas 4 amostras)."""
    rng = np.random.default_rng(7)
    doms = []
    for uf, n in (("35", 40), ("26", 25), ("50", 20)):
        for _ in range(n):
            tam = int(rng.integers(1, 5))
            doms.append(
                {
                    "uf": uf,
                    "tam": tam,
                    "peso": round(float(rng.uniform(100, 900)), 4),
                    "renda": float(rng.uniform(800, 9000)),
                    "pensionista": bool(rng.random() < 0.2),
                }
            )
    return doms


def _linhas(ano: int, visita: int) -> list[dict]:
    out = []
    for d in _domicilios():
        mult = (CRESC[d["uf"]] if ano == ANO_ALVO else 1.0) * NIVEL_VISITA[visita]
        total = round(d["renda"] * mult)
        pc = round(total / d["tam"])
        for i in range(d["tam"]):
            out.append(
                {
                    "UF": d["uf"],
                    "V1032": d["peso"],
                    "V2005": "01" if i == 0 else "02",
                    "VD2003": d["tam"],
                    "VD5007": total,
                    "VD5008": pc,
                }
            )
        if d["pensionista"]:  # fora do universo: VD5008 em branco
            out.append(
                {
                    "UF": d["uf"],
                    "V1032": d["peso"],
                    "V2005": "17",
                    "VD2003": None,
                    "VD5007": None,
                    "VD5008": None,
                }
            )
    return out


def _campo(valor, largura: int, texto: bool) -> str:
    if valor is None:
        return " " * largura
    if texto:
        return str(valor).rjust(largura, "0") if str(valor).isdigit() else str(valor).ljust(largura)
    if isinstance(valor, float):
        return f"{valor:0{largura}.8f}"[:largura].rjust(largura)
    return str(valor).rjust(largura)


def _escrever_amostra(
    dir_: Path, ano: int, visita: int, *, sem_variavel: str | None = None
) -> None:
    lay = LAYOUTS[visita]
    txt = ["/* layout sintetico */", "input"]
    for nome, (ini, larg, tipo) in lay.items():
        if nome == sem_variavel:
            continue
        txt.append(f"@{ini:04d} {nome}   {tipo}{larg}.   /* {nome} */")
    txt += [";", "run;"]
    (dir_ / NOMES_LAYOUT[(ano, visita)]).write_text("\n".join(txt) + "\n", encoding="latin-1")
    linhas = []
    for reg in _linhas(ano, visita):
        buf = [" "] * LARGURA[visita]
        reg = {"Ano": ano, **reg}
        for nome, (ini, larg, tipo) in lay.items():
            s = _campo(reg[nome], larg, tipo == "$")
            buf[ini - 1 : ini - 1 + larg] = list(s)
        linhas.append("".join(buf))
    with zipfile.ZipFile(dir_ / NOMES_ZIP[(ano, visita)], "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr(f"PNADC_{ano}_visita{visita}.txt", "\r\n".join(linhas) + "\r\n")


@pytest.fixture
def origem(tmp_path: Path) -> Path:
    d = tmp_path / "ftp"
    d.mkdir()
    for a in (ANO_BASE, ANO_ALVO):
        for v in (1, 5):
            _escrever_amostra(d, a, v)
    return d


class FtpFalso:
    """Listagem e download injetados: nada sai da maquina."""

    def __init__(self, origem: Path, *, omitir: set[str] | None = None) -> None:
        self.origem = origem
        self.omitir = omitir or set()
        self.baixados: list[str] = []

    def listar(self, url: str) -> list[str]:
        visita = 1 if "Visita_1/" in url else 5
        nomes = [p.name for p in self.origem.iterdir() if f"visita{visita}" in p.name]
        # iscas: outro ano e republicacao mais antiga do mesmo arquivo
        nomes += [
            f"PNADC_2024_visita{visita}_20250101.zip",
            f"PNADC_2022_visita{visita}_20240101.zip",
            f"dicionario_PNADC_microdados_2025_visita{visita}_20260923.xls",
        ]
        if "Documentacao" in url:
            nomes = [n for n in nomes if n.startswith("input_") or n.startswith("dicionario")]
        else:
            nomes = [n for n in nomes if n.endswith(".zip")]
        return sorted(n for n in nomes if n not in self.omitir)

    def baixar(self, url: str, destino: Path) -> None:
        nome = url.rsplit("/", 1)[-1]
        self.baixados.append(nome)
        shutil.copyfile(self.origem / nome, destino)


# ---------------------------------------------------------------------------
# Referencias independentes (sem o codigo sob teste)
# ---------------------------------------------------------------------------


def _df(ano: int, visita: int) -> pd.DataFrame:
    d = pd.DataFrame(_linhas(ano, visita))
    return d[d["VD5008"].notna()]


def _wm(x, w) -> float:
    return float(np.average(np.asarray(x, float), weights=np.asarray(w, float)))


def _nivel(d: pd.DataFrame) -> dict[str, float]:
    dom = d[d["V2005"] == "01"]
    return {
        "pc": _wm(d["VD5008"], d["V1032"]),
        "dom": _wm(dom["VD5007"], dom["V1032"]),
        "mor": _wm(dom["VD2003"], dom["V1032"]),
    }


def _referencia(uf_cod: str | None) -> dict[str, float]:
    f = {}
    for v in (1, 5):
        b, a = _df(ANO_BASE, v), _df(ANO_ALVO, v)
        if uf_cod:
            b, a = b[b["UF"] == uf_cod], a[a["UF"] == uf_cod]
        nb, na = _nivel(b), _nivel(a)
        for k in ("pc", "dom", "mor"):
            f[f"{k}_v{v}"] = na[k] / nb[k]
    return {
        "per_capita": (f["pc_v1"] * f["pc_v5"]) ** 0.5,
        "domiciliar": (f["dom_v1"] * f["dom_v5"]) ** 0.5,
        "moradores": (f["mor_v1"] * f["mor_v5"]) ** 0.5,
        **f,
    }


_SIGLA = {"35": "SP", "26": "PE", "50": "MS"}


def _mult_nao_uniforme(ano: int, chave: str) -> float:
    """Multiplicador DIFERENTE por (ano, territorio), todos dentro de 0,4% (passa na conferencia).

    Uniforme (o mesmo escalar em todas as UFs) nao pegaria uma derivacao invariante a escala,
    p.ex. normalizar a razao 7531 de cada UF pela media das UFs.
    """
    return 1.0 + 0.004 * math.sin(int(chave) * 1.7 + ano * 0.31)


def _sidra_7531(*, adulterar_2025: float = 1.0, nao_uniforme: bool = False) -> list[dict]:
    """7531 sintetica: 2022 = nivel da VISITA 5, 2025 = nivel da VISITA 1 (como a real)."""
    resp = [
        {
            "NC": "Nível Territorial (Código)",
            "V": "Valor",
            "D1C": "Brasil e Unidade da Federação (Código)",
            "D2C": "Variável (Código)",
            "D3C": "Ano (Código)",
            "D4C": "Classes de percentual das pessoas (Código)",
        }
    ]
    for ano, visita in ((ANO_BASE, 5), (ANO_ALVO, 1)):
        mult = adulterar_2025 if ano == ANO_ALVO else 1.0
        d = _df(ano, visita)
        resp.append(
            {
                "NC": "1",
                "V": repr(
                    _wm(d["VD5008"], d["V1032"])
                    * (_mult_nao_uniforme(ano, "1") if nao_uniforme else mult)
                ),
                "D1C": "1",
                "D2C": "10824",
                "D3C": str(ano),
                "D4C": "49243",
            }
        )
        for cod, g in d.groupby("UF"):
            resp.append(
                {
                    "NC": "3",
                    "V": repr(
                        _wm(g["VD5008"], g["V1032"])
                        * (_mult_nao_uniforme(ano, cod) if nao_uniforme else mult)
                    ),
                    "D1C": cod,
                    "D2C": "10824",
                    "D3C": str(ano),
                    "D4C": "49243",
                }
            )
            # outra classe: tem de ser ignorada
            resp.append(
                {"NC": "3", "V": "1", "D1C": cod, "D2C": "10824", "D3C": str(ano), "D4C": "49244"}
            )
    return resp


def _vigente(dir_: Path, versao: str = "2026-08_caged_v0") -> Path:
    d = dir_ / "fatores" / "BR"
    d.mkdir(parents=True)
    (d / "VIGENTE").write_text(f"{versao}\n", encoding="utf-8")
    origem = Path(af.__file__).parent / "fatores" / "BR" / f"{versao}.json"
    shutil.copyfile(origem, d / f"{versao}.json")
    return dir_ / "fatores"


def _args(
    tmp_path: Path, *extra: str, sidra_json: list[dict] | None = None, saida: str = "saida"
) -> list[str]:
    sj = tmp_path / f"t7531_{saida}.json"
    sj.write_text(
        json.dumps(sidra_json if sidra_json is not None else _sidra_7531()), encoding="utf-8"
    )
    fatores = tmp_path / "fatores"
    if not fatores.exists():
        _vigente(tmp_path)
    return [
        "--pais",
        "BR",
        "--ano-base",
        str(ANO_BASE),
        "--ano-alvo",
        str(ANO_ALVO),
        "--cache-dir",
        str(tmp_path / "cache"),
        "--saida-dir",
        str(tmp_path / saida),
        "--fatores-dir",
        str(fatores),
        "--sidra-7531-json",
        str(sj),
        "--n-min",
        "10",
        *extra,
    ]


def _rodar(argv: list[str], ftp: FtpFalso) -> dict:
    args = af.construir_parser().parse_args(argv)
    return af.executar(args, listar=ftp.listar, baixar=ftp.baixar, hoje=HOJE)


# ---------------------------------------------------------------------------
# Fatores
# ---------------------------------------------------------------------------


def test_fatores_corretos_mesma_visita_media_geometrica(tmp_path: Path, origem: Path) -> None:
    res = _rodar(_args(tmp_path), FtpFalso(origem))
    dados = res["dados"]
    br = _referencia(None)
    for tipo in ("per_capita", "domiciliar", "moradores"):
        assert dados["nacional"][tipo] == pytest.approx(br[tipo], rel=1e-12)
    # UF: com estrutura de domicilio fixa, o fator da UF e' o crescimento sintetico
    calc = res["calc"]
    for cod, sigla in _SIGLA.items():
        ref = _referencia(cod)
        assert calc.fatores[sigla]["per_capita"] == pytest.approx(ref["per_capita"], rel=1e-12)
        assert calc.fatores[sigla]["domiciliar"] == pytest.approx(ref["domiciliar"], rel=1e-12)
        assert calc.fatores[sigla]["per_capita"] == pytest.approx(CRESC[cod], rel=2e-3)
    # nacional = Brasil inteiro, NAO media simples das UFs
    media_ufs = np.mean([calc.fatores[s]["per_capita"] for s in _SIGLA.values()])
    assert abs(dados["nacional"]["per_capita"] - media_ufs) > 1e-3
    # o "artefato de visita" (v1 6% maior) nao contamina: fator v1 == fator v5
    assert calc.fatores["BR"]["pc_v1"] == pytest.approx(calc.fatores["BR"]["pc_v5"], rel=2e-3)


def test_arquivo_de_versao_tem_o_schema_e_passa_no_loader(tmp_path: Path, origem: Path) -> None:
    from motor_expansao.renda.carregador import validar_versao

    res = _rodar(_args(tmp_path, "--aprovar-uf", "PE"), FtpFalso(origem))
    caminho = res["json"]
    assert caminho.name == "2026-10_pnad2025_v1.json"
    dados = json.loads(caminho.read_text(encoding="utf-8"))
    validar_versao(dados, caminho, pais="BR", versao="2026-10_pnad2025_v1")
    assert dados["visita_sidra"] == {"2022": 5, "2025": 1}
    assert dados["artefatos_obrigatorios"] == [
        "uplift_renda_domiciliar_municipio.parquet",
        "uplift_composicao_setor.parquet",
    ]
    assert dados["artefato_k_obrigatorio"] is True
    assert "rotulo_pdf" not in dados  # proveniencia e dado interno: sem texto de PDF
    assert {a["papel"] for a in dados["fonte"]["arquivos"]} == {"microdados", "layout"}
    assert all(len(a["sha256"]) == 64 for a in dados["fonte"]["arquivos"])
    assert dados["fonte"]["tabela_sidra_conferencia"]["erros"]["2025"]["visita"] == 1
    # relatorio amarrado por sha256
    rel = caminho.parent / dados["relatorio"]["caminho"]
    import hashlib

    assert (
        hashlib.sha256(rel.read_text(encoding="utf-8").encode("utf-8")).hexdigest()
        == dados["relatorio"]["sha256"]
    )
    texto = rel.read_text(encoding="utf-8")
    assert "Sensibilidade" in texto and "ATENÇÃO" in texto  # 1,1641 -> ~1,3: variacao > 10%
    # VIGENTE nao muda
    assert (tmp_path / "fatores" / "BR" / "VIGENTE").read_text(
        encoding="utf-8"
    ).strip() == "2026-08_caged_v0"
    # proxima rodada vira v2, sem baixar de novo (cache com sha256)
    ftp2 = FtpFalso(origem)
    res2 = _rodar(_args(tmp_path, saida="saida"), ftp2)
    assert res2["versao"] == "2026-10_pnad2025_v2" and ftp2.baixados == []


def test_cache_corrompido_aborta(tmp_path: Path, origem: Path) -> None:
    _rodar(_args(tmp_path), FtpFalso(origem))
    alvo = tmp_path / "cache" / NOMES_LAYOUT[(2022, 1)]
    alvo.write_text(alvo.read_text(encoding="latin-1") + "\n/* adulterado */\n", encoding="latin-1")
    with pytest.raises(pnad.PnadErro, match="cache corrompido"):
        _rodar(_args(tmp_path, saida="s2"), FtpFalso(origem))


def test_amostra_ausente_aborta(tmp_path: Path, origem: Path) -> None:
    ftp = FtpFalso(origem, omitir={NOMES_ZIP[(2025, 5)]})
    with pytest.raises(pnad.PnadErro, match="2025 visita 5"):
        _rodar(_args(tmp_path), ftp)


def test_variavel_ausente_no_layout_aborta(tmp_path: Path, origem: Path) -> None:
    _escrever_amostra(origem, 2025, 5, sem_variavel="VD5007")
    with pytest.raises(pnad.PnadErro, match="VD5007"):
        _rodar(_args(tmp_path), FtpFalso(origem))


def test_escolhe_a_republicacao_mais_recente() -> None:
    nomes = [
        "PNADC_2022_visita1_20240101.zip",
        "PNADC_2022_visita1_20250822.zip",
        "PNADC_2022_visita1.zip",
    ]
    assert pnad._escolher(nomes, pnad.regex_microdados(2022, 1)) == (
        "PNADC_2022_visita1_20250822.zip",
        "20250822",
    )


# ---------------------------------------------------------------------------
# Regra de excecao
# ---------------------------------------------------------------------------


def test_regra_de_excecao_aponta_candidatas(tmp_path: Path, origem: Path) -> None:
    res = _rodar(_args(tmp_path), FtpFalso(origem))
    dados = res["dados"]
    # PE (1,55) acima e MS (1,10) abaixo do nacional por mais de 7% nas duas visitas; SP perto
    assert sorted(dados["candidatas_regra"]) == ["MS", "PE"]
    assert dados["excecoes_aprovadas"] == {}
    det = dados["regra_excecao"]["candidatas_detalhe"]
    assert det["PE"]["desvio_pc_v1"] > 0.07 and det["MS"]["desvio_pc_v5"] < -0.07


def test_regra_n_min_e_estrita() -> None:
    def calc(fatores_uf: dict[str, tuple[float, float]], n: int = 10_000) -> pnad.FatoresCalculados:
        fat = {
            "BR": {
                "pc_v1": 1.0,
                "pc_v5": 1.0,
                "dom_v1": 1.0,
                "dom_v5": 1.0,
                "per_capita": 1.0,
                "domiciliar": 1.0,
                "moradores": 1.0,
                "n_min_amostras": 1e6,
            }
        }
        for uf, (v1, v5) in fatores_uf.items():
            fat[uf] = {
                "pc_v1": v1,
                "pc_v5": v5,
                "dom_v1": v1,
                "dom_v5": v5,
                "per_capita": (v1 * v5) ** 0.5,
                "domiciliar": (v1 * v5) ** 0.5,
                "moradores": 1.0,
                "n_min_amostras": float(n),
            }
        return pnad.FatoresCalculados(ANO_BASE, ANO_ALVO, {}, fat)

    # limiar 0,5 para o desvio exato caber em float (1,5 - 1 == 0,5)
    c = calc({"AA": (1.6, 0.4), "BB": (1.6, 1.5000001), "CC": (1.5, 1.9), "DD": (0.4, 0.45)})
    assert [r["uf"] for r in pnad.candidatas(c, limiar=0.5)] == [
        "DD",
        "BB",
    ]  # AA: sinal oposto; CC: estrito
    assert pnad.candidatas(calc({"DD": (0.80, 0.85)}, n=4_999)) == []
    assert [r["uf"] for r in pnad.candidatas(calc({"DD": (0.80, 0.85)}, n=5_000))] == ["DD"]


def test_aprovar_uf_nao_candidata_aborta(tmp_path: Path, origem: Path) -> None:
    with pytest.raises(af.AtualizacaoAbortada, match="SP"):
        _rodar(_args(tmp_path, "--aprovar-uf", "SP"), FtpFalso(origem))
    assert not (tmp_path / "saida").exists() or not list((tmp_path / "saida").glob("*.json"))


def test_aprovar_uf_candidata_grava_excecao(tmp_path: Path, origem: Path) -> None:
    res = _rodar(_args(tmp_path, "--aprovar-uf", "pe", "MS"), FtpFalso(origem))
    exc = res["dados"]["excecoes_aprovadas"]
    assert sorted(exc) == ["MS", "PE"]
    ref = _referencia("26")
    assert exc["PE"]["per_capita"] == pytest.approx(ref["per_capita"], rel=1e-12)
    assert exc["PE"]["domiciliar"] == pytest.approx(ref["domiciliar"], rel=1e-12)
    assert exc["PE"]["moradores"] == pytest.approx(ref["moradores"], rel=1e-12)
    assert "aprovada via --aprovar-uf" in exc["PE"]["evidencia"]


# ---------------------------------------------------------------------------
# Conferencia SIDRA 7531: so' NIVEL, nunca fator
# ---------------------------------------------------------------------------


def test_conferencia_falha_com_visita_trocada(tmp_path: Path, origem: Path) -> None:
    argv = _args(tmp_path, "--visita-sidra", "2022=1", "--visita-sidra", "2025=5")
    with pytest.raises(sidra.ConferenciaSidraFalhou, match="reprovou"):
        _rodar(argv, FtpFalso(origem))
    assert not list((tmp_path / "saida").glob("*.json"))


def test_ano_sem_visita_declarada_aborta(tmp_path: Path, origem: Path) -> None:
    # Ano-alvo fora do mapa padrao e sem `--visita-sidra` para ele (o ultimo --ano-alvo vale).
    with pytest.raises(af.AtualizacaoAbortada, match="sem visita declarada"):
        _rodar(_args(tmp_path, "--ano-alvo", "2026"), FtpFalso(origem))


def test_visita_sidra_completa_o_mapa_padrao() -> None:
    """O runbook declara so o ano novo; o ano-base 2022 continua com a visita padrao."""
    padrao = dict(sidra.VISITA_SIDRA_7531)
    assert af._parse_visita_sidra(None) == padrao
    assert af._parse_visita_sidra(["2026=1"]) == {**padrao, 2026: 1}
    assert af._parse_visita_sidra(["2022=1"]) == {**padrao, 2022: 1}  # so o ano dado muda
    with pytest.raises(af.AtualizacaoAbortada, match="ANO=VISITA"):
        af._parse_visita_sidra(["2026:1"])


def test_conferencia_devolve_so_erros() -> None:
    micro = {(2022, 5): {"SP": 100.0}, (2025, 1): {"SP": 150.0}}
    pub = {2022: {"SP": 100.2}, 2025: {"SP": 149.5}}
    res = sidra.conferir_nivel_7531(micro, pub, {2022: 5, 2025: 1}, (2022, 2025))
    assert set(res) == {"2022", "2025"}
    for e in res.values():
        assert set(e) == {"visita", "erro_max", "uf_erro_max", "erro_medio_abs", "erros_uf"}
        assert e["erro_max"] < 0.005  # erros relativos, nunca niveis nem razoes
    with pytest.raises(sidra.ConferenciaSidraFalhou):
        sidra.conferir_nivel_7531(
            micro, {2022: {"SP": 100.0}, 2025: {"SP": 160.0}}, {2022: 5, 2025: 1}, (2022, 2025)
        )


def _blocos_de_fator(dados: dict) -> dict:
    return {"nacional": dados["nacional"], "excecoes_aprovadas": dados["excecoes_aprovadas"]}


def test_felipe_a_7531_adulterada_passa_e_fatores_identicos(tmp_path: Path, origem: Path) -> None:
    """(a) 2025 x 1,0049 em todas as UFs ainda passa na conferencia (< 0,5%) e NAO move fator."""
    verdadeira = _rodar(_args(tmp_path, "--aprovar-uf", "PE", saida="verdadeira"), FtpFalso(origem))
    adulterada = _rodar(
        _args(
            tmp_path,
            "--aprovar-uf",
            "PE",
            saida="adulterada",
            sidra_json=_sidra_7531(adulterar_2025=1.0049),
        ),
        FtpFalso(origem),
    )
    a, b = verdadeira["dados"], adulterada["dados"]
    assert _blocos_de_fator(a) == _blocos_de_fator(b)  # igualdade EXATA de float
    assert a["candidatas_regra"] == b["candidatas_regra"]
    assert a["fonte"]["fatores_por_visita"] == b["fonte"]["fatores_por_visita"]
    # a conferencia ENXERGOU a adulteracao (erro ~ -0,49%), mas so' como erro
    e = b["fonte"]["tabela_sidra_conferencia"]["erros"]["2025"]
    assert e["erro_max"] == pytest.approx(1 - 1 / 1.0049, abs=1e-9)
    assert a["fonte"]["tabela_sidra_conferencia"]["erros"]["2025"]["erro_max"] < 1e-9


def test_felipe_a_7531_adulterada_nao_uniforme_tambem_nao_move_fator(
    tmp_path: Path, origem: Path
) -> None:
    """(a) com um multiplicador por UF e por ano (<= 0,4%): nem funcao RELATIVA da 7531 move."""
    verdadeira = _rodar(_args(tmp_path, "--aprovar-uf", "PE", saida="verdadeira"), FtpFalso(origem))
    adulterada = _rodar(
        _args(
            tmp_path,
            "--aprovar-uf",
            "PE",
            saida="adulterada",
            sidra_json=_sidra_7531(nao_uniforme=True),
        ),
        FtpFalso(origem),
    )
    a, b = verdadeira["dados"], adulterada["dados"]
    assert _blocos_de_fator(a) == _blocos_de_fator(b)  # igualdade EXATA de float
    assert a["candidatas_regra"] == b["candidatas_regra"]
    assert a["fonte"]["fatores_por_visita"] == b["fonte"]["fatores_por_visita"]
    # a adulteracao chegou a conferencia nos DOIS anos, e com erro diferente por UF
    for ano in ("2022", "2025"):
        erros = b["fonte"]["tabela_sidra_conferencia"]["erros"][ano]["erros_uf"]
        assert len({round(v, 12) for v in erros.values()}) == len(erros) > 1


def test_felipe_b_nacional_nao_e_razao_da_7531(tmp_path: Path, origem: Path) -> None:
    resp = _sidra_7531()
    res = _rodar(_args(tmp_path), FtpFalso(origem))
    br = {int(r["D3C"]): float(r["V"]) for r in resp[1:] if r["NC"] == "1"}
    razao = br[ANO_ALVO] / br[ANO_BASE]
    assert abs(res["dados"]["nacional"]["per_capita"] / razao - 1) > 0.01
    for cod, sigla in _SIGLA.items():
        uf = {
            int(r["D3C"]): float(r["V"])
            for r in resp[1:]
            if r["NC"] == "3" and r["D1C"] == cod and r["D4C"] == "49243"
        }
        assert (
            abs(res["calc"].fatores[sigla]["per_capita"] / (uf[ANO_ALVO] / uf[ANO_BASE]) - 1) > 0.01
        )


def test_felipe_c_nenhuma_chave_sidra_nos_blocos_de_fator(tmp_path: Path, origem: Path) -> None:
    res = _rodar(_args(tmp_path, "--aprovar-uf", "PE", "MS"), FtpFalso(origem))
    dados = json.loads(res["json"].read_text(encoding="utf-8"))

    def chaves(o) -> list[str]:
        if isinstance(o, dict):
            return [str(k) for k in o] + [c for v in o.values() for c in chaves(v)]
        if isinstance(o, list):
            return [c for v in o for c in chaves(v)]
        return []

    for bloco in _blocos_de_fator(dados).values():
        for k in chaves(bloco):
            assert "7531" not in k and "sidra" not in k.lower(), k
    assert set(dados["nacional"]) == {"per_capita", "domiciliar", "moradores"}
    for exc in dados["excecoes_aprovadas"].values():
        assert set(exc) == {"per_capita", "domiciliar", "moradores", "evidencia"}


def _imports(path: Path) -> set[str]:
    arvore = ast.parse(path.read_text(encoding="utf-8"))
    out: set[str] = set()
    for no in ast.walk(arvore):
        if isinstance(no, ast.Import):
            out |= {a.name for a in no.names}
        elif isinstance(no, ast.ImportFrom):
            base = no.module or ""
            out.add(base)
            out |= {f"{base}.{a.name}" for a in no.names}
    return out


def test_felipe_d_calculo_nao_importa_sidra() -> None:
    caminho = Path(pnad.__file__)
    imports = _imports(caminho)
    assert not [i for i in imports if "sidra" in i.lower()], imports
    arvore = ast.parse(caminho.read_text(encoding="utf-8"))
    nomes = {n.id for n in ast.walk(arvore) if isinstance(n, ast.Name)}
    assert not [n for n in nomes if "sidra" in n.lower()]
    # e a funcao de calculo nao recebe nada da SIDRA
    func = next(
        n for n in arvore.body if isinstance(n, ast.FunctionDef) and n.name == "calcular_fatores"
    )
    assert [a.arg for a in func.args.args] == ["dados", "ano_base", "ano_alvo"]


def test_auto_teste_da_varredura_ast(tmp_path: Path) -> None:
    ruim = tmp_path / "ruim.py"
    ruim.write_text(
        "from motor_expansao.renda import sidra\nx = sidra.niveis_7531\n", encoding="utf-8"
    )
    assert any("sidra" in i for i in _imports(ruim))


# ---------------------------------------------------------------------------
# Reproducao com os microdados REAIS em cache (opcional)
# ---------------------------------------------------------------------------

_CACHE_REAL = os.environ.get("MOTOR_PNAD_CACHE_DIR")


_SEM_CACHE_REAL = not _CACHE_REAL or not Path(_CACHE_REAL).is_dir()


def _cache_real_isolado(tmp_path: Path) -> tuple[Path, Path]:
    """Microdados e layouts do cache real ligados (hardlink; copia se nao der) num diretorio
    do teste, mais a 7531. O `atualizar_fatores` ESCREVE no cache (manifesto, parquets de
    extracao): sem isto o teste sujaria o cache de quem o roda, que pode ser so-leitura."""
    # Guarda propria: o helper nao e teste, entao um `skipif` em cima dele nao faria nada. Sem
    # ela, `Path("")` varreria o diretorio corrente e um diretorio inexistente daria
    # FileNotFoundError em vez de skip.
    if _SEM_CACHE_REAL or not _CACHE_REAL:
        pytest.skip("MOTOR_PNAD_CACHE_DIR ausente (microdados reais)")
    cache = Path(_CACHE_REAL)
    sidra_json = Path(os.environ.get("MOTOR_PNAD_SIDRA_7531_JSON") or cache / "t7531_uf.json")
    if not sidra_json.exists():
        pytest.skip(f"sem a 7531 em cache ({sidra_json})")
    isolado = tmp_path / "cache_real"
    isolado.mkdir()
    for arq in sorted(cache.iterdir()):
        if arq.is_file() and arq.name.startswith(("PNADC_", "input_PNADC_")):
            try:
                os.link(arq, isolado / arq.name)
            except OSError:
                shutil.copyfile(arq, isolado / arq.name)
    return isolado, sidra_json


@pytest.mark.skipif(_SEM_CACHE_REAL, reason="MOTOR_PNAD_CACHE_DIR ausente (microdados reais)")
def test_reproduz_numeros_reais_do_cache(tmp_path: Path) -> None:
    cache, sidra_json = _cache_real_isolado(tmp_path)
    _vigente(tmp_path)
    argv = [
        "--pais",
        "BR",
        "--ano-base",
        "2022",
        "--ano-alvo",
        "2025",
        "--offline",
        "--cache-dir",
        str(cache),
        "--saida-dir",
        str(tmp_path / "saida"),
        "--fatores-dir",
        str(tmp_path / "fatores"),
        "--sidra-7531-json",
        str(sidra_json),
    ]
    res = af.executar(af.construir_parser().parse_args(argv), hoje=HOJE)
    f = res["calc"].fatores
    esperado = {
        "BR": (1.34005575, 1.24695996, 0.93054448),
        "PE": (1.4816307, 1.34606215, 0.90853146),
        "MS": (1.23688697, 1.16070803, 0.93842144),
    }
    for uf, (pc, dom, mor) in esperado.items():
        assert f[uf]["per_capita"] == pytest.approx(pc, abs=1e-8)
        assert f[uf]["domiciliar"] == pytest.approx(dom, abs=1e-8)
        assert f[uf]["moradores"] == pytest.approx(mor, abs=1e-8)
    assert sorted(res["dados"]["candidatas_regra"]) == ["MS", "PE"]
    erros = res["dados"]["fonte"]["tabela_sidra_conferencia"]["erros"]
    assert erros["2022"]["visita"] == 5 and erros["2022"]["erro_max"] == pytest.approx(
        0.00318, abs=5e-6
    )
    assert erros["2025"]["visita"] == 1 and erros["2025"]["erro_max"] == pytest.approx(
        0.00370, abs=5e-6
    )


_FATORES_PACOTE = Path(af.__file__).parent / "fatores"
_REPO = Path(__file__).resolve().parents[2]
#: Campos que o humano preenche DEPOIS da geracao (aprovacao e onde o relatorio foi versionado).
_CAMPOS_DA_APROVACAO = ("dec", "aprovado_por", "relatorio")


def _iguais_aprox(a: object, b: object, caminho: str = "") -> list[str]:
    """Diferencas entre dois JSON; float compara com rel 1e-12 (soma em outra maquina/BLAS)."""
    if isinstance(a, dict) and isinstance(b, dict):
        difs = [f"{caminho}: chaves {sorted(set(a) ^ set(b))}"] if set(a) != set(b) else []
        for k in sorted(set(a) & set(b)):
            difs += _iguais_aprox(a[k], b[k], f"{caminho}.{k}")
        return difs
    if isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b):
            return [f"{caminho}: {len(a)} x {len(b)} itens"]
        return [
            d
            for i, (x, y) in enumerate(zip(a, b, strict=True))
            for d in _iguais_aprox(x, y, f"{caminho}[{i}]")
        ]
    if isinstance(a, float) and isinstance(b, float):
        return [] if a == pytest.approx(b, rel=1e-12, abs=1e-15) else [f"{caminho}: {a!r} x {b!r}"]
    return [] if a == b else [f"{caminho}: {a!r} x {b!r}"]


@pytest.mark.skipif(_SEM_CACHE_REAL, reason="MOTOR_PNAD_CACHE_DIR ausente (microdados reais)")
def test_reproduz_a_versao_publicada_a_partir_do_cache(tmp_path: Path) -> None:
    """Teste 8 do plano (secao 10.4, item 6): a versao VIGENTE publicada sai de novo, identica,
    do comando documentado sobre os microdados em cache -- com as MESMAS UFs aprovadas e a mesma
    data de extracao. So `dec`, `aprovado_por` e `relatorio` (preenchidos na aprovacao) diferem;
    o relatorio gerado tem de ser byte a byte o versionado em `docs/` (mesmo sha256)."""
    vigente = (_FATORES_PACOTE / "BR" / "VIGENTE").read_text(encoding="utf-8").strip()
    publicada = json.loads((_FATORES_PACOTE / "BR" / f"{vigente}.json").read_text(encoding="utf-8"))
    if not str(publicada["fonte"].get("pesquisa", "")).startswith("PNAD"):
        pytest.skip(f"VIGENTE {vigente} nao e uma versao gerada pela PNAD")
    # O ponto de partida da geracao: a versao que era vigente quando ela foi gerada. Sai do
    # proprio relatorio versionado (linha "Versao vigente comparada"), nao de um nome cravado:
    # a proxima versao anual parte desta, nao da v0, e o relatorio compara contra a de partida.
    relatorio_versionado = (_REPO / publicada["relatorio"]["caminho"]).read_text(encoding="utf-8")
    partida = re.search(r"Versão vigente comparada: `([^`]+)`", relatorio_versionado)
    assert partida, "relatorio versionado sem a linha 'Versão vigente comparada'"
    if not (_FATORES_PACOTE / "BR" / f"{partida.group(1)}.json").exists():
        pytest.skip(f"versao de partida {partida.group(1)} nao esta mais no pacote")
    cache, sidra_json = _cache_real_isolado(tmp_path)
    _vigente(tmp_path, partida.group(1))
    argv = [
        "--pais", "BR",
        "--ano-base", str(publicada["ano_base_renda"]),
        "--ano-alvo", str(publicada["ano_alvo"]),
        "--offline",
        "--cache-dir", str(cache),
        "--saida-dir", str(tmp_path / "saida"),
        "--fatores-dir", str(tmp_path / "fatores"),
        "--sidra-7531-json", str(sidra_json),
    ]
    for uf in sorted(publicada["excecoes_aprovadas"]):
        argv += ["--aprovar-uf", uf]
    hoje = date.fromisoformat(publicada["data_extracao"])
    res = af.executar(af.construir_parser().parse_args(argv), hoje=hoje)
    assert res["versao"] == vigente
    gerada = json.loads(res["json"].read_text(encoding="utf-8"))
    sem = {k: v for k, v in publicada.items() if k not in _CAMPOS_DA_APROVACAO}
    assert _iguais_aprox({k: v for k, v in gerada.items() if k not in _CAMPOS_DA_APROVACAO}, sem) == []
    # Relatorio: o gerado agora == o versionado (o blob do git e LF; o checkout pode ser CRLF).
    import hashlib

    versionado = (_REPO / publicada["relatorio"]["caminho"]).read_bytes().replace(b"\r\n", b"\n")
    assert res["relatorio"].read_bytes() == versionado
    assert hashlib.sha256(versionado).hexdigest() == publicada["relatorio"]["sha256"]
    assert gerada["relatorio"]["sha256"] == publicada["relatorio"]["sha256"]


def test_main_cli_imprime_resumo(
    tmp_path: Path, origem: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    ftp = FtpFalso(origem)
    rc = af.main(
        _args(tmp_path, "--aprovar-uf", "PE"), listar=ftp.listar, baixar=ftp.baixar, hoje=HOJE
    )
    assert rc == 0
    saida = capsys.readouterr().out
    assert "2026-10_pnad2025_v1" in saida and "VIGENTE inalterado" in saida and "'PE'" in saida
