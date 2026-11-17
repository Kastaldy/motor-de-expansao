"""Dominio do modelo de praca: onde ele NAO estima a demanda (DEC-086, emenda 1).

"Nao podemos projetar faturamento em um ponto que nao conseguimos estimar" (Felipe,
17/11/2026). Fora do dominio, nenhuma superficie projeta pelo modelo de praca: a aba de
imoveis mostra "sem projecao" (sem passar pela curva de densidade) e a sugestao do
simulador recusa o ponto -- a Viabilidade segue na faixa de comparaveis, com o aviso.

Duas regras, as duas MEDIDAS (nenhum limiar novo inventado):

1. AREA PEQUENA: a isocrona de 10 min abaixo de `V2_AREA_MIN_KM2`. O ponto ficou preso numa
   via interna (condominio logistico, parque industrial, aeroporto) e a populacao que o
   modelo ve e' artefato. Com `ln_pop_c10` de sinal negativo, o numero saia ALTO justamente
   nesses pontos (mediana de R$ 282 mil contra R$ 199 mil da lista, a 1.500 m2).
2. ZONA MORTA: a regua que a Viabilidade ja' usa (DEC-042, `flag_zona_morta` na captacao de
   `RAIO_CATCHMENT_KM`): poucos moradores em volta, fora do que as unidades do ajuste viram.
   Captacao indisponivel e' INDECIDIVEL e nunca veta (o contrato da DEC-042).

A area vem antes: com a isocrona quebrada, as entradas do modelo sao artefato, e esse e' o
motivo de nao estimar, mesmo que o ponto tambem seja zona morta. A mesma ordem nas duas
superficies, senao o mesmo imovel daria dois motivos.

Puro: sem I/O, a nao ser `captacao`, que recebe os setores ja' carregados.
"""

from __future__ import annotations

import math
from typing import Any

from motor_expansao.dimensionamento.config import RAIO_CATCHMENT_KM, V2_AREA_MIN_KM2
from motor_expansao.dimensionamento.viabilidade_ponto import flag_zona_morta

# Tokens do motivo (identificadores: vao ao payload cru, nunca a tela).
MOTIVO_AREA_PEQUENA = "area_pequena"
MOTIVO_ZONA_MORTA = "zona_morta"
# So' na aba: o modelo nao rodou no ponto (sem via a 300 m, area grande demais, sem setor
# ou renda, coordenada fora da malha), o anuncio nao traz a area, ou o lote noturno ainda
# nao calculou o imovel.
MOTIVO_SEM_CALCULO = "sem_calculo"
MOTIVO_SEM_AREA = "sem_area"
MOTIVO_AGUARDANDO = "aguardando"

MOTIVOS = (
    MOTIVO_AREA_PEQUENA,
    MOTIVO_ZONA_MORTA,
    MOTIVO_SEM_CALCULO,
    MOTIVO_SEM_AREA,
    MOTIVO_AGUARDANDO,
)


def _finito(valor: Any) -> float | None:
    try:
        f = float(valor)
    except (TypeError, ValueError):
        return None
    return f if math.isfinite(f) else None


def area_pequena(area_km2: Any) -> bool:
    """A isocrona do ponto ficou abaixo do piso (`V2_AREA_MIN_KM2`)? Sem area -> False."""
    a = _finito(area_km2)
    return a is not None and a < V2_AREA_MIN_KM2


def zona_morta(pop_captacao: Any, renda_pc_captacao: Any) -> str | None:
    """O motivo cru da DEC-042 ("pop<5000", "renda<500" ou os dois) quando o ponto e' zona
    morta; `None` fora dela OU sem captacao -- indecidivel nunca veta."""
    zm = flag_zona_morta(
        {
            "pop_captacao": _finito(pop_captacao),
            "renda_per_capita_captacao": _finito(renda_pc_captacao),
        }
    )
    if zm["flag_zona_morta"] is True:
        return str(zm["motivo_zona_morta"])
    return None


