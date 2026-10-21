import { DENSIDADE_BANDS, RENDA_DOMICILIAR_SETOR_BANDS } from './colors'

/* Mapa de calor de setor censitário: as regras puras das duas chaves (densidade e
   renda) e da legenda delas, num lugar só para serem testadas — o vitest roda em node
   e não monta a tela.

   AO LIGAR O CALOR, AS CORES DOS HEXÁGONOS DESLIGAM (pedido do Vinicius, 2026-10-20).
   O polígono de setor pousa por cima do hexágono com alfa 150 de 255: com as duas
   coropletas acesas, a cor que o operador vê é a MISTURA das duas réguas, e nenhuma
   legenda traduz uma mistura. Desligar o calor NÃO religa as cores sozinho ("até que
   seja ligada de novo") — o operador religa pela própria chave. Trocar densidade por
   renda também é ligar um calor, então desliga de novo.

   E O CONTRÁRIO TAMBÉM (pedido do Vinicius, 2026-10-20): religar as cores dos
   hexágonos desliga o calor. As duas coropletas passam a ser EXCLUSIVAS nos dois
   sentidos, então a mistura nunca chega à tela. Desligar as cores não liga calor nenhum. */

export type ModoCalor = 'densidade' | 'renda'

export interface ChavesCalor {
  calor: ModoCalor | null
  coresHex: boolean
}

/** O que acontece ao clicar na chave de um modo de calor. */
export function alternarCalor(estado: ChavesCalor, modo: ModoCalor): ChavesCalor {
  if (estado.calor === modo) return { calor: null, coresHex: estado.coresHex }
  return { calor: modo, coresHex: false }
}

/** O que acontece ao clicar na chave "Cores dos hexágonos". */
export function alternarCoresHex(estado: ChavesCalor): ChavesCalor {
  if (estado.coresHex) return { calor: estado.calor, coresHex: false }
  return { calor: null, coresHex: true }
}

export interface FaixaLegendaCalor {
  cor: string
  rotulo: string
}

export interface LegendaCalor {
  titulo: string
  unidade: string
  faixas: FaixaLegendaCalor[]
}

/** O setor sem leitura (densidade ou renda nula) — o MESMO cinza do `HexMap`. */
export const SEM_LEITURA_CALOR: FaixaLegendaCalor = {
  cor: 'rgba(120,120,140,.24)',
  rotulo: 'sem dado',
}

/* O swatch usa o alfa do mapa (150/255), e não a cor cheia: no mapa a faixa clara da
   densidade é quase branca sobre o basemap, e um swatch opaco prometeria uma cor que
   o operador não encontra. */
function rgba([r, g, b, a]: readonly number[]): string {
  return `rgba(${r},${g},${b},${+(a / 255).toFixed(2)})`
}

/** Título, unidade e faixas da legenda de cada modo — os rótulos são os das réguas. */
export function legendaDoCalor(modo: ModoCalor): LegendaCalor {
  const faixas = modo === 'densidade' ? DENSIDADE_BANDS : RENDA_DOMICILIAR_SETOR_BANDS
  return {
    // Desde a E1 o servidor manda a renda média DOMICILIAR do setor (a mesma do card do
    // Relatório Pontual), e as faixas são as domiciliares: o título e a unidade dizem isso,
    // senão "R$ 14.000" leria como renda de uma pessoa.
    titulo: modo === 'densidade' ? 'Densidade demográfica' : 'Renda domiciliar',
    unidade: modo === 'densidade' ? 'hab/km²' : 'por domicílio/mês',
    faixas: faixas.map(([, rotulo, cor]) => ({ cor: rgba(cor), rotulo })),
  }
}
