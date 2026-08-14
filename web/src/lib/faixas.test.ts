import { describe, expect, it } from 'vitest'
import {
  FAIXA_M1_HEX,
  FAIXA_M1_ORDEM,
  faixaM1ToColor,
  HEX_FILL_ALPHA,
  NA_FILL,
  PRESSAO_FORA_DO_UNIVERSO_FILL,
  PRESSAO_SEM_MEDICAO_FILL,
  pressaoMaToColor,
  SCORE_BANDS_HEX,
  scoreBandToColor,
} from './colors'
import {
  alunosDaFaixa,
  bandasDaFaixa,
  bandasDaFaixaPressao,
  CAPACIDADE_UNIDADE_ALUNOS,
  FAIXAS_DEMANDA,
  FAIXAS_POTENCIAL,
  FAIXAS_PRESSAO_MA,
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

  it('camada 5 nao usa rampa de score — colore pela faixa do M1', () => {
    expect(faixasDoPasso(5)).toBeNull()
    expect(tituloDaLegenda(5)).toBe('Faixa de oportunidade M1')
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

  it('camada 5 — faixa de oportunidade M1, na ordem da legenda', () => {
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
    expect([1, 2, 3, 5].map(tituloDaLegenda)).toEqual([
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

/* Overlay de PRESSAO COMPETITIVA sobre as independentes (BLK-MA-13 / DEC-028).

   O que estes testes protegem: a INVERSAO da rampa (que e' o unico ponto do mapa onde ela
   e' lida ao contrario) e a distincao entre os tres estados da cor. Colapsar "sem medicao"
   em "sem pressao" faria o mapa afirmar ausencia de concorrencia onde ha ausencia de dado. */
describe('overlay de pressão competitiva', () => {
  it('pressão ALTA sai na cor de score BAIXO: vermelho = território apertado', () => {
    // 85 de pressao -> banda de 15 na rampa -> #B92323 (a mesma cor do "Saturado" da demanda).
    expect(pressaoMaToColor(85)).toEqual([0xb9, 0x23, 0x23, HEX_FILL_ALPHA])
  })

  it('pressão ZERO sai no verde do topo da rampa — é medição, não ausência', () => {
    expect(pressaoMaToColor(0)).toEqual([0x0a, 0x82, 0x26, HEX_FILL_ALPHA])
  })

  it('devolve null sem medição, para o chamador escolher a cor de ausência', () => {
    expect(pressaoMaToColor(null)).toBeNull()
    expect(pressaoMaToColor(undefined)).toBeNull()
    expect(pressaoMaToColor(NaN)).toBeNull()
  })

  it('clampa fora de [0,100] em vez de estourar o índice da rampa', () => {
    expect(pressaoMaToColor(-5)).toEqual(pressaoMaToColor(0))
    expect(pressaoMaToColor(140)).toEqual(pressaoMaToColor(100))
  })

  it('os três estados de ausência têm cores DIFERENTES entre si e do verde de pressão 0', () => {
    const semPressao = pressaoMaToColor(0)!
    expect(PRESSAO_SEM_MEDICAO_FILL).not.toEqual(PRESSAO_FORA_DO_UNIVERSO_FILL)
    expect(PRESSAO_SEM_MEDICAO_FILL).not.toEqual(semPressao)
    expect(PRESSAO_FORA_DO_UNIVERSO_FILL).not.toEqual(semPressao)
  })

  it('é monotônica: mais pressão desce na rampa, nunca sobe', () => {
    /* Compara o ÍNDICE na rampa, não o canal verde. A paleta não é um gradiente de G: o
       verde-escuro do topo (#0A8226) tem G=130 e o verde-claro do meio (#50C33C) tem G=195,
       então medir "verdor" pelo canal daria falso alarme na primeira comparação. */
    const indice = (p: number) => {
      const [r, g, b] = pressaoMaToColor(p)!
      const hex = `#${[r, g, b].map((c) => c.toString(16).padStart(2, '0')).join('')}`
      return SCORE_BANDS_HEX.findIndex((h) => h.toLowerCase() === hex)
    }
    const indices = [0, 25, 50, 75, 100].map(indice)
    expect(indices).not.toContain(-1)
    for (let i = 1; i < indices.length; i++) {
      expect(indices[i]).toBeLessThan(indices[i - 1])
    }
  })

  it('a legenda mostra as bandas que o mapa de fato pinta (rampa espelhada)', () => {
    // "Sem pressão" (0-20) -> complemento 80-100 -> as duas bandas verdes do topo.
    expect(bandasDaFaixaPressao(FAIXAS_PRESSAO_MA[0])).toEqual([
      SCORE_BANDS_HEX[8],
      SCORE_BANDS_HEX[9],
    ])
    // "Sufocante" (80-100) -> complemento 0-20 -> os dois vermelhos do fundo.
    expect(bandasDaFaixaPressao(FAIXAS_PRESSAO_MA[4])).toEqual([
      SCORE_BANDS_HEX[0],
      SCORE_BANDS_HEX[1],
    ])
  })

  it('a cor declarada de cada faixa é uma das bandas que ela cobre', () => {
    for (const f of FAIXAS_PRESSAO_MA) {
      expect(bandasDaFaixaPressao(f)).toContain(f.cor)
    }
  })

  it('a paleta é a da demanda ao contrário — não há paleta nova', () => {
    expect(FAIXAS_PRESSAO_MA.map((f) => f.cor)).toEqual(
      [...FAIXAS_DEMANDA].reverse().map((f) => f.cor),
    )
  })

  it('não entra em `faixasDoPasso`: o overlay não é camada do funil', () => {
    for (const n of [1, 2, 3, 4, 5, 6]) {
      expect(faixasDoPasso(n)).not.toBe(FAIXAS_PRESSAO_MA)
    }
  })
})