def motivo_fora_do_dominio(
    *,
    area_km2: Any = None,
    pop_captacao: Any = None,
    renda_pc_captacao: Any = None,
) -> str | None:
    """`MOTIVO_AREA_PEQUENA`, `MOTIVO_ZONA_MORTA` ou `None` (dentro do dominio).

    Cada argumento ausente simplesmente nao conta: o simulador confere a area antes de
    carregar os setores, e a captacao depois.
    """
    if area_pequena(area_km2):
        return MOTIVO_AREA_PEQUENA
    if zona_morta(pop_captacao, renda_pc_captacao) is not None:
        return MOTIVO_ZONA_MORTA
    return None


def captacao(lat: float, lng: float, setores_df: Any) -> tuple[float | None, float | None]:
    """(populacao, renda per capita) da captacao de `RAIO_CATCHMENT_KM` -- o MESMO calculo da
    Viabilidade (`viabilidade_ponto`, DEC-042). Sem setores ou com a conta falhando ->
    (None, None): a captacao e' contexto e NUNCA levanta (indecidivel nao veta)."""
    if setores_df is None:
        return None, None
    try:
        from motor_expansao.dimensionamento.catchment_batch import calcular_catchment_unidade

        c = calcular_catchment_unidade(lat, lng, setores_df, raio_km=RAIO_CATCHMENT_KM)
    except Exception:  # noqa: BLE001 -- contexto (DEC-042): a falha vira "indecidivel"
        return None, None
    return _finito(c.get("pop_captacao")), _finito(c.get("renda_per_capita_captacao"))


def _zona_morta_legivel(pop_captacao: Any, renda_pc_captacao: Any) -> str:
    """A frase da zona morta pela MESMA traducao do PDF e da tela da Viabilidade."""
    bruto = zona_morta(pop_captacao, renda_pc_captacao)
    if bruto:
        try:
            from motor_expansao.dashboard.censo_report import _conclusao_motivo_zona_morta

            return _conclusao_motivo_zona_morta(bruto)
        except Exception:  # noqa: BLE001 -- sem traducao, a frase generica abaixo
            pass
    return "poucos moradores em volta"


def texto_sem_projecao(
    motivo: str,
    *,
    pop_captacao: Any = None,
    renda_pc_captacao: Any = None,
) -> str:
    """Frase da aba de imoveis para o imovel SEM projecao (texto para aprovacao do Felipe)."""
    if motivo == MOTIVO_AREA_PEQUENA:
        return (
            "Sem projeção: a área de 10 min de carro não pôde ser medida a partir do imóvel "
            "(ele fica numa via interna, como de condomínio ou área industrial)."
        )
    if motivo == MOTIVO_ZONA_MORTA:
        legivel = _zona_morta_legivel(pop_captacao, renda_pc_captacao)
        return f"Sem projeção: zona morta ({legivel})."
    if motivo == MOTIVO_SEM_AREA:
        return "Sem projeção: o anúncio não traz a área."
    if motivo == MOTIVO_AGUARDANDO:
        return "Sem projeção ainda: o cálculo deste imóvel roda na próxima madrugada."
    return "Sem projeção: o modelo de praça não pôde ser calculado para este ponto."


def mensagem_sugestao_recusada(
    motivo: str,
    *,
    pop_captacao: Any = None,
    renda_pc_captacao: Any = None,
) -> str:
    """Frase do simulador quando o modelo de praca recusa o ponto (400; texto para
    aprovacao do Felipe). A tela segue na faixa de comparaveis e mostra esta frase."""
    if motivo == MOTIVO_ZONA_MORTA:
        legivel = _zona_morta_legivel(pop_captacao, renda_pc_captacao)
        causa = f"zona morta ({legivel})"
    else:
        causa = (
            "a área de 10 min de carro não pôde ser medida a partir dele (o ponto fica "
            "numa via interna, como de condomínio ou área industrial)"
        )
    return f"O modelo de praça não estima a demanda deste ponto: {causa}. Informe a demanda."


__all__ = [
    "MOTIVOS",
    "MOTIVO_AGUARDANDO",
    "MOTIVO_AREA_PEQUENA",
    "MOTIVO_SEM_AREA",
    "MOTIVO_SEM_CALCULO",
    "MOTIVO_ZONA_MORTA",
    "area_pequena",
    "captacao",
    "mensagem_sugestao_recusada",
    "motivo_fora_do_dominio",
    "texto_sem_projecao",
    "zona_morta",
]
