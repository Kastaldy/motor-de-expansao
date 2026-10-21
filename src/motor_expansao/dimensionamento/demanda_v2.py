"""Viabilidade v2 — o MODELO, puro (sem I/O). DEC-077 (ampliada em 2026-10-20).

O que a v2 faz: sugere o FATURAMENTO MENSAL MADURO de uma unidade a partir da praca (a
isocrona de 10 min de carro) e da metragem, e converte esse faturamento em alunos pelas
premissas da propria requisicao. A demanda continua EDITAVEL pelo operador: a v2 so' a
semeia (decisao D1(b) do desenho). Variaveis decididas pelo dono (Felipe, 20/10/2026):
SEM os dummies de master.

    X   = [1, ln m2, ln renda_dom_c10, ln pop_c10, studios]
    p50 = exp(X . beta + cal_2026)          (OLS em log do faturamento mensal maduro)
    p10 = p50 x faixa.p10 ;  p90 = p50 x faixa.p90

- `cal_2026` e' o ajuste de calendario em LOG (nivel 2026). O deslocamento de -6% da
  mediana dos residuos do UNI-07 NAO entra no p50 (critica A4): o p50 e' o do modelo, e a
  faixa e' a do UNI-07 como ela foi medida. Declarado na DEC.
- `studios` e' BINARIO no modelo (tem estudio ou nao). O custo do estudio na Viabilidade e'
  POR estudio (DEC-068). Consequencia declarada: o 2o estudio nao muda o faturamento
  previsto e custa mais R$ 6.000/mes, e por isso a v2 penaliza estruturalmente o 2o.
- `xtx_inv` e `sigma` entram so' no diagnostico (erro-padrao da previsao em log); a faixa
  exibida e' a empirica do UNI-07.

SCHEMA DO JSON DE COEFICIENTES (estrito: chave faltando, sobrando ou de tipo errado ->
`CoeficientesInvalidos`, e a v2 fica INDISPONIVEL com o motivo; nunca erro 500)::

    {
      "versao": "v2-sem-masters-2026-10",          # texto livre, curto
      "fonte": "ficha_v2/01_ficha_tecnica.py (Felipe)",
      "data": "2026-10-20",                         # AAAA-MM-DD
      "beta": {"intercepto": f, "ln_m2": f, "ln_renda_dom_c10": f,
               "ln_pop_c10": f, "studios": f},
      "xtx_inv": [[f x5] x5],                       # ordem de `ORDEM_X`, simetrica
      "sigma": f > 0,                               # desvio do residuo em log
      "cal_2026": f,                                # ajuste de calendario em LOG
      "envelope": {"ln_m2": [min, max], "ln_renda_dom_c10": [min, max],
                   "ln_pop_c10": [min, max]},       # intervalo do TREINO
      "faixa": {"p10": 0 < f <= 1, "p90": f >= 1, "provisoria": bool},
      "sha256_insumos": {"<arquivo>": "<64 hex>", ...},   # ao menos um
      # OPCIONAL: golden de aceitacao (turma 2026), para o teste que reproduz a ficha
      "aceitacao_turma_2026": [
        {"unidade": "id anonimo", "m2": f, "renda_dom_c10": f, "pop_c10": f,
         "studios": 0|1, "fat_previsto_cal2026": f}, ...]
    }

Identificadores sem acento (CLAUDE.md secao 2); textos de usuario (motivos) acentuados.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

# Ordem das colunas de X (e de `xtx_inv`). Mudar a ordem muda o significado da matriz.
ORDEM_X = ("intercepto", "ln_m2", "ln_renda_dom_c10", "ln_pop_c10", "studios")
COVARIAVEIS_ENVELOPE = ("ln_m2", "ln_renda_dom_c10", "ln_pop_c10")
_CHAVES_TOPO = frozenset(
    {
        "versao",
        "fonte",
        "data",
        "beta",
        "xtx_inv",
        "sigma",
        "cal_2026",
        "envelope",
        "faixa",
        "sha256_insumos",
    }
)
_CHAVES_TOPO_OPCIONAIS = frozenset({"aceitacao_turma_2026"})
_CHAVES_FAIXA = frozenset({"p10", "p90", "provisoria"})
_CHAVES_ACEITACAO = frozenset(
    {"unidade", "m2", "renda_dom_c10", "pop_c10", "studios", "fat_previsto_cal2026"}
)
_RE_SHA = re.compile(r"^[0-9a-f]{64}$")
_RE_DATA = re.compile(r"^\d{4}-\d{2}-\d{2}$")
# Simetria de (X'X)^-1: tolerancia relativa (a exportacao arredonda).
_TOL_SIMETRIA = 1e-6


class CoeficientesInvalidos(ValueError):
    """O JSON de coeficientes nao segue o schema. `str(exc)` e' o motivo (portugues)."""


