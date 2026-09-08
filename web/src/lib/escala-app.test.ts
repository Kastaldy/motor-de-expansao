import { describe, expect, it } from 'vitest'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'

/* A escala global de 69% (PR #301, `--escala-app` em styles/global.css) foi REVERTIDA
   a pedido do Juan em 2026-09-08: o app volta a renderizar a 100% e quem precisar de
   mais largura ajusta o zoom do navegador. Reintroduzir escala global e' decisao de
   produto — se ela voltar, este teste morre junto, de proposito. */

const ler = (rel: string) => readFileSync(fileURLToPath(new URL(rel, import.meta.url)), 'utf-8')

describe('app sem escala global (reversao do PR #301)', () => {
  it('global.css nao define --escala-app nem transform no #root', () => {
    const css = ler('../styles/global.css')
    expect(css).not.toContain('--escala-app')
    expect(css).not.toMatch(/#root\s*\{[^}]*transform/)
  })

  it('o App mede a altura da janela com 100vh', () => {
    const tsx = ler('../App.tsx')
    expect(tsx).toContain("height: '100vh'")
  })
})
