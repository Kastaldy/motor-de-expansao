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
  erroFlutuanteVisivel,
  falhou,
  itemAtivo,
  janelaNaMontagem,
  limpar,
  mostrar,
  movimentoDoMapa,
  pedir,
  pinParaAtivo,
  pinsDoEstado,
  LEITURA_ULTRA,
  leituraComAlcance,
  leituraComModo,
  leituraUltra,
  partesDaLeitura,
  TROCAS_VAZIO,
  concluirTroca,
  leituraDaFicha,
  pedirTroca,
  remover,
  substituir,
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
  const ativo = { lat: A.lat, lng: A.lng, hexId: 'h', territorio: null, doMapa: false }

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

/* ---------------- Área desenhada (DEC-071, fase 1) ---------------- */

/** Um quadradinho de ~1 km em volta de `c`, como anel GeoJSON fechado. */
function anelEm(c: { lat: number; lng: number }, d = 0.0045): [number, number][][] {
  const anel: [number, number][] = [
    [c.lng - d, c.lat - d],
    [c.lng + d, c.lat - d],
    [c.lng + d, c.lat + d],
    [c.lng - d, c.lat + d],
  ]
  anel.push(anel[0])
  return [anel]
}

/** A ficha que o servidor devolve para a área: `lat`/`lng` = ponto interno, mais o anel. */
function fichaDeArea(c: { lat: number; lng: number }, geometria = anelEm(c)) {
  return {
    ...(ficha(c.lat, c.lng) as object),
    raio_km: null,
    geometria,
    recorte: { tipo: 'poligono', area_km2: 1, n_vertices: 4, metodo: 'x' },
  } as unknown as PontoPayload
}

describe('área desenhada na mesma lista dos pontos', () => {
  it('entra como pendente com a geometria, e o pin provisório já tem o contorno', () => {
    const g = anelEm(A)
    const e = pedir(PONTOS_VAZIO, A.lat, A.lng, g)
    expect(e.pendentes).toEqual([{ lat: A.lat, lng: A.lng, geometria: g }])
    const [pin] = pinsDoEstado(e)
    expect(pin.geometria).toBe(g)
    expect(pin.carregando).toBe(true)
    expect(pin.rotulo).toBe('Área desenhada')
  })

  it('a ficha da área chega e ocupa a vaga dela', () => {
    const g = anelEm(A)
    const e = chegou(pedir(PONTOS_VAZIO, A.lat, A.lng, g), { lat: A.lat, lng: A.lng, geometria: g }, fichaDeArea(A, g))
    expect(e.fichas).toHaveLength(1)
    expect(e.pendentes).toHaveLength(0)
    expect(pinsDoEstado(e)[0].geometria).toEqual(g)
  })

  it('área e ponto no MESMO lugar não se confundem', () => {
    const g = anelEm(A)
    const comArea = chegou(pedir(PONTOS_VAZIO, A.lat, A.lng, g), { lat: A.lat, lng: A.lng, geometria: g }, fichaDeArea(A, g))
    // Buscar a coordenada exata do ponto interno da área é um PONTO novo, não a área.
    expect(decidirPedido(comArea, A.lat, A.lng)).toEqual({ tipo: 'ler' })
    const comPonto = lido(PONTOS_VAZIO, A)
    expect(decidirPedido(comPonto, A.lat, A.lng, g)).toEqual({ tipo: 'ler' })
  })

  it('desenhar de novo a MESMA área é repetição; outra área é item novo', () => {
    const g = anelEm(A)
    const e = chegou(pedir(PONTOS_VAZIO, A.lat, A.lng, g), { lat: A.lat, lng: A.lng, geometria: g }, fichaDeArea(A, g))
    expect(decidirPedido(e, A.lat, A.lng, anelEm(A))).toEqual({ tipo: 'repetido', indice: 0 })
    expect(decidirPedido(e, A.lat, A.lng, anelEm(A, 0.006))).toEqual({ tipo: 'ler' })
  })

  it('área conta no teto como qualquer ponto', () => {
    let e = PONTOS_VAZIO
    for (const p of [A, B, C, { lat: -8.05, lng: -34.88 }]) e = lido(e, p)
    e = pedir(e, -15.79, -47.88, anelEm({ lat: -15.79, lng: -47.88 }))
    expect(decidirPedido(e, -3.73, -38.52, anelEm({ lat: -3.73, lng: -38.52 }))).toEqual({ tipo: 'cheio' })
  })

  it('a leitura da área que falha tira só o pin dela', () => {
    const g = anelEm(B)
    const e = pedir(lido(PONTOS_VAZIO, A), B.lat, B.lng, g)
    const depois = falhou(e, { lat: B.lat, lng: B.lng, geometria: g })
    expect(depois.pendentes).toHaveLength(0)
    expect(depois.fichas).toHaveLength(1)
  })

  it('duas áreas viram "Área desenhada #1" e "#2"', () => {
    const ga = anelEm(A)
    const gb = anelEm(B)
    let e = chegou(pedir(PONTOS_VAZIO, A.lat, A.lng, ga), { lat: A.lat, lng: A.lng, geometria: ga }, fichaDeArea(A, ga))
    e = chegou(pedir(e, B.lat, B.lng, gb), { lat: B.lat, lng: B.lng, geometria: gb }, fichaDeArea(B, gb))
    expect(pinsDoEstado(e).map((p) => p.rotulo)).toEqual(['Área desenhada #1', 'Área desenhada #2'])
  })
})

