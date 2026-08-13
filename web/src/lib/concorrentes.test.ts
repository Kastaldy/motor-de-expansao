import { describe, expect, it } from 'vitest'

import {
  leituraDeAglomeracao,
  reguaDeConcorrentes,
  rotuloDaRede,
  semDistancia,
} from './concorrentes'

const c = (rede: string | null, dist_km: number | null) => ({ rede, dist_km })

describe('leituraDeAglomeracao', () => {
  // Raio de 1,0 km (DEC-021) -> o terço do corte é 333 m.
  const regua = (...dists: number[]) => reguaDeConcorrentes(dists.map((d) => c('SF', d)), 1)

  it('separa os dois territórios que "4 concorrentes" funde: todos colados', () => {
    const l = leituraDeAglomeracao(regua(0.1, 0.2, 0.3), 1)
    expect(l?.perto).toBe(3)
    expect(l?.frase).toBe('Todos os 3 estão a menos de 333 m: a disputa é na porta.')
  })

  it('...e todos na borda', () => {
    const l = leituraDeAglomeracao(regua(0.8, 0.9, 1.0), 1)
    expect(l?.perto).toBe(0)
    expect(l?.borda).toBe(3)
    expect(l?.frase).toBe('Nenhum concorrente a menos de 333 m — a pressão vem de fora, não da esquina.')
  })

  it('maioria perto ainda pesa como perto', () => {
    const l = leituraDeAglomeracao(regua(0.1, 0.2, 0.9), 1)
    expect(l?.frase).toBe(
      '2 dos 3 concorrentes estão a menos de 333 m: o peso da disputa é perto do imóvel.',
    )
  })

  it('minoria perto diz que o resto se espalha', () => {
    const l = leituraDeAglomeracao(regua(0.1, 0.7, 0.8, 0.9), 1)
    expect(l?.frase).toBe(
      'Só 1 dos 4 está a menos de 333 m; o resto se espalha até a borda do raio.',
    )
  })

  it('singular não sai agramatical', () => {
    expect(leituraDeAglomeracao(regua(0.1), 1)?.frase).toBe(
      'O único concorrente do raio está a menos de 333 m — a disputa é na porta.',
    )
  })

  it('o corte acompanha o raio, em vez de ser 333 fixo', () => {
    expect(leituraDeAglomeracao(regua(0.1), 1.5)?.corteM).toBe(500)
  })

  it('sem ponto posicionável não inventa leitura', () => {
    expect(leituraDeAglomeracao([], 1)).toBeNull()
    expect(leituraDeAglomeracao(regua(0.5), 0)).toBeNull()
  })
})

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

  it('concorrentes concentrados NÃO se atropelam — cada um é uma linha', () => {
    // O caso que quebrou a primeira versão: cinco redes agrupadas na mesma faixa.
    const r = reguaDeConcorrentes(
      [c('A', 0.45), c('B', 0.48), c('C', 0.78), c('D', 0.87), c('E', 0.96)],
      1,
    )
    expect(r).toHaveLength(5)
    expect(r.map((p) => p.rede)).toEqual(['A', 'B', 'C', 'D', 'E'])
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
