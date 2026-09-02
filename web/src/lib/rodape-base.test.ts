import { afterEach, describe, expect, it } from 'vitest'

import { _resetarPerfilParaTeste, definirPerfil, type PerfilCliente } from './perfil'
import {
  censoDaBase,
  institutoDoCenso,
  nomeDasUnidades,
  rodapeDaBase,
  tituloEscolhaUnidade,
} from './rodape-base'

/**
 * Estes testes mudaram de eixo em 2026-09-02, e vale registrar por que.
 *
 * Antes eles passavam LISTAS DE UFs e esperavam que o modulo deduzisse o pais
 * (`['BS','CA','MZ','TU']` -> Argentina). A deducao era por disjuncao binaria — todas as
 * siglas brasileiras -> Brasil, nenhuma -> Argentina — e o Bloco A (DEC-047) a substituiu
 * pelo PERFIL da instancia.
 *
 * Entao o que se exercita agora e o que passou a existir: o pais vem do perfil, e a lista
 * de UFs serve so para CONTAR. A troca nao e cosmetica — a deducao acertava com dois
 * paises e carimbaria a Argentina na Colombia.
 */

/** Perfil argentino, no formato que `/api/me` entrega. */
const AR: PerfilCliente = {
  pais: 'AR',
  nome: 'Argentina',
  locale: 'es-AR',
  moeda: { codigo: 'ARS', simbolo: '$' },
  bbox: { lat_min: -55.2, lat_max: -21.6, lng_min: -74.0, lng_max: -53.4 },
  vista_padrao: { lat: -38.4, lng: -63.6, zoom: 3.6 },
  reguas: { pop_min_acionavel: 5000, capacidade_unidade_alunos: 2500 },
}

/** Um TERCEIRO pais — o caso que a deducao binaria nao sabia representar. */
const CO: PerfilCliente = { ...AR, pais: 'CO', nome: 'Colômbia', locale: 'es-CO' }

const TRES = ['SP', 'RJ', 'MG']
const QUATRO = ['BS', 'CA', 'MZ', 'TU']

afterEach(() => {
  _resetarPerfilParaTeste()
})

describe('rodapeDaBase', () => {
  it('credita o IBGE e a rede Ultra na instancia brasileira', () => {
    expect(rodapeDaBase(TRES)).toBe(
      '3 estados · Censo 2022 (IBGE) + rede Ultra e concorrentes mapeados · camada visual read-only',
    )
  })

  it('credita o INDEC e NAO promete rede Ultra na instancia argentina', () => {
    definirPerfil(AR)
    const t = rodapeDaBase(QUATRO)
    expect(t).toBe(
      '4 províncias · Censo 2022 (INDEC) + concorrentes mapeados · camada visual read-only',
    )
    // O projeto argentino e' greenfield: nao ha uma unidade Ultra no pais.
    expect(t).not.toContain('Ultra')
    expect(t).not.toContain('IBGE')
    expect(t).not.toContain('estados')
  })

  it('a CONTAGEM vem da base e o PAIS vem do perfil — sao fontes diferentes', () => {
    // A mesma lista de siglas produz frases diferentes conforme a instancia. Sob a
    // deducao antiga isso era impossivel: a lista DETERMINAVA o pais.
    expect(rodapeDaBase(QUATRO)).toContain('4 estados')
    definirPerfil(AR)
    expect(rodapeDaBase(QUATRO)).toContain('4 províncias')
  })

  it('a contagem vem da BASE, nunca de uma constante', () => {
    expect(rodapeDaBase(['SP'])).toContain('1 estado ·')
    expect(rodapeDaBase(Array.from({ length: 27 }, () => 'SP'))).toContain('27 estados')
  })

  it('sem base nao inventa frase — quem chama nao desenha nada', () => {
    expect(rodapeDaBase([])).toBeNull()
    expect(rodapeDaBase(null)).toBeNull()
  })

  it('pais SEM vocabulario nestas tabelas conta e cala sobre censo e pontos', () => {
    // Substitui o antigo caso de "base misturada", que deixou de existir junto com a
    // deducao. O ramo de degradacao continua, com motivo melhor: era "nao sei o pais",
    // passou a ser "sei o pais e ainda nao traduzi a palavra dele".
    definirPerfil(CO)
    const t = rodapeDaBase(['AN', 'CU'])
    expect(t).toBe('2 unidades federativas · camada visual read-only')
    expect(t).not.toContain('Censo')
    expect(t).not.toContain('INDEC')
  })
})

describe('nomeDasUnidades', () => {
  it('concorda em genero e numero', () => {
    expect(nomeDasUnidades(TRES)).toBe('os 3 estados')
    expect(nomeDasUnidades(['SP'])).toBe('o estado')
    definirPerfil(AR)
    expect(nomeDasUnidades(QUATRO)).toBe('as 4 províncias')
    expect(nomeDasUnidades(['MZ'])).toBe('a província')
  })

  it('degrada para termo neutro sem base ou sem vocabulario', () => {
    expect(nomeDasUnidades([])).toBe('as unidades federativas')
    definirPerfil(CO)
    expect(nomeDasUnidades(['AN', 'CU'])).toBe('as unidades federativas')
  })
})

describe('as frases que citam a FONTE', () => {
  it('seguem o pais da instancia', () => {
    expect(censoDaBase()).toBe('Censo 2022 (IBGE)')
    expect(institutoDoCenso()).toBe('IBGE')
    expect(tituloEscolhaUnidade()).toBe('Escolha o estado')

    definirPerfil(AR)
    expect(censoDaBase()).toBe('Censo 2022 (INDEC)')
    expect(institutoDoCenso()).toBe('INDEC')
    expect(tituloEscolhaUnidade()).toBe('Escolha a província')
  })

  it('calam num pais sem vocabulario, em vez de creditar o instituto errado', () => {
    // Era o defeito exato que `institutoDoCenso` tinha ate 2026-09-02: um ternario
    // `pais === 'BR' ? 'IBGE' : 'INDEC'` creditaria o INDEC a Colombia.
    definirPerfil(CO)
    expect(censoDaBase()).toBeNull()
    expect(institutoDoCenso()).toBeNull()
    expect(tituloEscolhaUnidade()).toBe('Escolha a unidade federativa')
  })
})