describe('mostrar (clique no pin colorido)', () => {
  it('abre a aba pelo ÍNDICE e revela a janela, sem ler nada', () => {
    const e = lido(lido(PONTOS_VAZIO, A), B)
    const depois = mostrar(e, 0)
    expect(depois.aberto).toBe(0)
    expect(depois.revelar).toBe(e.revelar + 1)
    expect(depois.pendentes).toHaveLength(0)
  })

  it('vale para a ÁREA desenhada — pedir a coordenada dela leria um ponto novo', () => {
    const g = anelEm(A)
    const e = lido(
      chegou(pedir(PONTOS_VAZIO, A.lat, A.lng, g), { lat: A.lat, lng: A.lng, geometria: g }, fichaDeArea(A, g)),
      B,
    )
    expect(decidirPedido(e, A.lat, A.lng)).toEqual({ tipo: 'ler' })
    expect(mostrar(e, 0).aberto).toBe(0)
  })

  it('índice fora da lista não muda nada', () => {
    const e = lido(PONTOS_VAZIO, A)
    expect(mostrar(e, 3)).toBe(e)
  })
})

/* ---------------- O mapa volta ao ponto escolhido ---------------- */

describe('foco — escolher o ponto ABERTO de novo o traz de volta ao mapa', () => {
  it('abrir a aba que já está aberta sobe o `foco` (antes devolvia o mesmo estado)', () => {
    const e = lido(lido(PONTOS_VAZIO, A), B) // aberto = 1
    const d = abrir(e, 1)
    expect(d.aberto).toBe(1)
    expect(d.foco).toBe(e.foco + 1)
  })

  it('mostrar (pin colorido) e pedido repetido também sobem o `foco`', () => {
    const e = lido(lido(PONTOS_VAZIO, A), B)
    expect(mostrar(e, 1).foco).toBe(e.foco + 1)
    expect(pedir(e, A.lat, A.lng).foco).toBe(e.foco + 1)
  })

  it('pedido NOVO e leitura que chega não sobem o `foco` (quem move o mapa ali é a chave)', () => {
    const e = lido(PONTOS_VAZIO, A)
    const p = pedir(e, B.lat, B.lng)
    expect(p.foco).toBe(e.foco)
    expect(chegou(p, B, ficha(B.lat, B.lng)).foco).toBe(e.foco)
  })

  it('limpar não volta o `foco` atrás (é contador de eventos)', () => {
    const e = abrir(lido(PONTOS_VAZIO, A), 0)
    expect(limpar(e).foco).toBe(e.foco)
  })
})

