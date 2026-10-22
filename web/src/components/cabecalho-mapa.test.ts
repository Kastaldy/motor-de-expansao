/**
 * O cabeçalho do mapa ACIMA das janelas (pedido do Vinicius, 21/10/2026: "as outras abas
 * acabam ficando por cima dele, dificultando pra trocar estado / município").
 *
 * A ordem dos números é de `lib/camadas-mapa.test`. Aqui se trava que as PEÇAS usam esses
 * números -- uma constante certa que ninguém lê não protege nada. Lê o FONTE: o Vitest roda
 * sem DOM (molde de `camada-ponto.test`).
 */
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'

import { describe, expect, it } from 'vitest'

import { Z_CABECALHO_MAPA } from '../lib/camadas-mapa'

const fonte = (rel: string) => readFileSync(fileURLToPath(new URL(rel, import.meta.url)), 'utf-8')
const mapa = fonte('../screens/MapScreen.tsx')
const metodologia = fonte('./MethodologyPanel.tsx')
const hexmap = fonte('./HexMap.tsx')

describe('o cabeçalho do mapa', () => {
  it('usa Z_CABECALHO_MAPA (e não um número cravado)', () => {
    const abre = mapa.indexOf('className="barra-ultra"')
    expect(abre).toBeGreaterThan(-1)
    const estilo = mapa.slice(abre, mapa.indexOf('}}', abre))
    expect(estilo).toContain('zIndex: Z_CABECALHO_MAPA,')
  })

  it('a gaveta da Metodologia usa a constante dela, acima do cabeçalho', () => {
    expect(metodologia).toContain("import { Z_GAVETA_METODOLOGIA } from '../lib/camadas-mapa'")
    expect(metodologia).toContain('zIndex: Z_GAVETA_METODOLOGIA,')
    expect(metodologia).not.toMatch(/zIndex: \d/)
  })

  it('os tooltips do mapa seguem acima do cabeçalho (são transitórios e não pegam o mouse)', () => {
    const zs = [...hexmap.matchAll(/zIndex: (\d+)/g)].map((m) => Number(m[1]))
    expect(zs.length).toBeGreaterThan(0)
    for (const z of zs) expect(z).toBeGreaterThan(Z_CABECALHO_MAPA)
  })
})
