import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'

import { describe, expect, it } from 'vitest'

import * as rampa from './viabilidade-rampa'
import {
  MESES_DEPOIS_DO_PICO,
  PICO_RAMPA_MAX,
  PICO_RAMPA_MIN,
  PICO_RAMPA_OBSERVADO,
  ajudaDaRampa,
  casaNoMes1,
  ebitdaDosPrimeirosMeses,
  eixoDaRampa,
  formaDoPayload,
  larguraDaLinhaDaGrade,
  mesCurto,
  mesFimDaRampa,
  mesesDaGrade,
  notaDaRampa,
  origemDoPadrao,
  passoPico,
  picoExibido,
  picoParaEnviar,
  rotuloPico,
} from './viabilidade-rampa'

// Por MÊS DE VIDA, como no estudo: o índice 0 é a inauguração (o 1º mês de operação), e
// o fim da rampa servido (`mes_maturidade_rampa`) é em mês de OPERAÇÃO = pico + 1.
const CURVA_OBS = [0.8, 0.68, 0.77, 0.84, 0.88, 0.9, 0.92, 0.97, 0.97, 0.99, 1, 1, 1]
const CURVA = {
  maturacao_meses: 8,
  forma_rampa: 'curva_uni03',
  mes_maturidade_rampa: 11,
  mes_pico_rampa: 10,
  curva_rampa: CURVA_OBS,
}
const CURVA_PICO_6 = {
  maturacao_meses: 8,
  forma_rampa: 'curva_uni03',
  mes_maturidade_rampa: 7,
  mes_pico_rampa: 6,
  // `curva_rampa_com_pico(6)` do motor: os meses 0 e 1 ficam os observados (80% e 68%).
  curva_rampa: [0.8, 0.68, 0.826, 0.892, 0.94, 0.974, 1, 1, 1],
}
// Rampa linear: só chega da API pública ou com a constante do servidor revertida.
const LINEAR = { maturacao_meses: 8, forma_rampa: 'reta', mes_maturidade_rampa: 8, mes_pico_rampa: null }

describe('pico de maturação (emenda de 21/10/2026 da DEC-078)', () => {
  it('o intervalo e o pico observado espelham o config.py do servidor', () => {
    const config = readFileSync(
      fileURLToPath(new URL('../../../src/motor_expansao/dimensionamento/config.py', import.meta.url)),
      'utf-8',
    )
    expect(config).toContain(`SIM_MES_PICO_RAMPA_MIN = ${PICO_RAMPA_MIN}\n`)
    expect(config).toContain(`SIM_MES_PICO_RAMPA_MAX = ${PICO_RAMPA_MAX}\n`)
    // o observado é DERIVADO da curva no servidor: o 1º mês DE VIDA (base 0) com 100%
    const curva = /SIM_CURVA_RAMPA_UNI03 = \(([^)]*)\)/.exec(config)
    expect(curva).not.toBeNull()
    const fracoes = curva![1].split(',').map((s) => s.trim()).filter(Boolean).map(Number)
    expect(fracoes[0]).toBe(0.8) // o mês 0 do estudo entra (emenda de 22/10/2026)
    expect(fracoes.findIndex((f) => f >= 1)).toBe(PICO_RAMPA_OBSERVADO)
    expect(rotuloPico(12)).toBe('12 meses')
    expect(rotuloPico(1)).toBe('1 mês')
  })

  it('o contador anda de mês em mês e para nas pontas do intervalo', () => {
    expect(passoPico(10, 1)).toBe(11)
    expect(passoPico(10, -1)).toBe(9)
    expect(passoPico(PICO_RAMPA_MIN, -1)).toBe(PICO_RAMPA_MIN)
    expect(passoPico(PICO_RAMPA_MAX, 1)).toBe(PICO_RAMPA_MAX)
  })

  it('a tela não crava padrão nem oferece a forma: ambos são do servidor', () => {
    expect('FORMA_RAMPA_PADRAO' in rampa).toBe(false)
    expect('FORMAS_RAMPA' in rampa).toBe(false)
    expect('ROTULO_FORMA_RAMPA' in rampa).toBe(false)
    expect('PICO_PADRAO' in rampa).toBe(false)
  })

  it('sem escolha, o pedido vai SEM mes_pico_rampa e vale o pico observado do servidor', () => {
    expect(picoParaEnviar(null)).toBeUndefined()
    expect(JSON.stringify({ mes_pico_rampa: picoParaEnviar(null) })).toBe('{}')
  })

  it('o pico escolhido vai no pedido como mes_pico_rampa', () => {
    for (const m of [1, 7, 36]) {
      expect(JSON.parse(JSON.stringify({ mes_pico_rampa: picoParaEnviar(m) }))).toEqual({
        mes_pico_rampa: m,
      })
    }
  })

  it('sem escolha, o seletor marca o pico que o servidor usou', () => {
    expect(picoExibido(null, CURVA)).toBe(10)
    expect(picoExibido(null, CURVA_PICO_6)).toBe(6)
    // backend sem o eco do pico (anterior ao mês 0): cai no fim da rampa servido
    expect(picoExibido(null, { ...CURVA, mes_pico_rampa: undefined })).toBe(11)
  })

  it('antes do primeiro cálculo o contador parte do observado; na rampa linear, nenhum pico', () => {
    expect(picoExibido(null, null)).toBe(PICO_RAMPA_OBSERVADO)
    expect(picoExibido(null, LINEAR)).toBeNull()
  })

  it('a escolha do operador vence o pico servido', () => {
    expect(picoExibido(18, CURVA)).toBe(18)
  })
})

