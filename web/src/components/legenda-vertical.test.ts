import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'

import { describe, expect, it } from 'vitest'

const fonte = readFileSync(fileURLToPath(new URL('./ScoreLegend.tsx', import.meta.url)), 'utf-8')

describe('legenda do mapa na vertical', () => {
  it('as três legendas usam o MESMO contêiner, derivado de uma chave só', () => {
    expect(fonte).toContain('export const LEGENDA_VERTICAL = true')
    expect(fonte.match(/<div style=\{LINHA\}>/g)).toHaveLength(3)
    // Nenhum contêiner de faixas ficou com a fileira cravada.
    expect(fonte).not.toContain("gap: 9, flexWrap: 'wrap' }}>")
  })

  it('o filete de separação segue a orientação (nenhum borderLeft cravado)', () => {
    expect(fonte.match(/\.\.\.SEPARADOR|style=\{SEPARADOR\}/g)).toHaveLength(3)
    expect(fonte.split("borderLeft: '1px solid var(--line-mid)'")).toHaveLength(2)
  })
})

describe('legenda vertical: positivo em cima, negativo embaixo', () => {
  it('as rampas são invertidas na hora de desenhar', async () => {
    const { doPositivoAoNegativo } = await import('./ScoreLegend')
    const { faixasDoPasso } = await import('../lib/faixas')
    const { legendaDoCalor } = await import('../lib/camadas-calor')
    expect(doPositivoAoNegativo(faixasDoPasso(1) ?? []).map((f) => f.nome)).toEqual([
      'Excelente',
      'Forte',
      'Promissor',
      'Fraco',
      'Desfavorável',
    ])
    expect(doPositivoAoNegativo(faixasDoPasso(2) ?? [])[0].nome).toBe('Livre')
    expect(doPositivoAoNegativo(legendaDoCalor('densidade').faixas)[0].rotulo).toBe('>25.000')
    expect(doPositivoAoNegativo(legendaDoCalor('renda').faixas).at(-1)?.rotulo).toMatch(/^até /)
  })

  it('as duas rampas da legenda passam pela inversão; M1 e crescimento já nascem do melhor', () => {
    expect(fonte.match(/doPositivoAoNegativo\(faixas\)\.map/g)).toHaveLength(2)
    expect(fonte).toContain("[CRESC_ALTA_HEX, 'em alta (+30%)'],")
  })
})

describe('texto da legenda com mais contraste (pedido de 20/10/2026)', () => {
  it('título, nome e sublinha usam os tokens FORTES do tema, com peso maior', async () => {
    const { TITULO, NOME, SUB } = await import('./ScoreLegend')
    expect(TITULO.color).toBe('var(--tx-strong)')
    expect(NOME.color).toBe('var(--tx-strong)')
    expect(SUB.color).toBe('var(--tx-soft)')
    const peso = (f: unknown) => Number(String(f).split(' ')[0])
    expect(peso(TITULO.font)).toBeGreaterThanOrEqual(600)
    expect(peso(NOME.font)).toBeGreaterThanOrEqual(500)
    expect(peso(SUB.font)).toBeGreaterThanOrEqual(500)
  })

  it('nenhum texto da legenda volta aos tokens de apoio', () => {
    expect(fonte).not.toContain("color: 'var(--tx-sub)'")
    expect(fonte).not.toContain("color: 'var(--tx-label)'")
  })

  it('os tokens fortes são os de maior contraste nos DOIS temas', () => {
    const tokens = readFileSync(fileURLToPath(new URL('../styles/tokens.css', import.meta.url)), 'utf-8')
    const valores = (nome: string) => [...tokens.matchAll(new RegExp(`--${nome}: (#[0-9a-f]{6});`, 'g'))].map((m) => m[1])
    const luz = (h: string) => {
      const c = [1, 3, 5].map((i) => parseInt(h.slice(i, i + 2), 16) / 255)
      const l = c.map((x) => (x <= 0.03928 ? x / 12.92 : ((x + 0.055) / 1.055) ** 2.4))
      return 0.2126 * l[0] + 0.7152 * l[1] + 0.0722 * l[2]
    }
    // [0] = tema escuro (:root), [1] = tema claro. No escuro o forte é mais CLARO, no
    // claro mais ESCURO que os tokens de apoio de antes.
    const [forteE, forteC] = valores('tx-strong')
    const [suaveE, suaveC] = valores('tx-soft')
    for (const antigo of ['tx-sub', 'tx-label']) {
      const [e, c] = valores(antigo)
      expect(luz(forteE)).toBeGreaterThan(luz(e))
      expect(luz(suaveE)).toBeGreaterThan(luz(e))
      expect(luz(forteC)).toBeLessThan(luz(c))
      expect(luz(suaveC)).toBeLessThan(luz(c))
    }
  })
})
