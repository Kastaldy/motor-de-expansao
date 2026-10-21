/* ---------------------------------------------------------------------------
   Viabilidade v2 na tela (DEC-077 ampliada): quando o SERVIDOR diz que a v2 está
   disponível, a demanda é semeada pelo p50 dela (editável), a faixa p10–p90 aparece
   marcada como provisória e o pedido leva o token de procedência.

   A tela não decide nada sozinha (crítica C4): quem liga e desliga é o servidor
   (`/api/demanda-v2/estado`, chave `MOTOR_VIABILIDADE_V2`). Indisponível -> o modo
   densidade de sempre, com o motivo discreto. Módulo PURO: a regra mora aqui, onde o
   Vitest alcança sem servidor.
   --------------------------------------------------------------------------- */

import type { DemandaV2In, DemandaV2Out, EstadoDemandaV2, ViabilidadeIn } from './types'

/** A v2 vale para esta tela? Só com o servidor dizendo `disponivel: true`. */
export function v2Disponivel(estado: EstadoDemandaV2 | null | undefined): boolean {
  return estado?.disponivel === true
}

/** Motivo discreto da indisponibilidade (ou `null` quando disponível/sem resposta). */
export function motivoV2(
  estado: EstadoDemandaV2 | null | undefined,
  erroSugestao: string | null,
): string | null {
  if (estado && !estado.disponivel) return estado.motivo ?? 'A Viabilidade v2 está indisponível.'
  return erroSugestao
}

/** Corpo da sugestão: o ponto, a metragem e as premissas que mudam a conversão. */
export function corpoSugestaoV2(p: {
  lat: number
  lng: number
  m2: number
  ticket?: number
  shareBalcao?: number
  ticketsStudios: number[]
}): DemandaV2In {
  return {
    lat: p.lat,
    lng: p.lng,
    m2: p.m2,
    ticket: p.ticket,
    share_balcao: p.shareBalcao,
    n_studios: p.ticketsStudios.length,
    tickets_studios: p.ticketsStudios,
  }
}

/** O cenário que a sugestão precisa casar: o PONTO, a metragem e os estúdios. */
export interface CenarioV2 {
  lat: number | null | undefined
  lng: number | null | undefined
  m2: number
  nStudios: number
}

/** Casas do ponto no token (`CASAS_PONTO_TOKEN` do servidor): 5 casas, ~1,1 m. */
const CASAS_PONTO = 5

/* Compara ARREDONDANDO como o servidor (5 casas), e não por tolerância: dois pontos a menos
   de 1e-5 um do outro, cada um de um lado da fronteira de arredondamento, passavam aqui e
   levavam 422 lá. `toFixed` arredonda o valor binário exato, como o `round` do Python. */
export function mesmoPonto(a: number | null | undefined, b: number | null | undefined): boolean {
  if (a == null || b == null || !Number.isFinite(a) || !Number.isFinite(b)) return false
  return a.toFixed(CASAS_PONTO) === b.toFixed(CASAS_PONTO)
}

/**
 * A sugestão ainda vale para o cenário? O token amarra o PONTO, a metragem e a PRESENÇA
 * de estúdio (binária no modelo). Mudou qualquer um, a sugestão é velha e o pedido NÃO
 * pode carimbar "sugerida pela v2" (o servidor recusaria com 422). O ponto entra porque
 * a tela não é remontada ao trocar de ponto: sem ele, a sugestão de Londrina seguia
 * valendo em Manaus até a nova chegar.
 */
export function sugestaoValePara(
  sug: DemandaV2Out | null | undefined,
  cenario: CenarioV2,
): sug is DemandaV2Out {
  if (!sug || !sug.ponto) return false
  return (
    mesmoPonto(sug.ponto.lat, cenario.lat) &&
    mesmoPonto(sug.ponto.lng, cenario.lng) &&
    sug.entradas.m2 === cenario.m2 &&
    sug.entradas.studios === (cenario.nStudios > 0 ? 1 : 0)
  )
}

/** Demanda semeada pela v2: o p50 em alunos, arredondado. `null` sem número válido. */
export function sementeDaDemandaV2(sug: DemandaV2Out | null | undefined): number | null {
  const p50 = sug?.alunos?.p50
  if (p50 == null || !Number.isFinite(p50) || p50 <= 0) return null
  return Math.round(p50)
}

/** Campos do pedido da Viabilidade: `v2` + token quando a sugestão vale; nada senão. */
export function camposDeV2(
  sug: DemandaV2Out | null | undefined,
  cenario: CenarioV2,
): Pick<ViabilidadeIn, 'modelo_demanda' | 'demanda_v2'> {
  if (!sugestaoValePara(sug, cenario)) return {}
  const { pop_c10, dom_c10, renda_pc_c10 } = sug.entradas
  if (pop_c10 == null || dom_c10 == null || renda_pc_c10 == null) return {}
  return {
    modelo_demanda: 'v2',
    demanda_v2: { token: sug.token, pop_c10, dom_c10, renda_pc_c10 },
  }
}

/** Avisos da sugestão, em português, para a tela (a faixa provisória vem sempre). */
export function avisosV2(sug: DemandaV2Out): string[] {
  const avisos: string[] = []
  if (sug.faixa_provisoria) {
    avisos.push('Faixa provisória: no teste fora da amostra ela cobriu 72% das unidades.')
  }
  if (sug.flag_extrapolacao) {
    avisos.push(
      'Este ponto está fora do intervalo das unidades usadas no ajuste (extrapolação).',
    )
  }
  if (sug.rampa_reta_forcada_sem_agregador) {
    avisos.push('Sem agregador: a rampa usada é a reta.')
  }
  return avisos
}
