import { latLngToCell } from 'h3-js'
import { describe, expect, it } from 'vitest'

import { rotuloDoPonto, rotulosDosPontos } from './comparacao-pontos'
import {
  SUFIXO_ESTUDO_UNIDADE,
  TOLERANCIA_UNIDADE_ULTRA_M,
  avisoDeEstudoDePonto,
  ehEstudoDaUnidade,
  ehRecusaDoEstudoDaUnidade,
  indiceDaMesmaUnidade,
  ofertaDeEstudoUltra,
  sufixoDoModo,
} from './estudo-ultra'
import { leituraDoMercado } from './mercado-ponto'
import { PONTOS_VAZIO, chegou, decidirPedido, pedir, substituir, type EstadoPontos } from './pontos-estado'
import type { PontoMercado, PontoPayload } from './types'

/**
 * O caso que originou a emenda da DEC-070: o estudo da região da Ultra Santana/SP, com o
 * ponto a 9 m da unidade. Valores medidos com o dado real: SAM 6.418, concorrentes 4.865,
 * Ultra 2.486 (a própria Santana), residual 0 no estudo de ponto e 1.553 no da unidade.
 */
const SANTANA = { lat: -23.485162, lng: -46.61771 }
const ULTRA = { ultra_id: 'd052c90c', nome: 'Santana', dist_m: 9 }

function mercadoPonto(over: Partial<PontoMercado> = {}): PontoMercado {
  return {
    disponivel: true,
    motivo: null,
    grao: 'raio',
    raio_km: 1,
    sam: 6418,
    consumo_concorrentes: 4865,
    consumo_ultra: 2486,
    consumo_total: 7351,
    residual: 0,
    score_residual: 0,
    n_concorrentes_alcancam: 8,
    n_ultra_alcancam: 1,
    modo_estudo: 'ponto',
    declaracao_modo: null,
    unidade_ultra_estudada: null,
    ultra_proxima: ULTRA,
    ...over,
  }
}

const DECLARACAO =
  'Estudo da unidade Ultra Santana: consumo da própria unidade (2.486 alunos) desconsiderado; as outras Ultras continuam contando.'

function mercadoUnidade(over: Partial<PontoMercado> = {}): PontoMercado {
  return mercadoPonto({
    consumo_ultra: 0,
    consumo_total: 4865,
    residual: 1553,
    score_residual: 62.1,
    n_ultra_alcancam: 0,
    modo_estudo: 'unidade_ultra',
    declaracao_modo: DECLARACAO,
    unidade_ultra_estudada: {
      ...ULTRA,
      consumo_excluido: 2486,
      capacidade_real: false,
      tolerancia_m: 150,
    },
    ...over,
  })
}

function ficha(mercado: PontoMercado, over: Partial<PontoPayload> = {}): PontoPayload {
  return {
    lat: SANTANA.lat,
    lng: SANTANA.lng,
    raio_km: 1,
    hex_id: latLngToCell(SANTANA.lat, SANTANA.lng, 7),
    local: { uf: 'SP', municipio: 'São Paulo', bairro: 'Santana' },
    mercado,
    ...over,
  } as unknown as PontoPayload
}

