"""Contrato financeiro do ponto — o `viabilidade_payload_v1` e seus insumos.

REGUA UNICA (FIN-VIAB-01). Este modulo nasceu de um MOVE de `web/server/app.py`: a
montagem do payload vivia dentro do piloto, e a API GeoEspacial (`src/motor_expansao/api/`)
nao tinha como cha-la sem importar uma app FastAPI inteira. Copiar teria recriado a
segunda regua que o FIN-VIAB-01 existe para matar — foi ela que fez o mesmo cenario sair
com payback 35 x 33 e aluguel-teto R$55,5 mil x R$105,8 mil. Agora ha UMA implementacao e
DOIS chamadores: o piloto (`/api/viabilidade`, `/api/relatorio/pontual`,
`/api/simulador/xlsx`) e a API publica.

O que mudou em relacao ao codigo movido, e por que:

- `staging_dir` e' PARAMETRO. Antes `_base_calibracao()` lia a constante `STAGING_DIR` do
  `app.py`; um modulo em `src/` que dependesse dela continuaria amarrado ao piloto.
- `setores_df` e' PARAMETRO. Antes a funcao chamava `_setores_para_catchment` do proprio
  `app.py`. Cada superficie carrega a malha do seu jeito (o piloto pela particao da UF, a
  API pelo `_resolver_e_carregar`) — mas passar e' OBRIGATORIO na pratica: sem malha,
  `flag_zona_morta` volta a sair `None` em 100% das chamadas e o gate E4 da Conclusao some
  em silencio, exatamente o defeito que a DEC-042 encontrou em producao.

GUARDRAIL que atravessa o modulo: `demanda` e' PREMISSA EXPLICITA do operador (DEC-009),
nunca derivada de lat/lng. READ-ONLY sobre o M1.
"""

from __future__ import annotations

import functools
import math
from pathlib import Path
from typing import Any

import pandas as pd
from pydantic import BaseModel, ConfigDict, Field


def num_json_safe(v: Any, casas: int = 0) -> float | None:
    """Converte para float JSON-safe (NaN/inf viram None).

    Era `_num` no `app.py`. Veio junto no move porque TODO numero do payload passa por
    aqui: deixar a copia la' e outra aqui seria a divergencia silenciosa em miniatura.
    """
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    if math.isnan(f) or math.isinf(f):
        return None
    return round(f, casas) if casas else round(f)


