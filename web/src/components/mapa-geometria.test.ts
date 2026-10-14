import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'

/* "ANALISAR GEOMETRIA" NO MAPA (decisão 7 do dono, 2026-10-14; DEC-070 fase 1).

   As regras do desenho (fechar por pixels, área, autointerseção, limites) são puras e
   testadas de verdade em `lib/geometria-desenho.test.ts`; a entrada da área na lista, em
   `lib/pontos-estado.test.ts`. Aqui fica a FIAÇÃO, como asserção sobre TEXTO-FONTE — o
   vitest deste repo roda em node, sem jsdom, e não monta React nem WebGL (mesma razão do
   `mapa-pins-e-ponto.test.ts`). */

const ler = (rel: string) => readFileSync(fileURLToPath(new URL(rel, import.meta.url)), 'utf-8')
const hexMap = ler('./HexMap.tsx')
const barra = ler('./BarraCamadas.tsx')
const mapScreen = ler('../screens/MapScreen.tsx')
const app = ler('../App.tsx')
const pontoScreen = ler('../screens/PontoScreen.tsx')
const painel = ler('./PainelPontos.tsx')

describe('o clique é do desenho, por cima de tudo', () => {
  it('a flag única do clique ocupado inclui o desenho', () => {
    expect(hexMap).toContain('const cliqueOcupado = medindo || selecionandoPonto || desenhando')
  })

  it('o clique do DeckGL vira vértice, com a escala de TELA da câmera', () => {
    expect(hexMap).toContain('onCliqueDesenho?.({ lat, lng }, metrosPorPixel(view.zoom, lat))')
  })

  it('duplo clique NÃO dá zoom durante o desenho', () => {
    expect(hexMap).toContain('doubleClickZoom: !desenhando')
  })

  it('o provisório é desenhado (véu, arestas, vértices) e entra nas deps do memo', () => {
    for (const id of ["id: 'desenho-area'", "id: 'desenho-arestas'", "id: 'desenho-vertices'"]) {
      expect(hexMap).toContain(id)
    }
    const deps = hexMap.slice(hexMap.indexOf('    return base\n  }, ['))
    const lista = deps.slice(0, deps.indexOf('])'))
    expect(lista).toContain('desenhando,')
    expect(lista).toContain('verticesDesenho,')
  })
})

describe('MapScreen: ferramenta única, barra e Esc', () => {
  it('liga pela ferramenta única e passa o desenho ao mapa', () => {
    expect(mapScreen).toContain("alternarFerramenta(f, 'geometria')")
    expect(mapScreen).toContain("desenhando={ferramenta === 'geometria'}")
    expect(mapScreen).toContain('verticesDesenho={vertices}')
  })

  it('desligar a ferramenta (Esc, outro botão, Cancelar) apaga o desenho', () => {
    expect(mapScreen).toContain("if (ferramenta === 'geometria') return\n    setVertices([])")
    // O Esc que já desligava qualquer ferramenta é o mesmo que cancela o desenho.
    expect(mapScreen).toContain("setFerramenta('nenhuma')")
  })

  it('a barra tem Concluir, Desfazer e Cancelar, e a área ao vivo', () => {
    const barraDesenho = mapScreen.slice(mapScreen.indexOf('Barra do DESENHO'))
    for (const t of ['Concluir', 'Desfazer', 'Cancelar', 'formatarKm2(avaliacaoDesenho.areaKm2)']) {
      expect(barraDesenho).toContain(t)
    }
    expect(barraDesenho).toContain('disabled={!avaliacaoDesenho.podeConcluir}')
  })

  it('ao concluir, a área vai a quem a analisa e a ferramenta desliga', () => {
    const corpo = mapScreen.slice(mapScreen.indexOf('function concluirDesenho'))
    expect(corpo).toContain('onGeometriaDesenhada?.(paraGeoJson(vs).coordinates)')
    expect(corpo).toContain("setFerramenta('nenhuma')")
  })

  it('no painel, "Analisar geometria" vem depois da régua', () => {
    const regua = mapScreen.indexOf("id: 'medir'")
    const geo = mapScreen.indexOf("id: 'analisar-geometria'")
    expect(geo).toBeGreaterThan(regua)
  })
})

describe('trilho', () => {
  it('o botão fica ABAIXO da régua, em verde (nem o rosa da régua, nem o azul do ponto)', () => {
    const regua = barra.indexOf('icone="regua"')
    const geo = barra.indexOf('icone="poligono"')
    const comparar = barra.indexOf('icone="comparar"')
    expect(geo).toBeGreaterThan(regua)
    expect(geo).toBeLessThan(comparar)
    const bloco = barra.slice(geo, comparar)
    expect(bloco).toContain('cor="var(--gr-verde)"')
  })
})

describe('a área entra na comparação dos pontos', () => {
  it('o App leva a área à lista', () => {
    expect(app).toContain('onGeometriaDesenhada={(g) => void pontos.analisarGeometria(g)}')
  })

  it('a ficha diz o recorte (sem "raio de" escrito à mão)', () => {
    expect(pontoScreen).not.toMatch(/raio de \$\{num\(ficha\.raio_km/)
    expect(pontoScreen).toContain('rotuloDoRecorte(ficha)')
  })

  it('o PDF de comparação recusa área desenhada, com mensagem', () => {
    expect(painel).toContain('const semPdf = motivoSemPdfDeComparacao(fichas)')
    expect(painel).toContain('setErroRelatorio(semPdf)')
  })

  it('o Simulador só aparece ativo para quem tem a aba Viabilidade', () => {
    expect(app).toContain("onAnalisarPonto={telaLiberada('viabilidade', abas) ? irParaViabilidade : undefined}")
  })
})
