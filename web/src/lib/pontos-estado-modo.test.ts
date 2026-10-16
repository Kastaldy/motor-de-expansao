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
  decidirPedido,
  esquecerTroca,
  limparTrocas,
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

describe('"Limpar tudo" e "remover" no meio de uma troca de modo (revisão do PR #457)', () => {
  it('limpar PRESERVA a geração: o pedido novo na mesma coordenada não reusa o número do velho', () => {
    // A está como estudo da unidade e o operador desliga: geração 1, em voo
    let t = pedirTroca(TROCAS_VAZIO, CHAVE, true, false).trocas
    t = limparTrocas(t)
    expect(pontosEmTroca(t)).toEqual([])
    // reanalisa A como ponto e liga o estudo da unidade
    const r = pedirTroca(t, CHAVE, false, true)
    expect(r.decisao).toEqual({ tipo: 'ler', geracao: 2 })
    // a resposta VELHA (geração 1) chega primeiro: descartada; a nova vale
    expect(concluirTroca(r.trocas, CHAVE, 1).vale).toBe(false)
    expect(concluirTroca(r.trocas, CHAVE, 2).vale).toBe(true)
  })

  it('limpar sem nada em voo não muda o estado', () => {
    expect(limparTrocas(TROCAS_VAZIO)).toBe(TROCAS_VAZIO)
  })

  it('propriedade: com "Limpar tudo" entre duas rodadas de cliques, o modo final é o do último clique', () => {
    // `ini`: o modo da ficha antes do limpar; `readicionada`: o modo em que o ponto volta
    for (const [ini, readicionada] of [[false, false], [false, true], [true, false], [true, true]]) {
      for (const antes of sequencias()) {
        for (const depois of sequencias()) {
          let trocas: TrocasDeModo = TROCAS_VAZIO
          const voo: { geracao: number; estudoUltra: boolean }[] = []
          for (const c of antes) {
            const r = pedirTroca(trocas, CHAVE, ini, c)
            trocas = r.trocas
            if (r.decisao.tipo === 'ler') voo.push({ geracao: r.decisao.geracao, estudoUltra: c })
          }
          trocas = limparTrocas(trocas)
          let modoDaFicha = readicionada
          for (const c of depois) {
            const r = pedirTroca(trocas, CHAVE, modoDaFicha, c)
            trocas = r.trocas
            if (r.decisao.tipo === 'ler') voo.push({ geracao: r.decisao.geracao, estudoUltra: c })
          }
          // a ordem hostil: as respostas de ANTES do limpar chegam PRIMEIRO, quando o número
          // delas já pode ter sido reusado por um pedido novo
          for (const req of voo) {
            const fim = concluirTroca(trocas, CHAVE, req.geracao)
            trocas = fim.trocas
            if (fim.vale) modoDaFicha = req.estudoUltra
          }
          expect({ ini, readicionada, antes, depois, modo: modoDaFicha }).toEqual({
            ini,
            readicionada,
            antes,
            depois,
            modo: depois[depois.length - 1],
          })
        }
      }
    }
  })

  it('remover o ponto descarta a troca em voo: a resposta antiga não troca a ficha readicionada', () => {
    let t = pedirTroca(TROCAS_VAZIO, CHAVE, false, true).trocas // liga: geração 1
    t = esquecerTroca(t, CHAVE) // o operador removeu o ponto
    expect(pontosEmTroca(t)).toEqual([])
    expect(concluirTroca(t, CHAVE, 1).vale).toBe(false)
  })

  it('remover um ponto não mexe na troca de outro', () => {
    let t = pedirTroca(TROCAS_VAZIO, 'a', false, true).trocas
    t = pedirTroca(t, 'b', false, true).trocas
    t = esquecerTroca(t, 'a')
    expect(pontosEmTroca(t)).toEqual(['b'])
    expect(concluirTroca(t, 'b', 2).vale).toBe(true)
    expect(esquecerTroca(t, 'zzz')).toBe(t)
  })
})

describe('ponto em leitura a poucos metros da unidade pedida (revisão do PR #457)', () => {
  const A = { lat: -23.48516, lng: -46.61771 } // o ponto clicado
  const U = { lat: -23.48508, lng: -46.61771 } // o cadastro da unidade, ~9 m ao norte
  const LONGE = { lat: -23.49, lng: -46.61771 } // ~540 m

  it('"Estudar a região desta unidade" com o ponto ainda carregando NÃO abre um segundo item', () => {
    let e = pedir(PONTOS_VAZIO, A.lat, A.lng)
    expect(decidirPedido(e, U.lat, U.lng, null, true)).toEqual({ tipo: 'esperando' })
    e = pedir(e, U.lat, U.lng, null, false, true)
    expect(e.pendentes).toHaveLength(1)
    expect(pendenteDoPedido(e, A)?.estudoUltra).toBe(true)
  })

  it('a unidade longe do ponto em leitura é OUTRO lugar: entra como item próprio', () => {
    const e = pedir(PONTOS_VAZIO, A.lat, A.lng)
    expect(decidirPedido(e, LONGE.lat, LONGE.lng, null, true)).toEqual({ tipo: 'ler' })
    expect(pedir(e, LONGE.lat, LONGE.lng, null, false, true).pendentes).toHaveLength(2)
  })

  it('um clique comum a poucos metros continua sendo outro ponto (a tolerância é só do estudo da unidade)', () => {
    const e = pedir(PONTOS_VAZIO, A.lat, A.lng)
    expect(decidirPedido(e, U.lat, U.lng)).toEqual({ tipo: 'ler' })
  })
})
