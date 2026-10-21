"""PNAD Continua ANUAL (visitas 1 e 5): localizar, baixar, ler e CALCULAR os fatores de renda.

Este modulo e' o UNICO lugar onde o fator temporal da renda nasce. Ele faz quatro coisas:

1. **Localiza** as 4 amostras (ano base e ano alvo, visitas 1 e 5) listando o diretorio do
   FTP do IBGE e casando os nomes por REGEX. Nenhuma data e' cravada: o sufixo `_AAAAMMDD`
   dos arquivos muda a cada republicacao (o 2022 de dados e' `20250822`, o layout dele e'
   `20231129`). Faltou qualquer uma das 4 amostras (zip OU layout) -> aborta.
2. **Cacheia** cada arquivo baixado com sha256 num manifesto (`manifesto_pnad.json`). Arquivo
   no cache com sha diferente do manifesto aborta (cache corrompido); arquivo sem registro e'
   adotado e registrado.
3. **Le** os microdados de largura fixa com as posicoes tiradas do `input_*.txt` da propria
   amostra (as posicoes MUDAM entre visita 1 e visita 5). Variavel ausente no layout -> aborta.
4. **Calcula** os fatores, so' a partir dos microdados:
   - universo de pessoas: `VD5008` (renda habitual domiciliar per capita) nao nula;
   - domicilio: o registro do responsavel, `V2005 == '01'`; moradores = `VD2003` nele;
   - nivel = media ponderada por `V1032` (peso com calibracao);
   - fator = nivel(ano alvo, visita X) / nivel(ano base, MESMA visita X), e o fator final
     e' a media GEOMETRICA das visitas 1 e 5 — para per capita, domiciliar e moradores;
   - o nacional sai do Brasil INTEIRO (todas as pessoas), nao de media de UFs.

REGRA DURA (ajuste do Felipe, 2026-10-20): **nada aqui le, recebe ou importa a SIDRA.**
A tabela 7531 mistura visitas (2022 reproduz a visita 5; 2025 reproduz a visita 1), entao a
razao 7531(2025)/7531(2022) carrega um artefato de visita de ~6%. A 7531 so' serve para
CONFERIR O NIVEL de cada ano, e isso vive em `motor_expansao.renda.sidra`, chamado pelo
orquestrador DEPOIS do calculo. Um teste de contrato varre este arquivo por AST e falha se
ele importar o modulo da SIDRA.
"""

from __future__ import annotations

import hashlib
import json
import re
import zipfile
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

#: Raiz HTTPS do FTP do IBGE para a PNAD Continua anual por visita.
FTP_BASE = (
    "https://ftp.ibge.gov.br/Trabalho_e_Rendimento/"
    "Pesquisa_Nacional_por_Amostra_de_Domicilios_continua/Anual/Microdados/Visita"
)
VISITAS = (1, 5)

#: Variaveis lidas do layout. Faltou uma -> aborta (nao ha fallback de posicao).
VARIAVEIS = ("UF", "V1032", "V2005", "VD2003", "VD5007", "VD5008")
NUMERICAS = ("V1032", "VD2003", "VD5007", "VD5008")
PESO = "V1032"
VAR_PC = "VD5008"
VAR_DOM = "VD5007"
VAR_MORADORES = "VD2003"
COND_RESPONSAVEL = "01"

#: Codigo IBGE da UF (2 digitos) -> sigla.
COD_UF = {
    "11": "RO", "12": "AC", "13": "AM", "14": "RR", "15": "PA", "16": "AP", "17": "TO",
    "21": "MA", "22": "PI", "23": "CE", "24": "RN", "25": "PB", "26": "PE", "27": "AL",
    "28": "SE", "29": "BA", "31": "MG", "32": "ES", "33": "RJ", "35": "SP", "41": "PR",
    "42": "SC", "43": "RS", "50": "MS", "51": "MT", "52": "GO", "53": "DF",
}  # fmt: skip