describe('ofertaDeEstudoUltra — detecção da Ultra próxima', () => {
  it('ponto a 9 m da Santana: oferece a chave, DESLIGADA por padrão', () => {
    const o = ofertaDeEstudoUltra(ficha(mercadoPonto()))
    expect(o).not.toBeNull()
    expect(o!.ligado).toBe(false)
    expect(o!.nome).toBe('Santana')
    expect(o!.pergunta).toBe(
      'Este ponto é a Ultra Santana (a 9 m). Estudar a região da unidade (sem o consumo dela)?',
    )
    expect(o!.declaracao).toBeNull()
  })

  it('sem Ultra na tolerância: nada a oferecer', () => {
    expect(ofertaDeEstudoUltra(ficha(mercadoPonto({ ultra_proxima: null })))).toBeNull()
    // payload antigo, sem o campo
    expect(ofertaDeEstudoUltra(ficha(mercadoPonto({ ultra_proxima: undefined })))).toBeNull()
  })

  it('unidade além de 150 m não é "este ponto" (defesa contra servidor de outra régua)', () => {
    const longe = { ...ULTRA, dist_m: TOLERANCIA_UNIDADE_ULTRA_M + 1 }
    expect(ofertaDeEstudoUltra(ficha(mercadoPonto({ ultra_proxima: longe })))).toBeNull()
    const borda = { ...ULTRA, dist_m: TOLERANCIA_UNIDADE_ULTRA_M }
    expect(ofertaDeEstudoUltra(ficha(mercadoPonto({ ultra_proxima: borda })))).not.toBeNull()
  })

  it('modo ligado: a oferta é a de desligar, com a frase do servidor', () => {
    const o = ofertaDeEstudoUltra(ficha(mercadoUnidade()))
    expect(o!.ligado).toBe(true)
    expect(o!.declaracao).toBe(DECLARACAO)
  })

  it('área desenhada e mercado indisponível não oferecem', () => {
    expect(ofertaDeEstudoUltra(ficha(mercadoPonto(), { geometria: [[[0, 0]]] }))).toBeNull()
    expect(ofertaDeEstudoUltra(ficha(mercadoPonto({ disponivel: false })))).toBeNull()
  })

  it('modo ligado com o mercado indisponível: a chave fica, para DESLIGAR (não prende o modo)', () => {
    // O ramo de falha do servidor: disponivel=false, modo unidade, unidade estudada nula.
    const falha = mercadoUnidade({ disponivel: false, unidade_ultra_estudada: null, ultra_proxima: null })
    const o = ofertaDeEstudoUltra(ficha(falha))
    expect(o).not.toBeNull()
    expect(o!.ligado).toBe(true)
    expect(o!.pergunta).toContain('Voltar ao estudo de ponto')
    // com a unidade ainda conhecida, a pergunta de sempre, com o nome
    const comNome = ofertaDeEstudoUltra(ficha(mercadoUnidade({ disponivel: false })))
    expect(comNome!.ligado).toBe(true)
    expect(comNome!.nome).not.toBe('')
  })
})

describe('o modo se declara', () => {
  it('ehEstudoDaUnidade / sufixoDoModo', () => {
    expect(ehEstudoDaUnidade(ficha(mercadoPonto()))).toBe(false)
    expect(ehEstudoDaUnidade(ficha(mercadoUnidade()))).toBe(true)
    expect(ehEstudoDaUnidade(null)).toBe(false)
    expect(sufixoDoModo(ficha(mercadoUnidade()))).toBe(SUFIXO_ESTUDO_UNIDADE)
    expect(sufixoDoModo(ficha(mercadoPonto()))).toBe('')
  })

  it('o nome do ponto (aba, comparação, PDF) carrega o modo, discreto', () => {
    expect(rotuloDoPonto(ficha(mercadoPonto()))).toBe('Santana')
    expect(rotuloDoPonto(ficha(mercadoUnidade()))).toBe('Santana (unidade Ultra)')
  })

  it('a conta da ficha diz que a parcela é a das OUTRAS Ultras', () => {
    const ponto = leituraDoMercado(mercadoPonto()).linhas.find((l) => l.chave === 'consumo_ultra')!
    expect(ponto.rotulo).toBe('Consumo da Ultra')
    const unidade = leituraDoMercado(mercadoUnidade({ n_ultra_alcancam: 2 })).linhas.find(
      (l) => l.chave === 'consumo_ultra',
    )!
    expect(unidade.rotulo).toBe('Consumo das outras Ultras')
    expect(unidade.detalhe).toBe('2 outras unidades Ultra alcançam o raio')
  })
})

describe('recusa do estudo da unidade', () => {
  it('só a recusa do modo (400 + "estudo da unidade") autoriza cair no estudo de ponto', () => {
    const recusa = {
      status: 400,
      message: 'Não há unidade Ultra a até 150 m deste ponto: o estudo da unidade Ultra não se aplica (use o estudo de ponto).',
    }
    expect(ehRecusaDoEstudoDaUnidade(recusa)).toBe(true)
    expect(
      ehRecusaDoEstudoDaUnidade({ status: 400, message: 'Sem cadastro de unidades Ultra: o estudo da unidade não pode ser montado.' }),
    ).toBe(true)
    expect(ehRecusaDoEstudoDaUnidade({ status: 400, message: 'Nao foi possivel resolver a coordenada: x' })).toBe(false)
    expect(ehRecusaDoEstudoDaUnidade({ status: 500, message: recusa.message })).toBe(false)
    expect(ehRecusaDoEstudoDaUnidade(null)).toBe(false)
  })

  it('o aviso diz o motivo e o que aconteceu', () => {
    expect(avisoDeEstudoDePonto('Motivo.', 'pdf')).toBe('Motivo. O PDF saiu como estudo de ponto.')
    expect(avisoDeEstudoDePonto('Motivo.', 'ponto')).toBe('Motivo. O ponto entrou como estudo de ponto.')
  })
})

