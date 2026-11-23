/**
 * O sino do piloto (DEC-090): os avisos dos pedidos dos masters, em texto de tela.
 *
 * O servidor manda o EVENTO da trilha (`estudo.solicitado`, `imovel.solicitado`) com quem fez,
 * quando e os metadados; aqui ele vira a linha que o sino mostra. Puro e testável no vitest
 * (ambiente `node`), no padrão de `lib/masters.ts`: o componente `SinoDeAvisos` só desenha.
 */

import type { MePayload } from './types'

/** Os avisos que existem (o mesmo conjunto do servidor, `db/avisos.py`). */
export type AvisoTipo = 'estudo_master' | 'imovel_master'

/** Um aviso do sino: um evento da trilha, com o master por extenso (`masters`). */
export interface ItemDeAviso {
  id: number
  aviso: AvisoTipo | null
  /** Quando o pedido foi feito (ISO 8601, com fuso). */
  quando: string | null
  /** O nome de quem pediu (o cadastro do login); `null` = sem nome. */
  quem: string | null
  dados: Record<string, unknown>
  /** O master de quem pediu, por extenso ("DF/GO"). */
  masters?: string[]
  /** Já estava visto quando o sino foi aberto pela última vez. */
  lido: boolean
}

/** `GET /api/avisos`. */
export interface SinoPayload {
  avisos: AvisoTipo[]
  itens: ItemDeAviso[]
  nao_lidos: number
  ultimo_lido: number
}

/** De quanto em quanto tempo o sino pergunta se chegou aviso novo (1 minuto: não precisa de
 *  tempo real, e a consulta é barata). */
export const INTERVALO_DO_SINO_MS = 60_000

const AVISOS_CONHECIDOS: readonly AvisoTipo[] = ['estudo_master', 'imovel_master']

/** Os avisos que chegam a esta pessoa (`avisos` do `/api/me`), defensivo contra payload velho
 *  ou estranho: só os conhecidos. Vazio = o sino não aparece. */
export function avisosDoPayload(me: Pick<MePayload, 'avisos'> | null | undefined): AvisoTipo[] {
  const lista = me?.avisos
  if (!Array.isArray(lista)) return []
  return AVISOS_CONHECIDOS.filter((a) => lista.includes(a))
}

/** "19/11 14:32", na hora local de quem lê; vazio sem data. */
export function quandoDoAviso(iso: string | null): string {
  if (!iso) return ''
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return ''
  const dois = (n: number) => String(n).padStart(2, '0')
  return `${dois(d.getDate())}/${dois(d.getMonth() + 1)} ${dois(d.getHours())}:${dois(d.getMinutes())}`
}

/** -15.8234 -> "-15,82". */
function coordenada(v: unknown): string | null {
  return typeof v === 'number' && Number.isFinite(v) ? v.toFixed(2).replace('.', ',') : null
}

/** O texto de um aviso: o título (o pedido e o master), a linha (quem pediu e o quê) e o
 *  destaque ("Fora da área", no estudo de um ponto fora do território do master). */
export function textoDoAviso(item: ItemDeAviso): { titulo: string; linha: string; destaque: string | null } {
  const master = item.masters && item.masters.length ? ` · ${item.masters.join(', ')}` : ''
  const quem = item.quem || 'Um master'
  if (item.aviso === 'estudo_master') {
    const lat = coordenada(item.dados.lat)
    const lng = coordenada(item.dados.lng)
    const ponto = lat && lng ? `(${lat}, ${lng})` : ''
    const lugar = typeof item.dados.lugar === 'string' && item.dados.lugar ? item.dados.lugar : ''
    const onde = [lugar, ponto].filter(Boolean).join(' ')
    return {
      titulo: `Estudo pedido${master}`,
      linha: onde ? `${quem} pediu o estudo de ${onde}.` : `${quem} pediu o estudo de um ponto.`,
      destaque: item.dados.fora_da_area === true ? 'Fora da área' : null,
    }
  }
  if (item.aviso === 'imovel_master') {
    const regiao = typeof item.dados.regiao === 'string' ? item.dados.regiao.trim() : ''
    return {
      titulo: `Imóvel pedido${master}`,
      linha: regiao ? `${quem} pediu um imóvel em: ${regiao}` : `${quem} pediu um imóvel.`,
      destaque: null,
    }
  }
  return { titulo: 'Aviso', linha: quem, destaque: null }
}

/** O número no sino: até 9, e "9+" daí em diante (o círculo é pequeno). */
export function rotuloDoContador(n: number): string {
  return n > 9 ? '9+' : String(Math.max(0, n))
}