#: Regra de excecao por UF (parametros declarados; gravados no arquivo de versao).
LIMIAR_PADRAO = 0.07
N_MIN_PADRAO = 5000
LIMIARES_SENSIBILIDADE = (0.03, 0.05, 0.07, 0.10)

MANIFESTO = "manifesto_pnad.json"

Listar = Callable[[str], list[str]]
Baixar = Callable[[str, Path], None]


class PnadErro(SystemExit):
    """Erro acionavel da etapa PNAD (aborta o comando com mensagem)."""

    def __init__(self, mensagem: str) -> None:
        super().__init__(f"[pnad] {mensagem}")
        self.mensagem = mensagem


# ---------------------------------------------------------------------------
# 1. Localizacao no FTP (por regex, sem datas cravadas)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ArquivoRemoto:
    nome: str
    url: str
    data_arquivo: str | None  # sufixo AAAAMMDD do nome, quando houver


@dataclass(frozen=True)
class Amostra:
    ano: int
    visita: int
    microdados: ArquivoRemoto
    layout: ArquivoRemoto

    @property
    def chave(self) -> str:
        return f"{self.ano}v{self.visita}"


def url_dados(visita: int) -> str:
    return f"{FTP_BASE}/Visita_{visita}/Dados/"


def url_documentacao(visita: int) -> str:
    return f"{FTP_BASE}/Visita_{visita}/Documentacao/"


def regex_microdados(ano: int, visita: int) -> re.Pattern[str]:
    return re.compile(rf"^PNADC_{ano}_visita{visita}(?:_(\d{{8}}))?\.zip$", re.IGNORECASE)


def regex_layout(ano: int, visita: int) -> re.Pattern[str]:
    return re.compile(rf"^input_PNADC_{ano}_visita{visita}(?:_(\d{{8}}))?\.txt$", re.IGNORECASE)


def _escolher(nomes: Iterable[str], padrao: re.Pattern[str]) -> tuple[str, str | None] | None:
    """Casa por regex e, havendo republicacoes, fica com a de data mais recente."""
    casados = []
    for nome in nomes:
        m = padrao.match(nome)
        if m:
            casados.append((m.group(1) or "", nome))
    if not casados:
        return None
    data, nome = max(casados)
    return nome, (data or None)


def localizar_amostras(
    listar: Listar, anos: Iterable[int], visitas: Iterable[int] = VISITAS
) -> dict[tuple[int, int], Amostra]:
    """Lista os diretorios do FTP e devolve as amostras (ano, visita). Aborta se faltar alguma."""
    out: dict[tuple[int, int], Amostra] = {}
    faltam: list[str] = []
    cache_listagem: dict[str, list[str]] = {}

    def _listar(url: str) -> list[str]:
        if url not in cache_listagem:
            cache_listagem[url] = list(listar(url))
        return cache_listagem[url]

    for visita in visitas:
        dados, doc = url_dados(visita), url_documentacao(visita)
        for ano in anos:
            zip_ = _escolher(_listar(dados), regex_microdados(ano, visita))
            lay = _escolher(_listar(doc), regex_layout(ano, visita))
            if zip_ is None:
                faltam.append(f"microdados {ano} visita {visita} ({dados})")
            if lay is None:
                faltam.append(f"layout input_*.txt {ano} visita {visita} ({doc})")
            if zip_ is None or lay is None:
                continue
            out[(ano, visita)] = Amostra(
                ano=ano,
                visita=visita,
                microdados=ArquivoRemoto(zip_[0], dados + zip_[0], zip_[1]),
                layout=ArquivoRemoto(lay[0], doc + lay[0], lay[1]),
            )
    if faltam:
        raise PnadErro(
            "amostra(s) ausente(s) — os fatores exigem as 4 (ano base e alvo x visitas 1 e 5): "
            + "; ".join(faltam)
        )
    return out


def listar_diretorio_local(cache_dir: Path) -> Listar:
    """Listagem OFFLINE: o mesmo casamento por regex, sobre os arquivos do cache."""

    def _listar(_url: str) -> list[str]:
        return sorted(p.name for p in Path(cache_dir).iterdir() if p.is_file())

    return _listar