class EntradasInvalidas(ValueError):
    """Entrada fora do dominio do log (zero, negativa, NaN) -> sem previsao."""


@dataclass(frozen=True)
class CoeficientesV2:
    versao: str
    fonte: str
    data: str
    beta: tuple[float, ...]  # na ordem de ORDEM_X
    xtx_inv: tuple[tuple[float, ...], ...]
    sigma: float
    cal_2026: float
    envelope: dict[str, tuple[float, float]]
    faixa_p10: float
    faixa_p90: float
    faixa_provisoria: bool
    sha256_insumos: dict[str, str]
    sha256: str  # do ARQUIVO lido (o carimbo de versao que vai no payload e no token)
    aceitacao_turma_2026: tuple[dict[str, Any], ...] = ()

    def beta_de(self, nome: str) -> float:
        return self.beta[ORDEM_X.index(nome)]


@dataclass(frozen=True)
class EntradasV2:
    """As entradas do modelo. `renda_dom_c10` e' DERIVADA (nunca recebida pronta)."""

    m2: float
    studios: int  # 0 ou 1
    pop_c10: float
    dom_c10: float
    renda_pc_c10: float

    @property
    def renda_dom_c10(self) -> float:
        """Renda DOMICILIAR da isocrona = renda per capita x pessoas / domicilios.

        NAO e' a renda domiciliar do Relatorio Pontual (V06004 x uplift x fator temporal):
        e' a definicao do estudo, e confundi-las e' erro de definicao (teste de mutacao).
        """
        return self.renda_pc_c10 * self.pop_c10 / self.dom_c10


@dataclass(frozen=True)
class PrevisaoV2:
    fat_p10: float
    fat_p50: float
    fat_p90: float
    ln_x: dict[str, float]
    flag_extrapolacao: bool
    fora_do_envelope: tuple[str, ...]
    faixa_provisoria: bool
    ep_log: float  # erro-padrao da previsao em log (diagnostico)


def studios_binario(n_studios: int | None) -> int:
    """O modelo ve o estudio como PRESENCA (0/1), nao como contagem."""
    return 1 if int(n_studios or 0) > 0 else 0


def sem_agregador(share_balcao: float, limiar: float | None = None) -> bool:
    """Predicado de "abre sem agregador" (UNI-14, critica A3): share de balcao >= limiar."""
    if limiar is None:
        from motor_expansao.dimensionamento.config import V2_SHARE_BALCAO_SEM_AGREGADOR

        limiar = V2_SHARE_BALCAO_SEM_AGREGADOR
    return float(share_balcao) >= float(limiar)


# --------------------------------------------------------------------------- #
# Validacao do schema                                                          #
# --------------------------------------------------------------------------- #
def _float(valor: Any, onde: str) -> float:
    if isinstance(valor, bool) or not isinstance(valor, (int, float)):
        raise CoeficientesInvalidos(f"{onde}: esperado número, veio {type(valor).__name__}")
    f = float(valor)
    if not math.isfinite(f):
        raise CoeficientesInvalidos(f"{onde}: número não finito")
    return f


def _texto(valor: Any, onde: str) -> str:
    if not isinstance(valor, str) or not valor.strip():
        raise CoeficientesInvalidos(f"{onde}: esperado texto não vazio")
    return valor.strip()


