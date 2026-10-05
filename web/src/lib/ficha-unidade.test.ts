import { describe, expect, it } from 'vitest'

import {
  ORDEM_COMODIDADES,
  ROTULO_COMODIDADE,
  TOLERANCIA_PIN_UNIDADE_M,
  estadoDasComodidades,
  itensDeclarados,
  modalidadesDoCanal,
  nomeDoConcorrente,
  planosDoConcorrente,
  unidadeDoPin,
  unidadesDaUf,
} from './ficha-unidade'
import type { RedeComodidadesCanal, RedeMapaConcorrente, RedeUnidade } from './types'

const canal = (itens: Partial<RedeComodidadesCanal['itens']> = {}): RedeComodidadesCanal => ({
  fonte: 'wellhub',
  nome: 'Academia',
  itens: {
    musculacao: null,
    luta: null,
    armario: null,
    chuveiro: null,
    vestiario: null,
    massagem: null,
    cadeira_massagem: null,
    ...itens,
  },
  lista: [],
  atividades: [],
  data_coleta: '2026-09-29',
})

const concorrente = (campos: Partial<RedeMapaConcorrente> = {}): RedeMapaConcorrente => ({
  lat: -23,
  lng: -46,
  nome: 'Bluefit Centro',
  rede: 'bluefit',
  classe: 'cadeia',
  distancia_m: 300,
  nota_wellhub: null,
  avaliacoes: null,
  vulnerabilidade: null,
  ...campos,
})

const unidade = (campos: Partial<RedeUnidade>): RedeUnidade =>
  ({ id: 'u', nome: 'Unidade', uf: 'SP', lat: -23.5, lng: -46.6, ...campos }) as RedeUnidade

describe('unidadesDaUf', () => {
  const rede = [
    unidade({ id: 'b', nome: 'Suzano', uf: 'SP' }),
    unidade({ id: 'c', nome: 'Botafogo', uf: 'RJ' }),
    unidade({ id: 'a', nome: 'Aclimação', uf: 'sp ' }),
  ]

  it('lista so as unidades do estado, por nome', () => {
    expect(unidadesDaUf(rede, 'SP').map((u) => u.id)).toEqual(['a', 'b'])
    expect(unidadesDaUf(rede, 'rj').map((u) => u.id)).toEqual(['c'])
  })

  it('sem estado escolhido nao lista nada — e nao muta a carteira', () => {
    expect(unidadesDaUf(rede, '')).toEqual([])
    expect(rede.map((u) => u.id)).toEqual(['b', 'c', 'a'])
  })
})

describe('unidadeDoPin', () => {
  const rede = [
    unidade({ id: 'perto', lat: -23.5005, lng: -46.6 }), // ~56 m
    unidade({ id: 'longe', lat: -23.52, lng: -46.6 }), // ~2,2 km
    unidade({ id: 'sem-ponto', lat: null, lng: null }),
  ]

  it('casa o pin com a unidade mais proxima dentro da tolerancia', () => {
    expect(unidadeDoPin({ lat: -23.5, lng: -46.6 }, rede)?.id).toBe('perto')
    expect(unidadeDoPin({ lat: -23.5201, lng: -46.6 }, rede)?.id).toBe('longe')
  })

  it('pin de unidade fora da base da rede nao abre a ficha da vizinha', () => {
    // Ha' unidade desenhada no mapa que ainda nao esta' na carteira: sem par, sem ficha.
    expect(unidadeDoPin({ lat: -23.51, lng: -46.6 }, rede)).toBeNull()
    expect(unidadeDoPin({ lat: -23.5, lng: -46.6 }, [])).toBeNull()
    expect(TOLERANCIA_PIN_UNIDADE_M).toBeLessThan(1000)
  })
})

describe('estadoDasComodidades', () => {
  it('base ausente e academia nao coletada sao estados DIFERENTES', () => {
    expect(estadoDasComodidades({ comodidades: null })).toBe('indisponivel')
    // Backend anterior a base: a chave nem vem.
    expect(estadoDasComodidades({})).toBe('indisponivel')
    expect(estadoDasComodidades({ comodidades: { recorrente: null, agregador: null } })).toBe(
      'nao_coletada',
    )
  })

  it('basta um canal para a academia contar como coletada', () => {
    expect(estadoDasComodidades({ comodidades: { recorrente: canal(), agregador: null } })).toBe(
      'coletada',
    )
    expect(estadoDasComodidades({ comodidades: { recorrente: null, agregador: canal() } })).toBe(
      'coletada',
    )
  })
})