def listar_http(url: str, *, timeout: float = 120.0) -> list[str]:
    """Le o indice HTML do FTP do IBGE e devolve os nomes de arquivo (hrefs)."""
    import requests

    resp = requests.get(url, timeout=timeout)
    resp.raise_for_status()
    nomes = re.findall(r'href="([^"?/][^"]*)"', resp.text)
    return sorted({n.rsplit("/", 1)[-1] for n in nomes})


def baixar_http(url: str, destino: Path, *, timeout: float = 600.0) -> None:
    """Download em streaming para `.parcial` + rename (nunca deixa arquivo meio-escrito)."""
    import requests

    tmp = destino.with_name(destino.name + ".parcial")
    with requests.get(url, stream=True, timeout=timeout) as resp:
        resp.raise_for_status()
        with tmp.open("wb") as fh:
            for bloco in resp.iter_content(chunk_size=1 << 20):
                fh.write(bloco)
    tmp.replace(destino)


# ---------------------------------------------------------------------------
# 2. Cache com sha256
# ---------------------------------------------------------------------------


def sha256_arquivo(path: Path) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as fh:
        for bloco in iter(lambda: fh.read(1 << 20), b""):
            h.update(bloco)
    return h.hexdigest()


def _ler_manifesto(cache_dir: Path) -> dict:
    p = cache_dir / MANIFESTO
    if not p.exists():
        return {"arquivos": {}, "extraidos": {}}
    dados = json.loads(p.read_text(encoding="utf-8"))
    dados.setdefault("arquivos", {})
    dados.setdefault("extraidos", {})
    return dados


def _gravar_manifesto(cache_dir: Path, manifesto: dict) -> None:
    p = cache_dir / MANIFESTO
    tmp = p.with_name(p.name + ".tmp")
    tmp.write_text(json.dumps(manifesto, ensure_ascii=False, indent=2, sort_keys=True), "utf-8")
    tmp.replace(p)


@dataclass
class ArquivoCache:
    nome: str
    url: str
    data_arquivo: str | None
    caminho: Path
    sha256: str
    bytes: int
    baixado: bool


def garantir_arquivo(
    remoto: ArquivoRemoto,
    cache_dir: Path,
    manifesto: dict,
    baixar: Baixar | None,
) -> ArquivoCache:
    """Reusa o arquivo do cache (conferindo o sha256) ou baixa. `baixar=None` = offline."""
    caminho = cache_dir / remoto.nome
    registro = manifesto["arquivos"].get(remoto.nome)
    baixado = False
    if not caminho.exists():
        if baixar is None:
            raise PnadErro(f"{remoto.nome} nao esta no cache {cache_dir} e o modo e' offline")
        baixar(remoto.url, caminho)
        baixado = True
        registro = None
    sha = sha256_arquivo(caminho)
    if registro is not None and registro.get("sha256") != sha:
        raise PnadErro(
            f"cache corrompido: {remoto.nome} tem sha256 {sha[:12]}... e o manifesto registra "
            f"{str(registro.get('sha256'))[:12]}... — apague o arquivo e rode de novo"
        )
    if registro is None:
        manifesto["arquivos"][remoto.nome] = {
            "sha256": sha,
            "bytes": caminho.stat().st_size,
            "url": remoto.url,
            "registrado_em": datetime.now(UTC).isoformat(timespec="seconds"),
        }
    return ArquivoCache(
        nome=remoto.nome,
        url=remoto.url,
        data_arquivo=remoto.data_arquivo,
        caminho=caminho,
        sha256=sha,
        bytes=caminho.stat().st_size,
        baixado=baixado,
    )


# ---------------------------------------------------------------------------
# 3. Layout e leitura de largura fixa
# ---------------------------------------------------------------------------

_RE_LAYOUT = re.compile(r"\s*@(\d+)\s+(\w+)\s+\$?(\d+)\.")