class ViabilidadeInputs(BaseModel):
    """Os inputs FINANCEIROS do cenario, sem a coordenada.

    Separado de `ViabilidadeIn` para a API GeoEspacial: la' a coordenada ja' vem no corpo
    da requisicao (ou do `maps_url`), e repetir `lat`/`lng` dentro do objeto de
    viabilidade abriria a porta para os dois discordarem. Aqui ficam os campos que sao
    do CENARIO; `ViabilidadeIn` acrescenta o ponto.
    """


    # allow_inf_nan=False (pentest Onda B #11): recusa NaN/Infinity em TODOS os floats.
    # Sem isso, `Infinity` passava no `Field(gt=0)` (inf > 0 e' True) e gerava DRE-lixo
    # exibido como valido numa tela de decisao de investimento; o 422 resultante sai
    # limpo pelo handler `_erro_de_validacao`.
    model_config = ConfigDict(allow_inf_nan=False)

    m2: float = Field(gt=0)
    aluguel: float = Field(ge=0)
    demanda: float = Field(gt=0, description="PREMISSA do operador — nunca prevista")
    ticket: float | None = None
    formato: str | None = None
    # Numero de studios extras (0..3): cada studio soma SIM_CUSTO_STUDIO (R$6.000/mes de
    # fopag) aos custos fixos. FIN-VIAB-01: ate aqui o campo era aceito e DESCARTADO —
    # o studio elevava o ticket no front e nao custava nada no DRE (receita fantasma).
    n_studios: int | None = Field(default=None, ge=0, le=3)
    # --- Investimento: Obra (CAPEX, equity) x Equipamentos (OPEX, financiado) ---
    # Obra: desembolso do franqueado (equity), parcelado sem juros (parcelas_obra,
    # default 4). E a base do ROIC e do fluxo acumulado (payback parte de -Obra).
    obra: float | None = Field(default=None, ge=0)
    parcelas_obra: int | None = Field(default=None, gt=0, le=12)
    # Taxa de franquia PARCELADA sem juros (decisao de Felipe, 2026-07-24; default 4).
    # Antes saia INTEIRA do caixa no M-4. As parcelas caem nos meses de CONTRATO 1..N
    # (M-4..M-1 com N=4), junto da obra. E SO timing de caixa: melhora TIR/VPL e nao
    # toca EBITDA, margem nem break-even. Mesma validacao de `parcelas_obra`.
    parcelas_franquia: int | None = Field(default=None, gt=0, le=12)
    # Equipamentos: financiado (prazo 36-60m + juros a.m.); a PMT entra ABAIXO do
    # EBITDA (nao e desembolso a vista) -> dilui no tempo e melhora o payback.
    equipamentos: float | None = Field(default=None, ge=0)
    prazo_equipamentos: int | None = Field(default=None, ge=1, le=60)
    juros_equipamentos_am: float | None = Field(default=None, ge=0, le=1)
    # --- LEGADO (compat): CAPEX unico + fracao/valor financiado ---
    # Preservados para nao quebrar chamadas antigas; usados so como fallback quando
    # obra/equipamentos nao vem preenchidos (ver `investimento_do_body()`).
    capex: float | None = Field(default=None, ge=0)
    capex_financiado_pct: float | None = Field(default=None, ge=0, le=1)
    capex_financiado_valor: float | None = Field(default=None, ge=0)
    juros_financiamento_am: float | None = Field(default=None, ge=0, le=1)
    capex_parcelas_meses: int | None = Field(default=None, gt=0)
    # Margem EBITDA-alvo (fracao). LEGADO: nao dirige mais o aluguel-teto (agora por
    # clusters % do faturamento); segue so alimentando `alunos_para_margem_alvo`.
    # None usa o default do motor (0.10).
    margem_alvo: float | None = Field(default=None, ge=0, le=1)
    # Carencia de aluguel: meses iniciais sem pagar aluguel (beneficio de rampa;
    # melhora payback/FCF, nao muda margem/breakeven de steady-state).
    carencia_aluguel_meses: int | None = Field(default=None, ge=0, le=60)
    # Meses de rampa de maturacao (Simulador E13; default do motor = 8). Controlavel
    # pelo operador; afeta a serie e o payback, nao a margem/breakeven de steady-state.
    rampa_meses: int | None = Field(default=None, ge=1, le=36)

    # --- Premissas explicitas (FIN-VIAB-01) ---------------------------------
    # Todas OPCIONAIS: None = default do config.py (fonte unica). Estavam escondidas
    # como literal no meio do codigo; agora o operador ve e pode sobrescrever.
    # Taxa de franquia: 160.000 por decisao de Felipe (a planilha diz 140.000), agora
    # EDITAVEL em vez de constante invisivel.
    taxa_franquia: float | None = Field(default=None, ge=0)
    deducoes_pct: float | None = Field(default=None, ge=0, le=1)
    reajuste_ticket_aa: float | None = Field(default=None, ge=0, le=1)
    reajuste_aluguel_aa: float | None = Field(default=None, ge=0, le=1)
    reajuste_custos_aa: float | None = Field(default=None, ge=0, le=1)
    # TAXA MINIMA DO NEGOCIO (a.a., fracao) — a UNICA taxa configuravel do modelo.
    # Default do config: 25% a.a. A taxa minima do SOCIO NAO entra aqui: ela e
    # DERIVADA dentro de `simular()` a partir desta, do custo da divida e da
    # alavancagem. Nao existe campo onde alguem possa digitar uma taxa de socio
    # abaixo do que o banco cobra — a incoerencia ficou impossivel por construcao.
    taxa_minima_negocio_aa: float | None = Field(default=None, ge=0, le=1)
    # ALIAS DEPRECIADO (1 versao) de `taxa_minima_negocio_aa`. Existe so para nao
    # quebrar consumidor que ainda manda o nome antigo; `taxa_minima_negocio_aa`
    # tem precedencia quando os dois vem preenchidos.
    taxa_desconto_aa: float | None = Field(default=None, ge=0, le=1)
    custo_pre_operacional_mes: float | None = Field(default=None, ge=0)
    valor_residual_mes_60: float | None = Field(default=None, ge=0)
    capex_renovacao: float | None = Field(default=None, ge=0)


class ViabilidadeIn(ViabilidadeInputs):
    """Cenario COMPLETO: os inputs financeiros mais o ponto. E o corpo que o piloto
    recebe em `/api/viabilidade` e `/api/simulador/xlsx` — shape inalterado."""

    lat: float = Field(ge=-90, le=90)
    lng: float = Field(ge=-180, le=180)


def investimento_do_body(body: ViabilidadeIn) -> dict[str, Any]:
    """Kwargs de investimento de `simular()` — o desmembramento REAL do desembolso.

    - OBRA: equity do franqueado, parcelada SEM juros ao longo de `parcelas_obra`
      (default 4, os meses M-4..M-1 de pre-abertura).
    - EQUIPAMENTOS: financiados (`prazo_equipamentos` meses a `juros_equipamentos_am`);
      a PMT (Price) sai do caixa mes a mes e a parcela de juros vai a DRE.
    - TAXA DE FRANQUIA: PARCELADA sem juros em `parcelas_franquia` (default 4), nos
      meses de contrato 1..N (M-4..M-1), junto da obra — antes saia inteira no M-4.
      Valor default do config (R$160 mil), sobrescrivivel pelo operador.

    Legado (`capex` + `capex_financiado_valor`/`_pct` + `juros_financiamento_am` +
    `capex_parcelas_meses`): a fracao financiada vira EQUIPAMENTOS, o resto vira OBRA.
    """
    from motor_expansao.dimensionamento.config import (
        SIM_CAPEX_DEFAULT,
        SIM_PARCELAS_FRANQUIA_DEFAULT,
        SIM_PARCELAS_OBRA_DEFAULT,
        SIM_TAXA_FRANQUIA,
    )

    obra = float(body.obra) if body.obra is not None else None
    equip = float(body.equipamentos) if body.equipamentos is not None else None
    if obra is None and equip is None:
        capex_total = float(body.capex) if body.capex is not None else float(SIM_CAPEX_DEFAULT)
        if body.capex_financiado_valor:
            equip = min(float(body.capex_financiado_valor), capex_total)
        elif body.capex_financiado_pct:
            equip = capex_total * float(body.capex_financiado_pct)
        else:
            equip = 0.0
        obra = capex_total - equip
    obra = float(obra or 0.0)
    equip = float(equip or 0.0)

    juros = body.juros_equipamentos_am
    if juros is None:
        juros = body.juros_financiamento_am
    franquia = SIM_TAXA_FRANQUIA if body.taxa_franquia is None else float(body.taxa_franquia)
    return {
        "obra": obra,
        "parcelas_obra": int(body.parcelas_obra or SIM_PARCELAS_OBRA_DEFAULT),
        "equipamentos": equip,
        # Sem prazo declarado, mantem o default historico de 36 meses; equipamento
        # zerado -> prazo 0 (o nucleo trata como nao-financiado).
        "prazo_equipamentos": (
            int(body.prazo_equipamentos or body.capex_parcelas_meses or 36) if equip > 0 else 0
        ),
        "juros_equipamentos_am": float(juros or 0.0),
        "taxa_franquia": float(franquia),
        "parcelas_franquia": int(body.parcelas_franquia or SIM_PARCELAS_FRANQUIA_DEFAULT),
    }


