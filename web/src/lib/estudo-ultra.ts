/**
 * ESTUDO DA UNIDADE ULTRA x ESTUDO DE PONTO (emenda da DEC-070, 2026-10-16).
 *
 * O caso que originou a regra: um estudo feito para analisar a REGIÃO da Ultra Santana/SP,
 * com a unidade no centro (a 9 m do ponto). Como estudo de ponto, o consumo da própria
 * Santana (2.486 alunos) entrava no mercado ocupado e o residual saía ZERO — a resposta de
 * "quanto sobra se a Santana existir", quando a pergunta era "quanto mercado há em volta
 * da Santana". Dois modos, então, e cada ficha DECLARA o seu:
 *
 *  - ESTUDO DE PONTO (padrão, como sempre): a Ultra próxima CONTA no consumo — quem estuda
 *    um imóvel ao lado de uma Ultra precisa ver que o mercado já está ocupado por ela.
 *  - ESTUDO DA UNIDADE ULTRA: o consumo DA PRÓPRIA unidade sai; as OUTRAS Ultras continuam
 *    contando. Liga sozinho quando o estudo parte da unidade (ficha da unidade no mapa) e,
 *    por escolha, no estudo de ponto que caia a até 150 m de uma Ultra — padrão DESLIGADO.
 *
 * O MODO MORA NA FICHA, não num estado paralelo: é o servidor que devolve `modo_estudo` e
 * a unidade que saiu da conta, e a ficha vive na lista do `App` (`lib/use-pontos`) — por
 * isso ela sobrevive à ida ao Simulador, e cada ponto da comparação carrega o seu.
 *
 * NADA É RECALCULADO AQUI: quem tira a unidade da conta é o servidor
 * (`mercado_raio.mercado_na_area`). Estas funções só decidem o que oferecer e o que dizer.
 */
import { distanciaCurta } from './format'
import { distanciaMetros } from './medicao'
import type { PontoPayload } from './types'

/**
 * A distância máxima entre o ponto e a unidade para o ponto "ser" a unidade. É a MESMA
 * tolerância que liga o pin da Ultra à ficha da unidade no mapa (`ficha-unidade.ts`) e a
 * do servidor (`TOLERANCIA_UNIDADE_ULTRA_M`).
 */
export const TOLERANCIA_UNIDADE_ULTRA_M = 150

/** Rótulo discreto do modo, para o nome do ponto (aba, comparação, PDF, Simulador). */
export const SUFIXO_ESTUDO_UNIDADE = ' (unidade Ultra)'

/** A ficha é um ESTUDO DA UNIDADE ULTRA? Ausente ou `'ponto'` = estudo de ponto. */
export function ehEstudoDaUnidade(f: Pick<PontoPayload, 'mercado'> | null | undefined): boolean {
  return f?.mercado?.modo_estudo === 'unidade_ultra'
}

/** O que a ficha oferece para trocar de modo — ou `null` quando não há o que oferecer. */
export interface OfertaEstudoUltra {
  /** Nome curto da unidade ("Santana"). */
  nome: string
  distM: number | null
  /** O modo atual da ficha: `true` = estudo da unidade Ultra. */
  ligado: boolean
  /** A pergunta da chave, sempre a mesma forma (o modo ligado ou não). */
  pergunta: string
  /** A frase do servidor que declara o modo, quando ligado. */
  declaracao: string | null
}

/**
 * A DETECÇÃO DA ULTRA PRÓXIMA, do jeito que a ficha a usa: oferece a troca quando o
 * servidor achou uma unidade a até `TOLERANCIA_UNIDADE_ULTRA_M` do ponto (ou quando o
 * modo já está ligado — aí a oferta é a de desligar).
 *
 * Não oferece em ÁREA DESENHADA (o recorte não tem centro que "seja" uma unidade) nem
 * sem mercado (não há consumo do que tirar).
 */
