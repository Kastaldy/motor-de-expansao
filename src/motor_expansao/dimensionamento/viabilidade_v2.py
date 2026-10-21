"""Viabilidade v2 — a COLA entre o modelo puro, os coeficientes e o contrato (DEC-077).

- Carregador dos coeficientes (`v2_coeficientes.json`, exportado pelo Felipe): schema
  estrito; ausente ou invalido -> v2 INDISPONIVEL com motivo, nunca erro 500.
- A CHAVE UNICA de servidor (`MOTOR_VIABILIDADE_V2`, critica C4): desligada, a v2 some de
  todas as superficies — estado, sugestao, viabilidade, PDF e planilha.
- Os corpos de entrada (`DemandaV2In`, `DemandaV2Ref`) e as duas montagens: a SUGESTAO
  (rota `/api/demanda-v2`) e o bloco `demanda_v2` da Viabilidade, que confere o token de
  procedencia sem nova chamada externa (critica C5).

O carregador NAO memoiza ausencia nem falha (licao da DEC-046): a leitura e' cacheada pela
assinatura do arquivo (caminho, mtime, tamanho), entao o JSON que chegar depois vale sem
reiniciar, e o que for apagado deixa de valer.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
from collections.abc import Callable
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from motor_expansao.dimensionamento.demanda_v2 import (
    CASAS_PONTO_TOKEN,
    CoeficientesInvalidos,
    CoeficientesV2,
    EntradasInvalidas,
    EntradasV2,
    PrevisaoV2,
    converter_em_alunos,
    prever_faturamento_v2,
    studios_binario,
    token_procedencia,
    validar_coeficientes,
)

# Motivos (texto de usuario: acentuado).
MOTIVO_DESLIGADA = "A Viabilidade v2 está desligada neste servidor."
MOTIVO_SEM_COEFICIENTES = (
    "A Viabilidade v2 ainda não tem coeficientes instalados neste servidor "
    "(aguardando a exportação da ficha técnica)."
)
MOTIVO_COEFICIENTES_INVALIDOS = "Os coeficientes da Viabilidade v2 são inválidos: {erro}"
MOTIVO_SEM_ROTAS = (
    "A Viabilidade v2 precisa do cálculo de 10 min de carro, que não está configurado "
    "neste servidor."
)
MSG_TOKEN_NAO_CONFERE = (
    "A sugestão da Viabilidade v2 não confere com o ponto, a metragem, os estúdios ou os "
    "coeficientes atuais. Peça uma nova sugestão antes de calcular."
)

_DESLIGADA = frozenset({"0", "false", "nao", "não", "off", "no"})


class V2Indisponivel(RuntimeError):
    """A v2 nao pode responder agora. `str(exc)` e' o motivo ao usuario (-> 503)."""


class TokenV2Invalido(ValueError):
    """O token de procedencia nao confere (-> 422)."""


def caminho_coeficientes() -> Path:
    """Onde o JSON mora: ao lado deste modulo (lido a cada chamada; testes trocam)."""
    from motor_expansao.dimensionamento.config import V2_COEFICIENTES_ARQUIVO

    return Path(__file__).with_name(V2_COEFICIENTES_ARQUIVO)


def chave_ligada() -> bool:
    """A chave de servidor. Ausente = ligada; "0"/"false"/"nao"/"off" = desligada."""
    from motor_expansao.dimensionamento.config import V2_ENV_CHAVE

    bruto = (os.environ.get(V2_ENV_CHAVE) or "").strip().lower()
    return bruto not in _DESLIGADA