def premissas_do_body(body: ViabilidadeIn):  # -> simulador.Premissas
    """Traduz o corpo da requisicao em `Premissas` — a fonte unica de coeficientes.

    Tudo que o operador NAO informa fica com o default do `config.py`. Nenhum
    coeficiente financeiro nasce aqui.

    `n_studios` deixa de ser receita fantasma: cada studio soma SIM_CUSTO_STUDIO
    (R$6.000/mes de fopag) em `outros_fixos_mes`. Antes o campo era aceito e
    DESCARTADO — o studio elevava o ticket no front e nao custava nada no DRE.
    """
    from motor_expansao.dimensionamento.config import (
        SIM_CUSTO_STUDIO,
        SIM_MENSALIDADE_BALCAO,
        SIM_OUTROS_FIXOS_MES,
    )
    from motor_expansao.dimensionamento.simulador import Premissas

    n_studios = int(body.n_studios or 0)
    opcionais: dict[str, Any] = {
        "devolucoes_pct": body.deducoes_pct,
        "reajuste_ticket_aa": body.reajuste_ticket_aa,
        "reajuste_aluguel_aa": body.reajuste_aluguel_aa,
        "reajuste_custos_aa": body.reajuste_custos_aa,
        # `taxa_desconto_aa` e o nome ANTIGO do mesmo campo (alias depreciado por 1
        # versao); o novo tem precedencia. Do lado do motor existe UM campo so:
        # `taxa_minima_negocio_aa`. A taxa minima do SOCIO nao e configuravel — sai
        # derivada de Ke = Ku + (Ku - Kd) * D/E dentro de `simular()`.
        "taxa_minima_negocio_aa": (
            body.taxa_minima_negocio_aa
            if body.taxa_minima_negocio_aa is not None
            else body.taxa_desconto_aa
        ),
        "custo_pre_operacional_mes": body.custo_pre_operacional_mes,
        "valor_residual_mes_60": body.valor_residual_mes_60,
        "capex_renovacao": body.capex_renovacao,
        "maturacao_meses": body.rampa_meses,
        "carencia_aluguel_meses": body.carencia_aluguel_meses,
    }
    return Premissas(
        ticket_cheio=float(body.ticket or SIM_MENSALIDADE_BALCAO),
        aluguel_mes=float(body.aluguel),
        outros_fixos_mes=float(SIM_OUTROS_FIXOS_MES) + n_studios * float(SIM_CUSTO_STUDIO),
        **{k: v for k, v in opcionais.items() if v is not None},
    )


# Campos da linha da serie que NAO sao numero (nao passam pelo arredondamento).
_SERIE_NAO_NUMERICOS = ("mes", "mes_contrato", "fase")


def _linha_serie(linha: dict[str, Any]) -> dict[str, Any]:
    """Uma linha da serie do nucleo, JSON-safe (NaN/inf -> None). NAO recalcula nada."""
    out: dict[str, Any] = {
        "mes": int(linha["mes"]),
        "mes_contrato": int(linha["mes_contrato"]),
        "fase": str(linha["fase"]),
    }
    for chave, valor in linha.items():
        if chave not in _SERIE_NAO_NUMERICOS:
            out[chave] = num_json_safe(valor, 2)
    return out


def _grade_json(grade: pd.DataFrame | None) -> list[dict[str, Any]]:
    """Grade de sensibilidade em JSON-safe. `payback` pode vir `inf` (nunca se paga):
    `json.dumps(..., allow_nan=False)` do Starlette quebraria com Infinity."""
    if grade is None or not len(grade):
        return []
    return [
        {
            "alunos": num_json_safe(t.alunos),
            "aluguel": num_json_safe(t.aluguel, 2),
            "fator_aluguel": num_json_safe(t.fator_aluguel, 2),
            "margem_liq": num_json_safe(t.margem_liq, 4),
            "viavel": bool(t.viavel),
            "payback": num_json_safe(t.payback, 1),
        }
        for t in grade.itertuples(index=False)
    ]


VIABILIDADE_PAYLOAD_VERSAO = "viabilidade_payload_v1"


def _motivo_zona_morta_legivel(bruto: str | None) -> str | None:
    """Token cru de zona morta -> frase de usuario, pela MESMA tradução do PDF.

    `None` entra e sai como `None`: sem motivo nao ha frase, e a tela ja' tem o seu
    proprio texto de fallback para o caso de a flag existir sem motivo.
    """
    if not bruto:
        return None
    try:
        from motor_expansao.dashboard.censo_report import _conclusao_motivo_zona_morta

        return _conclusao_motivo_zona_morta(str(bruto))
    except Exception:  # noqa: BLE001 — sem traducao, a tela cai no seu fallback
        return None