export function ofertaDeEstudoUltra(
  f: Pick<PontoPayload, 'mercado' | 'geometria'>,
): OfertaEstudoUltra | null {
  if (f.geometria?.length) return null
  const m = f.mercado
  if (!m) return null
  const ligado = ehEstudoDaUnidade(f)
  // Mercado indisponivel: so' a SAIDA do modo ligado. Desde que o modo vale em todo alcance
  // (Emenda 2 da DEC-074), trocar de alcance preserva o modo; sem a chave aqui, uma falha do
  // mercado deixava o estudo da unidade preso em todos os alcances, sem como desligar.
  if (!m.disponivel && !ligado) return null
  const unidade = (ligado ? m.unidade_ultra_estudada : null) ?? m.ultra_proxima ?? null
  if (!unidade) {
    if (!ligado) return null
    // Na falha o servidor manda `unidade_ultra_estudada: null`: a chave fica, sem o nome.
    return {
      nome: '',
      distM: null,
      ligado,
      pergunta: 'Estudo da região da unidade Ultra (sem o consumo dela). Voltar ao estudo de ponto?',
      declaracao: m.declaracao_modo ?? null,
    }
  }
  const dist = unidade.dist_m ?? null
  if (dist != null && dist > TOLERANCIA_UNIDADE_ULTRA_M) return null
  const onde = dist != null ? ` (a ${distanciaCurta(dist)})` : ''
  return {
    nome: unidade.nome,
    distM: dist,
    ligado,
    pergunta: `Este ponto é a Ultra ${unidade.nome}${onde}. Estudar a região da unidade (sem o consumo dela)?`,
    declaracao: ligado ? (m.declaracao_modo ?? null) : null,
  }
}

/**
 * O ponto da lista que JÁ É o lugar de uma unidade Ultra pedida pela coordenada dela —
 * ou `-1`.
 *
 * Existe porque "Estudar a região desta unidade" pede a coordenada do CADASTRO da unidade,
 * e o ponto que o operador abriu antes (clique, endereço) cai a alguns metros dela: em
 * Santana, a 9 m. A identidade da lista é a coordenada a 5 casas (~1 m), então os dois
 * viravam DOIS pontos e a comparação punha a unidade para competir com ela mesma (residual
 * 0 contra 1.527, "leva a comparação"). O contrato do modo é o contrário: o mesmo lugar
 * nos dois modos é o MESMO ponto, e o pedido troca o modo da ficha que já está aberta.
 *
 * "Mesmo lugar" = um ponto com raio (não área desenhada) que o servidor já ligou a uma
 * Ultra a até `TOLERANCIA_UNIDADE_ULTRA_M` e que está a até essa mesma tolerância da
 * coordenada pedida. Havendo mais de um, o mais próximo.
 */
export function indiceDaMesmaUnidade(
  fichas: readonly Pick<PontoPayload, 'lat' | 'lng' | 'geometria' | 'mercado'>[],
  lat: number,
  lng: number,
): number {
  let melhor = -1
  let melhorDist = Infinity
  fichas.forEach((f, i) => {
    if (f.geometria?.length) return
    const m = f.mercado
    const unidade = m?.unidade_ultra_estudada ?? m?.ultra_proxima ?? null
    if (!unidade || unidade.dist_m == null || unidade.dist_m > TOLERANCIA_UNIDADE_ULTRA_M) return
    const d = distanciaMetros({ lat: f.lat, lng: f.lng }, { lat, lng })
    if (d <= TOLERANCIA_UNIDADE_ULTRA_M && d < melhorDist) {
      melhor = i
      melhorDist = d
    }
  })
  return melhor
}

/**
 * O erro é a RECUSA do estudo da unidade (sem unidade Ultra a até 150 m, ou sem cadastro)?
 *
 * Só essa recusa autoriza cair no estudo de ponto. Qualquer outro 400 (coordenada que não
 * resolve, parâmetro inválido) falharia de novo no outro modo — e cair nele esconderia o
 * motivo real. As duas frases do servidor (`mercado_raio.exigir_unidade_ultra`) dizem
 * "estudo da unidade"; o teste Python trava isso.
 */
export function ehRecusaDoEstudoDaUnidade(e: unknown): boolean {
  if (typeof e !== 'object' || e === null) return false
  const { status, message } = e as { status?: unknown; message?: unknown }
  return status === 400 && typeof message === 'string' && /estudo da unidade/i.test(message)
}

/** O aviso de quando o estudo da unidade foi recusado e o pedido seguiu como estudo de ponto. */
export function avisoDeEstudoDePonto(motivo: string, oQue: 'ponto' | 'pdf'): string {
  const fim = oQue === 'pdf' ? 'O PDF saiu como estudo de ponto.' : 'O ponto entrou como estudo de ponto.'
  return `${motivo} ${fim}`
}

/** O sufixo do nome do ponto no estudo da unidade; vazio no estudo de ponto. */
export function sufixoDoModo(f: Pick<PontoPayload, 'mercado'> | null | undefined): string {
  return ehEstudoDaUnidade(f) ? SUFIXO_ESTUDO_UNIDADE : ''
}
