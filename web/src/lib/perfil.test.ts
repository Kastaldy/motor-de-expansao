import { afterEach, describe, expect, it } from 'vitest'

import { parseCoordinate } from './coord'
import { classificarEntrada } from './entrada-ponto'
import { brl } from './format'
import {
  _resetarPerfilParaTeste,
  definirPerfil,
  moeda,
  moedaRenda,
  perfilDoCliente,
  type PerfilCliente,
} from './perfil'
import { PERFIL_BR } from './perfil-br'

/** Perfil argentino de teste — a caixa real do `data/perfis/AR/perfil.json`.
 *  `indicadores_renda: 'USD'` DIVERGE de `moeda.codigo: 'ARS'` de proposito: e'
 *  exatamente a caixa real (moeda oficial ARS, renda do pacote em USD). */
const AR: PerfilCliente = {
  pais: 'AR',
  nome: 'Argentina',
  locale: 'es-AR',
  moeda: { codigo: 'ARS', simbolo: '$', indicadores_renda: 'USD' },
  bbox: { lat_min: -55.2, lat_max: -21.6, lng_min: -74.0, lng_max: -53.4 },
  vista_padrao: { lat: -38.4, lng: -63.6, zoom: 3.6 },
  reguas: { pop_min_acionavel: 5000, capacidade_unidade_alunos: 2500 },
}

afterEach(() => {
  _resetarPerfilParaTeste()
})

describe('default compilado', () => {
  it('nasce no Brasil, para os modulos puros terem numero valido no import', () => {
    // E o que mantem `colors.test.ts`, `faixas.test.ts`, `coord.test.ts` e
    // `mapa-ponto.test.ts` verdes sem uma linha de mudanca neles.
    expect(perfilDoCliente()).toBe(PERFIL_BR)
    expect(perfilDoCliente().nome).toBe('Brasil')
    expect(moeda()).toBe('R$')
  })
})

describe('definirPerfil — instala o pais da instancia', () => {
  it('troca o perfil vigente', () => {
    definirPerfil(AR)
    expect(perfilDoCliente().nome).toBe('Argentina')
    expect(moeda()).toBe('$')
  })

  it('a validacao de coordenada passa a ser a do pais novo', () => {
    // Buenos Aires: recusada sob BR, aceita sob AR. E o defeito A0 do lado do front —
    // esta linha recusava ANTES de sair requisicao.
    expect(parseCoordinate('-34.6037, -58.3816')).toBeNull()
    definirPerfil(AR)
    expect(parseCoordinate('-34.6037, -58.3816')).toEqual({
      lat: -34.6037,
      lng: -58.3816,
    })
    // e a simetria: Sao Paulo sai do bbox argentino
    expect(parseCoordinate('-23.5613, -46.6565')).toBeNull()
  })

  it('a frase de aviso nomeia o pais da instancia', () => {
    definirPerfil(AR)
    const r = classificarEntrada('-23.5613, -46.6565')
    expect(r.tipo).toBe('fora-do-brasil') // o VALOR do enum nao muda
    expect(r.aviso).toContain('fora de Argentina')
  })

  it('o formatador de moeda segue o simbolo do perfil', () => {
    expect(brl(1500)).toContain('R$')
    definirPerfil(AR)
    expect(brl(1500)).toContain('$')
    expect(brl(1500)).not.toContain('R$')
  })
})

describe('moedaRenda — o simbolo do INDICADOR de renda, nao o da moeda oficial', () => {
  it('no Brasil as duas moedas coincidem: moedaRenda() == moeda()', () => {
    expect(moedaRenda()).toBe('R$')
    expect(moedaRenda()).toBe(moeda())
  })

  it('na Argentina DIVERGE: moeda oficial e ARS, renda do pacote e USD', () => {
    definirPerfil(AR)
    expect(moeda()).toBe('$') // moeda oficial (ARS) — para aluguel, DRE, viabilidade
    expect(moedaRenda()).toBe('USD') // a coluna de renda do pacote — NUNCA "$"
    expect(moedaRenda()).not.toBe(moeda())
  })
})

describe('definirPerfil — fail-safe, e por que ele e assim', () => {
  // Derrubar a SPA por causa de um campo ausente trocaria uma degradacao por uma tela
  // branca. Quem falha ALTO quando o perfil falta e o backend, no boot do container,
  // onde a mensagem nomeia o campo e o custo de parar e baixo.
  it.each([
    ['undefined', undefined],
    ['null', null],
    ['string', 'BR'],
    ['objeto vazio', {}],
    ['sem pais', { ...AR, pais: undefined }],
    ['sem bbox', { ...AR, bbox: undefined }],
    ['bbox incompleto', { ...AR, bbox: { lat_min: -55, lat_max: -21 } }],
    ['bbox com string', { ...AR, bbox: { ...AR.bbox, lat_min: '-55.2' } }],
    ['sem reguas', { ...AR, reguas: undefined }],
    ['sem moeda', { ...AR, moeda: undefined }],
    ['sem indicadores_renda', { ...AR, moeda: { codigo: 'ARS', simbolo: '$' } }],
    ['sem vista_padrao', { ...AR, vista_padrao: undefined }],
  ])('payload %s mantem o default e nao levanta', (_nome, payload) => {
    expect(() => definirPerfil(payload)).not.toThrow()
    expect(perfilDoCliente().nome).toBe('Brasil')
  })

  it('um backend ANTERIOR ao bloco, que nao manda o campo, continua abrindo', () => {
    const payloadVelho = { usuario: 'felipe', abas: ['mapa'] } as Record<string, unknown>
    definirPerfil(payloadVelho.perfil)
    expect(perfilDoCliente().nome).toBe('Brasil')
  })
})
