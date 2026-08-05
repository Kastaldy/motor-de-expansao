import { describe, expect, it } from 'vitest'
import {
  FAIXA_M1_HEX,
  FAIXA_M1_ORDEM,
  faixaM1ToColor,
  NA_FILL,
  SCORE_BANDS_HEX,
  scoreBandToColor,
} from './colors'
import {
  alunosDaFaixa,
  bandasDaFaixa,
  CAPACIDADE_UNIDADE_ALUNOS,
  FAIXAS_DEMANDA,
  FAIXAS_POTENCIAL,
  faixasDoPasso,
  fundoDoSwatch,
  tituloDaLegenda,
} from './faixas'

describe('faixas nomeadas por camada', () => {
  // Tuplas de 1 elemento: `it.each` desestrutura o array externo, entao passar
  // [A, B] entregaria os ITENS de A como argumentos, nao A inteiro.
  it.each([[FAIXAS_POTENCIAL], [FAIXAS_DEMANDA]])(
    'cobrem 0-100 sem buraco nem sobreposicao',
    (faixas) => {
      expect(faixas[0].de).toBe(0)
      expect(faixas[faixas.length - 1].ate).toBe(100)
      for (let i = 1; i < faixas.length; i++) {
        // o `ate` de uma e o `de` da seguinte: sem lacuna (score cairia sem nome)
        // e sem sobreposicao (score teria dois nomes).
        expect(faixas[i].de).toBe(faixas[i - 1].ate)
      }
    },
  )

  it('camada 1 da veredito; camada 2 fala de saturacao — vocabularios distintos', () => {
    expect(FAIXAS_POTENCIAL.map((f) => f.nome)).toEqual([
      'Desfavorável',
      'Fraco',
      'Promissor',
      'Forte',
      'Excelente',
    ])
    expect(FAIXAS_DEMANDA.map((f) => f.nome)).toEqual([
      'Saturado',
      'Restrito',
      'Moderado',
      'Amplo',
      'Livre',
    ])
    // O pedido do Juan foi explicito: os nomes VARIAM por camada.
    expect(FAIXAS_POTENCIAL.map((f) => f.nome)).not.toEqual(FAIXAS_DEMANDA.map((f) => f.nome))
  })

  it('camada 3 herda a 2 (mesma cor, mesmo score residual)', () => {
    expect(faixasDoPasso(3)).toBe(faixasDoPasso(2))
  })

  it('camada 4 nao usa rampa de score — colore pela faixa do M1', () => {
    expect(faixasDoPasso(4)).toBeNull()
    expect(tituloDaLegenda(4)).toBe('Faixa de oportunidade M1')
  })
})

describe('etiqueta de alunos da camada de demanda', () => {
  it('ancora no 2.500 (capacidade de uma unidade)', () => {
    expect(CAPACIDADE_UNIDADE_ALUNOS).toBe(2500)
  })

  it('usa separador de milhar pt-BR, como todo numero do app', () => {
    // A primeira versao escrevia "1000-1500" cru e destoava do resto da tela.
    expect(alunosDaFaixa(FAIXAS_DEMANDA[2])).toBe('1.000–1.500')
  })

  it('a ultima faixa e ABERTA porque o score e CLIPADO em 100', () => {
    // `score_oportunidade_residual` tem `.clip(upper=100)`: 2.500 e 10.000 alunos
    // marcam o mesmo 100. O rotulo nao pode prometer "mais de uma unidade".
    expect(alunosDaFaixa(FAIXAS_DEMANDA[4])).toBe('2.000+')
  })

  it('a unidade fica no TITULO, nao repetida em cada etiqueta', () => {
    expect(tituloDaLegenda(2)).toContain('(alunos)')
    for (const f of FAIXAS_DEMANDA) {
      expect(alunosDaFaixa(f)).not.toContain('alunos')
    }
  })
})

/* --- Exemplo executavel: a legenda INTEIRA, camada por camada ---------------
   Serve de duas coisas ao mesmo tempo: documenta o que o usuario ve (da para ler
   o teste e saber a legenda de cor) e trava as strings contra mudanca acidental.
   Se alguem renomear uma faixa, este teste aponta exatamente qual e o novo texto. */
