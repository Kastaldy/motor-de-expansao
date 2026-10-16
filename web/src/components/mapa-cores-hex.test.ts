/**
 * Chave "Cores dos hexágonos" e o painel único do trilho (pedido do Vinicius, 2026-10-16).
 *
 * As regras puras moram em `lib/painel-trilho` e `lib/contorno-halo`, testadas lá. Aqui só se
 * trava a LIGAÇÃO no fonte — o vitest roda em node e não monta o deck.gl.
 */
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'

import { describe, expect, it } from 'vitest'

const ler = (rel: string) => readFileSync(fileURLToPath(new URL(rel, import.meta.url)), 'utf-8')
const hexMap = ler('./HexMap.tsx')
const barra = ler('./BarraCamadas.tsx')
const mapScreen = ler('../screens/MapScreen.tsx')

describe('cores dos hexágonos', () => {
  it('desligadas, o hexágono fica invisível mas CLICÁVEL (alfa 1, não 0)', () => {
    expect(hexMap).toContain('if (!coresHex) return [0, 0, 0, 1]')
    expect(hexMap).toContain('return coresHex ? [8, 11, 16, 55] : pele.gradeSemCor')
  })

  it('a coropleta recortada do raio sai junto, e a chave entra nos gatilhos e nas deps', () => {
    expect(hexMap).toContain('...(coresHex && raio1km && PASSOS_DA_PRESSAO.has(passo.n) && cobertura1k?.pecas?.length')
    expect(hexMap).toContain('getFillColor: [passo.n, raio1km, hexesCobertos, tema, coresHex]')
    const deps = hexMap.slice(hexMap.indexOf('    return base\n  }, ['))
    expect(deps.slice(0, deps.indexOf('])'))).toContain('coresHex,')
  })

  it('a chave mora no painel de camadas, ligada por padrão, e a legenda some sem cor', () => {
    expect(mapScreen).toContain("id: 'cores-hex'")
    expect(mapScreen).toContain('const [coresHex, setCoresHex] = useState(true)')
    expect(mapScreen).toContain('{legendaVisivel && coresHex && (')
    expect(mapScreen).toContain('legendaDisponivel={coresHex}')
    expect(mapScreen).toContain('coresHex={coresHex}')
  })
})

describe('painel do trilho: uma caixa só', () => {
  it('camadas e desenho usam o MESMO invólucro, e nunca juntos', () => {
    expect(barra).toContain('export function PainelDoTrilho(')
    expect(barra).toContain('rotulo="Camadas do mapa"')
    expect(barra).toContain('rotulo="Desenhar área"')
    expect(barra).toMatch(/\{aberto \? \(\s*<PainelDoTrilho[\s\S]*\) : painelDesenho \? \(/)
  })

  it('a barra antiga empilhada acima do trilho não existe mais', () => {
    expect(mapScreen).not.toContain('aria-label="Desenho da área"')
  })
})

describe('contorno duplo (halo)', () => {
  it('área desenhada, área concluída e pin da comparação têm a passada de halo por baixo', () => {
    for (const id of [
      "['desenho-arestas-halo', aresta.halo]",
      "id: 'desenho-vertices-halo'",
      "id: 'comparacao-areas-halo'",
      "id: 'comparacao-pin-halo'",
    ]) {
      expect(hexMap).toContain(id)
    }
    // O halo vem ANTES (por baixo) da passada de cor.
    expect(hexMap.indexOf("id: 'comparacao-pin-halo'")).toBeLessThan(
      hexMap.indexOf("id: 'comparacao-pin-anel'"),
    )
    expect(hexMap.indexOf("id: 'comparacao-areas-halo'")).toBeLessThan(
      hexMap.indexOf("id: 'comparacao-areas',"),
    )
  })
})
