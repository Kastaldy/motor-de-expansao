/**
 * Troca de modo (estudo de ponto <-> estudo da unidade Ultra) com respostas FORA DE ORDEM.
 *
 * Revisão do PR #457: "o modo final pode contradizer o último clique do usuário". A regra
 * pura (`pedirTroca`/`concluirTroca`) é exercitada aqui contra TODAS as ordens de chegada
 * das respostas — a propriedade é uma só: depois que tudo chega, o modo da ficha é o do
 * último clique.
 */
import { latLngToCell } from 'h3-js'
import { describe, expect, it } from 'vitest'

import {
  PONTOS_VAZIO,
  TROCAS_VAZIO,
  chegou,
  concluirTroca,
  pedir,
  pedirTroca,
  pendenteDoPedido,
  pontosEmTroca,
  releituraAoChegar,
  type TrocasDeModo,
} from './pontos-estado'
import type { PontoPayload } from './types'

const CHAVE = '-23.48516,-46.61771'

/** Simula a ficha de um ponto: cliques no interruptor e respostas que chegam na ordem dada. */
function simular(cliques: boolean[], ordemDeChegada: (n: number) => number[]) {
  let trocas: TrocasDeModo = TROCAS_VAZIO
  let modoDaFicha = false
  const emVoo: { geracao: number; estudoUltra: boolean }[] = []
  for (const c of cliques) {
    const r = pedirTroca(trocas, CHAVE, modoDaFicha, c)
    trocas = r.trocas
    if (r.decisao.tipo === 'ler') emVoo.push({ geracao: r.decisao.geracao, estudoUltra: c })
  }
  for (const k of ordemDeChegada(emVoo.length)) {
    const req = emVoo[k]
    const fim = concluirTroca(trocas, CHAVE, req.geracao)
    trocas = fim.trocas
    if (fim.vale) modoDaFicha = req.estudoUltra
  }
  return { modoDaFicha, trocas, leituras: emVoo.length }
}

function permutacoes(n: number): number[][] {
  if (n === 0) return [[]]
  const out: number[][] = []
  for (const resto of permutacoes(n - 1)) {
    for (let i = 0; i <= resto.length; i++) out.push([...resto.slice(0, i), n - 1, ...resto.slice(i)])
  }
  return out
}

/** Toda sequência de 1 a 4 cliques, com o modo inicial "desligado". */
function sequencias(): boolean[][] {
  const out: boolean[][] = []
  for (let n = 1; n <= 4; n++) {
    for (let m = 0; m < 1 << n; m++) out.push(Array.from({ length: n }, (_, k) => ((m >> k) & 1) === 1))
  }
  return out
}

describe('troca de modo — o último clique vence, chegue a resposta na ordem que chegar', () => {
  it('liga e desliga rápido: a resposta do "liga" chega depois e é descartada', () => {
    const r = simular([true, false], () => [0])
    expect(r.modoDaFicha).toBe(false)
    expect(pontosEmTroca(r.trocas)).toEqual([])
  })

  it('liga, desliga, liga: a resposta velha chega por ÚLTIMO e não vence a nova', () => {
    // duas leituras de "ligar" (gerações 1 e 3); a 1 chega depois da 3
    const r = simular([true, false, true], (n) => Array.from({ length: n }, (_, k) => n - 1 - k))
    expect(r.leituras).toBe(2)
    expect(r.modoDaFicha).toBe(true)
  })

  it('clicar de novo no modo já pedido não abre segunda leitura', () => {
    expect(simular([true, true, true], (n) => [...Array(n).keys()]).leituras).toBe(1)
  })

  it('propriedade: em TODA sequência e TODA ordem de chegada, o modo final é o do último clique', () => {
    for (const cliques of sequencias()) {
      const n = simular(cliques, () => []).leituras
      for (const ordem of permutacoes(n)) {
        const r = simular(cliques, () => ordem)
        expect({ cliques, ordem, modo: r.modoDaFicha }).toEqual({ cliques, ordem, modo: cliques[cliques.length - 1] })
        expect(pontosEmTroca(r.trocas)).toEqual([])
      }
    }
  })

  it('a resposta (ou falha) de uma geração velha não tira o ponto do "trocando"', () => {
    let t = pedirTroca(TROCAS_VAZIO, CHAVE, false, true).trocas // geração 1
    t = pedirTroca(t, CHAVE, false, false).trocas // cancela
    t = pedirTroca(t, CHAVE, false, true).trocas // geração 2
    const velha = concluirTroca(t, CHAVE, 1)
    expect(velha.vale).toBe(false)
    expect(pontosEmTroca(velha.trocas)).toEqual([CHAVE])
  })

  it('pontos diferentes não interferem um no outro', () => {
    let t = pedirTroca(TROCAS_VAZIO, 'a', false, true).trocas
    t = pedirTroca(t, 'b', false, true).trocas
    expect(concluirTroca(t, 'a', 1).vale).toBe(true)
    expect(concluirTroca(t, 'b', 2).vale).toBe(true)
  })
})

describe('pedido ainda em leitura e pedido de novo como estudo da unidade', () => {
  const A = { lat: -23.48516, lng: -46.61771 }
  const fichaPonto = (modo?: string) =>
    ({
      lat: A.lat,
      lng: A.lng,
      raio_km: 1,
      hex_id: latLngToCell(A.lat, A.lng, 7),
      local: { uf: 'SP', municipio: 'São Paulo', bairro: 'Santana' },
      mercado: modo ? { modo_estudo: modo } : {},
    }) as unknown as PontoPayload

  it('o pendente passa a QUERER o estudo da unidade, e a ficha que chega no modo velho é relida', () => {
    let e = pedir(PONTOS_VAZIO, A.lat, A.lng) // estudo de ponto, em voo
    e = pedir(e, A.lat, A.lng, null, false, true) // agora: estudo da unidade
    expect(e.pendentes).toHaveLength(1)
    const pendente = pendenteDoPedido(e, A)
    expect(pendente?.estudoUltra).toBe(true)
    const ficha = fichaPonto()
    expect(releituraAoChegar(pendente, false, ficha)).toBe(true)
    expect(chegou(e, A, ficha).fichas).toHaveLength(1)
  })

  it('sem o segundo pedido, nada a reler', () => {
    const e = pedir(PONTOS_VAZIO, A.lat, A.lng)
    expect(releituraAoChegar(pendenteDoPedido(e, A), false, fichaPonto())).toBe(false)
  })

  it('a leitura já pediu a unidade e o servidor caiu no estudo de ponto: NÃO relê (seria um laço)', () => {
    const e = pedir(PONTOS_VAZIO, A.lat, A.lng, null, false, true)
    expect(releituraAoChegar(pendenteDoPedido(e, A), true, fichaPonto())).toBe(false)
  })

  it('a ficha já chegou no estudo da unidade: nada a reler', () => {
    let e = pedir(PONTOS_VAZIO, A.lat, A.lng)
    e = pedir(e, A.lat, A.lng, null, false, true)
    expect(releituraAoChegar(pendenteDoPedido(e, A), false, fichaPonto('unidade_ultra'))).toBe(false)
  })

  it('pedir de novo no MESMO modo não muda o estado', () => {
    const e = pedir(PONTOS_VAZIO, A.lat, A.lng, null, false, true)
    expect(pedir(e, A.lat, A.lng, null, false, true)).toBe(e)
    expect(pedir(e, A.lat, A.lng)).toBe(e)
  })
})
