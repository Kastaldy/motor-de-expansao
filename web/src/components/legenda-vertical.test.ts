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