def _pct_do_faturamento(valor: Any, faturamento: Any) -> float | None:
    """Fracao de uma linha da DRE sobre o faturamento bruto de steady-state.

    Existe no BACKEND por causa do FIN-VIAB-01: a tela nao divide numero
    financeiro, so renderiza o que o payload traz. `None` (o front omite o %)
    quando o faturamento e zero/ausente, o que evita divisao por zero.
    """
    fat = num_json_safe(faturamento, 2)
    v = num_json_safe(valor, 2)
    if v is None or not fat:
        return None
    return num_json_safe(v / fat, 4)


def montar_payload_viabilidade(
    body: ViabilidadeIn,
    *,
    staging_dir: Path | str,
    setores_df: pd.DataFrame | None = None,
) -> dict[str, Any]:
    """Monta o `viabilidade_payload_v1` a partir de UMA rodada do nucleo.

    CONTRATO (FIN-VIAB-01): este dict e a UNICA saida financeira do backend — a tela
    e o PDF consomem o MESMO objeto, sem recalcular. Antes existiam cinco series
    mensais e nove KPIs com implementacao dupla aqui dentro (payback do card 35 x 33
    do grafico, aluguel-teto R$55,5 mil x R$105,8 mil).

    Convencao de unidades: TODA taxa/percentual vai como FRACAO (margem 0,3873 =
    38,73%; retorno 0,4475; TIR 0,4221). Dinheiro em reais, alunos em alunos TOTAIS.
    Nenhum valor nao-finito sai daqui (payback infinito / TIR inexistente -> null).
    """
    from motor_expansao.dimensionamento.config import (
        SIM_MARGEM_VIAVEL_MIN,
        SIM_PAYBACK_VIAVEL_MAX,
    )
    from motor_expansao.dimensionamento.viabilidade_ponto import (
        analisar_viabilidade_ponto,
    )

    premissas = premissas_do_body(body)
    inv = investimento_do_body(body)
    base, fonte_base = base_calibracao(staging_dir)

    res = analisar_viabilidade_ponto(
        lat=body.lat,
        lng=body.lng,
        m2=body.m2,
        aluguel_pedido=body.aluguel,
        demanda_premissa=body.demanda,
        premissas=premissas,
        base_calibracao_df=base,
        # LIGA O CATCHMENT (DEC-042). Sem este argumento o motor pula o catchment e
        # `flag_zona_morta` sai SEMPRE `None` — foi o estado de producao ate' hoje, e
        # ele nao deixava nada quebrado: apagava em SILENCIO o aviso da tela de
        # Viabilidade E o gate E4 da Conclusao do PDF, que a DEC-030 declara como "o
        # unico gate da praca que REPROVA fora do so-estudo".
        #
        # `None` continua sendo resposta VALIDA (municipio sem malha materializada,
        # coordenada fora da malha do IBGE): a flag volta a `None` com motivo
        # `catchment_indisponivel`, exatamente como antes. O que muda e' que agora isso
        # e' a EXCECAO e nao a regra.
        setores_df=setores_df,
        formato=body.formato,
        **inv,
    )
    r = res.viabilidade
    serie = [_linha_serie(linha) for linha in r.serie_mensal]
    # 1o mes em que o aluguel de fato entra no caixa (LEITURA da serie — a carencia
    # conta a partir do M-4, entao o operador precisa ver o mes resultante).
    mes_inicio_aluguel = next((linha["mes"] for linha in serie if (linha["aluguel"] or 0) > 0), None)
    teto = res.aluguel_teto_faixas
    # Linha da serie a que a DRE de steady-state se refere (regime pleno). O motor ja
    # publica `deducoes` e `impostos` como COLUNAS dessa linha; ler daqui elimina as
    # duas ultimas subtracoes que montavam degrau de DRE dentro do backend.
    linha_steady = next(
        (linha for linha in serie if linha["mes"] == int(r.mes_referencia_steady)), {}
    )

    return {
        "versao": VIABILIDADE_PAYLOAD_VERSAO,
        "premissas": {
            "ticket_cheio": num_json_safe(premissas.ticket_cheio, 2),
            "ticket_agregador": num_json_safe(premissas.ticket_agregador, 2),
            "ticket_blended": num_json_safe(premissas.ticket_blended, 2),
            "ticket_agregador_fator": num_json_safe(premissas.ticket_agregador_fator, 4),
            "share_balcao": num_json_safe(premissas.share_balcao, 4),
            "folha_pct": num_json_safe(premissas.folha_pct, 4),
            # FOLHA FIXA DESDE O MES 1 (decisao de Felipe, 2026-07-24). `folha_pct`
            # nao e mais um percentual da receita DO MES: ele DIMENSIONA a folha pelo
            # faturamento MADURO (regime pleno, a precos do ano 1) e o valor resultante
            # e pago integralmente desde o mes 1 — a equipe existe antes dos alunos.
            # Consequencia: a folha e CUSTO FIXO (saiu de `fator_receita_para_ebitda`) e
            # os meses de rampa ficam mais pesados. Os tres campos abaixo vem do proprio
            # motor (`Premissas.folha_fixa_mes` / `.faturamento_maduro`); a tela LE, nao
            # multiplica percentual por faturamento.
            "folha_fixa_mes": num_json_safe(premissas.folha_fixa_mes(float(body.demanda)), 2),
            "folha_base_faturamento_maduro": num_json_safe(
                premissas.faturamento_maduro(float(body.demanda)), 2
            ),
            "folha_fixa_desde_mes_1": True,
            "folha_regime": "fixa_desde_mes_1_dimensionada_pelo_faturamento_maduro",
            "deducoes_pct": num_json_safe(premissas.devolucoes_pct, 4),
            "impostos_receita_pct": num_json_safe(premissas.impostos_receita_pct, 4),
            "custo_variavel_pct": num_json_safe(premissas.custo_variavel_pct, 4),
            "reajuste_ticket_aa": num_json_safe(premissas.reajuste_ticket_aa, 4),
            "reajuste_aluguel_aa": num_json_safe(premissas.reajuste_aluguel_aa, 4),
            "reajuste_custos_aa": num_json_safe(premissas.reajuste_custos_aa, 4),
            # TAXA MINIMA DO NEGOCIO (a.a.): a unica taxa configuravel. A do SOCIO nao
            # aparece aqui de proposito — ela e DERIVADA e viaja no bloco `retorno`
            # (`socio.taxa_minima_aa`), junto do custo da divida e da alavancagem que a
            # produzem. Expor as duas como premissa editavel era o que permitia digitar
            # uma taxa de socio menor que a do credor.
            "taxa_minima_negocio_aa": num_json_safe(premissas.taxa_minima_negocio_aa, 4),
            # ALIAS DEPRECIADO (1 versao) do campo acima — nome antigo, mesmo numero.
            "taxa_desconto_aa": num_json_safe(premissas.taxa_minima_negocio_aa, 4),
            # Reguas do veredito (`dre.flag_viavel`), servidas para a tela e o PDF
            # rotularem o criterio sem cravar o numero. Sao CONSTANTES da fonte unica
            # (`dimensionamento/config.py`), nao contas feitas aqui.
            "margem_viavel_min": num_json_safe(SIM_MARGEM_VIAVEL_MIN, 4),
            "payback_viavel_max": int(SIM_PAYBACK_VIAVEL_MAX),
            "carencia_aluguel_meses": int(premissas.carencia_aluguel_meses),
            "mes_inicio_aluguel": mes_inicio_aluguel,
            "custo_pre_operacional_mes": num_json_safe(premissas.custo_pre_operacional_mes, 2),
            "maturacao_meses": int(premissas.maturacao_meses),
            "horizonte_meses": int(premissas.horizonte_meses),
            # Anuidade (Simulador J10/J12): R$ por aluno de BALCAO que completa
            # `anuidade_mes_inicio` meses, cobrada 1x/ano e reconhecida pro-rata.
            # A elegibilidade sai do proprio churn ((1-churn)^12) — nem todo aluno
            # chega a 12 meses. Exposta aqui para o operador ver a linha, e nao um
            # faturamento maior sem causa visivel.
            "anuidade_valor": num_json_safe(premissas.anuidade_valor, 2),
            "anuidade_mes_inicio": int(premissas.anuidade_mes_inicio),
            "anuidade_apenas_balcao": bool(premissas.anuidade_apenas_balcao),
            "anuidade_elegivel_pct": num_json_safe(premissas.anuidade_elegivel_efetivo, 4),
            # Mes de operacao a que a DRE de steady-state se refere (regime pleno:
            # alunos maduros E anuidade ja em cobranca). LEIA daqui — nao recalcule.
            "mes_referencia_steady": int(r.mes_referencia_steady),
            "valor_residual_mes_60": num_json_safe(premissas.valor_residual_mes_60, 2),
            "capex_renovacao": num_json_safe(premissas.capex_renovacao, 2),
            "fonte_base_calibracao": fonte_base,
        },
        "dre": {
            "faturamento": num_json_safe(r.faturamento_mensal_steady, 2),
            # Parcela de anuidade dentro do faturamento acima (0 antes do mes de inicio).
            "receita_anuidade": num_json_safe(r.receita_anuidade_mensal, 2),
            # LEITURA da coluna `deducoes` da linha de steady (nao a subtracao
            # faturamento - receita_liquida): o degrau ja existe pronto no motor.
            "deducoes": linha_steady.get("deducoes"),
            # Niveis intermediarios servidos PRONTOS: sem eles o gerador de graficos
            # reconstruia os dois degraus do waterfall por subtracao — era a ultima
            # formula financeira viva fora do simulador.py.
            "receita_liquida": num_json_safe(r.receita_liquida, 2),
            "receita_pos_impostos": num_json_safe(r.receita_pos_impostos, 2),
            # Idem: coluna `impostos` da MESMA linha, nao receita_liquida - pos_impostos.
            "impostos": linha_steady.get("impostos"),
            "custos_op": num_json_safe(r.custos_op_mensal, 2),
            "custos_variaveis": num_json_safe(r.custos_variaveis_mensal, 2),
            "folha": num_json_safe(r.folha_mensal, 2),
            "custos_fixos": num_json_safe(r.custos_fixos_mensal, 2),
            "ebitda": num_json_safe(r.ebitda_mensal, 2),
            "margem": num_json_safe(r.margem_ebitda_pct, 4),
            "ir_csll": num_json_safe(r.ir_csll_mensal, 2),
            "despesa_financeira": num_json_safe(r.despesa_financeira_mensal, 2),
            "resultado_apos_ir": num_json_safe(r.resultado_apos_ir_mensal, 2),
            # FRACAO do faturamento bruto de steady da linha de RESULTADO APOS IR da
            # cascata. Servido aqui porque a tela nao faz conta financeira
            # (FIN-VIAB-01) — ela so renderiza. `None` quando o faturamento e zero
            # (cenario degenerado): a tela omite o % em vez de exibir infinito.
            # NAO existe campo irmao para o EBITDA: o percentual dele ja e' `margem`
            # (o motor define `margem_ebitda_pct = ebitda / faturamento`) e servir os
            # dois abria a porta para divergirem em silencio se a definicao mudasse.
            "resultado_apos_ir_pct_faturamento": _pct_do_faturamento(
                r.resultado_apos_ir_mensal, r.faturamento_mensal_steady
            ),
            "flag_viavel": bool(r.flag_viavel),
        },
        "investimento": {
            "obra": num_json_safe(inv["obra"], 2),
            "equipamentos": num_json_safe(inv["equipamentos"], 2),
            "capex_total": num_json_safe(r.capex_total, 2),
            "taxa_franquia": num_json_safe(r.taxa_franquia, 2),
            "investimento_total": num_json_safe(r.investimento_total, 2),
            "pmt": num_json_safe(r.pmt_mensal, 2),
            "juros_totais": num_json_safe(r.juros_totais, 2),
            "prazo_equipamentos": int(inv["prazo_equipamentos"]),
            "juros_equipamentos_am": num_json_safe(inv["juros_equipamentos_am"], 6),
            "parcelas_obra": int(inv["parcelas_obra"]),
            # Franquia PARCELADA sem juros: N parcelas iguais nos meses de contrato
            # 1..N (M-4..M-1 com N=4), junto da obra. A divisao abaixo e RENDER do
            # cronograma de desembolso (valor / n de parcelas sem juros), nao uma
            # formula financeira nova — nenhum coeficiente entra nela.
            "parcelas_franquia": int(inv["parcelas_franquia"]),
            "franquia_parcela": num_json_safe(
                inv["taxa_franquia"] / inv["parcelas_franquia"]
                if inv["taxa_franquia"] > 0 and inv["parcelas_franquia"] > 0
                else 0.0,
                2,
            ),
            # APORTE INICIAL (obra + taxa de franquia) = o dinheiro que o CONTRATO pede
            # do socio, e o denominador do retorno dele. VOCABULARIO: nao se chama mais
            # "equity aportado"; e "aporte inicial". A soma e dos DOIS campos que ja
            # estao neste mesmo bloco (nao ha coeficiente nem formula financeira aqui) e
            # reproduz literalmente o denominador que o nucleo usa em `simular()`.
            "aporte_inicial": num_json_safe(inv["obra"] + inv["taxa_franquia"], 2),
            # CHEQUE TOTAL: o pior ponto do caixa acumulado — quanto o investidor precisa
            # TER disponivel, nao quanto o contrato pede. No caso de referencia sao
            # R$1,14 mi no mes 5 contra R$760 mil de aporte (1,50x). E o numero que
            # decide se o negocio e FINANCIAVEL e nao existia em lugar nenhum do produto.
            # Vem PRONTO do nucleo (`cheque_total` / `mes_cheque_total`).
            "cheque_total": num_json_safe(r.cheque_total, 2),
            "mes_cheque_total": int(r.mes_cheque_total),
        },
        "retorno": {
            # ------------------------------------------------------------------
            # DUAS OTICAS, SEPARADAS E ROTULADAS — nunca no mesmo numero.
            #   `negocio` (FCFF): sem financiamento, CAPEX inteiro desembolsado. Mede o
            #       ATIVO. Descontado a taxa minima do NEGOCIO (premissa).
            #   `socio`   (FCFE): PMT inteira sai do caixa e so obra+franquia entram como
            #       aporte. Mede a ESTRUTURA. Descontado a taxa minima do SOCIO, que e
            #       DERIVADA (Ke = Ku + (Ku - Kd) * D/E) — o socio e subordinado ao
            #       banco, entao a taxa dele nao pode ser menor que a do credor.
            # Sem escudo fiscal no Lucro Presumido, WACC = taxa minima do negocio: a
            # divida so cria valor por ARBITRAGEM (tomar a 23,87% para um ativo que
            # rende 25%), nunca por beneficio tributario.
            # Rotulos de usuario: "do negocio" (era "desalavancado") e "do socio".
            # ------------------------------------------------------------------
            "negocio": {
                "tir_anual": num_json_safe(r.tir_negocio_anual, 4),
                "vpl": num_json_safe(r.vpl_negocio, 2),
                "taxa_minima_aa": num_json_safe(r.taxa_minima_negocio_aa, 4),
                "retorno_anual": num_json_safe(r.retorno_anual_desalavancado, 4),
            },
            "socio": {
                "tir_anual": num_json_safe(r.tir_socio_anual, 4),
                "vpl": num_json_safe(r.vpl_socio, 2),
                "taxa_minima_aa": num_json_safe(r.taxa_minima_socio_aa, 4),
                "retorno_anual": num_json_safe(r.retorno_anual_equity, 4),
            },
            "custo_divida_aa": num_json_safe(r.custo_divida_aa, 4),
            "alavancagem_divida_sobre_aporte": num_json_safe(r.alavancagem_divida_sobre_aporte, 4),
            # VPL da divida descontado a taxa minima do NEGOCIO = a ARBITRAGEM. Vem do
            # nucleo quando ele o publica; `null` enquanto nao publicar — este backend
            # NAO calcula formula financeira para preencher o campo.
            "vpl_divida_arbitragem": num_json_safe(getattr(r, "vpl_divida_arbitragem", None), 2),
            # GUARDA 1: se a divida custa mais que a taxa minima do negocio, a
            # alavancagem DESTROI valor em vez de criar (sem escudo fiscal nao ha o que
            # compensar). Aviso visivel na tela.
            "alerta_divida_acima_da_taxa_negocio": bool(
                r.alerta_divida_acima_da_taxa_negocio
            ),
            # GUARDA 2 (diagnostico, NAO tolerancia): VPL do socio @taxa do socio menos
            # VPL do negocio @taxa do negocio. Os dois NAO coincidem de proposito — a
            # taxa do socio usa a alavancagem INICIAL enquanto o saldo devedor cai a
            # zero ao longo do contrato. -R$36.073,94 no caso de referencia.
            "vpl_identidade_residuo": num_json_safe(r.vpl_identidade_residuo, 2),
            # --- CHAVES PLANAS: ALIAS HISTORICOS (o PDF e o XLSX leem delas) ---------
            # `tir_anual` e `vpl` sao o par do SOCIO (e o que o nucleo mantem como alias
            # em `ViabilidadeResult`). `retorno_anual_desalavancado` e o retorno DO
            # NEGOCIO e `retorno_anual_equity` o DO SOCIO — os nomes ficam pelo contrato
            # antigo; os rotulos de usuario sao "do negocio" e "do socio".
            "otica": "desalavancada",  # LEGADO: `censo_report` escolhe o rotulo do card
            # por `otica.startswith("desalav")`; mudar o VALOR aqui trocaria o card do
            # PDF para "ROIC anual". O rotulo novo e responsabilidade do consumidor.
            "retorno_anual_desalavancado": num_json_safe(r.retorno_anual_desalavancado, 4),
            "retorno_anual_equity": num_json_safe(r.retorno_anual_equity, 4),
            "tir_anual": num_json_safe(r.tir_anual, 4),
            "vpl": num_json_safe(r.vpl, 2),
            "payback": num_json_safe(r.payback_meses, 1),
        },
        "break_even": {
            "unidade": "alunos_totais",
            "ebitda": num_json_safe(res.alunos_breakeven, 1),
            "caixa": num_json_safe(res.alunos_breakeven_caixa, 1),
        },
        "aluguel_teto": {
            "base": "faturamento_bruto",
            "ideal": num_json_safe(teto.get("ideal"), 2),
            "teto": num_json_safe(teto.get("teto"), 2),
            "excecao": num_json_safe(teto.get("excecao"), 2),
            "canonico": num_json_safe(res.aluguel_teto_calculado, 2),
            # Teto sobre o p10 da faixa (nao circular). null sem base de comparaveis.
            "teto_p10": num_json_safe(res.aluguel_teto_p10, 2),
        },
        "faixa_alunos": {
            "p10": num_json_safe(res.faixa_alunos_p10),
            "p50": num_json_safe(res.faixa_alunos_p50),
            "p90": num_json_safe(res.faixa_alunos_p90),
            "n_comparaveis": res.n_comparaveis,
        },
        "serie_mensal": serie,
        "mes_caixa_operacional_positivo": r.mes_caixa_operacional_positivo,
        "acumulado_mes_final": num_json_safe(r.acumulado_mes_final, 2),
        "demanda_premissa": num_json_safe(res.demanda_premissa, 1),
        "demanda_fonte": res.demanda_fonte,
        "split": {
            "balcao": num_json_safe(res.alunos_balcao_premissa, 1),
            "agregadores": num_json_safe(res.alunos_agregadores_premissa, 1),
        },
        "flag_zona_morta": res.flag_zona_morta,
        # BRUTO (`pop<5000; renda<500`): identificador, nao texto de usuario. Fica no
        # contrato porque o PDF e os consumidores historicos ja' o leem e o traduzem.
        "motivo_zona_morta": res.motivo_zona_morta,
        # TRADUZIDO, para a TELA. Enquanto a flag era sempre `None` (ver DEC-042) o ramo
        # que exibe o motivo nunca renderizava, e ninguem reparou que a tela mostraria o
        # TOKEN CRU ao operador — contra o §2 do CLAUDE.md, que manda texto de usuario ser
        # portugues acentuado e identificador nunca aparecer. Ligar o gate expunha isso.
        #
        # Traduzido AQUI e nao no front de proposito: `_conclusao_motivo_zona_morta` ja' e'
        # a traducao do PDF, e ela deriva dos limiares. Uma segunda tabela no TypeScript
        # seria uma segunda regua para a mesma coisa — o defeito que esta sessao passou o
        # dia corrigindo.
        "motivo_zona_morta_texto": _motivo_zona_morta_legivel(res.motivo_zona_morta),
        "flag_fora_envelope": bool(res.flag_fora_envelope),
        "grade": _grade_json(res.grade_sensibilidade),
        # Sugestao de ajuste quando o payback estoura (LEITURA da serie; nao e KPI).
        "melhoria_payback": _melhoria_payback(
            serie, num_json_safe(r.payback_meses, 1), float(body.aluguel), float(r.investimento_total)
        ),
    }