def ler_layout(path: Path) -> dict[str, tuple[int, int]]:
    """Posicoes (inicio, fim) 0-based do `input_*.txt` (programa SAS do IBGE)."""
    out: dict[str, tuple[int, int]] = {}
    for linha in Path(path).read_text(encoding="latin-1").splitlines():
        m = _RE_LAYOUT.match(linha)
        if m:
            ini, nome, larg = int(m.group(1)), m.group(2), int(m.group(3))
            out[nome] = (ini - 1, ini - 1 + larg)
    return out


def posicoes(layout: Mapping[str, tuple[int, int]], origem: str) -> dict[str, tuple[int, int]]:
    faltam = [v for v in VARIAVEIS if v not in layout]
    if faltam:
        raise PnadErro(f"variavel(is) ausente(s) no layout {origem}: {faltam}")
    return {v: layout[v] for v in VARIAVEIS}


def ler_microdados(zip_path: Path, pos: Mapping[str, tuple[int, int]]) -> pd.DataFrame:
    """Le o .txt de largura fixa dentro do zip, so' as colunas de `pos`, em streaming."""
    colunas: dict[str, list[str]] = {v: [] for v in pos}
    fatias = [(v, a, b) for v, (a, b) in pos.items()]
    with zipfile.ZipFile(zip_path) as z:
        txts = [n for n in z.namelist() if n.lower().endswith(".txt")]
        if len(txts) != 1:
            raise PnadErro(f"{Path(zip_path).name}: esperado 1 .txt no zip, achei {txts}")
        with z.open(txts[0]) as fh:
            for bruta in fh:
                linha = bruta.decode("latin-1").rstrip("\r\n")
                if not linha.strip():
                    continue
                for v, a, b in fatias:
                    colunas[v].append(linha[a:b].strip())
    df = pd.DataFrame(colunas)
    for c in NUMERICAS:
        if c in df:
            df[c] = pd.to_numeric(df[c].replace("", np.nan), errors="coerce")
    return df


def extrair_amostra(
    microdados: ArquivoCache,
    layout: ArquivoCache,
    cache_dir: Path,
    manifesto: dict,
    ano: int,
    visita: int,
) -> pd.DataFrame:
    """Extrai (ou reusa) o parquet enxuto da amostra, amarrado ao sha256 do zip de origem."""
    pos = posicoes(ler_layout(layout.caminho), layout.nome)
    alvo = cache_dir / f"pnad_{ano}_v{visita}_e0.parquet"
    reg = manifesto["extraidos"].get(alvo.name)
    if (
        alvo.exists()
        and reg is not None
        and reg.get("origem_sha256") == microdados.sha256
        and reg.get("layout_sha256") == layout.sha256
        and reg.get("posicoes") == {k: list(v) for k, v in pos.items()}
        and reg.get("sha256") == sha256_arquivo(alvo)
    ):
        return pd.read_parquet(alvo)
    df = ler_microdados(microdados.caminho, pos)
    df.to_parquet(alvo, index=False)
    manifesto["extraidos"][alvo.name] = {
        "origem": microdados.nome,
        "origem_sha256": microdados.sha256,
        "layout": layout.nome,
        "layout_sha256": layout.sha256,
        "posicoes": {k: list(v) for k, v in pos.items()},
        "linhas": int(len(df)),
        "sha256": sha256_arquivo(alvo),
    }
    return df


@dataclass
class Insumos:
    amostras: dict[tuple[int, int], Amostra]
    arquivos: dict[tuple[int, int], tuple[ArquivoCache, ArquivoCache]]
    dados: dict[tuple[int, int], pd.DataFrame] = field(repr=False)