describe('estado por ponto (`substituir`)', () => {
  const B = { lat: -23.5613, lng: -46.6565 }
  function lista(): EstadoPontos {
    let e = chegou(pedir(PONTOS_VAZIO, SANTANA.lat, SANTANA.lng), SANTANA, ficha(mercadoPonto()))
    e = chegou(pedir(e, B.lat, B.lng), B, ficha(mercadoPonto({ ultra_proxima: null }), B))
    return e
  }

  it('troca a ficha NO LUGAR: mesma posição, aba aberta intacta, o outro ponto no modo dele', () => {
    const e = { ...lista(), aberto: 1 }
    const d = substituir(e, ficha(mercadoUnidade()))
    expect(d.fichas).toHaveLength(2)
    expect(ehEstudoDaUnidade(d.fichas[0])).toBe(true)
    expect(ehEstudoDaUnidade(d.fichas[1])).toBe(false)
    expect(d.aberto).toBe(1)
    expect(rotulosDosPontos(d.fichas)[0]).toBe('Santana (unidade Ultra)')
  })

  it('casa pela coordenada, não pelo índice: ponto removido no meio-tempo não volta', () => {
    const e = lista()
    const semSantana = { ...e, fichas: e.fichas.slice(1) }
    expect(substituir(semSantana, ficha(mercadoUnidade()))).toBe(semSantana)
  })

  it('área desenhada não troca de modo', () => {
    const e = lista()
    expect(substituir(e, ficha(mercadoUnidade(), { geometria: [[[0, 0]]] }))).toBe(e)
  })

  it('"Estudar a região desta unidade" a 9 m de um ponto já aberto NÃO duplica o ponto', () => {
    // O cadastro da Santana fica a ~9 m do ponto do operador: chaves de coordenada
    // diferentes, mas o mesmo lugar. Sem esta regra entravam DOIS pontos e a unidade
    // competia com ela mesma na comparação.
    const cadastro = { lat: -23.485085, lng: -46.617685 }
    const e = lista()
    expect(decidirPedido(e, cadastro.lat, cadastro.lng, null, true)).toEqual({ tipo: 'repetido', indice: 0 })
    const d = pedir(e, cadastro.lat, cadastro.lng, null, false, true)
    expect(d.fichas).toHaveLength(2)
    expect(d.pendentes).toHaveLength(0)
    expect(d.aberto).toBe(0)
    // Sem o estudo da unidade, a regra de identidade segue a da coordenada.
    expect(decidirPedido(e, cadastro.lat, cadastro.lng)).toEqual({ tipo: 'ler' })
    // Ponto sem Ultra ligada a ele não absorve o pedido, mesmo perto.
    const perto = { lat: B.lat + 0.0005, lng: B.lng }
    expect(indiceDaMesmaUnidade(e.fichas, perto.lat, perto.lng)).toBe(-1)
  })

  it('a unidade longe (> 150 m) de qualquer ponto aberto entra como ponto novo', () => {
    const e = lista()
    const longe = { lat: SANTANA.lat + 0.002, lng: SANTANA.lng } // ~220 m
    expect(indiceDaMesmaUnidade(e.fichas, longe.lat, longe.lng)).toBe(-1)
    expect(decidirPedido(e, longe.lat, longe.lng, null, true)).toEqual({ tipo: 'ler' })
  })

  it('o pedido do estudo da unidade carrega o modo no pendente (e só no ponto)', () => {
    const e = pedir(PONTOS_VAZIO, SANTANA.lat, SANTANA.lng, null, false, true)
    expect(e.pendentes[0].estudoUltra).toBe(true)
    const sem = pedir(PONTOS_VAZIO, SANTANA.lat, SANTANA.lng)
    expect(sem.pendentes[0].estudoUltra).toBeUndefined()
  })
})