def _melhoria_payback(
    serie: list[dict[str, Any]],
    payback: float | None,
    aluguel: float,
    capex_efetivo: float,
    alvo_meses: int = 36,
    gatilho_meses: int = 40,
) -> dict[str, Any] | None:
    """Quando o payback estoura (> gatilho), estima quanto cortar de CAPEX OU de aluguel
    para o payback cair para ~alvo_meses. Estimativa de 1a ordem LIDA da serie do nucleo
    (`fcf_acumulado` no mes-alvo): o CAPEX desloca a curva 1:1; cada R$1/mes a menos de
    aluguel soma ~alvo_meses ao caixa no mes-alvo. NAO e KPI e nao recalcula o motor —
    e uma sugestao de ajuste. None quando nao ha o que sugerir.

    payback None (nunca vira dentro do horizonte) e o PIOR caso -> tambem gera sugestao."""
    if payback is not None and payback <= gatilho_meses:
        return None
    row = next((r for r in serie if r.get("mes") == alvo_meses), None)
    if row is None or row.get("fcf_acumulado") is None or float(row["fcf_acumulado"]) >= 0:
        return None
    deficit = -float(row["fcf_acumulado"])  # caixa que ainda falta no mes-alvo
    reduzir_capex = (
        float(round(deficit)) if (capex_efetivo > 0 and deficit < capex_efetivo) else None
    )
    red_aluguel = deficit / alvo_meses
    reduzir_aluguel = float(round(red_aluguel)) if (aluguel > 0 and red_aluguel < aluguel) else None
    return {
        "alvo_meses": alvo_meses,
        "reduzir_capex": reduzir_capex,
        "reduzir_aluguel": reduzir_aluguel,
    }


