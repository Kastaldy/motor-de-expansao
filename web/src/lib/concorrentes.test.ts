import { describe, expect, it } from 'vitest'

import {
  LINHAS,
  SEPARACAO_MINIMA,
  reguaDeConcorrentes,
  rotuloDaRede,
  semDistancia,
} from './concorrentes'

const c = (rede: string | null, dist_km: number | null) => ({ rede, dist_km })

describe('reguaDeConcorrentes', () => {
  it('ordena por distância e posiciona entre 0 e 1', () => {
    const r = reguaDeConcorrentes([c('SF', 0.9), c('BF', 0.2), c('EC', 0.5)], 1)
    expect(r.map((p) => p.rede)).toEqual(['BF', 'EC', 'SF'])
    expect(r.map((p) => p.fracao)).toEqual([0.2, 0.5, 0.9])
  })

  it('a fração é relativa ao RAIO, não a 1 km fixo', () => {
    const r = reguaDeConcorrentes([c('SF', 0.75)], 1.5)
    expect(r[0].fracao).toBe(0.5)
  })

  it('descarta quem não tem distância — plantar no zero seria inventar vizinhança', () => {
    const r = reguaDeConcorrentes([c('SF', null), c('BF', 0.4)], 1)
    expect(r.map((p) => p.rede)).toEqual(['BF'])
    expect(semDistancia([c('SF', null), c('BF', 0.4)])).toBe(1)
  })

  it('prende na borda quem passa do raio por arredondamento', () => {
    expect(reguaDeConcorrentes([c('SF', 1.004)], 1)[0].fracao).toBe(1)
    expect(reguaDeConcorrentes([c('SF', -0.01)], 1)[0].fracao).toBe(0)
  })

  it('vizinhos colados vão para linhas diferentes', () => {
    const r = reguaDeConcorrentes([c('A', 0.20), c('B', 0.21), c('C', 0.22)], 1)
    expect(r.map((p) => p.linha)).toEqual([0, 1, 2])
  })

  it('vizinhos separados voltam todos para a primeira linha', () => {
    const r = reguaDeConcorrentes([c('A', 0.1), c('B', 0.5), c('C', 0.9)], 1)
    expect(r.every((p) => p.linha === 0)).toBe(true)
  })

  it('empilhamento cicla e nunca passa do número de linhas', () => {
    const muitos = Array.from({ length: 9 }, (_, i) => c(`R${i}`, 0.3 + i * 0.001))
    const r = reguaDeConcorrentes(muitos, 1)
    expect(r.every((p) => p.linha >= 0 && p.linha < LINHAS)).toBe(true)
  })

  it('a separação mínima é o limite exato entre mesma linha e linha nova', () => {
    const iguais = reguaDeConcorrentes([c('A', 0), c('B', SEPARACAO_MINIMA)], 1)
    expect(iguais.map((p) => p.linha)).toEqual([0, 0])
    const colados = reguaDeConcorrentes([c('A', 0), c('B', SEPARACAO_MINIMA - 0.001)], 1)
    expect(colados.map((p) => p.linha)).toEqual([0, 1])
  })

  it('rede vazia vira rótulo genérico em vez de espaço em branco', () => {
    expect(reguaDeConcorrentes([c(null, 0.3), c('  ', 0.8)], 1).map((p) => p.rede)).toEqual([
      'Concorrente',
      'Concorrente',
    ])
  })

  it('o identificador da rede NÃO vaza cru para a tela', () => {
    expect(reguaDeConcorrentes([c('smart_fit', 0.4)], 1)[0].rede).toBe('Smart Fit')
  })
})

describe('rotuloDaRede', () => {
  it('converte o identificador em texto de gente', () => {
    expect(rotuloDaRede('smart_fit')).toBe('Smart Fit')
    expect(rotuloDaRede('bluefit')).toBe('Bluefit')
    expect(rotuloDaRede('body_tech_premium')).toBe('Body Tech Premium')
  })

  it('não estraga o que já vem legível', () => {
    expect(rotuloDaRede('Smart Fit')).toBe('Smart Fit')
  })

  it('sobrevive a underscores repetidos e espaços nas pontas', () => {
    expect(rotuloDaRede('  smart__fit  ')).toBe('Smart Fit')
  })

  it('ausente ou vazio cai no rótulo genérico', () => {
    expect(rotuloDaRede(null)).toBe('Concorrente')
    expect(rotuloDaRede('   ')).toBe('Concorrente')
  })

  it('lista vazia, ausente ou raio inválido não desenham nada', () => {
    expect(reguaDeConcorrentes([], 1)).toEqual([])
    expect(reguaDeConcorrentes(null, 1)).toEqual([])
    expect(reguaDeConcorrentes([c('SF', 0.5)], 0)).toEqual([])
    expect(semDistancia(null)).toBe(0)
  })
})