def _chaves_exatas(obj: Any, esperadas: frozenset[str], onde: str, opcionais=frozenset()) -> None:
    if not isinstance(obj, Mapping):
        raise CoeficientesInvalidos(f"{onde}: esperado objeto")
    faltando = sorted(esperadas - set(obj))
    sobrando = sorted(set(obj) - esperadas - set(opcionais))
    if faltando:
        raise CoeficientesInvalidos(f"{onde}: falta(m) {', '.join(faltando)}")
    if sobrando:
        raise CoeficientesInvalidos(f"{onde}: chave(s) desconhecida(s) {', '.join(sobrando)}")


def validar_coeficientes(dados: Any, sha256: str) -> CoeficientesV2:
    """Valida o dict do JSON (schema ESTRITO) e devolve os coeficientes prontos."""
    _chaves_exatas(dados, _CHAVES_TOPO, "coeficientes", _CHAVES_TOPO_OPCIONAIS)
    data = _texto(dados["data"], "data")
    if not _RE_DATA.match(data):
        raise CoeficientesInvalidos("data: formato AAAA-MM-DD")

    _chaves_exatas(dados["beta"], frozenset(ORDEM_X), "beta")
    beta = tuple(_float(dados["beta"][k], f"beta.{k}") for k in ORDEM_X)

    xtx = dados["xtx_inv"]
    n = len(ORDEM_X)
    if not isinstance(xtx, Sequence) or isinstance(xtx, str) or len(xtx) != n:
        raise CoeficientesInvalidos(f"xtx_inv: esperada matriz {n}x{n}")
    linhas: list[tuple[float, ...]] = []
    for i, linha in enumerate(xtx):
        if not isinstance(linha, Sequence) or isinstance(linha, str) or len(linha) != n:
            raise CoeficientesInvalidos(f"xtx_inv: linha {i} não tem {n} colunas")
        linhas.append(tuple(_float(v, f"xtx_inv[{i}]") for v in linha))
    for i in range(n):
        if linhas[i][i] <= 0:
            raise CoeficientesInvalidos("xtx_inv: diagonal tem de ser positiva")
        for j in range(i + 1, n):
            a, b = linhas[i][j], linhas[j][i]
            if abs(a - b) > _TOL_SIMETRIA * max(1.0, abs(a), abs(b)):
                raise CoeficientesInvalidos("xtx_inv: matriz não é simétrica")

    sigma = _float(dados["sigma"], "sigma")
    if sigma <= 0:
        raise CoeficientesInvalidos("sigma: tem de ser positivo")
    cal = _float(dados["cal_2026"], "cal_2026")

    _chaves_exatas(dados["envelope"], frozenset(COVARIAVEIS_ENVELOPE), "envelope")
    envelope: dict[str, tuple[float, float]] = {}
    for k in COVARIAVEIS_ENVELOPE:
        par = dados["envelope"][k]
        if not isinstance(par, Sequence) or isinstance(par, str) or len(par) != 2:
            raise CoeficientesInvalidos(f"envelope.{k}: esperado [mínimo, máximo]")
        lo, hi = _float(par[0], f"envelope.{k}"), _float(par[1], f"envelope.{k}")
        if lo > hi:
            raise CoeficientesInvalidos(f"envelope.{k}: mínimo maior que o máximo")
        envelope[k] = (lo, hi)

    _chaves_exatas(dados["faixa"], _CHAVES_FAIXA, "faixa")
    p10 = _float(dados["faixa"]["p10"], "faixa.p10")
    p90 = _float(dados["faixa"]["p90"], "faixa.p90")
    if not 0 < p10 <= 1:
        raise CoeficientesInvalidos("faixa.p10: multiplicador em (0, 1]")
    if p90 < 1:
        raise CoeficientesInvalidos("faixa.p90: multiplicador >= 1")
    provisoria = dados["faixa"]["provisoria"]
    if not isinstance(provisoria, bool):
        raise CoeficientesInvalidos("faixa.provisoria: esperado verdadeiro/falso")

    shas = dados["sha256_insumos"]
    if not isinstance(shas, Mapping) or not shas:
        raise CoeficientesInvalidos("sha256_insumos: esperado objeto com ao menos um arquivo")
    for nome, h in shas.items():
        if not isinstance(h, str) or not _RE_SHA.match(h):
            raise CoeficientesInvalidos(f"sha256_insumos.{nome}: esperado sha256 (64 hex)")

    aceitacao: list[dict[str, Any]] = []
    for i, item in enumerate(dados.get("aceitacao_turma_2026") or []):
        _chaves_exatas(item, _CHAVES_ACEITACAO, f"aceitacao_turma_2026[{i}]")
        reg: dict[str, Any] = {
            k: _float(item[k], f"aceitacao_turma_2026[{i}].{k}")
            for k in _CHAVES_ACEITACAO
            if k != "unidade"
        }
        if reg["studios"] not in (0.0, 1.0):
            raise CoeficientesInvalidos(f"aceitacao_turma_2026[{i}].studios: 0 ou 1")
        reg["unidade"] = _texto(item["unidade"], f"aceitacao_turma_2026[{i}].unidade")
        aceitacao.append(reg)

    return CoeficientesV2(
        versao=_texto(dados["versao"], "versao"),
        fonte=_texto(dados["fonte"], "fonte"),
        data=data,
        beta=beta,
        xtx_inv=tuple(linhas),
        sigma=sigma,
        cal_2026=cal,
        envelope=envelope,
        faixa_p10=p10,
        faixa_p90=p90,
        faixa_provisoria=provisoria,
        sha256_insumos={str(k): str(v) for k, v in shas.items()},
        sha256=str(sha256),
        aceitacao_turma_2026=tuple(aceitacao),
    )


