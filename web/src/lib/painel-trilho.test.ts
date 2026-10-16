import { describe, expect, it } from 'vitest'

import type { FerramentaMapa } from './ferramenta-mapa'
import {
  desenhoPausado,
  painelDoTrilho,
  rascunhoSobrevive,
  transicaoTrilho,
  type AcaoTrilho,
  type EstadoTrilho,
} from './painel-trilho'

const FERRAMENTAS: FerramentaMapa[] = ['nenhuma', 'ponto', 'regua', 'geometria']

describe('transicaoTrilho — exclusão mútua dos dois painéis', () => {
  it('abrir as camadas com o desenho ligado pausa o desenho (fecha o painel dele)', () => {
    const e = transicaoTrilho(
      { camadasAberto: false, ferramenta: 'geometria' },
      { tipo: 'alternar-camadas' },
    )
    expect(e).toEqual({ camadasAberto: true, ferramenta: 'nenhuma' })
    expect(painelDoTrilho(e)).toBe('camadas')
  })

  it('ligar o desenho fecha as camadas — também quando o gesto vem de dentro do painel', () => {
    const e = transicaoTrilho(
      { camadasAberto: true, ferramenta: 'nenhuma' },
      { tipo: 'alternar-ferramenta', alvo: 'geometria' },
    )
    expect(e).toEqual({ camadasAberto: false, ferramenta: 'geometria' })
    expect(painelDoTrilho(e)).toBe('desenho')
  })

  it('régua e ponto convivem com o painel de camadas aberto', () => {
    for (const alvo of ['regua', 'ponto'] as const) {
      const e = transicaoTrilho(
        { camadasAberto: true, ferramenta: 'nenhuma' },
        { tipo: 'alternar-ferramenta', alvo },
      )
      expect(e).toEqual({ camadasAberto: true, ferramenta: alvo })
    }
  })

  it('abrir as camadas com régua/ponto ligados mantém a ferramenta', () => {
    for (const ferramenta of ['regua', 'ponto'] as const) {
      const e = transicaoTrilho({ camadasAberto: false, ferramenta }, { tipo: 'alternar-camadas' })
      expect(e).toEqual({ camadasAberto: true, ferramenta })
    }
  })

  it('tocar no polígono com o desenho ligado pausa (desliga sem reabrir as camadas)', () => {
    const e = transicaoTrilho(
      { camadasAberto: false, ferramenta: 'geometria' },
      { tipo: 'alternar-ferramenta', alvo: 'geometria' },
    )
    expect(e).toEqual({ camadasAberto: false, ferramenta: 'nenhuma' })
    expect(painelDoTrilho(e)).toBeNull()
  })

  it('fechar as camadas não mexe na ferramenta', () => {
    for (const ferramenta of FERRAMENTAS) {
      expect(
        transicaoTrilho({ camadasAberto: true, ferramenta }, { tipo: 'fechar-camadas' }),
      ).toEqual({ camadasAberto: false, ferramenta })
    }
  })

  it('INVARIANTE: de qualquer estado válido, nenhuma ação deixa os dois painéis abertos', () => {
    const validos: EstadoTrilho[] = FERRAMENTAS.flatMap((ferramenta) => [
      { camadasAberto: false, ferramenta },
      { camadasAberto: true, ferramenta },
    ]).filter((e) => !(e.camadasAberto && e.ferramenta === 'geometria'))
    const acoes: AcaoTrilho[] = [
      { tipo: 'alternar-camadas' },
      { tipo: 'fechar-camadas' },
      { tipo: 'desligar-ferramenta' },
      ...FERRAMENTAS.map((alvo) => ({ tipo: 'alternar-ferramenta' as const, alvo })),
    ]
    for (const e of validos) {
      for (const a of acoes) {
        const n = transicaoTrilho(e, a)
        expect(n.camadasAberto && n.ferramenta === 'geometria').toBe(false)
      }
    }
  })

  it('painelDoTrilho: o desenho é a ferramenta ligada; sem ela, as camadas se abertas', () => {
    expect(painelDoTrilho({ camadasAberto: false, ferramenta: 'nenhuma' })).toBeNull()
    expect(painelDoTrilho({ camadasAberto: false, ferramenta: 'regua' })).toBeNull()
    expect(painelDoTrilho({ camadasAberto: true, ferramenta: 'ponto' })).toBe('camadas')
    expect(painelDoTrilho({ camadasAberto: false, ferramenta: 'geometria' })).toBe('desenho')
  })
})

describe('rascunho do desenho', () => {
  it('só a pausa guarda os vértices', () => {
    expect(rascunhoSobrevive('pausa')).toBe(true)
    for (const m of ['cancelar', 'esc', 'concluir', 'territorio'] as const) {
      expect(rascunhoSobrevive(m)).toBe(false)
    }
  })

  it('pausado = vértices guardados com a ferramenta desligada', () => {
    expect(desenhoPausado('nenhuma', 3)).toBe(true)
    expect(desenhoPausado('regua', 1)).toBe(true)
    expect(desenhoPausado('geometria', 3)).toBe(false)
    expect(desenhoPausado('nenhuma', 0)).toBe(false)
  })
})