def preparar_insumos(
    *,
    ano_base: int,
    ano_alvo: int,
    cache_dir: Path,
    listar: Listar,
    baixar: Baixar | None,
) -> Insumos:
    """Localiza as 4 amostras, garante o cache (sha256) e extrai as colunas necessarias."""
    cache_dir = Path(cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)
    amostras = localizar_amostras(listar, (ano_base, ano_alvo))
    manifesto = _ler_manifesto(cache_dir)
    arquivos: dict[tuple[int, int], tuple[ArquivoCache, ArquivoCache]] = {}
    dados: dict[tuple[int, int], pd.DataFrame] = {}
    try:
        for chave in sorted(amostras):
            a = amostras[chave]
            zc = garantir_arquivo(a.microdados, cache_dir, manifesto, baixar)
            lc = garantir_arquivo(a.layout, cache_dir, manifesto, baixar)
            arquivos[chave] = (zc, lc)
            dados[chave] = extrair_amostra(zc, lc, cache_dir, manifesto, a.ano, a.visita)
    finally:
        _gravar_manifesto(cache_dir, manifesto)
    return Insumos(amostras=amostras, arquivos=arquivos, dados=dados)


# ---------------------------------------------------------------------------
# 4. Calculo dos fatores (SO' microdados; nada de SIDRA aqui)
# ---------------------------------------------------------------------------


def _wmean(x: pd.Series, w: pd.Series) -> float:
    m = x.notna() & w.notna()
    return float(np.average(x[m], weights=w[m])) if m.any() else float("nan")


def preparar_pessoas(df: pd.DataFrame) -> pd.DataFrame:
    """Universo: pessoas com VD5008 definido. Acrescenta a sigla da UF."""
    d = df[df[VAR_PC].notna()].copy()
    cod = d["UF"].astype(str).str.strip()
    d["uf"] = cod.map(COD_UF)
    desconhecidas = sorted(set(cod[d["uf"].isna()]))
    if desconhecidas:
        raise PnadErro(f"codigo(s) de UF desconhecido(s) nos microdados: {desconhecidas}")
    return d


def niveis_grupo(pessoas: pd.DataFrame) -> dict[str, float]:
    dom = pessoas[pessoas["V2005"].astype(str).str.strip() == COND_RESPONSAVEL]
    return {
        "pc": _wmean(pessoas[VAR_PC], pessoas[PESO]),
        "dom": _wmean(dom[VAR_DOM], dom[PESO]),
        "moradores": _wmean(dom[VAR_MORADORES], dom[PESO]),
        "n_pessoas": int(len(pessoas)),
        "n_domicilios": int(len(dom)),
    }


def niveis_por_uf(df: pd.DataFrame) -> dict[str, dict[str, float]]:
    """Niveis de UMA amostra: 'BR' (Brasil inteiro) + cada UF."""
    p = preparar_pessoas(df)
    out = {"BR": niveis_grupo(p)}
    for uf, g in p.groupby("uf", sort=True):
        out[str(uf)] = niveis_grupo(g)
    return out


@dataclass
class FatoresCalculados:
    ano_base: int
    ano_alvo: int
    #: niveis[(ano, visita)][uf] = {pc, dom, moradores, n_pessoas, n_domicilios}
    niveis: dict[tuple[int, int], dict[str, dict[str, float]]]
    #: fatores[uf] = {pc_v1, pc_v5, per_capita, dom_v1, dom_v5, domiciliar, mor_v1, mor_v5, moradores, n_min_amostras}
    fatores: dict[str, dict[str, float]]

    @property
    def nacional(self) -> dict[str, float]:
        f = self.fatores["BR"]
        return {
            "per_capita": f["per_capita"],
            "domiciliar": f["domiciliar"],
            "moradores": f["moradores"],
        }

    def ufs(self) -> list[str]:
        return sorted(u for u in self.fatores if u != "BR")