# --------------------------------------------------------------------------- #
# Previsao                                                                     #
# --------------------------------------------------------------------------- #
def _ln_positivo(valor: float, nome: str) -> float:
    try:
        f = float(valor)
    except (TypeError, ValueError) as exc:
        raise EntradasInvalidas(f"{nome} inválido") from exc
    if not math.isfinite(f) or f <= 0:
        raise EntradasInvalidas(f"{nome} tem de ser positivo e finito para entrar no log")
    return math.log(f)


def prever_faturamento_v2(entradas: EntradasV2, coef: CoeficientesV2) -> PrevisaoV2:
    """Faturamento mensal maduro p10/p50/p90 e flags. Puro: nenhum I/O."""
    if entradas.studios not in (0, 1):
        raise EntradasInvalidas("studios é binário no modelo (0 ou 1)")
    dom = float(entradas.dom_c10)
    if not math.isfinite(dom) or dom <= 0:
        raise EntradasInvalidas("domicílios da isócrona têm de ser positivos")
    ln = {
        "ln_m2": _ln_positivo(entradas.m2, "m2"),
        "ln_renda_dom_c10": _ln_positivo(entradas.renda_dom_c10, "renda domiciliar"),
        "ln_pop_c10": _ln_positivo(entradas.pop_c10, "população"),
    }
    x = (1.0, ln["ln_m2"], ln["ln_renda_dom_c10"], ln["ln_pop_c10"], float(entradas.studios))
    eta = sum(b * xi for b, xi in zip(coef.beta, x, strict=True))
    p50 = math.exp(eta + coef.cal_2026)
    fora = tuple(
        k for k in COVARIAVEIS_ENVELOPE
        if not coef.envelope[k][0] <= ln[k] <= coef.envelope[k][1]
    )
    alavanca = sum(
        x[i] * coef.xtx_inv[i][j] * x[j] for i in range(len(x)) for j in range(len(x))
    )
    ep = coef.sigma * math.sqrt(max(0.0, 1.0 + alavanca))
    return PrevisaoV2(
        fat_p10=p50 * coef.faixa_p10,
        fat_p50=p50,
        fat_p90=p50 * coef.faixa_p90,
        ln_x=ln,
        flag_extrapolacao=bool(fora),
        fora_do_envelope=fora,
        faixa_provisoria=bool(coef.faixa_provisoria),
        ep_log=ep,
    )


@dataclass(frozen=True)
class ConversaoAlunos:
    fixo: float  # faturamento com 0 alunos (receita fixa de personal)
    r_aluno: float  # faturamento de cada aluno a mais, em regime pleno
    alunos_p10: float
    alunos_p50: float
    alunos_p90: float


