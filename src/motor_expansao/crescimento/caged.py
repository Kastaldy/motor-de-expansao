"""Atualiza o CSV consolidado do Novo CAGED com os meses que faltam.

Port do `baixar_agregar_caged.py` que vivia FORA do repositorio (na estacao do autor,
com `C:\\dados\\...` hardcoded e a lista de meses congelada em 2026-04 — as duas
armadilhas "caminho fixo na maquina de uma pessoa" e "campo derivado congelado").
Aqui os meses sao DESCOBERTOS do proprio consolidado e o caminho vem por argumento.

Contrato do consolidado (o que `data/reports/crescimento/{02,07,09,10}` leem):

    competencia,cod_municipio,uf,saldo,admissoes,desligamentos,salario_medio_adm
    202001,110001,11,-18,52,70,1169.413653846154

- separador VIRGULA e sem BOM, DE PROPOSITO: e' o formato que os 4 consumidores ja'
  leem com `pd.read_csv` default. A regra da casa (`sep=";"` + `utf-8-sig`, CLAUDE.md
  §2) vale para CSV NOVO; mudar o formato de um artefato existente quebraria a cadeia
  em silencio.
- `competencia` e' string AAAAMM; `cod_municipio` e' o codigo IBGE de 6 digitos do
  microdado (vira `cod6` no `02_enriquecer.py`).
- `salario_medio_adm` e' a MEDIA das ADMISSOES do mes (saldo == 1), como no original;
  o `02` e' quem aplica a mediana de 12 meses que doma os outliers do microdado.

Fonte: FTP publico do PDET, `ftp.mtps.gov.br /pdet/microdados/NOVO CAGED/<ANO>/<AAAAMM>/
CAGEDMOV<AAAAMM>.7z`. O `.7z` exige `py7zr` (extra `[crescimento]` do pyproject) — o
import e' TARDIO para o resto do pacote (validacao, aviso) funcionar sem ele, e a
falta vira mensagem acionavel, nao ImportError seco.
"""

from __future__ import annotations

import argparse
import ftplib
import os
import sys
import tempfile
from datetime import UTC, date, datetime
from pathlib import Path

import pandas as pd

FTP_HOST = "ftp.mtps.gov.br"
FTP_BASE = "/pdet/microdados/NOVO CAGED"

#: Colunas posicionais do microdado CAGEDMOV (mesmas do script original).
_USECOLS = [0, 2, 3, 6, 20]
_NAMES = ["competencia", "uf", "cod_municipio", "saldo", "salario"]

#: Ordem de colunas do consolidado — contrato com a cadeia 01..10.
COLUNAS_CONSOLIDADO = [
    "competencia",
    "cod_municipio",
    "uf",
    "saldo",
    "admissoes",
    "desligamentos",
    "salario_medio_adm",
]

#: Guarda de absurdo: uma rodada trimestral normal traz 3-5 meses (lag de publicacao
#: de ~40 dias). Mais que isto e' consolidado corrompido ou cron parado ha' muito —
#: melhor abortar com mensagem do que baixar anos de microdado sem ninguem pedir.
MAX_MESES_POR_RODADA = 8

#: Nome canonico do consolidado (sem periodo embutido: o `_2020_2026` legado
#: congelava o fim da serie no NOME — em 2027 o cron atualizaria um arquivo que a
#: cadeia nao le). O mesmo par de nomes vive em `data/reports/crescimento/_raizes.py`
#: (que nao pode importar daqui); `tests/unit/test_crescimento_atualizacao.py` trava
#: a paridade dos dois lados.
NOME_CONSOLIDADO = "caged_municipio_mensal_consolidado.csv"
NOME_CONSOLIDADO_LEGADO = "caged_municipio_mensal_2020_2026.csv"


def resolver_consolidado(caged_dir: Path) -> Path:
    """Consolidado a usar: o canonico; na falta dele, o legado (estacao do autor)."""
    novo = caged_dir / NOME_CONSOLIDADO
    if novo.exists():
        return novo
    legado = caged_dir / NOME_CONSOLIDADO_LEGADO
    if legado.exists():
        return legado
    return novo  # ausente: quem chamar recebe a mensagem acionavel de `atualizar()`


def competencias_existentes(csv_path: Path) -> list[str]:
    """Competencias (AAAAMM, ordenadas) ja' presentes no consolidado."""
    if not csv_path.exists():
        return []
    serie = pd.read_csv(csv_path, usecols=["competencia"], dtype={"competencia": str})
    return sorted(serie["competencia"].dropna().unique())


