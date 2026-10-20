import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'

/* "ANALISAR GEOMETRIA" NO MAPA (decisão 7 do dono, 2026-10-14; DEC-071 fase 1).

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
    for (const id of [
      "id: 'desenho-area'",
      "['desenho-arestas', aresta.traco]",
      "id: 'desenho-vertices'",
    ]) {
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
    expect(mapScreen).toContain("acaoTrilho({ tipo: 'alternar-ferramenta', alvo: 'geometria' })")
    expect(mapScreen).toContain("desenhando={ferramenta === 'geometria'}")
    expect(mapScreen).toContain('verticesDesenho={vertices}')
  })

  it('Esc e Cancelar apagam o desenho; fechar o painel só PAUSA (lib/painel-trilho)', () => {
    // Quem apaga é `encerrarDesenho` com motivo que não seja pausa (`rascunhoSobrevive`).
    expect(mapScreen).toContain('if (!rascunhoSobrevive(motivo)) setVertices([])')
    expect(mapScreen).toContain("if (ferramenta === 'geometria') encerrarDesenho('esc')")
    expect(mapScreen).toContain("onClick={() => encerrarDesenho('cancelar')}")
    expect(mapScreen).toContain("onFechar: () => encerrarDesenho('pausa')")
    // Não há mais efeito que apague os vértices ao desligar a ferramenta.
    expect(mapScreen).not.toContain("if (ferramenta === 'geometria') return\n    setVertices([])")
  })

  it('a barra tem Concluir, Desfazer e Cancelar, e a área ao vivo', () => {
    const barraDesenho = mapScreen.slice(mapScreen.indexOf('Painel do DESENHO'))
    for (const t of ['Concluir', 'Desfazer', 'Cancelar', 'formatarKm2(avaliacaoDesenho.areaKm2)']) {
      expect(barraDesenho).toContain(t)
    }
    expect(barraDesenho).toContain('disabled={!avaliacaoDesenho.podeConcluir}')
  })

  it('ao concluir, a área vai a quem a analisa e a ferramenta desliga', () => {
    const corpo = mapScreen.slice(mapScreen.indexOf('function concluirDesenho'))
    expect(corpo).toContain('onGeometriaDesenhada?.(paraGeoJson(vs).coordinates)')
    expect(corpo).toContain("encerrarDesenho('concluir')")
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

  it('o PDF de comparação aceita área e alcance (fase 2 da DEC-071): a recusa saiu', () => {
    expect(painel).not.toContain('motivoSemPdfDeComparacao')
  })

  it('o ranking do PDF é o MESMO da tela (sem os totais quando os recortes diferem)', () => {
    expect(painel).toContain('ranquear(dimensoesDoComparativo(fichas), fichas, rotulos')
    expect(painel).not.toMatch(/ranquear\(DIMENSOES_PONTO/)
  })

  it('cada item leva o seu recorte ao PDF, e a foto o contorno sempre (o de 1 km também)', () => {
    expect(painel).toContain('recorte: recorteParaOPdf(fichas[it.indice])')
    expect(painel).toContain('contorno: contornosDoItem(f),')
    expect(painel).not.toContain("tipoDoRecorte(f) !== 'raio_1km' ? { contorno")
  })

  it('o Simulador só aparece ativo para quem tem a aba Viabilidade', () => {
    // `simularDaFicha` = `irParaViabilidade` + a marca de que a ida saiu da ficha (é o que
    // a faz reabrir na volta, e só nela — `janelaNaMontagem`).
    expect(app).toContain("onAnalisarPonto={telaLiberada('viabilidade', abas) ? simularDaFicha : undefined}")
    expect(app).toContain('reabrirFicha={fichaNoSimulador}')
  })
})

/* ---------------- Alcance do ponto (DEC-074): a fiação ---------------- */
describe('o alcance do ponto, da ficha ao mapa', () => {
  const main = ler('../main.tsx')

  it('o perfil diz quais alcances existem (`/api/me`), antes da árvore', () => {
    expect(main).toContain('definirAlcances(me.alcances)')
    expect(main.indexOf('definirAlcances(me.alcances)')).toBeLessThan(main.indexOf("await import('./App')"))
  })

  it('o App liga o seletor da ficha à troca NO LUGAR da lista', () => {
    expect(app).toContain('onTrocarAlcance={(i, alcance) => void pontos.trocarAlcance(i, alcance)}')
  })

  it('a ficha mostra o seletor só em ponto, com mais de uma opção, e o modo Ultra só no 1 km', () => {
    expect(pontoScreen).toContain('{!area && alcance && onTrocarAlcance && opcoesDeAlcance.length > 1 && (')
    expect(pontoScreen).toContain('role="radiogroup"')
    expect(pontoScreen).toContain("{ofertaUltra && alcance === 'raio_1km' && (")
  })

  it('o Estudo manda o recorte da ficha (no corpo, via `api.relatorioPontual`)', () => {
    expect(pontoScreen).toContain('const recorte = recorteDoEstudo(ficha)')
    expect(pontoScreen).toContain('...recorte,')
  })

  it('o rodapé usa os estilos travados em teste (metade cada; magenta e azul)', () => {
    expect(pontoScreen).toContain('style={estiloDoBotaoEstudo(estudo.habilitado)}')
    expect(pontoScreen).toContain('style={estiloDoBotaoSimulador(simulador.habilitado)}')
    // O Simulador deixou de ser o botão fantasma: é cheio, no azul do sistema.
    expect(pontoScreen).not.toContain('ESTILO_RODAPE_GHOST')
  })

  it('o mapa desenha o contorno de TODO item (polígono a polígono), não só a área desenhada', () => {
    expect(hexMap).toContain('const areas = emOrdem.flatMap((p) => (p.contornos ?? []).map((poligono) => ({ pin: p, poligono })))')
    expect(hexMap).toContain('getPolygon: (d) => d.poligono')
    expect(hexMap).not.toContain('emOrdem.filter((p) => p.geometria?.length)')
  })

  it('a captura enquadra pelo contorno e o desenha na foto', () => {
    expect(hexMap).toContain('quadroDoAlvo(a, caixa?.width || 1200, caixa?.height || 800)')
    expect(hexMap).toContain("id: 'captura-contorno'")
  })
})

/* O alcance substitui a marca do hexágono do ponto (pedido de 20/10/2026). A regra mora
   em `lib/alcance` (testada lá); aqui só se trava que o mapa a USA nas duas marcas. */
describe('o alcance é a marca do ponto no mapa', () => {
  it('a seleção que veio do ponto passa por `selecaoMarcadaNoMapa`', () => {
    expect(mapScreen).toContain('selecaoMarcadaNoMapa(')
    expect(mapScreen).toMatch(/selecaoMarcadaNoMapa\(\s+selecionado,\s+selecaoDaBusca,/)
  })

  it('o realce do hexágono do ponto (`search-hex`) some quando o alcance o substitui', () => {
    expect(hexMap).toContain('marcaNoMapa.hexId !== hexSubstituidoPeloAlcance(pinDoSearch)')
    expect(hexMap).toContain("id: 'search-hex',\n          data: [{ id: hexDaMarca }],")
  })
})