def _alunos(fat: float, fixo: float, r_aluno: float) -> float:
    return max((float(fat) - fixo) / r_aluno, 1.0)


def converter_em_alunos(
    fat_p10: float, fat_p50: float, fat_p90: float, premissas: Any
) -> ConversaoAlunos:
    """Faturamento maduro -> alunos TOTAIS pelas premissas DA PROPRIA REQUISICAO.

    `FIXO = faturamento_maduro(0)` e `R_ALUNO = faturamento_maduro(1) - FIXO`: a mesma regua
    com que o motor dimensiona o regime pleno (estudios, ticket, split, anuidade,
    churn e inadimplencia incluidos — DEC-068). Como o faturamento do motor e' LINEAR em
    alunos, simular com `alunos_p50` devolve `fat_p50` (acima do piso de 1 aluno). Trocar o
    ticket depois da semente muda R_ALUNO e, portanto, os alunos: o FATURAMENTO previsto e'
    o que fica fixo (decisao declarada, critica A2).
    """
    fixo = float(premissas.faturamento_maduro(0.0))
    r_aluno = float(premissas.faturamento_maduro(1.0)) - fixo
    if not math.isfinite(r_aluno) or r_aluno <= 0:
        raise EntradasInvalidas("receita por aluno não positiva: premissas inconsistentes")
    return ConversaoAlunos(
        fixo=fixo,
        r_aluno=r_aluno,
        alunos_p10=_alunos(fat_p10, fixo, r_aluno),
        alunos_p50=_alunos(fat_p50, fixo, r_aluno),
        alunos_p90=_alunos(fat_p90, fixo, r_aluno),
    )


# --------------------------------------------------------------------------- #
# Token de procedencia (critica C5)                                            #
# --------------------------------------------------------------------------- #
# Casas decimais do PONTO no token: 5 casas = ~1,1 m no equador. Arredondado de forma
# declarada para que a mesma coordenada, ida e volta pelo JSON, gere o mesmo hash.
CASAS_PONTO_TOKEN = 5


def token_procedencia(
    entradas: EntradasV2,
    sha_coeficientes: str,
    fat_p50: float,
    *,
    lat: float,
    lng: float,
) -> str:
    """Hash do PONTO + entradas + sha dos coeficientes + p50.

    E' o que permite a Viabilidade, o PDF e a planilha carimbarem "demanda sugerida pela
    v2" SEM nova chamada externa: o cliente devolve as entradas da isocrona e o token, e o
    servidor recalcula o p50 a partir delas (conta pura) e confere o hash. Muda o m2, os
    estudios, o PONTO ou os coeficientes -> o token deixa de conferir. O ponto entra porque as
    entradas da isocrona vem do CLIENTE: sem ele, uma sugestao tirada em Londrina conferia
    numa requisicao em Manaus (achado da revisao de 2026-10-20). NAO e' assinatura: protege
    contra carimbo errado por acidente (sugestao velha), nao contra quem forje o hash de
    proposito — os usuarios sao operadores autenticados.
    """
    canon = {
        "lat": round(float(lat), CASAS_PONTO_TOKEN),
        "lng": round(float(lng), CASAS_PONTO_TOKEN),
        "m2": round(float(entradas.m2), 6),
        "studios": int(entradas.studios),
        "pop_c10": round(float(entradas.pop_c10), 6),
        "dom_c10": round(float(entradas.dom_c10), 6),
        "renda_pc_c10": round(float(entradas.renda_pc_c10), 6),
        "sha_coeficientes": str(sha_coeficientes),
        "fat_p50": round(float(fat_p50), 2),
    }
    bruto = json.dumps(canon, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "v2-" + hashlib.sha256(bruto).hexdigest()


__all__ = [
    "CASAS_PONTO_TOKEN",
    "COVARIAVEIS_ENVELOPE",
    "ORDEM_X",
    "CoeficientesInvalidos",
    "CoeficientesV2",
    "ConversaoAlunos",
    "EntradasInvalidas",
    "EntradasV2",
    "PrevisaoV2",
    "converter_em_alunos",
    "prever_faturamento_v2",
    "sem_agregador",
    "studios_binario",
    "token_procedencia",
    "validar_coeficientes",
]