describe('exemplo de TODAS as faixas, como aparecem na legenda', () => {
  it('camada 1 — Potencial socioeconomico (sem etiqueta de alunos)', () => {
    expect(FAIXAS_POTENCIAL.map((f) => `${f.nome} [${f.de}-${f.ate}]`)).toEqual([
      'Desfavorável [0-20]',
      'Fraco [20-40]',
      'Promissor [40-60]',
      'Forte [60-80]',
      'Excelente [80-100]',
    ])
  })

  it('camada 2/3 — Demanda nao atendida (nome + alunos)', () => {
    expect(FAIXAS_DEMANDA.map((f) => `${f.nome} ${alunosDaFaixa(f)}`)).toEqual([
      'Saturado 0–500',
      'Restrito 500–1.000',
      'Moderado 1.000–1.500',
      'Amplo 1.500–2.000',
      'Livre 2.000+',
    ])
  })

  it('camada 4 — faixa de oportunidade M1, na ordem da legenda', () => {
    expect([...FAIXA_M1_ORDEM]).toEqual([
      'Prioridade máxima',
      'Alta',
      'Média',
      'Baixa',
      'Descartado',
      'Inviável',
    ])
  })

  it('os titulos de cada camada', () => {
    expect([1, 2, 3, 4].map(tituloDaLegenda)).toEqual([
      'Potencial socioeconômico',
      'Demanda não atendida (alunos)',
      'Demanda não atendida (alunos)',
      'Faixa de oportunidade M1',
    ])
  })
})

describe('swatch da legenda cobre as cores que o mapa pinta', () => {
  // O defeito que estes testes travam: a legenda passou de barra de gradiente (10
  // bandas, as mesmas do mapa) para 5 blocos nomeados. Se cada bloco mostrar UMA cor,
  // metade das cores do mapa some da legenda e o usuario le a faixa errada.
  it.each([[FAIXAS_POTENCIAL], [FAIXAS_DEMANDA]])(
    'toda cor da rampa aparece em algum bloco',
    (faixas) => {
      const naLegenda = faixas.flatMap(bandasDaFaixa)
      expect(new Set(naLegenda)).toEqual(new Set(SCORE_BANDS_HEX))
    },
  )

  it('cada faixa de 20 pontos carrega as 2 bandas de 10 que o mapa usa', () => {
    for (const f of FAIXAS_DEMANDA) {
      const cores = bandasDaFaixa(f)
      expect(cores).toHaveLength(2)
      // A cor que o mapa daria ao meio de cada meia-faixa tem que estar no bloco.
      for (const amostra of [f.de + 5, f.de + 15]) {
        const [r, g, b] = scoreBandToColor(amostra)
        const hex = `#${[r, g, b].map((c) => c.toString(16).padStart(2, '0')).join('')}`
        expect(cores.map((c) => c.toLowerCase())).toContain(hex)
      }
    }
  })

  it('score 45 nao e mais lido como Restrito: a cor dele esta no bloco Moderado', () => {
    // Caso concreto do defeito: 45 pinta #F0941E (banda 40-50) e o unico bloco
    // laranja da legenda antiga era o da faixa 20-40 ("Restrito").
    const moderado = FAIXAS_DEMANDA.find((f) => f.nome === 'Moderado')!
    expect(bandasDaFaixa(moderado)).toContain('#F0941E')
    const restrito = FAIXAS_DEMANDA.find((f) => f.nome === 'Restrito')!
    expect(bandasDaFaixa(restrito)).not.toContain('#F0941E')
  })

  it('fundoDoSwatch: uma cor vira solida, duas viram faixas lado a lado', () => {
    expect(fundoDoSwatch(['#14C850'])).toBe('#14C850')
    expect(fundoDoSwatch([])).toBe('transparent')
    const fundo = fundoDoSwatch(['#941212', '#B92323'])
    expect(fundo).toContain('linear-gradient')
    expect(fundo).toContain('#941212 0.00% 50.00%')
    expect(fundo).toContain('#B92323 50.00% 100.00%')
  })
})

describe('cores da faixa M1', () => {
  it('todo rotulo da ordem tem cor definida', () => {
    for (const nome of FAIXA_M1_ORDEM) {
      expect(FAIXA_M1_HEX[nome]).toMatch(/^#[0-9A-F]{6}$/i)
    }
  })

  it('faixa ausente ou desconhecida cai no NA_FILL, sem inventar cor', () => {
    expect(faixaM1ToColor(null)).toEqual(NA_FILL)
    expect(faixaM1ToColor('Faixa Que Nao Existe')).toEqual(NA_FILL)
  })

  it('Prioridade máxima é o verde canonico do M1 (FAIXA_COLORS)', () => {
    expect(FAIXA_M1_HEX['Prioridade máxima']).toBe('#14C850')
    const [r, g, b, a] = faixaM1ToColor('Prioridade máxima', 115)
    expect([r, g, b]).toEqual([0x14, 0xc8, 0x50])
    expect(a).toBe(115)
  })
})
