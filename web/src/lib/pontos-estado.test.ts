import { latLngToCell } from 'h3-js'
import { describe, expect, it } from 'vitest'

import { corDeIdentidadeRgb } from './comparacao'
import { MAX_PONTOS } from './comparacao-pontos'
import {
  PONTOS_VAZIO,
  abrir,
  chaveDoAtivo,
  chegou,
  decidirPedido,
  falhou,
  itemAtivo,
  limpar,
  pedir,
  pinParaAtivo,
  pinsDoEstado,
  remover,
  type EstadoPontos,
} from './pontos-estado'
import type { PontoPayload } from './types'

/** Ficha mínima com a forma do `/api/ponto` — só o que estas regras leem. */
function ficha(lat: number, lng: number, over: { bairro?: string; municipio?: string; uf?: string } = {}) {
  return {
    lat,
    lng,
    raio_km: 1,
    hex_id: latLngToCell(lat, lng, 7),
    local: {
      uf: over.uf ?? 'SP',
      municipio: over.municipio ?? 'São Paulo',
      bairro: over.bairro ?? 'Santana',
    },
  } as unknown as PontoPayload
}

const A = { lat: -23.48516, lng: -46.61771 }
const B = { lat: -23.5613, lng: -46.6565 }
const C = { lat: -22.9068, lng: -43.1729 }

/** Pede e responde um ponto, como o hook faz. */
function lido(e: EstadoPontos, p: { lat: number; lng: number }, over = {}): EstadoPontos {
  return chegou(pedir(e, p.lat, p.lng), p, ficha(p.lat, p.lng, over))
}

describe('decidirPedido', () => {
  it('ponto novo com vaga: ler', () => {
    expect(decidirPedido(PONTOS_VAZIO, A.lat, A.lng)).toEqual({ tipo: 'ler' })
  })

  it('ponto já lido: repetido, com o índice dele', () => {
    const e = lido(lido(PONTOS_VAZIO, A), B)
    expect(decidirPedido(e, A.lat, A.lng)).toEqual({ tipo: 'repetido', indice: 0 })
  })

  it('ponto ainda em leitura: esperando — não pede duas vezes', () => {
    const e = pedir(PONTOS_VAZIO, A.lat, A.lng)
    expect(decidirPedido(e, A.lat, A.lng)).toEqual({ tipo: 'esperando' })
  })

  it('o teto conta os pendentes: 4 fichas + 1 em leitura = cheio', () => {
    let e = PONTOS_VAZIO
    for (let i = 0; i < MAX_PONTOS - 1; i++) e = lido(e, { lat: -23 - i * 0.01, lng: -46 })
    e = pedir(e, -10, -40)
    expect(decidirPedido(e, -11, -41)).toEqual({ tipo: 'cheio' })
  })
})

describe('pedir / chegou / falhou', () => {
  it('pedir um ponto novo cria o pendente e NÃO mexe nas fichas', () => {
    const e = pedir(PONTOS_VAZIO, A.lat, A.lng)
    expect(e.pendentes).toEqual([A])
    expect(e.fichas).toEqual([])
  })

  it('a ficha que chega entra no fim, vira a aberta e tira o pendente', () => {
    const e = lido(lido(PONTOS_VAZIO, A), B)
    expect(e.fichas.map((f) => f.lat)).toEqual([A.lat, B.lat])
    expect(e.aberto).toBe(1)
    expect(e.pendentes).toEqual([])
  })

  it('cada chegada sobe o `revelar` (é o que abre a janela)', () => {
    const e1 = lido(PONTOS_VAZIO, A)
    const e2 = lido(e1, B)
    expect(e2.revelar).toBeGreaterThan(e1.revelar)
  })

  it('pedir um ponto que já está na lista abre a aba dele e sobe o `revelar`', () => {
    const e = lido(lido(PONTOS_VAZIO, A), B)
    const d = pedir(e, A.lat, A.lng)
    expect(d.aberto).toBe(0)
    expect(d.fichas).toHaveLength(2)
    expect(d.revelar).toBe(e.revelar + 1)
  })

  it('pedido em teto cheio não muda nada (o hook mostra o erro)', () => {
    let e = PONTOS_VAZIO
    for (let i = 0; i < MAX_PONTOS; i++) e = lido(e, { lat: -23 - i * 0.01, lng: -46 })
    expect(pedir(e, -10, -40)).toBe(e)
  })

  it('resposta que chega depois de "Limpar tudo" NÃO ressuscita o ponto', () => {
    const pedido = pedir(PONTOS_VAZIO, A.lat, A.lng)
    const limpo = limpar(pedido)
    expect(chegou(limpo, A, ficha(A.lat, A.lng))).toBe(limpo)
  })

  it('a falha tira só o pendente; as fichas já lidas ficam', () => {
    const e = pedir(lido(PONTOS_VAZIO, A), B.lat, B.lng)
    const d = falhou(e, B)
    expect(d.pendentes).toEqual([])
    expect(d.fichas).toHaveLength(1)
  })

  it('a ficha que volta com a coordenada arredondada pelo servidor casa com o pedido', () => {
    const pedidoLongo = { lat: -23.485161830013, lng: -46.617709841104 }
    const e = pedir(PONTOS_VAZIO, pedidoLongo.lat, pedidoLongo.lng)
    const d = chegou(e, pedidoLongo, ficha(-23.485162, -46.61771))
    expect(d.fichas).toHaveLength(1)
    expect(d.pendentes).toEqual([])
  })
})