describe('abaFixada — o clique do operador vence um pedido ainda em leitura', () => {
  it('com um pendente, escolher uma aba passa o ativo para ela (o mapa se mexe)', () => {
    const e = pedir(lido(lido(PONTOS_VAZIO, A), B), C.lat, C.lng)
    expect(itemAtivo(e)!.lat).toBe(C.lat) // o pendente vence...
    const d = abrir(e, 0)
    expect(itemAtivo(d)!.lat).toBe(A.lat) // ...até o operador escolher uma aba
    expect(pinsDoEstado(d).map((p) => p.ativo)).toEqual([true, false, false])
  })

  it('a leitura que chega depois NÃO rouba a aba escolhida — mas a ficha entra na lista', () => {
    const e = abrir(pedir(lido(lido(PONTOS_VAZIO, A), B), C.lat, C.lng), 0)
    const d = chegou(e, C, ficha(C.lat, C.lng))
    expect(d.fichas).toHaveLength(3)
    expect(d.aberto).toBe(0)
    expect(d.pendentes).toEqual([])
    // Nem reabre a janela à força.
    expect(d.revelar).toBe(e.revelar)
    expect(chaveDoAtivo(itemAtivo(d))).toBe(chaveDoAtivo(itemAtivo(e)))
  })

  it('um pedido NOVO devolve a precedência ao pendente', () => {
    const e = abrir(lido(lido(PONTOS_VAZIO, A), B), 0)
    const d = pedir(e, C.lat, C.lng)
    expect(d.abaFixada).toBe(false)
    expect(itemAtivo(d)!.lat).toBe(C.lat)
  })
})

describe('doMapa — o pin do "Selecionar ponto" não voa', () => {
  it('o pedido marcado leva a marca ao ativo e ao pin', () => {
    const e = pedir(PONTOS_VAZIO, A.lat, A.lng, null, true)
    expect(e.pendentes).toEqual([{ lat: A.lat, lng: A.lng, doMapa: true }])
    const a = itemAtivo(e)!
    expect(a.doMapa).toBe(true)
    expect(pinParaAtivo(null, a, false)).toEqual({ lat: A.lat, lng: A.lng, hexId: a.hexId, semVoo: true })
  })

  it('a lupa e a caixa de colar seguem voando (sem marca)', () => {
    const a = itemAtivo(pedir(PONTOS_VAZIO, A.lat, A.lng))!
    expect(a.doMapa).toBe(false)
    expect(pinParaAtivo(null, a, false).semVoo).toBeUndefined()
  })

  it('o pin novo da troca de município HERDA o `semVoo` do clique no mesmo lugar', () => {
    const p = pedir(PONTOS_VAZIO, A.lat, A.lng, null, true)
    const pin = pinParaAtivo(null, itemAtivo(p)!, false)
    const f = chegou(p, A, ficha(A.lat, A.lng, { uf: 'RJ', municipio: 'Rio de Janeiro' }))
    const novo = pinParaAtivo(pin, itemAtivo(f)!, true)
    expect(novo).not.toBe(pin)
    expect(novo.semVoo).toBe(true)
  })

  it('`forcar` (o operador escolheu o item) sempre dá pin NOVO e com voo', () => {
    const atual = { lat: A.lat, lng: A.lng, hexId: 'h', semVoo: true }
    const ativo = { lat: A.lat, lng: A.lng, hexId: 'h', territorio: null, doMapa: false }
    const novo = pinParaAtivo(atual, ativo, false, true)
    expect(novo).not.toBe(atual)
    expect(novo.semVoo).toBeUndefined()
  })
})

describe('movimentoDoMapa — quando o efeito do App mexe no mapa', () => {
  const k1 = '-23.48516,-46.61771|?'
  const k1Lido = '-23.48516,-46.61771|SP/São Paulo'
  const k2 = '-23.5613,-46.6565|SP/São Paulo'

  it('mesma chave e mesmo foco: nada', () => {
    expect(movimentoDoMapa({ chave: k2, foco: 3 }, { chave: k2, foco: 3 }, false)).toBe('nenhum')
  })

  it('foco subiu: focar, MESMO com a chave igual e com o ponto solto', () => {
    expect(movimentoDoMapa({ chave: k2, foco: 3 }, { chave: k2, foco: 4 }, false)).toBe('focar')
    expect(movimentoDoMapa({ chave: k2, foco: 3 }, { chave: k2, foco: 4 }, true)).toBe('focar')
  })

  it('chave nova: seguir', () => {
    expect(movimentoDoMapa({ chave: k1Lido, foco: 0 }, { chave: k2, foco: 0 }, false)).toBe('seguir')
    expect(movimentoDoMapa({ chave: null, foco: 0 }, { chave: k1, foco: 0 }, false)).toBe('seguir')
  })

  it('ponto SOLTO (o operador navegou à mão) e a leitura em voo chegou: não desfaz a navegação', () => {
    expect(movimentoDoMapa({ chave: k1, foco: 0 }, { chave: k1Lido, foco: 0 }, true)).toBe('nenhum')
    // Sem ter soltado, a mesma chegada leva o mapa ao município do ponto.
    expect(movimentoDoMapa({ chave: k1, foco: 0 }, { chave: k1Lido, foco: 0 }, false)).toBe('seguir')
  })

  it('ponto solto e um pedido NOVO: segue (o pedido devolve o comando)', () => {
    expect(movimentoDoMapa({ chave: k1Lido, foco: 0 }, { chave: k2, foco: 0 }, true)).toBe('seguir')
  })

  it('a lista esvaziou: seguir (o App apaga o pin); vazia antes e depois: nada', () => {
    expect(movimentoDoMapa({ chave: k2, foco: 0 }, { chave: null, foco: 0 }, false)).toBe('seguir')
    expect(movimentoDoMapa({ chave: null, foco: 0 }, { chave: null, foco: 0 }, false)).toBe('nenhum')
  })
})