describe('itensDeclarados', () => {
  it('lista so o que a fonte DECLAROU, rotulado e na ordem do coletor', () => {
    expect(
      itensDeclarados(canal({ chuveiro: true, musculacao: true, cadeira_massagem: true })),
    ).toEqual(['Musculação', 'Chuveiro', 'Cadeira de massagem'])
  })

  it('nao declarado nao vira item — e canal ausente nao estoura', () => {
    expect(itensDeclarados(canal())).toEqual([])
    expect(itensDeclarados(null)).toEqual([])
    expect(itensDeclarados(undefined)).toEqual([])
  })

  it('todo item do coletor tem rotulo de exibicao', () => {
    for (const item of ORDEM_COMODIDADES) expect(ROTULO_COMODIDADE[item].trim()).not.toBe('')
    expect(ORDEM_COMODIDADES).toHaveLength(7)
  })
})

describe('planosDoConcorrente', () => {
  it('traz os dois agregadores, cada um com o plano e o preco dele', () => {
    const planos = planosDoConcorrente(
      concorrente({
        plano_wellhub: 'Basic',
        preco_plano_wellhub: 69.99,
        plano: 'TP 1',
        preco_plano: 109.9,
      }),
    )
    expect(planos).toEqual([
      { agregador: 'wellhub', rotulo: 'Wellhub', plano: 'Basic', preco: 69.99 },
      { agregador: 'totalpass', rotulo: 'TotalPass', plano: 'TP 1', preco: 109.9 },
    ])
  })

  it('plano sem preco continua aparecendo: preco de teste e nulo, o plano nao', () => {
    expect(planosDoConcorrente(concorrente({ plano: 'TP Free', preco_plano: null }))).toEqual([
      { agregador: 'totalpass', rotulo: 'TotalPass', plano: 'TP Free', preco: null },
    ])
  })

  it('o bloco `agregadores` vence as chaves soltas — ele acha o plano tambem pela rede', () => {
    const planos = planosDoConcorrente(
      concorrente({
        plano: null,
        plano_wellhub: null,
        agregadores: {
          wellhub: { plano: 'Silver', preco: 149.99, casado_por: 'rede' },
          totalpass: null,
        },
      }),
    )
    expect(planos).toEqual([{ agregador: 'wellhub', rotulo: 'Wellhub', plano: 'Silver', preco: 149.99 }])
  })

  it('bloco presente e vazio = nenhum agregador identificado, sem cair no fallback', () => {
    expect(
      planosDoConcorrente(
        concorrente({ plano: 'TP 1', agregadores: { wellhub: null, totalpass: null } }),
      ),
    ).toEqual([])
  })

  it('sem plano casado nao afirma agregador nenhum', () => {
    expect(planosDoConcorrente(concorrente())).toEqual([])
    expect(planosDoConcorrente(concorrente({ plano: null, plano_wellhub: null }))).toEqual([])
  })
})

describe('modalidadesDoCanal', () => {
  it('devolve o que a fonte declara, na ordem dela, sem vazio nem repeticao', () => {
    const c = { ...canal(), atividades: ['Musculação', ' Muay Thai ', '', 'musculação', 'Yoga'] }
    expect(modalidadesDoCanal(c)).toEqual(['Musculação', 'Muay Thai', 'Yoga'])
  })

  it('canal que nao declara modalidade devolve lista vazia, nunca uma afirmacao', () => {
    expect(modalidadesDoCanal(canal())).toEqual([])
    expect(modalidadesDoCanal(null)).toEqual([])
    expect(modalidadesDoCanal(undefined)).toEqual([])
  })

  it('payload de backend anterior, sem a chave, nao quebra a ficha', () => {
    const antigo = { ...canal() } as Partial<RedeComodidadesCanal>
    delete antigo.atividades
    expect(modalidadesDoCanal(antigo as RedeComodidadesCanal)).toEqual([])
  })
})

describe('nomeDoConcorrente', () => {
  it('cai para a rede e depois para o generico', () => {
    expect(nomeDoConcorrente({ nome: 'Bluefit Centro', rede: 'bluefit' })).toBe('Bluefit Centro')
    expect(nomeDoConcorrente({ nome: null, rede: 'bluefit' })).toBe('bluefit')
    expect(nomeDoConcorrente({ nome: ' ', rede: null })).toBe('Academia sem nome na base')
  })
})
