/* A legenda do passo 4 ("Área construída 2016–2023") tem o MESMO desenho das legendas das
   outras camadas (pedido de 2026-11-10: "a legenda da camada 4 não está igual das outras
   camadas"). Antes ela tinha bloco próprio — swatch 8x8, rótulo minúsculo com o corte entre
   parênteses e "sem medição" sem o filete que separa o que não é faixa. Agora usa o `Bloco`
   das camadas 1-3/5: swatch 14x9, nome com inicial maiúscula, corte na sublinha (como os
   alunos das camadas 2/3) e o item sem dado atrás do filete (como o "< 5k hab").

   Render de string (`renderToStaticMarkup`), sem DOM — o mesmo recurso de portal.test.ts. */
import { createElement } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'

import { CRESC_ALTA_HEX, CRESC_ESTAVEL_HEX, CRESC_PARADO_HEX } from '../lib/colors'
import ScoreLegend from './ScoreLegend'

const legenda = (passoN: number) => renderToStaticMarkup(createElement(ScoreLegend, { passoN }))

/** Os swatches desenhados, na ordem: `width:Wpx;height:Hpx;...;background:COR`. */
function swatches(markup: string): { w: string; h: string; cor: string }[] {
  return [...markup.matchAll(/width:(\d+)px;height:(\d+)px;border-radius:2px;background:([^;"]+)/g)].map(
    (m) => ({ w: m[1], h: m[2], cor: m[3] }),
  )
}

describe('legenda do passo 4 no padrão das outras camadas', () => {
  const p4 = legenda(4)
  const p1 = legenda(1)

  it('mesma caixa e mesmo título das outras legendas', () => {
    const abertura = (m: string) => m.slice(0, m.indexOf('>', m.indexOf('<div', 1)) + 1)
    expect(abertura(p4)).toBe(abertura(p1))
    expect(p4).toContain('Área construída 2016–2023')
  })

  it('todo swatch tem o tamanho do Bloco das camadas 1-3 (14x9), nenhum 8x8', () => {
    const s4 = swatches(p4)
    expect(s4).toHaveLength(4)
    expect(s4.every((s) => s.w === '14' && s.h === '9')).toBe(true)
    expect(new Set(swatches(p1).map((s) => `${s.w}x${s.h}`))).toEqual(new Set(['14x9']))
    expect(p4).not.toContain('width:8px;height:8px')
  })

  it('do positivo ao negativo, com as cores do mapa e o corte na sublinha', () => {
    expect(swatches(p4).map((s) => s.cor)).toEqual([
      CRESC_ALTA_HEX,
      CRESC_ESTAVEL_HEX,
      CRESC_PARADO_HEX,
      'rgba(120,120,140,.45)',
    ])
    const ordem = ['Em alta', '30%+', 'Estável', '0–30%', 'Sem obra nova', '&lt; 0%', 'Sem medição']
    const pos = ordem.map((t) => p4.indexOf(`>${t}<`))
    expect(pos.every((p) => p >= 0)).toBe(true)
    expect(pos).toEqual([...pos].sort((a, b) => a - b))
  })

  it('"Sem medição" fica atrás do filete, como o "< 5k hab" das outras camadas', () => {
    const filete = 'border-top:1px solid var(--line-mid)'
    expect(p4).toContain(filete)
    expect(p4.indexOf(filete)).toBeLessThan(p4.indexOf('>Sem medição<'))
    expect(p4.indexOf(filete)).toBeGreaterThan(p4.indexOf('>Sem obra nova<'))
  })
})

describe('mapa do passo 4: pintado como as outras camadas, sem holofote', () => {
  it('o passo 4 pinta pela classe com a opacidade do tema, sem esmaecer o que está fora do recorte', async () => {
    const { readFileSync } = await import('node:fs')
    const { fileURLToPath } = await import('node:url')
    const fonte = readFileSync(fileURLToPath(new URL('./HexMap.tsx', import.meta.url)), 'utf-8').replace(/\r\n/g, '\n')
    const ramo = fonte.slice(fonte.indexOf('if (passoN === 4)'), fonte.indexOf('\n', fonte.indexOf('if (passoN === 4)')))
    expect(ramo).toContain('crescClasseToColor(h.cres_hex_classe, alphaHex)')
    expect(ramo).not.toContain('cres_hex_taxa')
    expect(ramo).not.toContain('DIM_FORA_DO_PASSO')
    expect(ramo).not.toContain('noPasso')
  })
})
