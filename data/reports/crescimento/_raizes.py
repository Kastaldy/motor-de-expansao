"""Raizes de dados da camada de crescimento, resolvidas por variavel de ambiente.

Antes cada um dos 10 scripts repetia quatro caminhos absolutos com o nome de usuario
do autor embutido. Rodar em outra maquina exigia editar os 10 arquivos, e o erro
chegava como `FileNotFoundError` de um caminho que o leitor nunca tinha visto.

A raiz `MOTOR` e a MESMA `MOTOR_DATA_DIR` que `web/server/app.py` usa para achar
`staging/` — os artefatos ja eram gravados no lugar certo, mas por um literal que
podia divergir do backend sem ninguem notar. Agora e' a mesma variavel nos dois
lados, entao nao ha como escrever num `staging/` e ler de outro.

    MOTOR_DATA_DIR       data/ do motor: le `outputs/`, escreve `staging/`
    CRESCIMENTO_TEC_DIR  saida do projeto `Crescimento Regional TEC`
    SOCIOECONOMICO_DIR   RAIS, CAGED, CNPJ e PIB/populacao
    POC_SATELITE_DIR     projeto `poc_satelite` (mosaicos `hex_google_temporal_*`)

Os defaults sao o layout do autor, para nao quebrar quem ja roda isto hoje.

O QUE ESTE MODULO **NAO** RESOLVE: os insumos nao estao no repositorio e nao podem
estar — sao dezenas de GB de microdado (RAIS, CAGED, CNPJ) e de mosaicos de satelite
por UF. Reproduzir a camada do zero exige os dois projetos irmaos alem deste. O que
da para garantir e que o script DIGA o que falta, com o nome da variavel a definir,
em vez de estourar apontando para o disco de outra pessoa. Ver o README.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

_AQUI = Path(__file__).resolve().parent
# data/reports/crescimento -> data/reports -> data
_DATA_DO_REPO = _AQUI.parents[1]

# chave -> (variavel de ambiente, default, para que serve)
_RAIZES: dict[str, tuple[str, str, str]] = {
    "MOTOR": (
        "MOTOR_DATA_DIR",
        str(_DATA_DO_REPO),
        "data/ do motor — de onde o piloto le staging/ e outputs/",
    ),
    "TEC": (
        "CRESCIMENTO_TEC_DIR",
        r"C:\Users\Juan.lima\OneDrive - Grupo Ultra\Área de Trabalho"
        r"\Crescimento Regional TEC\output",
        "saida do projeto Crescimento Regional TEC (os 3 CSVs municipais)",
    ),
    "SOCIO": (
        "SOCIOECONOMICO_DIR",
        r"C:\dados\socioeconomico",
        "microdado socioeconomico: rais/, caged/, cnpj/, pib/",
    ),
    "POC": (
        "POC_SATELITE_DIR",
        r"C:\Users\Juan.lima\OneDrive - Grupo Ultra\Área de Trabalho"
        r"\Google Engine\poc_satelite",
        "projeto poc_satelite (data/uf=XX/hex_google_temporal_YYYY.parquet)",
    ),
}


def raiz(chave: str) -> Path:
    """Raiz de dados pela chave, com mensagem util quando o diretorio nao existe."""
    var, default, para_que = _RAIZES[chave]
    p = Path(os.environ.get(var, default))
    if not p.is_dir():
        sys.exit(
            f"\n[{chave}] diretorio nao encontrado: {p}\n"
            f"  para que serve : {para_que}\n"
            f"  como apontar   : defina a variavel de ambiente {var}\n"
            f"  (default deste repo: {default})\n"
        )
    return p


def entrada(base: Path, *partes: str) -> Path:
    """Caminho de ENTRADA, checado. Falha dizendo QUAL arquivo falta, nao um traceback.

    O modo de falha que isto mata: o `08` lia `_eixo_trajetoria.parquet` por caminho
    relativo, entao rodar de outro diretorio nao dava erro de caminho — dava
    `FileNotFoundError` do arquivo certo no lugar errado, ou pior, lia um
    intermediario velho de outra pasta sem avisar.
    """
    p = base.joinpath(*partes)
    if not p.exists():
        sys.exit(f"\nfalta o insumo: {p}\n  (veja o README desta pasta: de onde ele vem)\n")
    return p


# Intermediarios (`_mun_cresc_bruto`, `_cres_extra`, `_dims`, `_eixo_trajetoria`) ficam
# ANCORADOS na pasta dos scripts, nao no CWD: rodar de outro diretorio antes lia um
# intermediario de outra execucao, em silencio. Gitignorado por `_*` no .gitignore da pasta.
TRABALHO = _AQUI


def trabalho(nome: str) -> Path:
    """Arquivo intermediario, sempre no mesmo lugar independente do CWD."""
    return TRABALHO / nome


def staging(nome: str) -> Path:
    """Artefato final, no `staging/` que o piloto de fato le."""
    d = raiz("MOTOR") / "staging"
    d.mkdir(parents=True, exist_ok=True)
    return d / nome


def outputs(*partes: str) -> Path:
    """Artefato do M1 (leitura). READ-ONLY: nada aqui escreve em `outputs/`."""
    return raiz("MOTOR").joinpath("outputs", *partes)


#: O artefato municipal, mutado em sequencia por 03 -> 05 -> 06 -> 07 -> 08 -> 09 -> 10.
def artefato_municipal() -> Path:
    return staging("crescimento_municipal.parquet")


#: O artefato por hexagono, escrito so pelo 08.
def artefato_hex() -> Path:
    return staging("crescimento_hex.parquet")
