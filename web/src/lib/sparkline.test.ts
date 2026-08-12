import { describe, expect, it } from 'vitest'

import {
  ancoraDoRotulo,
  caminhoSparkline,
  escalaDeBarras,
  fatiasDeRosca,
  ladoDoRotulo,
  percentualDaFatia,
} from './sparkline'

describe('caminhoSparkline', () => {
  it('desenha a série e marca o último ponto', () => {
    const s = caminhoSparkline([1, 2, 3, 4], 100, 20)
    expect(s.linha.startsWith('M')).toBe(true)
    expect(s.linha.split('L')).toHaveLength(4)
    expect(s.ultimo).not.toBeNull()
    expect(s.minimo).toBe(1)
    expect(s.maximo).toBe(4)
  })

  it('série toda igual não divide por zero', () => {
    // Uma unidade estável desenharia NaN no caminho e sumiria da tela sem erro nenhum.
    const s = caminhoSparkline([500, 500, 500], 100, 20)
    expect(s.linha).not.toContain('NaN')
    expect(s.linha).toContain('10.00') // reta no meio da caixa
  })

  it('um ponto só não estoura', () => {
    const s = caminhoSparkline([42], 100, 20)
    expect(s.linha).not.toContain('NaN')
    expect(s.area).toBe('')
  })

  it('série vazia devolve caminho vazio', () => {
    expect(caminhoSparkline([], 100, 20)).toMatchObject({ linha: '', area: '', ultimo: null })
    expect(caminhoSparkline([null, null], 100, 20).linha).toBe('')
  })

  it('buraco no meio não vira NaN nem quebra a linha', () => {
    const s = caminhoSparkline([10, null, 30], 100, 20)
    expect(s.linha).not.toContain('NaN')
    expect(s.linha.split('L')).toHaveLength(2)
  })

  it('maior valor fica no topo da caixa', () => {
    const s = caminhoSparkline([0, 100], 100, 20, 0)
    expect(s.ultimo?.y).toBeCloseTo(0)
  })

  it('`xs` tem um x por índice, buracos inclusive', () => {
    // Quem desenha o rótulo de cada mês indexa por posição na série, não por posição
    // entre os pontos que sobreviveram: pular o buraco deslocaria todos os seguintes.
    const s = caminhoSparkline([10, null, 30], 100, 20)
    expect(s.xs).toHaveLength(3)
    expect(s.xs[2]).toBeGreaterThan(s.xs[1])
  })

  it('série vazia ainda devolve os x — o eixo existe mesmo sem linha', () => {
    expect(caminhoSparkline([null, null], 100, 20).xs).toHaveLength(2)
  })

  it('`ys` pousa na altura exata do ponto, e é null no buraco', () => {
    // O rótulo de valor lê daqui. Se divergir do caminho, o número flutua ao lado do
    // ponto que ele nomeia — e ninguém percebe, porque os dois continuam plausíveis.
    const s = caminhoSparkline([10, null, 30], 100, 20, 0)
    expect(s.ys[1]).toBeNull()
    expect(s.ys[0]).toBeCloseTo(20) // menor valor, no pé da caixa
    expect(s.ys[2]).toBeCloseTo(0) // maior valor, no topo
    expect(s.ultimo?.y).toBeCloseTo(s.ys[2] as number)
  })

  it('a folga afasta o menor ponto do pé da caixa (é o que dá espaço ao rótulo)', () => {
    // Com folga 6 o ponto mais baixo ficava a 5 px do eixo e o rótulo que desce saía
    // riscado pela linha do eixo; a folga é o único parâmetro que abre esse espaço.
    const justo = caminhoSparkline([1, 2], 100, 200, 6)
    const folgado = caminhoSparkline([1, 2], 100, 200, 15)
    expect(justo.ys[0]).toBeCloseTo(194)
    expect(folgado.ys[0]).toBeCloseTo(185)
  })

  it('série toda igual põe todo mundo no meio, sem NaN', () => {
    const s = caminhoSparkline([7, 7, 7], 100, 20)
    expect(s.ys).toEqual([10, 10, 10])
  })
})