describe('ajuda do controle', () => {
  it('é curta (uma linha) e diz que é preciso recalcular', () => {
    for (const p of [null, CURVA, CURVA_PICO_6, LINEAR]) {
      expect(ajudaDaRampa(p).toLowerCase()).toContain('recalcule para atualizar o payback')
      // pedido de 22/10/2026: o detalhe vai para as notas metodológicas
      expect(ajudaDaRampa(p).length).toBeLessThanOrEqual(95)
    }
  })

  it('nenhum texto da rampa fala em "reta"', () => {
    for (const p of [null, CURVA, CURVA_PICO_6, LINEAR]) {
      expect(ajudaDaRampa(p)).not.toMatch(/\breta\b/i)
    }
    for (const p of [CURVA, CURVA_PICO_6, LINEAR]) {
      expect(notaDaRampa(p)).not.toMatch(/\breta\b/i)
      expect(casaNoMes1(p)).not.toMatch(/\breta\b/i)
      expect(ebitdaDosPrimeirosMeses(p)).not.toMatch(/\breta\b/i)
    }
  })
})

describe('fim da rampa lido do payload', () => {
  it('lê o mês servido pelo motor (mês de operação = pico + 1), não o parâmetro da reta', () => {
    expect(mesFimDaRampa(CURVA)).toBe(11)
    expect(mesFimDaRampa(CURVA_PICO_6)).toBe(7)
  })

  it('backend anterior à DEC-078 (sem o campo) cai na rampa de maturacao_meses', () => {
    expect(mesFimDaRampa({ maturacao_meses: 8 })).toBe(8)
    expect(formaDoPayload({ maturacao_meses: 8 })).toBe('reta')
  })

  it('sem premissas não inventa mês', () => {
    expect(mesFimDaRampa(null)).toBeNull()
  })

  it('forma desconhecida vinda do payload nunca é lida como curva', () => {
    expect(formaDoPayload({ maturacao_meses: 8, forma_rampa: 'outra' })).toBe('reta')
  })
})