describe('janelaNaMontagem / erroFlutuanteVisivel', () => {
  it('a ficha reabre sozinha SÓ na volta do Simulador, e só com ponto na lista', () => {
    expect(janelaNaMontagem(true, 2)).toBe(true)
    expect(janelaNaMontagem(false, 2)).toBe(false) // Executiva, ranking, imóveis
    expect(janelaNaMontagem(true, 0)).toBe(false)
  })

  it('com fichas e a caixa fechada, o erro (6o ponto, clique no mar) aparece flutuando', () => {
    expect(erroFlutuanteVisivel({ nFichas: 5, caixaAberta: false, carregando: false, erro: 'Máximo' })).toBe(true)
  })

  it('sem ficha (Explorar antes do 1o ponto) também', () => {
    expect(erroFlutuanteVisivel({ nFichas: 0, caixaAberta: true, carregando: false, erro: 'x' })).toBe(true)
  })

  it('com ficha e a caixa de colar aberta, o erro fica na caixa (sem duplicar)', () => {
    expect(erroFlutuanteVisivel({ nFichas: 2, caixaAberta: true, carregando: false, erro: 'x' })).toBe(false)
  })

  it('durante a leitura, ou sem erro, nada', () => {
    expect(erroFlutuanteVisivel({ nFichas: 2, caixaAberta: false, carregando: true, erro: 'x' })).toBe(false)
    expect(erroFlutuanteVisivel({ nFichas: 2, caixaAberta: false, carregando: false, erro: null })).toBe(false)
  })
})