describe('caminhoSparkline · distribuição', () => {
  it('`pontas` encosta nas duas bordas', () => {
    const s = caminhoSparkline([1, 2, 3], 100, 20, 0, 'pontas')
    expect(s.xs).toEqual([0, 50, 100])
  })

  it('`faixas` centra cada ponto na sua fatia, como a barra do mesmo mês', () => {
    // 4 fatias de 25 px: 12,5 / 37,5 / 62,5 / 87,5. É o x em que `BarrasPeriodo` põe a
    // barra, e é onde o rótulo do eixo (um flex de 4 partes iguais) fica centrado.
    expect(caminhoSparkline([1, 2, 3, 4], 100, 20, 0, 'faixas').xs).toEqual([12.5, 37.5, 62.5, 87.5])
  })

  it('em `faixas` nenhum ponto encosta na borda — nem com um valor só', () => {
    // Encostar é o sintoma de ter voltado para `pontas`: com um ponto só, `pontas`
    // devolveria o padding e a marca subiria na borda esquerda em vez do centro.
    const s = caminhoSparkline([42], 100, 20, 6, 'faixas')
    expect(s.xs).toEqual([50])
    expect(s.ultimo?.x).toBe(50)
  })

  it('o desenho ocupa a largura INTEIRA que recebe', () => {
    // A regressão de 2026-08-11 não estava aqui — estava no `viewBox` de 340 px que o
    // componente passava para um cartão de 936 —, mas é aqui que ela fica visível: se a
    // largura recebida crescer, o último ponto tem de crescer junto.
    const estreito = caminhoSparkline([1, 2, 3], 340, 20, 6, 'faixas')
    const largo = caminhoSparkline([1, 2, 3], 936, 20, 6, 'faixas')
    expect(largo.xs[2] / estreito.xs[2]).toBeCloseTo(936 / 340)
  })
})

describe('escalaDeBarras', () => {
  it('escala pela maior barra, com base em ZERO', () => {
    // Base no mínimo faria uma variação de 2% parecer queda pela metade — é o
    // defeito da escala congelada do bloco diário da planilha do time.
    expect(escalaDeBarras([50, 100])).toEqual([0.5, 1])
  })

  it('série toda zero não divide por zero', () => {
    expect(escalaDeBarras([0, 0])).toEqual([0, 0])
  })

  it('negativo mantém o sinal e escala pelo módulo', () => {
    expect(escalaDeBarras([-100, 50])).toEqual([-1, 0.5])
  })

  it('buraco vira zero, não NaN', () => {
    expect(escalaDeBarras([null, 10, undefined])).toEqual([0, 1, 0])
  })
})

describe('fatiasDeRosca', () => {
  const cores = { a: '#0a7', b: '#c39' }

  it('duas fatias somam a volta inteira', () => {
    const { fatias, total, perimetro } = fatiasDeRosca(
      [
        { rotulo: 'Recorrentes', valor: 906, cor: cores.a },
        { rotulo: 'Agregadores', valor: 713, cor: cores.b },
      ],
      50,
    )
    expect(total).toBe(1619)
    expect(fatias[0].fracao + fatias[1].fracao).toBeCloseTo(1)
    // a segunda fatia começa exatamente onde a primeira termina
    expect(fatias[1].deslocamento).toBeCloseTo(-perimetro * fatias[0].fracao)
  })

  it('fatia de 100% fecha a volta', () => {
    // Foi o caso que a versão em Python errou: uma unidade sem NENHUM agregador
    // desenhava 100% como um setor mordido.
    const { fatias, perimetro } = fatiasDeRosca(
      [
        { rotulo: 'Recorrentes', valor: 3870, cor: cores.a },
        { rotulo: 'Agregadores', valor: 0, cor: cores.b },
      ],
      50,
    )
    expect(fatias[0].fracao).toBe(1)
    expect(fatias[0].traco).toBe(`${perimetro} 0`)
    expect(fatias[1].fracao).toBe(0)
  })

  it('fatia vazia não desloca a seguinte', () => {
    const { fatias } = fatiasDeRosca(
      [
        { rotulo: 'vazia', valor: 0, cor: cores.a },
        { rotulo: 'cheia', valor: 10, cor: cores.b },
      ],
      50,
    )
    expect(fatias[1].deslocamento).toBe(-0)
  })

  it('total zero não divide por zero', () => {
    const { fatias, total } = fatiasDeRosca(
      [
        { rotulo: 'a', valor: 0, cor: cores.a },
        { rotulo: 'b', valor: 0, cor: cores.b },
      ],
      50,
    )
    expect(total).toBe(0)
    expect(fatias.every((f) => f.fracao === 0 && !Number.isNaN(f.deslocamento))).toBe(true)
    expect(fatias.every((f) => !f.traco.includes('NaN'))).toBe(true)
  })

  it('valor negativo não vira fatia', () => {
    const { fatias, total } = fatiasDeRosca(
      [
        { rotulo: 'a', valor: -5, cor: cores.a },
        { rotulo: 'b', valor: 10, cor: cores.b },
      ],
      50,
    )
    expect(total).toBe(10)
    expect(fatias[0].fracao).toBe(0)
    expect(fatias[1].fracao).toBe(1)
  })

  it('percentualDaFatia devolve null sem base', () => {
    expect(percentualDaFatia(5, 20)).toBe(25)
    expect(percentualDaFatia(0, 0)).toBeNull()
  })
})