describe('nota metodológica', () => {
  it('na curva, diz o mês do pico e o que NÃO é modelado', () => {
    expect(notaDaRampa(CURVA)).toContain('mês 10')
    expect(notaDaRampa(CURVA_PICO_6)).toContain('pico de maturação, mês 6')
    expect(notaDaRampa(CURVA)).toContain('não é modelado')
  })

  it('carrega o detalhe que saiu da ajuda: abertura servida e amarra do agregador', () => {
    for (const p of [CURVA, CURVA_PICO_6]) {
      expect(notaDaRampa(p)).toContain('(mês 0, o 1º mês de operação) com 80% da demanda')
      expect(notaDaRampa(p)).toContain('mês 1 com 68%')
    }
    expect(notaDaRampa(CURVA)).toContain('agregador')
    // sem curva servida, não inventa percentual
    expect(notaDaRampa({ ...CURVA, curva_rampa: undefined })).not.toMatch(/\d+%/)
  })

  it('pico até o mês 12: a rampa não mexe na margem de steady-state', () => {
    for (const ref of [undefined, null, 10, 12]) {
      expect(notaDaRampa({ ...CURVA, mes_referencia_steady: ref })).toContain(
        'não a margem de steady-state',
      )
    }
  })

  it('pico depois do mês 12: a nota NÃO diz que o steady-state fica igual (reajuste do 2º ano)', () => {
    const tardio = { ...CURVA, mes_maturidade_rampa: 19, mes_pico_rampa: 18, mes_referencia_steady: 19 }
    const nota = notaDaRampa(tardio)
    expect(nota).not.toContain('não a margem de steady-state')
    expect(nota).toContain('pico de maturação, mês 18')
    expect(nota).toContain('mês 19')
    expect(nota).toContain('reajuste anual')
    expect(nota).toContain('2º ano')
    // a rampa linear da API, com maturação longa, tem o mesmo efeito
    const linearLonga = { ...LINEAR, maturacao_meses: 30, mes_maturidade_rampa: 30, mes_referencia_steady: 30 }
    expect(notaDaRampa(linearLonga)).toContain('3º ano')
  })

  it('"casa vazia" no mês 1 só na rampa linear: na curva o mês 1 já tem boa parte da demanda', () => {
    expect(casaNoMes1(LINEAR)).toBe('com a casa vazia')
    expect(casaNoMes1(CURVA)).not.toContain('vazia')
  })

  it('o EBITDA dos primeiros meses só é afirmado NEGATIVO na rampa linear', () => {
    expect(ebitdaDosPrimeirosMeses(LINEAR)).toBe(
      'então o EBITDA dos primeiros meses é bem NEGATIVO enquanto a casa não enche.',
    )
    expect(ebitdaDosPrimeirosMeses(CURVA)).not.toMatch(/NEGATIVO/i)
    expect(ebitdaDosPrimeirosMeses(CURVA)).toContain('positivo')
  })
})

/* ---------------------------------------------------------------------------
   A TELA (fonte): produto único. Sem o React Testing Library neste repo, a trava lê a
   FONTE da tela e de suas libs de texto e extrai o que vira texto de usuário (literais
   de string e texto JSX), sem comentários e sem as linhas de import. Identificadores
   (`sugestaoV2`, `modelo_demanda: 'v2'`, `forma_rampa`) não são texto e ficam de fora.
   --------------------------------------------------------------------------- */

const ler = (rel: string) => readFileSync(fileURLToPath(new URL(rel, import.meta.url)), 'utf-8')