@lru_cache(maxsize=4)
def _ler_coeficientes(caminho: str, _mtime_ns: int, _tamanho: int) -> CoeficientesV2:
    """Le e valida. Excecao NAO e' memoizada pelo `lru_cache` (nem ausencia: quem chama
    so' chega aqui com o arquivo existente)."""
    bruto = Path(caminho).read_bytes()
    try:
        dados = json.loads(bruto.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CoeficientesInvalidos(f"JSON ilegível ({exc.__class__.__name__})") from exc
    return validar_coeficientes(dados, hashlib.sha256(bruto).hexdigest())


def carregar_coeficientes(caminho: Path | None = None) -> CoeficientesV2:
    """Coeficientes prontos, ou `V2Indisponivel` com o motivo. Respeita a chave."""
    if not chave_ligada():
        raise V2Indisponivel(MOTIVO_DESLIGADA)
    alvo = caminho or caminho_coeficientes()
    try:
        st = alvo.stat()
    except OSError as exc:
        raise V2Indisponivel(MOTIVO_SEM_COEFICIENTES) from exc
    try:
        return _ler_coeficientes(str(alvo), int(st.st_mtime_ns), int(st.st_size))
    except CoeficientesInvalidos as exc:
        raise V2Indisponivel(MOTIVO_COEFICIENTES_INVALIDOS.format(erro=exc)) from exc
    except OSError as exc:
        raise V2Indisponivel(MOTIVO_SEM_COEFICIENTES) from exc


def estado_v2(rotas_configuradas: bool, caminho: Path | None = None) -> dict[str, Any]:
    """O que a TELA consulta para decidir o modo da demanda. NUNCA levanta.

    Disponivel = chave ligada E coeficientes validos E servico de rotas configurado. O
    servico pode estar configurado e fora do ar: ai' a sugestao responde 503 com motivo e
    a tela cai no modo densidade, como aqui.
    """
    try:
        coef = carregar_coeficientes(caminho)
    except V2Indisponivel as exc:
        return {"disponivel": False, "motivo": str(exc), "versao": None, "sha256": None}
    base = {"versao": coef.versao, "sha256": coef.sha256}
    if not rotas_configuradas:
        return {"disponivel": False, "motivo": MOTIVO_SEM_ROTAS, **base}
    return {"disponivel": True, "motivo": None, **base, "faixa_provisoria": coef.faixa_provisoria}


def limpar_cache() -> None:
    _ler_coeficientes.cache_clear()


# --------------------------------------------------------------------------- #
# Contrato                                                                     #
# --------------------------------------------------------------------------- #
class _StudiosCoerentes(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)

    n_studios: int | None = Field(default=None, ge=0, le=3)
    tickets_studios: list[Annotated[float, Field(gt=0)]] | None = Field(default=None, max_length=3)

    @model_validator(mode="after")
    def _coerentes(self):  # type: ignore[no-untyped-def]
        if (
            self.tickets_studios is not None
            and self.n_studios is not None
            and len(self.tickets_studios) != self.n_studios
        ):
            raise ValueError(
                f"tickets_studios tem {len(self.tickets_studios)} item(ns), mas "
                f"n_studios = {self.n_studios}: informe um ticket por studio"
            )
        return self


class DemandaV2In(_StudiosCoerentes):
    """Corpo de `POST /api/demanda-v2`: o ponto, a metragem e as premissas que mudam a
    conversao faturamento -> alunos (ticket, mix, estudios). O resto das premissas e' o
    default do config, exatamente como na Viabilidade."""

    lat: float = Field(ge=-90, le=90)
    lng: float = Field(ge=-180, le=180)
    m2: float = Field(gt=0)
    ticket: float | None = Field(default=None, gt=0)
    share_balcao: float | None = Field(default=None, ge=0, le=1)


class DemandaV2Ref(BaseModel):
    """O que a Viabilidade/PDF/planilha recebem de volta da sugestao: o token e as
    entradas da isocrona. O servidor recalcula o p50 (conta pura) e confere o token."""

    model_config = ConfigDict(allow_inf_nan=False, extra="forbid")

    token: str = Field(min_length=10, max_length=80)
    pop_c10: float = Field(gt=0)
    dom_c10: float = Field(gt=0)
    renda_pc_c10: float = Field(gt=0)


def _premissas_da_sugestao(body: DemandaV2In) -> Any:
    """As `Premissas` pela MESMA traducao da Viabilidade (`premissas_do_body`)."""
    from motor_expansao.dimensionamento.payload_viabilidade import (
        ViabilidadeIn,
        premissas_do_body,
    )

    corpo = ViabilidadeIn(
        lat=body.lat,
        lng=body.lng,
        m2=body.m2,
        aluguel=0.0,
        demanda=1.0,
        ticket=body.ticket,
        share_balcao=body.share_balcao,
        n_studios=body.n_studios,
        tickets_studios=body.tickets_studios,
    )
    return premissas_do_body(corpo)


def _n(v: float, casas: int) -> float | None:
    f = float(v)
    return round(f, casas) if math.isfinite(f) else None


def _flags(prev: PrevisaoV2) -> dict[str, Any]:
    return {
        "flag_extrapolacao": bool(prev.flag_extrapolacao),
        "fora_do_envelope": list(prev.fora_do_envelope),
        "faixa_provisoria": bool(prev.faixa_provisoria),
    }


def _bloco(
    entradas: EntradasV2,
    coef: CoeficientesV2,
    premissas: Any,
    *,
    lat: float,
    lng: float,
) -> tuple[PrevisaoV2, dict[str, Any]]:
    prev = prever_faturamento_v2(entradas, coef)
    conv = converter_em_alunos(prev.fat_p10, prev.fat_p50, prev.fat_p90, premissas)
    bloco = {
        "faturamento": {
            "p10": _n(prev.fat_p10, 2),
            "p50": _n(prev.fat_p50, 2),
            "p90": _n(prev.fat_p90, 2),
        },
        "alunos": {
            "p10": _n(conv.alunos_p10, 1),
            "p50": _n(conv.alunos_p50, 1),
            "p90": _n(conv.alunos_p90, 1),
        },
        "conversao": {"fixo": _n(conv.fixo, 2), "r_aluno": _n(conv.r_aluno, 4)},
        # O ponto a que a sugestao pertence (o mesmo arredondamento do token).
        "ponto": {
            "lat": round(float(lat), CASAS_PONTO_TOKEN),
            "lng": round(float(lng), CASAS_PONTO_TOKEN),
        },
        "entradas": {
            "m2": _n(entradas.m2, 2),
            "studios": int(entradas.studios),
            "pop_c10": _n(entradas.pop_c10, 6),
            "dom_c10": _n(entradas.dom_c10, 6),
            "renda_pc_c10": _n(entradas.renda_pc_c10, 6),
            "renda_dom_c10": _n(entradas.renda_dom_c10, 2),
        },
        **_flags(prev),
        "diagnostico": {"ep_log": _n(prev.ep_log, 4)},
        "coeficientes": {"versao": coef.versao, "sha256": coef.sha256, "data": coef.data},
        "token": token_procedencia(entradas, coef.sha256, prev.fat_p50, lat=lat, lng=lng),
    }
    return prev, bloco


def montar_sugestao_v2(
    body: DemandaV2In,
    *,
    pop_c10: float,
    dom_c10: float,
    renda_pc_c10: float,
    coef: CoeficientesV2,
    extras: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Resposta da rota de sugestao (sem I/O: as entradas ja' vem agregadas)."""
    entradas = EntradasV2(
        m2=float(body.m2),
        studios=studios_binario(body.n_studios),
        pop_c10=float(pop_c10),
        dom_c10=float(dom_c10),
        renda_pc_c10=float(renda_pc_c10),
    )
    try:
        _prev, bloco = _bloco(
            entradas, coef, _premissas_da_sugestao(body), lat=body.lat, lng=body.lng
        )
    except EntradasInvalidas as exc:
        raise V2Indisponivel(f"A Viabilidade v2 não se aplica a este ponto: {exc}") from exc
    return {**bloco, **(extras or {})}


@dataclass(frozen=True)
class DemandaV2Conferida:
    bloco: dict[str, Any]
    demanda_fonte: str  # "modelo_v2" | "premissa_editada"


DEMANDA_FONTE_V2 = "modelo_v2"
DEMANDA_FONTE_EDITADA = "premissa_editada"
# A tela semeia a demanda pelo p50 ARREDONDADO ao aluno: meia unidade de folga.
_TOL_DEMANDA_SEMENTE = 0.5 + 1e-9


def conferir_demanda_v2(
    body: Any,
    premissas: Any,
    *,
    rampa_reta_forcada: bool,
    carregar: Callable[[], CoeficientesV2] = carregar_coeficientes,
) -> DemandaV2Conferida:
    """Bloco `demanda_v2` da Viabilidade em modo v2. SEM chamada externa.

    Recalcula o p50 das entradas devolvidas pelo cliente com os coeficientes de agora,
    NO PONTO DO CORPO (`body.lat`/`body.lng`, que entram no hash), confere o token (`TokenV2Invalido` se nao conferir) e classifica a demanda do corpo:
    igual ao p50 sugerido (ate' meio aluno) -> "modelo_v2"; diferente -> "premissa_editada".
    """
    coef = carregar()
    ref: DemandaV2Ref = body.demanda_v2
    entradas = EntradasV2(
        m2=float(body.m2),
        studios=studios_binario(getattr(premissas, "n_studios", 0)),
        pop_c10=float(ref.pop_c10),
        dom_c10=float(ref.dom_c10),
        renda_pc_c10=float(ref.renda_pc_c10),
    )
    try:
        # O ponto conferido e' o do CORPO: token tirado em outro ponto nao confere.
        _prev, bloco = _bloco(
            entradas, coef, premissas, lat=float(body.lat), lng=float(body.lng)
        )
    except EntradasInvalidas as exc:
        raise TokenV2Invalido(MSG_TOKEN_NAO_CONFERE) from exc
    if bloco["token"] != ref.token:
        raise TokenV2Invalido(MSG_TOKEN_NAO_CONFERE)
    sugerida = float(bloco["alunos"]["p50"] or 0.0)
    fonte = (
        DEMANDA_FONTE_V2
        if abs(float(body.demanda) - sugerida) <= _TOL_DEMANDA_SEMENTE
        else DEMANDA_FONTE_EDITADA
    )
    bloco["demanda_sugerida"] = bloco["alunos"]["p50"]
    bloco["demanda_usada"] = _n(float(body.demanda), 1)
    bloco["rampa_reta_forcada_sem_agregador"] = bool(rampa_reta_forcada)
    bloco["demanda_fonte"] = fonte
    return DemandaV2Conferida(bloco=bloco, demanda_fonte=fonte)


__all__ = [
    "DEMANDA_FONTE_EDITADA",
    "DEMANDA_FONTE_V2",
    "DemandaV2Conferida",
    "DemandaV2In",
    "DemandaV2Ref",
    "TokenV2Invalido",
    "V2Indisponivel",
    "caminho_coeficientes",
    "carregar_coeficientes",
    "chave_ligada",
    "conferir_demanda_v2",
    "estado_v2",
    "limpar_cache",
    "montar_sugestao_v2",
]