# Bases da curva tamanho->densidade, em ordem de preferencia: (arquivo, rotulo da fonte).
# O rotulo VAI NO PAYLOAD (`premissas.fonte_base_calibracao`) porque a degradacao era
# SILENCIOSA: caindo no fallback (ou sem base nenhuma), a faixa p10/p50/p90 mudava de
# significado sem nenhum sinal na tela nem no PDF.
_BASES_CALIBRACAO = (
    ("base_calibracao_maduras.parquet", "base_calibracao_maduras.parquet (oficial)"),
    ("unidades_ultra_performance_hex.parquet", "unidades_ultra_performance_hex.parquet (fallback)"),
)
FONTE_BASE_INDISPONIVEL = "indisponivel (faixa de alunos nao calculada)"


@functools.lru_cache(maxsize=4)
def base_calibracao(staging_dir: Path | str) -> tuple[pd.DataFrame | None, str]:
    """Base de comparaveis da curva tamanho->densidade + QUAL arquivo a alimentou.

    A curva exige a coluna `alunos_por_m2`. `base_calibracao_multirede` NAO a tem
    (traz `alunos_reais` + `metragem` crus), entao entregar aquele parquet faz a
    faixa voltar vazia com n_comparaveis=0 — foi o bug da primeira versao.
    Prioriza as bases que ja trazem a coluna e valida antes de devolver.
    """
    for nome, rotulo in _BASES_CALIBRACAO:
        caminho = Path(staging_dir) / nome
        if not caminho.exists():
            continue
        try:
            df = pd.read_parquet(caminho)
        except Exception:  # noqa: BLE001 — base opcional, degrada gracioso
            continue
        if "alunos_por_m2" in df.columns and len(df):
            return df, rotulo
    return None, FONTE_BASE_INDISPONIVEL