function textosDeUsuario(fonte: string): string[] {
  const semComentarios = fonte
    .replace(/\/\*[\s\S]*?\*\//g, '')
    .split('\n')
    .filter((l) => !/^\s*import\b/.test(l) && !/^\s*\}\s*from\s/.test(l))
    .map((l) => l.replace(/(^|[^:'"`])\/\/.*$/, '$1'))
    .join('\n')
  const literais = [...semComentarios.matchAll(/'([^'\n]*)'|"([^"\n]*)"|`([^`]*)`/g)].map(
    (m) => m[1] ?? m[2] ?? m[3] ?? '',
  )
  const jsx = [...semComentarios.matchAll(/>([^<>{}]+)</g)].map((m) => m[1].trim())
  return [...literais, ...jsx].filter((t) => /[A-Za-zÀ-ÿ]{2}/.test(t))
}

const TELA = ler('../screens/ViabilityScreen.tsx')
const FONTES_DE_TEXTO = {
  tela: TELA,
  rampa: ler('./viabilidade-rampa.ts'),
  demanda: ler('./viabilidade-demanda-v2.ts'),
  notas: ler('../components/ViabilityNotes.tsx'),
  graficos: ler('../components/ViabilityCharts.tsx'),
}

describe('a tela trata a Viabilidade como produto único', () => {
  it('nenhum texto de usuário menciona versão ("v2", "segunda versão", "versão 2")', () => {
    for (const [nome, fonte] of Object.entries(FONTES_DE_TEXTO)) {
      const achados = textosDeUsuario(fonte).filter((t) =>
        /\bv2\b|segunda vers[ãa]o|vers[ãa]o 2\b/i.test(t),
      )
      expect(achados, nome).toEqual([])
    }
  })

  it('nenhum texto de usuário traz aviso de faixa provisória', () => {
    for (const [nome, fonte] of Object.entries(FONTES_DE_TEXTO)) {
      const achados = textosDeUsuario(fonte).filter((t) => /faixa provis[óo]ria/i.test(t))
      expect(achados, nome).toEqual([])
    }
    expect(TELA).not.toMatch(/Faixa provis[óo]ria/)
  })

  it('a rampa não oferece mais a reta: nem rótulo, nem seletor de meses', () => {
    const textos = textosDeUsuario(TELA)
    expect(textos.filter((t) => /\breta\b/i.test(t))).toEqual([])
    expect(TELA).not.toContain('Meses até o platô')
    expect(TELA).not.toContain('setRampaMeses')
    expect(TELA).not.toContain('forma_rampa:')
  })

  it('o pico é um contador "−/+" de mês em mês e vai no pedido como mes_pico_rampa', () => {
    expect(TELA).toContain('setPicoRampa(passoPico(picoMostrado, -1))')
    expect(TELA).toContain('setPicoRampa(passoPico(picoMostrado, 1))')
    expect(TELA).toContain('aria-label="Diminuir o pico de maturação"')
    expect(TELA).toContain('aria-label="Aumentar o pico de maturação"')
    expect(TELA).toContain('mes_pico_rampa: picoParaEnviar(picoRampa)')
    expect(TELA).not.toContain('Pico de maturação, em meses')
  })
})

/* ---------------------------------------------------------------------------
   Eixo do gráfico "Rampa de alunos" (pedido de 28/10/2026): termina 2 meses depois do
   pico, e não mais em no mínimo 18 meses. O payload serve `mes_maturidade_rampa` = pico +
   1 (mês de OPERAÇÃO), conferido no motor (`premissas_do_body` + a série mensal) para os
   picos 1, 2, 8, 10, 12 e 36; na rampa linear, o próprio N.
   --------------------------------------------------------------------------- */

// Alunos por MÊS DE VIDA de uma curva com pico `pico`, no formato da do motor (80% no mês
// 0, 68% no mês 1, demanda cheia do pico em diante), já no eixo do gráfico; 60 meses.
function serieCurva(pico: number, meses = 60): { mes: number; v: number }[] {
  const demanda = 2500
  return Array.from({ length: meses }, (_, mes) => {
    if (mes === 0) return { mes, v: demanda * 0.8 }
    if (mes >= pico) return { mes, v: demanda }
    return { mes, v: demanda * (0.68 + (0.32 * (mes - 1)) / (pico - 1)) }
  })
}

describe('eixo do gráfico "Rampa de alunos" (pedido de 28/10/2026)', () => {
  it('vai até 2 meses depois do pico: pico 8 mostra 10, 10 mostra 12 e 12 mostra 14', () => {
    expect(MESES_DEPOIS_DO_PICO).toBe(2)
    for (const [pico, fimDoEixo] of [
      [8, 10],
      [10, 12],
      [12, 14],
    ]) {
      // a tela recebe o fim servido (pico + 1); na curva o eixo é o mês de vida
      expect(eixoDaRampa(pico + 1, true, serieCurva(pico))).toEqual({
        plato: pico,
        limite: fimDoEixo,
      })
    }
  })

  it('lê o fim da rampa do payload pelo mesmo caminho da tela (mesFimDaRampa)', () => {
    expect(eixoDaRampa(mesFimDaRampa(CURVA), true, serieCurva(10))).toEqual({
      plato: 10,
      limite: 12,
    })
    expect(eixoDaRampa(mesFimDaRampa(CURVA_PICO_6), true, serieCurva(6))).toEqual({
      plato: 6,
      limite: 8,
    })
  })

  it('sem piso nem teto: pico 1 mostra 3 meses e o pico máximo (36), 38', () => {
    expect(eixoDaRampa(2, true, serieCurva(1))).toEqual({ plato: 1, limite: 3 })
    expect(eixoDaRampa(PICO_RAMPA_MAX + 1, true, serieCurva(PICO_RAMPA_MAX))).toEqual({
      plato: PICO_RAMPA_MAX,
      limite: PICO_RAMPA_MAX + 2,
    })
  })

  it('rampa linear (só pela API): eixo em mês de operação e platô no próprio fim servido', () => {
    const reta = Array.from({ length: 60 }, (_, i) => ({ mes: i + 1, v: Math.min(i + 1, 8) * 250 }))
    expect(eixoDaRampa(mesFimDaRampa(LINEAR), false, reta)).toEqual({ plato: 8, limite: 10 })
  })

  it('série mais curta que o pico + 2: o eixo termina nela e o marcador do platô some', () => {
    // o gráfico só desenha o marcador com `plato <= limite`
    expect(eixoDaRampa(13, true, serieCurva(12, 6))).toEqual({ plato: 12, limite: 5 })
  })

  it('sem fim servido: ancora no 1º mês com o máximo da série e não inventa platô', () => {
    expect(eixoDaRampa(null, true, serieCurva(10))).toEqual({ plato: null, limite: 12 })
    expect(eixoDaRampa(null, true, serieCurva(20))).toEqual({ plato: null, limite: 22 })
    // fim não finito conta como ausente, como em `mesFimDaRampa`
    expect(eixoDaRampa(Number.NaN, true, serieCurva(8))).toEqual({ plato: null, limite: 10 })
  })

  it('o gráfico usa a regra e não guarda mais a janela de 18 meses', () => {
    const fonte = FONTES_DE_TEXTO.graficos
    const corpo = fonte.slice(
      fonte.indexOf('export function RampaAlunos('),
      fonte.indexOf('export function FluxoCaixa('),
    )
    expect(corpo).toContain('eixoDaRampa(maturacaoMeses, curva, pts)')
    expect(corpo).not.toMatch(/const limite\s*=/)
    expect(corpo).not.toMatch(/,\s*18\s*\)/)
  })
})

/* ---------------------------------------------------------------------------
   Grade do gráfico "Rampa de alunos" (pedido de 28/10/2026: "uma linha tracejada vertical
   para cada mês"). Todo mês do eixo, do 0 ao penúltimo, tem exatamente UMA linha
   vertical: a de grade ou, no mês do platô, o marcador que já existia. O mês 0 ganha a
   linha inteira (pedido do mesmo dia: "a linha do mês 0 para o 1 completa"): ali o SVG
   corta a metade de fora do traço, e por isso ele tem o dobro da largura. O fim do eixo
   fica sem linha ("pode ser cortada, visto que vira uma reta").
   --------------------------------------------------------------------------- */

/** Meses inteiros de `de` a `ate`, inclusive. */
const meses = (de: number, ate: number) => Array.from({ length: ate - de + 1 }, (_, i) => de + i)

describe('grade de meses do gráfico "Rampa de alunos" (pedido de 28/10/2026)', () => {
  it('uma linha por mês do eixo, do 0 ao penúltimo: picos 1, 8, 10, 12 e 36', () => {
    // [pico, linhas de grade]: o eixo vai de 0 a pico + 2 e os meses com linha são 0 a
    // pico + 1; o do platô fica com o marcador, então sobram `pico + 1` linhas de grade
    for (const [pico, linhas] of [
      [1, 2],
      [8, 9],
      [10, 11],
      [12, 13],
      [PICO_RAMPA_MAX, 37],
    ]) {
      const { plato, limite } = eixoDaRampa(pico + 1, true, serieCurva(pico))
      const grade = mesesDaGrade(limite, plato)
      expect(grade, `pico ${pico}`).toHaveLength(linhas)
      // nenhum mês fica sem linha nem ganha duas: grade + marcador = 0 a limite - 1
      expect([...grade, plato!].sort((a, b) => a - b), `pico ${pico}`).toEqual(meses(0, limite - 1))
    }
    expect(mesesDaGrade(3, 1)).toEqual([0, 2]) // pico 1: eixo de 0 a 3, marcador no 1
    expect(mesesDaGrade(10, 8)).toEqual([0, 1, 2, 3, 4, 5, 6, 7, 9]) // pico 8: eixo de 0 a 10
  })

  it('o mês 0 ganha linha e o fim do eixo não', () => {
    for (const limite of [3, 10, 12, 14, 38]) {
      const grade = mesesDaGrade(limite, null)
      expect(grade).toEqual(meses(0, limite - 1))
      expect(grade).toContain(0)
      expect(grade).not.toContain(limite)
    }
  })

  it('a linha do mês 0 tem o dobro da largura: o SVG corta a metade de fora da borda', () => {
    expect(larguraDaLinhaDaGrade(0)).toBe(2)
    for (const mes of meses(1, PICO_RAMPA_MAX + 1)) {
      expect(larguraDaLinhaDaGrade(mes), `mês ${mes}`).toBe(1)
    }
    // a metade que fica dentro do SVG tem a largura das outras linhas
    expect(larguraDaLinhaDaGrade(0) / 2).toBe(larguraDaLinhaDaGrade(1))
  })

  it('platô fora do eixo ou ausente não tira mês nenhum', () => {
    // série mais curta que o pico + 2: o marcador some (platô 12, eixo até 5)
    const curta = eixoDaRampa(13, true, serieCurva(12, 6))
    expect(mesesDaGrade(curta.limite, curta.plato)).toEqual([0, 1, 2, 3, 4])
    // sem fim servido: não há marcador, e todo mês do eixo, menos o último, tem grade
    const semFim = eixoDaRampa(null, true, serieCurva(10))
    expect(mesesDaGrade(semFim.limite, semFim.plato)).toEqual(meses(0, 11))
  })

  it('rampa linear (só pela API): a mesma regra, no mês de operação', () => {
    const reta = Array.from({ length: 60 }, (_, i) => ({ mes: i + 1, v: Math.min(i + 1, 8) * 250 }))
    const { plato, limite } = eixoDaRampa(mesFimDaRampa(LINEAR), false, reta)
    expect(mesesDaGrade(limite, plato)).toEqual([0, 1, 2, 3, 4, 5, 6, 7, 9])
  })

  it('eixo de um mês fica só com a borda esquerda; eixo degenerado, sem grade (nem laço infinito)', () => {
    // série de 2 pontos (meses 0 e 1): o eixo vai de 0 a 1
    expect(mesesDaGrade(1, null)).toEqual([0])
    for (const limite of [0, -3, Number.NaN, Number.POSITIVE_INFINITY]) {
      expect(mesesDaGrade(limite, null)).toEqual([])
    }
  })

  it('o gráfico desenha a grade ATRÁS da área e da linha, distinta do marcador do platô', () => {
    const fonte = FONTES_DE_TEXTO.graficos
    const corpo = fonte.slice(
      fonte.indexOf('export function RampaAlunos('),
      fonte.indexOf('export function FluxoCaixa('),
    )
    expect(corpo).toContain('mesesDaGrade(limite, mat)')
    const iGrade = corpo.indexOf('{grade.map(')
    expect(iGrade, 'a grade não é desenhada').toBeGreaterThan(-1)
    // no SVG, a ordem do código é a ordem de pintura: o que vem antes fica atrás
    expect(iGrade).toBeLessThan(corpo.indexOf('<polygon points={area}'))
    expect(iGrade).toBeLessThan(corpo.indexOf('<polyline'))
    const linha = corpo.slice(iGrade, corpo.indexOf('/>', iGrade))
    const marcador = corpo.slice(corpo.indexOf('{xMat != null && ('), corpo.indexOf('<polyline'))
    const attr = (trecho: string, nome: string) =>
      new RegExp(`\\s${nome}="([^"]*)"`).exec(trecho)?.[1]
    // tracejada, fina e sem deformar com o preserveAspectRatio="none"
    expect(attr(linha, 'strokeDasharray')).toBeTruthy()
    // o traço do mês 0 é mais largo: na borda, o SVG corta a metade de fora
    expect(linha).toContain('strokeWidth={larguraDaLinhaDaGrade(m)}')
    expect(attr(linha, 'vectorEffect')).toBe('non-scaling-stroke')
    // sem crispEdges: em escala de tela fracionária ele dá 1 px a umas linhas e 2 a outras
    expect(linha).not.toContain('crispEdges')
    // cor própria da grade, do design system (não a de destaque), e outro tracejado
    expect(attr(linha, 'stroke')).toBe('var(--line-grid)')
    expect(attr(marcador, 'stroke')).toBe('var(--ac)')
    expect(attr(marcador, 'strokeDasharray')).toBe('3 3')
    expect(attr(linha, 'strokeDasharray')).not.toBe(attr(marcador, 'strokeDasharray'))
  })
})

describe('padrão do pico por estado (emenda de 29/10/2026 da DEC-078)', () => {
  const SP = { meses: 11, origem: 'estado' as const, uf: 'SP', unidades_maduras: 17, competencia_corte: '2026-09' }
  const GO = { meses: 10, origem: 'rede' as const, uf: 'GO', unidades_maduras: 0, competencia_corte: '2026-09' }
  const SEM = { meses: 10, origem: 'padrao' as const, uf: null, unidades_maduras: null, competencia_corte: null }

  it('a ajuda diz de onde veio o padrão, em uma linha', () => {
    expect(ajudaDaRampa({ ...CURVA, mes_pico_rampa: 11, pico_padrao: SP })).toBe(
      'Padrão de SP: 11 meses, de 17 unidades maduras. Recalcule para atualizar o payback.',
    )
    expect(ajudaDaRampa({ ...CURVA, pico_padrao: GO })).toBe(
      'Padrão da rede: 10 meses (GO tem menos de 5 maduras). Recalcule para atualizar o payback.',
    )
    for (const pp of [SP, GO, SEM]) {
      // pedido de 22/10/2026: a ajuda é UMA linha
      expect(ajudaDaRampa({ ...CURVA, pico_padrao: pp }).length).toBeLessThanOrEqual(95)
    }
  })

  it('sem medição publicada, a ajuda e a nota são as de antes', () => {
    expect(origemDoPadrao(SEM)).toBeNull()
    expect(origemDoPadrao(null)).toBeNull()
    expect(ajudaDaRampa({ ...CURVA, pico_padrao: SEM })).toBe(ajudaDaRampa(CURVA))
    expect(notaDaRampa({ ...CURVA, pico_padrao: SEM })).toBe(notaDaRampa(CURVA))
  })

  it('a nota metodológica explica a regra e o mês da medição', () => {
    const nota = notaDaRampa({ ...CURVA, pico_padrao: SP })
    expect(nota.startsWith(notaDaRampa(CURVA))).toBe(true)
    expect(nota).toContain('5 ou mais unidades maduras')
    expect(nota).toContain('no máximo 1 mês por vez (medição até set/2026).')
  })

  it('mês curto', () => {
    expect(mesCurto('2026-09')).toBe('set/2026')
    expect(mesCurto('2026-13')).toBeNull()
    expect(mesCurto(null)).toBeNull()
  })

  it('o contador mostra o pico que o servidor usou, e sem escolha o pedido não manda pico', () => {
    expect(picoExibido(null, { ...CURVA, mes_pico_rampa: 11, pico_padrao: SP })).toBe(11)
    expect(picoParaEnviar(null)).toBeUndefined()
  })
})
