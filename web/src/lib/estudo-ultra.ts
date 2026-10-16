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
  if (!m || !m.disponivel) return null
  const ligado = ehEstudoDaUnidade(f)
  const unidade = (ligado ? m.unidade_ultra_estudada : null) ?? m.ultra_proxima ?? null
  if (!unidade) return null
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

/** O sufixo do nome do ponto no estudo da unidade; vazio no estudo de ponto. */
export function sufixoDoModo(f: Pick<PontoPayload, 'mercado'> | null | undefined): string {
  return ehEstudoDaUnidade(f) ? SUFIXO_ESTUDO_UNIDADE : ''
}
