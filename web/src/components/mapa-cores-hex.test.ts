/**
 * Chave "Cores dos hexágonos" e o painel único do trilho (pedido do Vinicius, 2026-10-16).
 *
 * As regras puras moram em `lib/painel-trilho` e `lib/contorno-halo`, testadas lá. Aqui só se
 * trava a LIGAÇÃO no fonte — o vitest roda em node e não monta o deck.gl.
 */
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'

import { describe, expect, it } from 'vitest'

// `\r\n -> \n`: os recortes abaixo procuram `\n`, e o checkout Windows (core.autocrlf) traz
// o fonte em CRLF — sem isto o teste reprovava só na máquina local, nunca no CI.
const ler = (rel: string) =>
  readFileSync(fileURLToPath(new URL(rel, import.meta.url)), 'utf-8').replace(/\r\n/g, '\n')
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
    // O Top 10 da camada 5 (recomendação única) também entra no gatilho do preenchimento:
    // sem ele, trocar de município manteria a cor de segmento dos hexágonos antigos.
    expect(hexMap).toContain('getFillColor: [passo.n, raio1km, hexesCobertos, tema, coresHex, top10Chave]')
    const deps = hexMap.slice(hexMap.indexOf('    return base\n  }, ['))
    expect(deps.slice(0, deps.indexOf('])'))).toContain('coresHex,')
  })

  it('na camada 5, a cor do segmento do Top 10 vem ANTES do corte de < 5k hab', () => {
    /* O Top 10 lê o recorte inteiro com régua própria: um Premium ou Mata Virgem nunca
       pode sair cinza "descartado" no mapa enquanto o painel o lista. */
    const fonte = hexMap.replace(/\r\n/g, '\n')
    const corpo = fonte.slice(fonte.indexOf('function fillDoHex('), fonte.indexOf('/* --- Numeros do ranking'))
    expect(corpo).toContain('corTop10(')
    expect(corpo.indexOf('corTop10(')).toBeGreaterThan(-1)
    expect(corpo.indexOf('corTop10(')).toBeLessThan(corpo.indexOf('h.pop < POP_MIN_ACIONAVEL'))
  })

  it('a chave mora no painel de camadas, ligada por padrão, e a legenda some sem cor', () => {
    expect(mapScreen).toContain("id: 'cores-hex'")
    expect(mapScreen).toContain('const [coresHex, setCoresHex] = useState(true)')
    expect(mapScreen).toContain('{legendaVisivel && coresHex && (')
    expect(mapScreen).toContain('legendaDisponivel={coresHex || calorDesenhado}')
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

describe('captura do mapa (PDF)', () => {
  it('o desenho PAUSADO nao entra na foto: vertices vazios com `capturando`', () => {
    expect(hexMap).toContain('const vertices = capturando ? [] : (verticesDesenho ?? [])')
  })

  it('os halos novos tambem saem da foto', () => {
    expect(hexMap).toContain('...(!capturando && cenarioLista.length')
    // o halo do search-hex depende de `pinDoSearch`, que e nulo durante a captura
    expect(hexMap).toContain('if (!searchPin || capturando) return null')
    expect(hexMap).toMatch(/if \(pinDoSearch\) \{\s+const halo = tracoComHalo/)
  })
})

describe('ordem das chaves de cor no painel de camadas', () => {
  it('"Cores dos hexágonos" vem logo acima dos mapas de calor', () => {
    const iCores = mapScreen.indexOf("id: 'cores-hex'")
    const iDensidade = mapScreen.indexOf("id: 'calor-densidade'")
    expect(iCores).toBeGreaterThan(-1)
    expect(iDensidade).toBeGreaterThan(iCores)
    // Nenhuma outra chave entre as duas.
    expect(mapScreen.slice(iCores + 1, iDensidade)).not.toMatch(/id: '[a-z-]+',\n\s+icone:/)
  })
})
