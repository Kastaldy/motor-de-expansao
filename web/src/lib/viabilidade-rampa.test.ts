import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'

import { describe, expect, it } from 'vitest'

import * as rampa from './viabilidade-rampa'
import {
  PICO_RAMPA_MAX,
  PICO_RAMPA_MIN,
  PICO_RAMPA_OBSERVADO,
  ajudaDaRampa,
  casaNoMes1,
  ebitdaDosPrimeirosMeses,
  formaDoPayload,
  mesFimDaRampa,
  notaDaRampa,
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

describe('pico de maturação (emenda de 21/10/2026 da DEC-077)', () => {
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

  it('backend anterior à DEC-077 (sem o campo) cai na rampa de maturacao_meses', () => {
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
