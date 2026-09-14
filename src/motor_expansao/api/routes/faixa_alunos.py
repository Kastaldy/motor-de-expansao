"""Rota ``GET /faixa-alunos`` — a faixa plausivel de alunos para uma metragem.

NAO E PREVISAO DE DEMANDA (DEC-009). A faixa sai da curva tamanho->densidade dos
comparaveis Ultra: dado o m2, quantos alunos unidades daquele tamanho ocupam. Ela nao
recebe lat/lng e nao sabe nada da praca — dois imoveis do mesmo tamanho em cidades
opostas recebem a mesma faixa.

Por que ela existe no contrato publico: `demanda` e campo OBRIGATORIO do cenario de
viabilidade, e e PREMISSA de quem pede. Sem esta rota, quem consome a API precisa cravar
um numero fixo — o mesmo para um imovel de 600 m2 e para um de 10.000 m2, que e' o pior
jeito de escolher. Com ela, o consumidor ancora a premissa no tamanho do imovel e declara
de onde tirou.

A resposta carrega `fonte`. Isso nao e' enfeite: sem o `base_calibracao_maduras.parquet` o
motor cai num fallback e a faixa MUDA DE SIGNIFICADO — mesma escala, outra populacao de
comparaveis. Sem o campo, essa degradacao chegaria ao consumidor invisivel, e ele ancoraria
uma decisao de investimento num numero que nao e' o que ele pensa que e'.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse

from motor_expansao.api.auth import resolver_consumidor
from motor_expansao.api.schemas import ErrorResponse, FaixaAlunosResponse
from motor_expansao.api.settings import Settings, get_settings
from motor_expansao.dimensionamento.payload_viabilidade import base_calibracao

router = APIRouter(tags=["analise"])

_ERR: dict[int | str, dict[str, Any]] = {
    401: {"model": ErrorResponse},
    422: {"model": ErrorResponse},
    500: {"model": ErrorResponse},
}


@router.get(
    "/faixa-alunos",
    response_model=FaixaAlunosResponse,
    responses=_ERR,
    summary="Faixa plausivel de alunos por metragem (NAO e previsao)",
)
def faixa_alunos(
    m2: float = Query(gt=0, description="Area util do imovel, em m2.", examples=[1500]),
    formato: str | None = Query(
        default=None,
        description="Restringe os comparaveis ao mesmo formato de operacao.",
    ),
    consumidor: str = Depends(resolver_consumidor),
    settings: Settings = Depends(get_settings),
) -> JSONResponse:
    from motor_expansao.dimensionamento.viabilidade_ponto import faixa_alunos_por_densidade

    base, fonte = base_calibracao(settings.staging_dir)
    if base is None:
        # Ausencia de base NAO e erro: e' resposta legitima, e a `fonte` diz o porque.
        # Devolver 500 aqui obrigaria o consumidor a tratar excecao para um caso que o
        # contrato preve; devolver zeros sem a fonte seria pior ainda — ele acharia que
        # a faixa e' estreita, e nao que ela nao existe.
        return JSONResponse(
            content=FaixaAlunosResponse(
                m2=m2, p10=None, p50=None, p90=None, n_comparaveis=0, fonte=fonte
            ).model_dump()
        )

    r = faixa_alunos_por_densidade(m2, base, formato=formato)
    return JSONResponse(
        content=FaixaAlunosResponse(
            m2=m2,
            p10=_num(r.get("faixa_alunos_p10")),
            p50=_num(r.get("faixa_alunos_p50")),
            p90=_num(r.get("faixa_alunos_p90")),
            n_comparaveis=int(r.get("n_comparaveis") or 0),
            fonte=fonte,
        ).model_dump()
    )


def _num(v: Any) -> float | None:
    """Arredonda para alunos inteiros, JSON-safe. Aluno e' unidade contavel: devolver
    `412,7 alunos` sugeriria uma precisao que a curva nao tem."""
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return None if f != f or f in (float("inf"), float("-inf")) else float(round(f))