def montar_payload_para_pdf(
    body: ViabilidadeIn,
    *,
    staging_dir: Path | str,
    setores_df: pd.DataFrame | None = None,
) -> dict[str, Any] | None:
    """Payload do slide de viabilidade do PDF — o MESMO `viabilidade_payload_v1` da tela.

    FIN-VIAB-01: o PDF NAO re-roda o motor nem realinha KPI nenhum. Antes esta funcao
    chamava o motor de novo e depois sobrescrevia payback/ROIC "para bater com a tela";
    era exatamente essa segunda passagem que fazia o mesmo cenario sair com payback
    35 x 33 e aluguel-teto R$55,5 mil x R$105,8 mil.

    O achatamento v1 -> chaves planas do slide (e os 4 PNGs) vem de
    `viabilidade_charts.montar_payload_pdf_viabilidade`, a ponte UNICA do PDF. Havia aqui
    uma segunda copia desse mapeamento e ela ja tinha regredido em dois pontos: a chave
    plana `aluguel_teto` (float) sobrescrevia a secao v1 homonima (dict) e sumia com a
    linha "ideal | teto | excecao"; e o waterfall reencontrava a linha de steady na serie
    por `maturacao_meses` em vez de ler o `dre` do payload, entao grafico e card do MESMO
    slide podiam sair de meses diferentes.

    Devolve o payload v1 + as chaves PLANAS que o slide legado consome + `graficos`.
    `None` em qualquer falha -> o PDF cai no payload so-numeros (`viabilidade_json`).
    """
    from motor_expansao.dashboard.viabilidade_charts import montar_payload_pdf_viabilidade

    try:
        payload = montar_payload_viabilidade(
            body, staging_dir=staging_dir, setores_df=setores_df
        )
    except Exception:  # noqa: BLE001 — o PDF nunca cai por causa da viabilidade
        return None

    saida: dict[str, Any] = dict(payload)
    try:
        saida.update(montar_payload_pdf_viabilidade(payload) or {})
    except Exception:  # noqa: BLE001 — sem graficos o slide sai so com os numeros
        saida.update(montar_payload_pdf_viabilidade(payload, incluir_graficos=False) or {})
    # `flag_viavel` nao faz parte do contrato v1 fechado; o slide le do `dre` quando existe.
    saida["flag_viavel"] = payload["dre"].get("flag_viavel")
    return saida