describe('remover / abrir / limpar', () => {
  const tres = () => lido(lido(lido(PONTOS_VAZIO, A), B), C)

  it('remover um ponto ANTES do aberto mantém aberto o MESMO ponto', () => {
    const e = tres() // aberto = 2 (C)
    const d = remover(e, 0)
    expect(d.fichas).toHaveLength(2)
    expect(d.fichas[d.aberto].lat).toBe(C.lat)
  })

  it('remover o aberto do fim cai no anterior', () => {
    const d = remover(tres(), 2)
    expect(d.aberto).toBe(1)
  })

  it('remover o último deixa a lista vazia, sem ativo', () => {
    const d = remover(lido(PONTOS_VAZIO, A), 0)
    expect(d.fichas).toEqual([])
    expect(itemAtivo(d)).toBeNull()
  })

  it('abrir prende o índice ao intervalo válido', () => {
    expect(abrir(tres(), 9).aberto).toBe(2)
    expect(abrir(tres(), -1).aberto).toBe(0)
  })

  it('limpar tira fichas E pendentes, mas o `revelar` não volta atrás', () => {
    const e = pedir(tres(), -10, -40)
    const d = limpar(e)
    expect(d.fichas).toEqual([])
    expect(d.pendentes).toEqual([])
    expect(d.revelar).toBe(e.revelar)
  })
})

describe('itemAtivo — a regra única de precedência do pin', () => {
  it('sem nada: null', () => {
    expect(itemAtivo(PONTOS_VAZIO)).toBeNull()
  })

  it('o pendente vence a aba aberta, e ainda não tem território', () => {
    const e = pedir(lido(PONTOS_VAZIO, A), B.lat, B.lng)
    const a = itemAtivo(e)!
    expect([a.lat, a.lng]).toEqual([B.lat, B.lng])
    expect(a.hexId).toBe(latLngToCell(B.lat, B.lng, 7))
    expect(a.territorio).toBeNull()
  })

  it('sem pendente, é a ficha aberta, com o território dela', () => {
    const e = abrir(lido(lido(PONTOS_VAZIO, A), C, { uf: 'RJ', municipio: 'Rio de Janeiro' }), 1)
    const a = itemAtivo(e)!
    expect(a.lat).toBe(C.lat)
    expect(a.territorio).toEqual({ uf: 'RJ', municipio: 'Rio de Janeiro' })
  })

  it('a chave muda quando o pendente vira ficha no MESMO lugar (é o que troca o município)', () => {
    const p = pedir(PONTOS_VAZIO, A.lat, A.lng)
    const f = chegou(p, A, ficha(A.lat, A.lng))
    expect(chaveDoAtivo(itemAtivo(p))).not.toBe(chaveDoAtivo(itemAtivo(f)))
    expect(chaveDoAtivo(null)).toBeNull()
  })
})

describe('pinParaAtivo — identidade do pin', () => {
  const ativo = { lat: A.lat, lng: A.lng, hexId: 'h', territorio: null }

  it('mesmo lugar e mesmo território: devolve o MESMO objeto (sem segundo voo)', () => {
    const atual = { lat: A.lat, lng: A.lng, hexId: 'h' }
    expect(pinParaAtivo(atual, ativo, false)).toBe(atual)
  })

  it('território mudou: objeto NOVO mesmo no mesmo lugar (devolve a seleção do hex)', () => {
    const atual = { lat: A.lat, lng: A.lng, hexId: 'h' }
    const novo = pinParaAtivo(atual, ativo, true)
    expect(novo).not.toBe(atual)
    expect(novo).toEqual(atual)
  })

  it('lugar diferente ou sem pin: objeto novo na coordenada do ativo', () => {
    expect(pinParaAtivo(null, ativo, false)).toEqual({ lat: A.lat, lng: A.lng, hexId: 'h' })
    const outro = { lat: B.lat, lng: B.lng, hexId: 'x' }
    expect(pinParaAtivo(outro, ativo, false)).toEqual({ lat: A.lat, lng: A.lng, hexId: 'h' })
  })
})

describe('pinsDoEstado — todos os pontos no mapa', () => {
  it('um pin por ficha, na cor de identidade do índice, e só o aberto ativo', () => {
    const e = abrir(lido(lido(PONTOS_VAZIO, A), B), 0)
    const pins = pinsDoEstado(e)
    expect(pins).toHaveLength(2)
    expect(pins.map((p) => p.rgb)).toEqual([corDeIdentidadeRgb(0), corDeIdentidadeRgb(1)])
    expect(pins.map((p) => p.ativo)).toEqual([true, false])
    expect(pins.every((p) => !p.carregando)).toBe(true)
  })

  it('o pendente entra no fim, com a cor que vai ter, ativo e marcado como carregando', () => {
    const e = pedir(lido(PONTOS_VAZIO, A), B.lat, B.lng)
    const pins = pinsDoEstado(e)
    expect(pins).toHaveLength(2)
    expect(pins[1]).toMatchObject({ lat: B.lat, carregando: true, ativo: true, indice: 1 })
    expect(pins[1].rgb).toEqual(corDeIdentidadeRgb(1))
    expect(pins[0].ativo).toBe(false)
  })

  it('o pendente sai com a coordenada como nome; a ficha, com o rótulo desambiguado', () => {
    const e = pedir(lido(lido(PONTOS_VAZIO, A), B), C.lat, C.lng)
    const pins = pinsDoEstado(e)
    expect(pins[0].rotulo).toBe('Santana #1')
    expect(pins[1].rotulo).toBe('Santana #2')
    expect(pins[2].rotulo).toBe(`${C.lat.toFixed(4)}, ${C.lng.toFixed(4)}`)
  })

  it('lista vazia: nenhum pin', () => {
    expect(pinsDoEstado(PONTOS_VAZIO)).toEqual([])
  })
})