def calcular_fatores(
    dados: Mapping[tuple[int, int], pd.DataFrame], ano_base: int, ano_alvo: int
) -> FatoresCalculados:
    """Fatores ano_alvo/ano_base na MESMA visita, media geometrica v1/v5. So' microdados.

    `dados[(ano, visita)]` e' o DataFrame cru da amostra (colunas de `VARIAVEIS`).
    """
    exigidas = [(a, v) for a in (ano_base, ano_alvo) for v in VISITAS]
    faltam = [k for k in exigidas if k not in dados]
    if faltam:
        raise PnadErro(f"amostra(s) ausente(s) para o calculo: {faltam}")
    niveis = {k: niveis_por_uf(dados[k]) for k in exigidas}
    grupos = set.intersection(*(set(n) for n in niveis.values()))
    fatores: dict[str, dict[str, float]] = {}
    for g in sorted(grupos):
        f: dict[str, float] = {}
        for v in VISITAS:
            base, alvo = niveis[(ano_base, v)][g], niveis[(ano_alvo, v)][g]
            f[f"pc_v{v}"] = alvo["pc"] / base["pc"]
            f[f"dom_v{v}"] = alvo["dom"] / base["dom"]
            f[f"mor_v{v}"] = alvo["moradores"] / base["moradores"]
        # media geometrica das duas visitas
        f["per_capita"] = (f["pc_v1"] * f["pc_v5"]) ** 0.5
        f["domiciliar"] = (f["dom_v1"] * f["dom_v5"]) ** 0.5
        f["moradores"] = (f["mor_v1"] * f["mor_v5"]) ** 0.5
        f["n_min_amostras"] = float(min(niveis[k][g]["n_pessoas"] for k in exigidas))
        fatores[g] = f
    if "BR" not in fatores:
        raise PnadErro("nivel nacional (BR) nao calculado")
    return FatoresCalculados(ano_base=ano_base, ano_alvo=ano_alvo, niveis=niveis, fatores=fatores)


def avaliar_regra(
    calc: FatoresCalculados, *, limiar: float = LIMIAR_PADRAO, n_min: int = N_MIN_PADRAO
) -> list[dict[str, Any]]:
    """Avalia a regra de excecao em TODAS as UFs (ordenadas pelo menor |desvio|, decrescente).

    Uma UF e' candidata quando, na per capita, o desvio contra o nacional da MESMA visita tem
    o mesmo sinal nas visitas 1 e 5, o menor |desvio| das duas e' > `limiar` (estrito) e a
    menor das 4 amostras tem >= `n_min` pessoas com renda (contagem de linhas, sem peso).
    """
    br = calc.fatores["BR"]
    linhas: list[dict[str, Any]] = []
    for uf in calc.ufs():
        f = calc.fatores[uf]
        d1 = f["pc_v1"] / br["pc_v1"] - 1
        d5 = f["pc_v5"] / br["pc_v5"] - 1
        menor = min(abs(d1), abs(d5))
        mesmo_sinal = bool(np.sign(d1) == np.sign(d5))
        n = int(f["n_min_amostras"])
        linhas.append(
            {
                "uf": uf,
                "desvio_pc_v1": d1,
                "desvio_pc_v5": d5,
                "desvio_dom_v1": f["dom_v1"] / br["dom_v1"] - 1,
                "desvio_dom_v5": f["dom_v5"] / br["dom_v5"] - 1,
                "mesmo_sinal": mesmo_sinal,
                "menor_desvio_abs": menor,
                "n_min_amostras": n,
                "atende": bool(mesmo_sinal and menor > limiar and n >= n_min),
                "per_capita": f["per_capita"],
                "domiciliar": f["domiciliar"],
                "moradores": f["moradores"],
            }
        )
    linhas.sort(key=lambda r: (-float(r["menor_desvio_abs"]), str(r["uf"])))
    return linhas


def candidatas(
    calc: FatoresCalculados, *, limiar: float = LIMIAR_PADRAO, n_min: int = N_MIN_PADRAO
) -> list[dict]:
    return [r for r in avaliar_regra(calc, limiar=limiar, n_min=n_min) if r["atende"]]


def nivel_pc_por_uf(calc: FatoresCalculados, ano: int, visita: int) -> dict[str, float]:
    """Nivel per capita (R$) por UF de uma amostra — insumo da CONFERENCIA, nunca do fator."""
    return {uf: n["pc"] for uf, n in calc.niveis[(ano, visita)].items() if uf != "BR"}