describe('ladoDoRotulo', () => {
  // A série do churn da rede em 2026-08, que é onde os dois defeitos apareceram.
  const CHURN = [6.54, 6.54, 6.48, 6.23, 7.09, 7.64, 5.32, 6.31, 6.07, 5.37, 5.5, 5.93]

  it('vale manda o rótulo para BAIXO — acima dele está o miolo do "V"', () => {
    expect(ladoDoRotulo(CHURN, 6)).toBe('abaixo') // fev, o mínimo da série
    expect(ladoDoRotulo(CHURN, 9)).toBe('abaixo') // mai
    expect(ladoDoRotulo(CHURN, 3)).toBe('abaixo') // nov
  })

  it('pico mantém o rótulo acima e centrado', () => {
    expect(ladoDoRotulo(CHURN, 5)).toBe('acima') // jan, o máximo
    expect(ladoDoRotulo(CHURN, 7)).toBe('acima') // mar
  })

  it('rampa foge da perna que sobe', () => {
    // Subindo, quem ocupa o espaço acima é a perna da DIREITA: o texto vai para a
    // esquerda. Foi o "R$ 140" de novembro na receita por recorrente.
    expect(ladoDoRotulo([1, 2, 3], 1)).toBe('acima-esquerda')
    expect(ladoDoRotulo([3, 2, 1], 1)).toBe('acima-direita')
  })

  it('as pontas decidem com o único vizinho que têm', () => {
    expect(ladoDoRotulo([1, 5], 0)).toBe('abaixo') // sobe à direita: pé de subida
    expect(ladoDoRotulo([1, 5], 1)).toBe('acima') // topo, nada acima dele
    expect(ladoDoRotulo([5, 1], 0)).toBe('acima')
  })

  it('trecho plano não tem lado ruim: fica acima', () => {
    expect(ladoDoRotulo([4, 4, 4], 1)).toBe('acima')
    expect(ladoDoRotulo([42], 0)).toBe('acima')
  })

  it('buraco e valor ilegível não escolhem lado nem estouram', () => {
    expect(ladoDoRotulo([1, null, 3], 1)).toBe('acima')
    // Vizinho ausente é IGNORADO, não tratado como zero: contado como zero, todo ponto
    // ao lado de um buraco viraria pico e o rótulo subiria em cima da linha.
    expect(ladoDoRotulo([null, 2, 9], 1)).toBe('abaixo')
    expect(ladoDoRotulo([NaN, 5, 1], 1)).toBe('acima')
  })
})

describe('ancoraDoRotulo', () => {
  const LARGURA = 340
  const MEIA = 17 // "1.808,0" a 8,5 px de mono ≈ 34 px de caixa

  it('no meio do quadro, cada lado sai onde o nome diz', () => {
    expect(ancoraDoRotulo('acima', 170, 100, MEIA, LARGURA)).toEqual({
      x: 170,
      y: 94,
      textAnchor: 'middle',
    })
    expect(ancoraDoRotulo('abaixo', 170, 100, MEIA, LARGURA)).toEqual({
      x: 170,
      y: 110,
      textAnchor: 'middle',
    })
    expect(ancoraDoRotulo('acima-esquerda', 170, 100, MEIA, LARGURA)).toMatchObject({
      x: 166,
      textAnchor: 'end',
    })
    expect(ancoraDoRotulo('acima-direita', 170, 100, MEIA, LARGURA)).toMatchObject({
      x: 174,
      textAnchor: 'start',
    })
  })

  it('a CAIXA do texto não sai do quadro em nenhuma ponta', () => {
    // Foi o defeito de "1.808,0" na ficha: grampeado só pelo x do ponto, o texto começava
    // em −2 px e o número aparecia como ".808,0" — valor errado, não rótulo feio.
    const esq = ancoraDoRotulo('abaixo', 2, 100, MEIA, LARGURA)
    expect(esq.x - MEIA).toBeGreaterThanOrEqual(0)
    const dir = ancoraDoRotulo('abaixo', LARGURA - 2, 100, MEIA, LARGURA)
    expect(dir.x + MEIA).toBeLessThanOrEqual(LARGURA)
    // Com âncora `end` o texto se estende para TRÁS do x; com `start`, para a frente.
    expect(ancoraDoRotulo('acima-esquerda', 5, 100, MEIA, LARGURA).x - 2 * MEIA).toBeGreaterThanOrEqual(0)
    expect(
      ancoraDoRotulo('acima-direita', LARGURA - 5, 100, MEIA, LARGURA).x + 2 * MEIA,
    ).toBeLessThanOrEqual(LARGURA)
  })

  it('rótulo alto não sobe além do teto do quadro', () => {
    expect(ancoraDoRotulo('acima', 170, 2, MEIA, LARGURA).y).toBe(9)
  })

  it('texto mais largo que o quadro encosta na borda em vez de virar NaN', () => {
    // Cartão espremido: sem o grampo defensivo, mínimo > máximo devolveria lixo e o
    // rótulo sumiria do SVG sem nenhum erro no console.
    for (const lado of ['acima', 'abaixo', 'acima-esquerda', 'acima-direita'] as const) {
      const p = ancoraDoRotulo(lado, 20, 50, 60, 40)
      expect(Number.isFinite(p.x)).toBe(true)
      expect(Number.isFinite(p.y)).toBe(true)
    }
  })
})
