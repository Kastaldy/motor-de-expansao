import { describe, expect, it } from 'vitest'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'

/* A escala global do app e' 85% — decisao de produto do Juan (2026-09-09, PR #324),
   substituindo tanto o 0.69 do PR #301 quanto a reversao total que este ramo carregou
   primeiro. O valor vive num lugar so' (`--escala-app` em styles/global.css); mudar a
   escala e' mudar la' e atualizar a assercao aqui, junto — nunca um segundo arquivo
   declarando o numero por conta propria. */

const ler = (rel: string) => readFileSync(fileURLToPath(new URL(rel, import.meta.url)), 'utf-8')

describe('escala global do app em 85% (PR #324)', () => {
  it('global.css define --escala-app: 0.85 num lugar so', () => {
    const css = ler('../styles/global.css')
    expect(css.match(/--escala-app:\s*0\.85/g)).toHaveLength(1)
  })

  it('#root mede em 1/escala e encolhe com transform ancorado no canto', () => {
    /* ha' mais de um bloco `#root` no arquivo (o de `height: 100%` vem antes) —
       o bloco da escala e' o que consome a variavel. */
    const css = ler('../styles/global.css')
    const blocos = css.match(/#root\s*\{[^}]*\}/g) ?? []
    const root = blocos.find((b) => b.includes('--escala-app')) ?? ''
    expect(root).toContain('width: calc(100% / var(--escala-app))')
    expect(root).toContain('height: calc(100% / var(--escala-app))')
    expect(root).toContain('transform: scale(var(--escala-app))')
    expect(root).toContain('transform-origin: 0 0')
  })

  it("o App mede height: '100%' — 100vh nao enxerga a escala", () => {
    const tsx = ler('../App.tsx')
    expect(tsx).toContain("height: '100%'")
    expect(tsx).not.toContain("height: '100vh'")
  })
})
