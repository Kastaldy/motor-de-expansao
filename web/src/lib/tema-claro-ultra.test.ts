import { describe, expect, it } from 'vitest'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'

/* O tema claro carrega as cores base da Ultra (Juan, 2026-09-08): turquesa #00A99E
   no fundo e no acento, magenta #C23C8E e laranja #EF7F1F como matizes de apoio na
   paleta de serie. Este teste le' o bloco [data-tema='claro'] de styles/tokens.css e
   verifica MATIZ (a identidade da marca) e CONTRASTE (as reguas que o proprio arquivo
   documenta) — numero em comentario envelhece, assercao nao. */

const css = readFileSync(fileURLToPath(new URL('../styles/tokens.css', import.meta.url)), 'utf-8')

function bloco(seletor: string): Record<string, string> {
  const ini = css.indexOf(`${seletor} {`)
  expect(ini).toBeGreaterThan(-1)
  const fim = css.indexOf('\n}', ini)
  const tokens: Record<string, string> = {}
  for (const m of css.slice(ini, fim).matchAll(/(--[a-z0-9-]+):\s*([^;]+);/g)) {
    tokens[m[1]] = m[2].trim()
  }
  return tokens
}

const blocoClaro = () => bloco("[data-tema='claro']")
/* O bloco escuro e' o :root; desde 2026-09-09 ele segue as MESMAS matizes da marca
   (o acento saiu do ~186° herdado do prototipo para o turquesa Ultra, e rosa/coral
   ancoram no magenta e no laranja de apoio, aclarados para o fundo escuro). */
const blocoEscuro = () => bloco(':root')

const hex2rgb = (h: string) => [1, 3, 5].map((i) => parseInt(h.slice(i, i + 2), 16))

/* Base rgb de um token de superficie (`rgba(r, g, b, a)` ou hex chapado), como hex. */
function baseDaSuperficie(valor: string): string {
  const m = valor.match(/rgba?\((\d+),\s*(\d+),\s*(\d+)/)
  if (!m) return valor
  return '#' + m.slice(1, 4).map((v) => Number(v).toString(16).padStart(2, '0')).join('')
}

function hsl(hex: string): [number, number, number] {
  let [r, g, b] = hex2rgb(hex).map((v) => v / 255)
  const max = Math.max(r, g, b)
  const min = Math.min(r, g, b)
  const l = (max + min) / 2
  if (max === min) return [0, 0, l]
  const d = max - min
  const s = l > 0.5 ? d / (2 - max - min) : d / (max + min)
  let h: number
  if (max === r) h = (g - b) / d + (g < b ? 6 : 0)
  else if (max === g) h = (b - r) / d + 2
  else h = (r - g) / d + 4
  return [h * 60, s, l]
}

const luminancia = (hex: string) => {
  const [r, g, b] = hex2rgb(hex).map((v) => {
    const c = v / 255
    return c <= 0.03928 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4)
  })
  return 0.2126 * r + 0.7152 * g + 0.0722 * b
}

const contraste = (a: string, b: string) => {
  const [x, y] = [luminancia(a), luminancia(b)].sort((p, q) => q - p)
  return (x + 0.05) / (y + 0.05)
}

const difMatiz = (a: number, b: number) => Math.min(Math.abs(a - b), 360 - Math.abs(a - b))

const H_TURQUESA = hsl('#00a99e')[0] // ~176
const H_MAGENTA = hsl('#c23c8e')[0] // ~323
const H_LARANJA = hsl('#ef7f1f')[0] // ~28

describe('tema claro nas cores base da Ultra', () => {
  const t = blocoClaro()

  it('o fundo tem a matiz do turquesa Ultra, nao um neutro azulado', () => {
    const [h, s] = hsl(t['--bg-base'])
    expect(difMatiz(h, H_TURQUESA)).toBeLessThanOrEqual(12)
    expect(s).toBeGreaterThanOrEqual(0.35)
    expect(difMatiz(hsl(t['--bg-lift'])[0], H_TURQUESA)).toBeLessThanOrEqual(12)
  })

  it('o acento e a camada 4 (par deliberado) seguem o turquesa Ultra', () => {
    expect(difMatiz(hsl(t['--ac'])[0], H_TURQUESA)).toBeLessThanOrEqual(8)
    expect(t['--l4']).toBe(t['--ac'])
  })

  it('magenta e laranja Ultra sao as matizes de apoio da paleta de serie', () => {
    expect(difMatiz(hsl(t['--gr-rosa'])[0], H_MAGENTA)).toBeLessThanOrEqual(8)
    expect(difMatiz(hsl(t['--gr-coral'])[0], H_LARANJA)).toBeLessThanOrEqual(20)
  })

  it('as superficies glass sao gelo turquesa, nao branco puro', () => {
    for (const nome of ['--surf-panel', '--surf-card', '--surf-sidebar', '--surf-mapa']) {
      const base = baseDaSuperficie(t[nome])
      const [h, s, l] = hsl(base)
      expect(s, nome).toBeGreaterThan(0)
      expect(difMatiz(h, H_TURQUESA), nome).toBeLessThanOrEqual(12)
      expect(l, nome).toBeLessThan(1) // branco puro tem L = 1
    }
  })

  it('as reguas de contraste do bloco continuam passando', () => {
    const superficie = baseDaSuperficie(t['--surf-panel'])
    expect(contraste(t['--ac-text'], superficie)).toBeGreaterThanOrEqual(4.5)
    expect(contraste(t['--tx-muted'], superficie)).toBeGreaterThanOrEqual(4.5)
    expect(contraste(t['--gr-coral'], superficie)).toBeGreaterThanOrEqual(3)
    expect(contraste(t['--tx-muted'], t['--bg-base'])).toBeGreaterThanOrEqual(4.5)
  })
})

describe('tema escuro nas mesmas cores base da Ultra', () => {
  const t = blocoEscuro()

  it('o acento e a camada 4 (par deliberado) seguem o turquesa Ultra', () => {
    expect(difMatiz(hsl(t['--ac'])[0], H_TURQUESA)).toBeLessThanOrEqual(8)
    expect(t['--l4']).toBe(t['--ac'])
  })

  it('magenta e laranja Ultra sao as matizes de apoio da paleta de serie', () => {
    expect(difMatiz(hsl(t['--gr-rosa'])[0], H_MAGENTA)).toBeLessThanOrEqual(8)
    expect(difMatiz(hsl(t['--gr-coral'])[0], H_LARANJA)).toBeLessThanOrEqual(20)
  })
})
