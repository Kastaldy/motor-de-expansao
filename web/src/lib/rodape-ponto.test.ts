import { describe, expect, it } from 'vitest'

import {
  DICA_ESTUDO,
  DICA_ESTUDO_RECORTE,
  DICA_ESTUDO_SEM_CONTORNO,
  DICA_SIMULADOR,
  DICA_SIMULADOR_ALCANCE,
  DICA_SIMULADOR_AREA,
  DICA_SIMULADOR_VETADO,
  ROTULO_ESTUDO,
  ROTULO_ESTUDO_GERANDO,
  estadoDoEstudo,
  estadoDoSimulador,
  estiloDoBotaoEstudo,
  estiloDoBotaoSimulador,
  recorteDoEstudo,
  rotuloParaSimulador,
} from './rodape-ponto'
import { ACC, ACC_GLOW, ACC_ON } from './imovel'
import { ehAreaDesenhada } from './recorte'
import type { PontoPayload } from './types'

const ANEL: [number, number][][] = [[[-46.6, -23.5], [-46.5, -23.5], [-46.5, -23.4], [-46.6, -23.5]]]
/** A área desenhada como o servidor a devolve: o contorno no payload, `grao` de geometria. */
const areaComContorno = {
  mercado: { disponivel: true, sam: 1, residual: 1, score_residual: 1, grao: 'geometria' },
  geometria: ANEL,
  recorte: { tipo: 'poligono', area_km2: 2.4, n_vertices: 3, metodo: 'x' },
} as Pick<PontoPayload, 'mercado' | 'geometria' | 'recorte'>
/** O raio de 2 km (DEC-074): `grao` de raio, sem geometria. */
const raio2km = {
  raio_km: 2,
  mercado: { disponivel: true, sam: 1, residual: 1, score_residual: 1, grao: 'raio' },
  recorte: { tipo: 'raio_2km', area_km2: 12.57, metodo: 'x', fator_regua: 4, contorno: null },
} as Pick<PontoPayload, 'mercado' | 'raio_km' | 'recorte'>
/** A isócrona: o mercado é de GEOMETRIA no servidor, mas o item é um ponto (a origem). */
const isocrona = {
  raio_km: null,
  mercado: { disponivel: true, sam: 1, residual: 1, score_residual: 1, grao: 'geometria' },
  recorte: { tipo: 'carro_10min', area_km2: 38.2, metodo: 'x', fator_regua: 12.16 },
} as Pick<PontoPayload, 'mercado' | 'raio_km' | 'recorte'>

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

  it('área desenhada DESTRAVA o Estudo (fase 2 da DEC-071), com a dica do recorte', () => {
    const e = estadoDoEstudo(areaComContorno, false)
    expect(e).toEqual({ habilitado: true, rotulo: ROTULO_ESTUDO, dica: DICA_ESTUDO_RECORTE, travadoPorque: null })
    expect(DICA_ESTUDO_RECORTE).toMatch(/sem nenhum dado financeiro/)
  })

  it('raio de 2 km e 10 min de carro também destravam (DEC-074)', () => {
    expect(estadoDoEstudo(raio2km, false)).toMatchObject({ habilitado: true, dica: DICA_ESTUDO_RECORTE })
    expect(estadoDoEstudo(isocrona, false)).toMatchObject({ habilitado: true, dica: DICA_ESTUDO_RECORTE })
  })

  it('área cujo mercado falhou (sem `grao`) mas com contorno: destrava pela geometria', () => {
    const semGrao = {
      mercado: { disponivel: false, sam: null, residual: null, score_residual: null },
      geometria: ANEL,
    } as Pick<PontoPayload, 'mercado' | 'geometria'>
    expect(ehAreaDesenhada(semGrao)).toBe(true)
    expect(estadoDoEstudo(semGrao, false).habilitado).toBe(true)
    expect(recorteDoEstudo(semGrao)).toEqual({ geometria: { type: 'Polygon', coordinates: ANEL } })
  })

  it('área SEM contorno no payload: travada e dizendo por quê (o PDF sairia do raio)', () => {
    // Só o `grao` denuncia a área: não há vértices para mandar ao servidor.
    const e = estadoDoEstudo(areaDesenhada, false)
    expect(e.habilitado).toBe(false)
    expect(e.travadoPorque).toBe(DICA_ESTUDO_SEM_CONTORNO)
    expect(recorteDoEstudo(areaDesenhada)).toBeNull()
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

describe('recorteDoEstudo — o que vai no CORPO do pedido do PDF', () => {
  it('raio de 1 km não manda nada (o default do servidor, byte a byte igual)', () => {
    expect(recorteDoEstudo(pontoComRaio)).toEqual({})
  })

  it('raio de 2 km e isócrona mandam só o ALCANCE: o servidor recalcula o contorno', () => {
    expect(recorteDoEstudo(raio2km)).toEqual({ alcance: 'raio_2km' })
    expect(recorteDoEstudo(isocrona)).toEqual({ alcance: 'carro_10min' })
    // Nunca o polígono da isócrona: o servidor não confia em contorno mandado pela tela.
    expect(recorteDoEstudo(isocrona)).not.toHaveProperty('geometria')
  })

  it('área desenhada manda o Polygon do desenho', () => {
    expect(recorteDoEstudo(areaComContorno)).toEqual({ geometria: { type: 'Polygon', coordinates: ANEL } })
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

  it('na área desenhada a dica diz que lá o estudo é do RAIO em volta do ponto central', () => {
    expect(estadoDoSimulador(areaDesenhada, true).dica).toBe(DICA_SIMULADOR_AREA)
    expect(DICA_SIMULADOR_AREA).toMatch(/raio de 1 km/)
  })

  it('ponto de outro alcance vai pela ORIGEM, e a dica diz que lá é o raio de 1 km', () => {
    expect(estadoDoSimulador(raio2km, true)).toMatchObject({ habilitado: true, dica: DICA_SIMULADOR_ALCANCE })
    expect(estadoDoSimulador(isocrona, true).dica).toBe(DICA_SIMULADOR_ALCANCE)
    expect(DICA_SIMULADOR_ALCANCE).toMatch(/raio de 1 km/)
  })

  it('sem ficha: travado', () => {
    expect(estadoDoSimulador(null, true).habilitado).toBe(false)
  })
})

describe('rotuloParaSimulador', () => {
  it('ponto com raio segue com o próprio rótulo (com o "#k" dos homônimos)', () => {
    expect(rotuloParaSimulador(pontoComRaio, 'Centro #2')).toBe('Centro #2')
  })

  it('ponto de outro alcance segue com o nome do LUGAR (a origem), nunca "Ponto central"', () => {
    expect(rotuloParaSimulador(raio2km, 'Santana')).toBe('Santana')
    expect(rotuloParaSimulador(isocrona, 'Santana')).toBe('Santana')
  })

  it('área desenhada chega à Viabilidade como o PONTO CENTRAL dela, nunca com o nome da área', () => {
    // A Viabilidade e o PDF dela são do raio em volta do ponto: o título não pode
    // afirmar que é a área.
    expect(rotuloParaSimulador(areaDesenhada, 'Área desenhada')).toBe(
      'Ponto central da área desenhada',
    )
    expect(rotuloParaSimulador(areaDesenhada, 'Área desenhada #2')).toBe(
      'Ponto central da área desenhada #2',
    )
  })
})

/* Nota do dono (19/10/2026): os dois botões dividem o quadro ao meio; Estudo no rosa
   magenta do "Ver no Mapa Territorial" (tokens de `lib/imovel`), Simulador no azul do
   sistema (`--ac`, o primário da Viabilidade — não o `--info`). */
describe('visual do rodapé: Estudo e Simulador', () => {
  it('cada botão ocupa METADE: mesma base flex, mesma fonte e mesmo padding', () => {
    for (const h of [true, false]) {
      const e = estiloDoBotaoEstudo(h)
      const s = estiloDoBotaoSimulador(h)
      expect(e.flex).toBe('1 1 0')
      expect(s.flex).toBe(e.flex)
      expect(e.minWidth).toBe(0)
      expect(s.minWidth).toBe(0)
      expect(s.font).toBe(e.font)
      expect(s.padding).toBe(e.padding)
      expect(s.border).toBe(e.border)
    }
  })

  it('Estudo cheio no magenta da camada imobiliária, com os MESMOS tokens', () => {
    const e = estiloDoBotaoEstudo(true)
    expect(e.background).toBe(ACC)
    expect(e.color).toBe(ACC_ON)
    expect(e.boxShadow).toBe(ACC_GLOW)
  })

  it('Simulador cheio no azul do SISTEMA (--ac), nunca o --info', () => {
    const s = estiloDoBotaoSimulador(true)
    expect(s.background).toBe('var(--ac)')
    expect(s.color).toBe('var(--ac-on)')
    expect(s.boxShadow).toBe('var(--ac-glow)')
    expect(JSON.stringify(s)).not.toContain('--info')
  })

  it('travado perde só o brilho: cor e texto continuam (a dica escrita explica)', () => {
    expect(estiloDoBotaoEstudo(false)).toMatchObject({ background: ACC, color: ACC_ON, boxShadow: 'none' })
    expect(estiloDoBotaoSimulador(false)).toMatchObject({ background: 'var(--ac)', boxShadow: 'none' })
  })
})