def meses_candidatos(ultima: str, hoje: date | None = None) -> list[str]:
    """Meses AAAAMM depois de `ultima` ate' o mes ANTERIOR ao corrente.

    O mes corrente nunca esta' publicado (o CAGED de um mes sai ~40 dias depois),
    entao ele fica fora por construcao; meses candidatos que ainda nao existirem no
    FTP sao pulados um a um na descoberta (`error_perm` nao e' falha).
    """
    if hoje is None:
        hoje = datetime.now(UTC).date()
    ano, mes = int(ultima[:4]), int(ultima[4:6])
    limite = (hoje.year, hoje.month)
    out: list[str] = []
    while True:
        mes += 1
        if mes > 12:
            ano, mes = ano + 1, 1
        if (ano, mes) >= limite:
            break
        out.append(f"{ano}{mes:02d}")
    return out


def _baixar_7z(comp: str, destino: Path, timeout: int = 300) -> Path | None:
    """Baixa CAGEDMOV<comp>.7z; devolve None se o mes ainda nao foi publicado."""
    nome = f"CAGEDMOV{comp}.7z"
    local = destino / nome
    if local.exists() and local.stat().st_size > 1000:
        return local
    # Baixa em `.part` e so' renomeia COMPLETO: uma queda de conexao no meio do
    # retrbinary deixaria arquivo parcial > 1000 bytes que o atalho acima reusaria
    # em TODA rodada futura — o cron quebraria no py7zr para sempre, ate' alguem
    # apagar o .7z na mao (defeito pego na revisao adversarial; o script original
    # era interativo e podia pagar esse preco, um cron autonomo nao).
    parcial = local.with_suffix(local.suffix + ".part")
    ftp = ftplib.FTP(FTP_HOST, timeout=timeout)
    try:
        ftp.login()
        try:
            ftp.cwd(f"{FTP_BASE}/{comp[:4]}/{comp}")
        except ftplib.error_perm:
            return None  # mes ainda nao publicado — esperado no fim da fila
        with open(parcial, "wb") as f:
            ftp.retrbinary("RETR " + nome, f.write, blocksize=1024 * 1024)
    finally:
        ftp.quit()
    os.replace(parcial, local)
    return local


def _extrair_txt(sevenzip: Path, destino: Path) -> Path:
    try:
        import py7zr  # import tardio: so' quem baixa precisa do extra [crescimento]
    except ImportError as exc:  # pragma: no cover - depende do ambiente
        raise SystemExit(
            "py7zr ausente: instale o extra do pipeline de crescimento "
            "(`pip install .[crescimento]`) — e' ele que abre o .7z do CAGED."
        ) from exc
    with py7zr.SevenZipFile(sevenzip, mode="r") as z:
        nomes = z.getnames()
        z.extractall(path=destino)
    return destino / nomes[0]


def agregar_microdado(df: pd.DataFrame, comp: str) -> pd.DataFrame:
    """Agrega o microdado de UM mes por municipio — mesma conta do script original.

    Recebe o DataFrame com as colunas `_NAMES` (ja' fatiadas do txt) para a conta
    ser testavel sem FTP nem .7z.
    """
    df = df.copy()
    df["salario"] = pd.to_numeric(
        df["salario"].astype(str).str.replace(",", ".", regex=False), errors="coerce"
    )
    df["saldo"] = pd.to_numeric(df["saldo"], errors="coerce")
    df["adm"] = (df["saldo"] == 1).astype("int64")
    df["desl"] = (df["saldo"] == -1).astype("int64")
    g = (
        df.groupby("cod_municipio")
        .agg(
            uf=("uf", "first"),
            saldo=("saldo", "sum"),
            admissoes=("adm", "sum"),
            desligamentos=("desl", "sum"),
        )
        .reset_index()
    )
    sal = (
        df.loc[df["saldo"] == 1]
        .groupby("cod_municipio")["salario"]
        .mean()
        .rename("salario_medio_adm")
        .reset_index()
    )
    g = g.merge(sal, on="cod_municipio", how="left")
    g.insert(0, "competencia", comp)
    return g[COLUNAS_CONSOLIDADO]


