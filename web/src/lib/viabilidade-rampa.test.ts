import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'

import { describe, expect, it } from 'vitest'

import * as rampa from './viabilidade-rampa'
import {
  MESES_PICO_RAMPA,
  ajudaDaRampa,
  casaNoMes1,
  ebitdaDosPrimeirosMeses,
  formaDoPayload,
  mesFimDaRampa,
  notaDaRampa,
  picoExibido,
  picoParaEnviar,
  rotuloPico,
} from './viabilidade-rampa'

const CURVA_OBS = [0.68, 0.77, 0.84, 0.88, 0.9, 0.92, 0.97, 0.97, 0.99, 1, 1, 1]
const CURVA = {
  maturacao_meses: 8,
  forma_rampa: 'curva_uni03',
  mes_maturidade_rampa: 10,
  mes_pico_rampa: 10,
  curva_rampa: CURVA_OBS,
}
const CURVA_PICO_6 = {
  maturacao_meses: 8,
  forma_rampa: 'curva_uni03',
  mes_maturidade_rampa: 6,
  mes_pico_rampa: 6,
  curva_rampa: [0.74, 0.853333, 0.9, 0.953333, 0.976667, 1, 1, 1],
}
// Rampa linear: só chega da API pública ou com a constante do servidor revertida.
const LINEAR = { maturacao_meses: 8, forma_rampa: 'reta', mes_maturidade_rampa: 8, mes_pico_rampa: null }

describe('pico de maturação (emenda de 21/10/2026 da DEC-077)', () => {
  it('as opções espelham SIM_MESES_PICO_RAMPA do servidor', () => {
    expect([...MESES_PICO_RAMPA]).toEqual([6, 8, 10, 12, 15, 18, 24])
    expect(rotuloPico(12)).toBe('12 meses')
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
    for (const m of MESES_PICO_RAMPA) {
      expect(JSON.parse(JSON.stringify({ mes_pico_rampa: picoParaEnviar(m) }))).toEqual({
        mes_pico_rampa: m,
      })
    }
  })

  it('sem escolha, o seletor marca o pico que o servidor usou', () => {
    expect(picoExibido(null, CURVA)).toBe(10)
    expect(picoExibido(null, CURVA_PICO_6)).toBe(6)
    // backend sem o eco do pico: cai no fim da rampa servido
    expect(picoExibido(null, { ...CURVA, mes_pico_rampa: undefined })).toBe(10)
  })

  it('antes do primeiro cálculo, ou na rampa linear, nenhum pico é marcado', () => {
    expect(picoExibido(null, null)).toBeNull()
    expect(picoExibido(null, LINEAR)).toBeNull()
  })

  it('a escolha do operador vence o pico servido', () => {
    expect(picoExibido(18, CURVA)).toBe(18)
  })
})

describe('ajuda do controle', () => {
  it('declara a amarra do agregador e que é preciso recalcular', () => {
    for (const p of [null, CURVA, CURVA_PICO_6, LINEAR]) {
      expect(ajudaDaRampa(p).toLowerCase()).toContain('recalcule para atualizar o payback')
    }
    expect(ajudaDaRampa(CURVA)).toContain('agregador')
  })

  it('os percentuais saem da curva servida, não de número cravado', () => {
    expect(ajudaDaRampa(CURVA)).toContain('68% da demanda no mês 1')
    expect(ajudaDaRampa(CURVA)).toContain('100% a partir do mês 10')
    expect(ajudaDaRampa(CURVA_PICO_6)).toContain('74% da demanda no mês 1')
    expect(ajudaDaRampa(CURVA_PICO_6)).toContain('100% a partir do mês 6')
    // antes do primeiro cálculo não há curva: a ajuda não inventa percentual
    expect(ajudaDaRampa(null)).not.toMatch(/\d+%/)
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
  it('lê o mês servido pelo motor (o pico), não o parâmetro da rampa linear', () => {
    expect(mesFimDaRampa(CURVA)).toBe(10)
    expect(mesFimDaRampa(CURVA_PICO_6)).toBe(6)
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

  it('o seletor de pico percorre as opções e manda mes_pico_rampa no pedido', () => {
    expect(TELA).toContain('MESES_PICO_RAMPA.map(')
    expect(TELA).toContain('onClick={() => setPicoRampa(m)}')
    expect(TELA).toContain('mes_pico_rampa: picoParaEnviar(picoRampa)')
    expect(TELA).toContain('aria-label="Pico de maturação, em meses"')
  })
})