/* ---------------- Alcance do ponto (DEC-074) ---------------- */
describe('alcance: o MESMO item, trocado no lugar', () => {
  /** A ficha do mesmo ponto relida em outro alcance: `lat`/`lng` = a origem clicada. */
  function emAlcance(c: { lat: number; lng: number }, tipo: 'raio_2km' | 'carro_5min' | 'carro_10min') {
    const base = ficha(c.lat, c.lng) as unknown as Record<string, unknown>
    return {
      ...base,
      raio_km: tipo === 'raio_2km' ? 2 : null,
      mercado: { disponivel: true, sam: 1, residual: 1, score_residual: 1, grao: tipo === 'raio_2km' ? 'raio' : 'geometria' },
      recorte: { tipo, area_km2: tipo === 'raio_2km' ? 12.57 : 38.2, metodo: 'x', fator_regua: tipo === 'raio_2km' ? 4 : 12.16 },
    } as unknown as PontoPayload
  }

  it('trocar o alcance substitui a ficha na MESMA posição (mesma cor, mesma aba)', () => {
    const e = lido(lido(PONTOS_VAZIO, A), B)
    const trocado = substituir(e, emAlcance(A, 'raio_2km'))
    expect(trocado.fichas).toHaveLength(2)
    expect(trocado.fichas[0].raio_km).toBe(2)
    expect(trocado.fichas[1]).toBe(e.fichas[1])
    expect(trocado.aberto).toBe(e.aberto)
    // E a isócrona também (mercado de geometria no servidor, mas é ponto).
    expect(substituir(trocado, emAlcance(A, 'carro_10min')).fichas[0].recorte?.tipo).toBe('carro_10min')
  })

  it('buscar de novo a origem de um item de alcance abre ele (não cria um segundo)', () => {
    const e = substituir(lido(PONTOS_VAZIO, A), emAlcance(A, 'carro_10min'))
    expect(decidirPedido(e, A.lat, A.lng)).toEqual({ tipo: 'repetido', indice: 0 })
  })

  it('a leitura da ficha: alcance e modo, em TODO alcance (emenda do item 6 da DEC-074)', () => {
    expect(leituraDaFicha(ficha(A.lat, A.lng))).toBe('raio_1km')
    expect(leituraDaFicha(emAlcance(A, 'raio_2km'))).toBe('raio_2km')
    expect(leituraDaFicha(emAlcance(A, 'carro_10min'))).toBe('carro_10min')
    const comUltra = (p: PontoPayload) =>
      ({ ...(p as object), mercado: { modo_estudo: 'unidade_ultra' } }) as unknown as PontoPayload
    expect(leituraDaFicha(comUltra(ficha(A.lat, A.lng)))).toBe(LEITURA_ULTRA)
    expect(LEITURA_ULTRA).toBe('raio_1km+ultra')
    // Era o defeito: fora do 1 km a leitura perdia o modo e a ficha "esquecia" o estudo.
    expect(leituraDaFicha(comUltra(emAlcance(A, 'raio_2km')))).toBe('raio_2km+ultra')
    expect(leituraDaFicha(comUltra(emAlcance(A, 'carro_5min')))).toBe('carro_5min+ultra')
    expect(leituraDaFicha(comUltra(emAlcance(A, 'carro_10min')))).toBe('carro_10min+ultra')
  })

  it('trocar o alcance PRESERVA o modo; trocar o modo PRESERVA o alcance', () => {
    expect(leituraComAlcance('raio_1km+ultra', 'carro_10min')).toBe('carro_10min+ultra')
    expect(leituraComAlcance('raio_2km', 'carro_5min')).toBe('carro_5min')
    expect(leituraComModo('carro_10min', true)).toBe('carro_10min+ultra')
    expect(leituraComModo('raio_2km+ultra', false)).toBe('raio_2km')
    expect(leituraComModo('raio_1km', true)).toBe(LEITURA_ULTRA)
    // "2 km" em voo e então "liga o estudo da unidade": o pedido é o 2 km COM o modo.
    const r1 = pedirTroca(TROCAS_VAZIO, 'k', 'raio_1km', leituraComAlcance('raio_1km', 'raio_2km'))
    const vigente = r1.trocas.emVoo.k.querido as string
    expect(leituraComModo(vigente, true)).toBe('raio_2km+ultra')
  })

  it('a leitura se desmonta em alcance + modo, e `leituraUltra` é a inversa', () => {
    expect(partesDaLeitura('carro_10min+ultra')).toEqual({ alcance: 'carro_10min', ultra: true })
    expect(partesDaLeitura('raio_2km')).toEqual({ alcance: 'raio_2km', ultra: false })
    for (const a of ['raio_1km', 'raio_2km', 'carro_5min', 'carro_10min']) {
      expect(partesDaLeitura(leituraUltra(a))).toEqual({ alcance: a, ultra: true })
    }
  })

  it('"último clique vence" entre modo e alcance: as duas trocas passam pelo MESMO registro', () => {
    const chave = 'k'
    // 2 km, depois "liga o estudo da unidade": a 1a leitura em voo é descartada.
    const r1 = pedirTroca(TROCAS_VAZIO, chave, 'raio_1km', 'raio_2km')
    const r2 = pedirTroca(r1.trocas, chave, 'raio_1km', LEITURA_ULTRA)
    if (r1.decisao.tipo !== 'ler' || r2.decisao.tipo !== 'ler') throw new Error('esperava duas leituras')
    expect(concluirTroca(r2.trocas, chave, r1.decisao.geracao).vale).toBe(false)
    expect(concluirTroca(r2.trocas, chave, r2.decisao.geracao).vale).toBe(true)
    // Voltar ao alcance que a ficha já tem cancela a leitura em voo, sem pedir outra.
    const r3 = pedirTroca(r1.trocas, chave, 'raio_1km', 'raio_1km')
    expect(r3.decisao).toEqual({ tipo: 'cancelar' })
  })

  it('o pin do item de alcance tem o contorno do recorte; o de 1 km, o círculo de 1 km', () => {
    const e = substituir(lido(lido(PONTOS_VAZIO, A), B), emAlcance(A, 'raio_2km'))
    const pins = pinsDoEstado(e)
    expect(pins[0].contornos).toHaveLength(1)
    expect(pins[1].contornos).toHaveLength(1)
    expect(pins[0].rotulo).toBe('Santana #1')
  })
})
