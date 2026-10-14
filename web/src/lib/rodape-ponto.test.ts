import { describe, expect, it } from 'vitest'

import {
  DICA_ESTUDO,
  DICA_ESTUDO_GEOMETRIA,
  DICA_SIMULADOR,
  DICA_SIMULADOR_VETADO,
  ROTULO_ESTUDO,
  ROTULO_ESTUDO_GERANDO,
  ehAreaDesenhada,
  estadoDoEstudo,
  estadoDoSimulador,
} from './rodape-ponto'
import type { PontoPayload } from './types'

const pontoComRaio = { mercado: { disponivel: true, sam: 1, residual: 1, score_residual: 1, grao: 'raio' } } as Pick<
  PontoPayload,
  'mercado'
>
const areaDesenhada = {
  mercado: { disponivel: true, sam: 1, residual: 1, score_residual: 1, grao: 'geometria' },
} as Pick<PontoPayload, 'mercado'>

describe('estadoDoEstudo', () => {
  it('ponto com raio: habilitado, com a dica do PDF só demográfico', () => {
    expect(estadoDoEstudo(pontoComRaio, false)).toEqual({
      habilitado: true,
      rotulo: ROTULO_ESTUDO,
      dica: DICA_ESTUDO,
      travadoPorque: null,
    })
  })

  it('a dica promete o que o PDF entrega: nenhum dado financeiro', () => {
    expect(DICA_ESTUDO).toMatch(/sem nenhum dado financeiro/)
  })

  it('gerando: travado e com o rótulo de espera (evita o PDF duplicado)', () => {
    const e = estadoDoEstudo(pontoComRaio, true)
    expect(e.habilitado).toBe(false)
    expect(e.rotulo).toBe(ROTULO_ESTUDO_GERANDO)
    // O spinner e o rótulo já explicam a trava: nada de linha extra embaixo.
    expect(e.travadoPorque).toBeNull()
  })

  it('área desenhada: travado, com a explicação da próxima fase (DEC-071)', () => {
    const e = estadoDoEstudo(areaDesenhada, false)
    expect(e.habilitado).toBe(false)
    expect(e.dica).toBe(DICA_ESTUDO_GEOMETRIA)
    expect(e.travadoPorque).toBe(DICA_ESTUDO_GEOMETRIA)
  })

  it('área desenhada cujo mercado falhou (sem `grao`) continua travada pela geometria', () => {
    const semGrao = {
      mercado: { disponivel: false, sam: null, residual: null, score_residual: null },
      geometria: [[[-46.6, -23.5], [-46.5, -23.5], [-46.5, -23.4], [-46.6, -23.5]]],
    } as Pick<PontoPayload, 'mercado' | 'geometria'>
    expect(ehAreaDesenhada(semGrao)).toBe(true)
    expect(estadoDoEstudo(semGrao, false).habilitado).toBe(false)
  })

  it('sem ficha aberta: travado', () => {
    expect(estadoDoEstudo(null, false).habilitado).toBe(false)
  })

  it('payload sem `grao` (antes da DEC-070) é ponto com raio', () => {
    const antigo = { mercado: { disponivel: true, sam: 1, residual: 1, score_residual: 1 } } as Pick<
      PontoPayload,
      'mercado'
    >
    expect(ehAreaDesenhada(antigo)).toBe(false)
    expect(estadoDoEstudo(antigo, false).habilitado).toBe(true)
  })
})

describe('estadoDoSimulador', () => {
  it('liberado e com ficha: habilitado', () => {
    expect(estadoDoSimulador(pontoComRaio, true)).toMatchObject({ habilitado: true, dica: DICA_SIMULADOR })
  })

  it('aba Viabilidade vetada: travado COM o motivo, nunca morto em silêncio', () => {
    const e = estadoDoSimulador(pontoComRaio, false)
    expect(e.habilitado).toBe(false)
    expect(e.dica).toBe(DICA_SIMULADOR_VETADO)
    expect(e.travadoPorque).toBe(DICA_SIMULADOR_VETADO)
  })

  it('a área desenhada vai ao Simulador pelo ponto representativo: não trava', () => {
    expect(estadoDoSimulador(areaDesenhada, true).habilitado).toBe(true)
  })

  it('sem ficha: travado', () => {
    expect(estadoDoSimulador(null, true).habilitado).toBe(false)
  })
})