def _processar_mes(sevenzip: Path, comp: str) -> pd.DataFrame:
    with tempfile.TemporaryDirectory(prefix="caged_") as tmp:
        txt = _extrair_txt(sevenzip, Path(tmp))
        df = pd.read_csv(
            txt,
            sep=";",
            encoding="latin1",
            header=0,
            usecols=_USECOLS,
            names=_NAMES,
            dtype={"competencia": str, "uf": str, "cod_municipio": str, "saldo": "Int64"},
        )
    return agregar_microdado(df, comp)


def atualizar_consolidado(csv_path: Path, novos: pd.DataFrame) -> None:
    """Anexa os meses novos ao consolidado, por SUBSTITUICAO de competencia.

    Se uma competencia dos `novos` ja' existir (re-rodada apos falha no meio), as
    linhas antigas dela CAEM e as novas entram — nunca as duas. Escrita atomica:
    `.tmp` ao lado + `os.replace`, para uma falha no meio nao deixar o consolidado
    truncado (mesma regra do runbook de publicacao dos parquets).
    """
    if novos.empty:
        return
    atual = pd.read_csv(
        csv_path, dtype={"competencia": str, "cod_municipio": str, "uf": str}
    )
    substituidas = set(novos["competencia"].astype(str))
    atual = atual[~atual["competencia"].isin(substituidas)]
    total = pd.concat([atual[COLUNAS_CONSOLIDADO], novos[COLUNAS_CONSOLIDADO]])
    total = total.sort_values(["competencia", "cod_municipio"], kind="stable")
    tmp = csv_path.with_suffix(csv_path.suffix + f".tmp-{os.getpid()}")
    total.to_csv(tmp, index=False, encoding="utf-8")
    os.replace(tmp, csv_path)


def atualizar(
    csv_path: Path,
    raw_dir: Path | None = None,
    max_meses: int = MAX_MESES_POR_RODADA,
) -> list[str]:
    """Baixa e incorpora os meses que faltam. Devolve as competencias incorporadas."""
    existentes = competencias_existentes(csv_path)
    if not existentes:
        raise SystemExit(
            f"consolidado ausente ou vazio: {csv_path}\n"
            "  Este modulo ATUALIZA um consolidado existente; a carga historica "
            "(2020..hoje) e' a do repasse inicial de insumos (docs/infra_producao.md)."
        )
    candidatos = meses_candidatos(existentes[-1])
    if len(candidatos) > max_meses:
        raise SystemExit(
            f"{len(candidatos)} meses faltando desde {existentes[-1]} — acima da guarda "
            f"de {max_meses}. Consolidado corrompido ou cadencia parada ha' "
            "muito; rode com --max-meses maior SO' depois de conferir o arquivo."
        )
    if raw_dir is None:
        raw_dir = csv_path.parent / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)

    incorporadas: list[str] = []
    partes: list[pd.DataFrame] = []
    for comp in candidatos:
        sz = _baixar_7z(comp, raw_dir)
        if sz is None:
            print(f"{comp}: ainda nao publicado no FTP; paro aqui")
            break  # a serie e' sequencial: mes seguinte tambem nao estara'
        g = _processar_mes(sz, comp)
        print(f"{comp}: {len(g)} municipios, saldo_total={int(g['saldo'].sum())}")
        partes.append(g)
        incorporadas.append(comp)
        # O bruto ja' virou agregado: apagar o .7z (centenas de MB/mes) e' o que
        # mantem verdadeira a promessa "o job escreve so' os artefatos + consolidado"
        # — na VPS o proprio healthcheck alarma disco >80%. Se a rodada falhar mais
        # adiante, a proxima simplesmente rebaixa do FTP.
        sz.unlink(missing_ok=True)

    if partes:
        atualizar_consolidado(csv_path, pd.concat(partes, ignore_index=True))
    return incorporadas


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--csv", required=True, type=Path, help="consolidado a atualizar")
    ap.add_argument("--raw-dir", type=Path, default=None, help="onde guardar os .7z")
    ap.add_argument(
        "--max-meses", type=int, default=MAX_MESES_POR_RODADA,
        help="guarda de absurdo (meses por rodada)",
    )
    args = ap.parse_args(argv)
    novas = atualizar(args.csv, args.raw_dir, max_meses=args.max_meses)
    if novas:
        print(f"incorporadas: {','.join(novas)}")
    else:
        print("nenhum mes novo publicado; consolidado ja' esta' em dia")
    return 0


if __name__ == "__main__":
    sys.exit(main())
