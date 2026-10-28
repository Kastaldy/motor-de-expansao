/**
 * O FIO do alcance: ficha do ponto -> Simulador (Viabilidade) -> PDF completo (DEC-074,
 * Emenda 4).
 *
 * O relato do Vinicius (27/10/2026): "selecionei uma coordenada com deslocamento de 5
 * minutos, fui para a Viabilidade e fiz o estudo dela, mas o relatório saiu com
 * deslocamento de 1 km". O alcance se perdia em três elos do front — o `PontoEscolhido` não
 * tinha o campo, `parametrosRelatorioPontual` não o repassava e `api.relatorioPontual` o
 * descartava fora do Estudo — e a rota recusava o recorte sem `so_estudo`. Cada elo puro tem
 * teste no próprio módulo; aqui ficam (1) o fio inteiro pelas funções puras e (2) as
 * costuras das TELAS, que o Vitest (sem DOM) só alcança pelo FONTE, no molde de
 * `botao-simulador.test`.
 */
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'

import { describe, expect, it } from 'vitest'

import { parametrosRelatorioPontual } from './report'
import { alcanceParaSimulador } from './rodape-ponto'
import type { PontoPayload } from './types'

const ler = (rel: string) => readFileSync(fileURLToPath(new URL(rel, import.meta.url)), 'utf-8')
const app = ler('../App.tsx')
const pontoScreen = ler('../screens/PontoScreen.tsx')
const viabScreen = ler('../screens/ViabilityScreen.tsx')

/** A ficha de um ponto lido em 5 min de carro, como a rota de alcance a devolve. */
const fichaCincoMin = {
  raio_km: null,
  mercado: { disponivel: true, sam: 1, residual: 1, score_residual: 1, grao: 'geometria' },
  recorte: { tipo: 'carro_5min', area_km2: 3.19, metodo: 'x', fator_regua: 1.01 },
} as Pick<PontoPayload, 'mercado' | 'raio_km' | 'recorte'>

/** A mesma ficha no raio de 1 km de sempre. */
const fichaUmKm = {
  raio_km: 1,
  mercado: { disponivel: true, sam: 1, residual: 1, score_residual: 1, grao: 'raio' },
} as Pick<PontoPayload, 'mercado' | 'raio_km'>

const DO_SIMULADOR = { hex: { lat: -23.5, lng: -46.6 }, rotulo: 'Santana', lat: -23.5025, lng: -46.6253 }

describe('o alcance da ficha chega ao PDF do Simulador', () => {
  it('ficha em 5 min de carro -> ponto do Simulador -> pedido do PDF com o alcance', () => {
    const ponto = { ...DO_SIMULADOR, ...alcanceParaSimulador(fichaCincoMin) }
    expect(parametrosRelatorioPontual(ponto)).toMatchObject({
      alcance: 'carro_5min',
      lat: -23.5025,
      lng: -46.6253,
      origemCentroideHex: false,
    })
  })

  it('ficha no raio de 1 km -> o pedido de sempre, sem o campo', () => {
    const ponto = { ...DO_SIMULADOR, ...alcanceParaSimulador(fichaUmKm) }
    expect('alcance' in parametrosRelatorioPontual(ponto)).toBe(false)
  })
})

describe('as costuras das telas (pelo fonte)', () => {
  it('o PontoEscolhido tem o campo do alcance', () => {
    const tipo = app.slice(app.indexOf('export interface PontoEscolhido'), app.indexOf('export default function App'))
    expect(tipo).toMatch(/\n\s*alcance\?: Alcance\n/)
  })

  it('o botão Simulador leva o alcance da ficha', () => {
    const inicio = pontoScreen.indexOf('const irParaSimulador')
    expect(inicio).toBeGreaterThan(-1)
    const corpo = pontoScreen.slice(inicio, pontoScreen.indexOf('\n  }\n', inicio))
    expect(corpo).toContain('...alcanceParaSimulador(ficha)')
  })

  it('a Viabilidade repassa o ponto ao PDF e mostra o recorte no botão e no aviso', () => {
    const inicio = viabScreen.indexOf('async function gerarPdf()')
    expect(inicio).toBeGreaterThan(-1)
    const corpo = viabScreen.slice(inicio, viabScreen.indexOf('\n  }\n', inicio))
    expect(corpo).toContain('...parametrosRelatorioPontual(ponto,')
    expect(viabScreen).toContain('title={dicaDoRelatorioCompleto(ponto.alcance)}')
    expect(viabScreen).toContain('avisoDoRecorteDoRelatorio(ponto.alcance)')
  })
})
