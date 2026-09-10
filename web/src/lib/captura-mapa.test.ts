import { cellToBoundary, cellToLatLng } from 'h3-js'
import { describe, expect, it } from 'vitest'

import {
  ESPERA_TILES_MS,
  ESPERA_VOO_MS,
  FATOR_RECORTE,
  OCUPACAO_DO_HEXAGONO,
  ZOOM_CAPTURA_MAX,
  ZOOM_CAPTURA_MIN,
  comporCanvas,
  esperaDeCaptura,
  chegouNoAlvo,
  larguraDoAnel,
  mapaPronto,
  metrosPorPixel,
  ordemDeVoo,
  ordenarParaEmpilhar,
  quadroDaCaptura,
  recorteCentral,
  zoomQueEnquadra,
} from './captura-mapa'

/* Os falsos abaixo entram por `as unknown as HTMLCanvasElement`: a lib e' tipada contra o
   DOM de verdade (e' o que a producao usa), e o casting fica no TESTE, que e' o unico
   lugar onde ele e' honesto. */

/** Canvas de destino falso: registra o que foi desenhado, na ordem. */
function destino() {
  const desenhos: {
    fonte: unknown
    w: number
    h: number
    origem?: { sx: number; sy: number; sw: number; sh: number }
  }[] = []
  return {
    width: 0,
    height: 0,
    desenhos,
    getContext: () => ({
      /* Aceita as DUAS assinaturas de `drawImage`: 5 argumentos (sem recorte) e 9
         (com), que e' a que carrega o retangulo de ORIGEM. */
      drawImage: (fonte: unknown, ...args: number[]) => {
        const [sx, sy, sw, sh] = args
        desenhos.push(
          args.length >= 8
            ? { fonte, w: sw, h: sh, origem: { sx, sy, sw, sh } }
            : { fonte, w: sw, h: sh },
        )
      },
    }),
    toDataURL: () => 'data:image/png;base64,FAKE',
  }
}

const comoDestino = (d: ReturnType<typeof destino>) => d as unknown as HTMLCanvasElement

const canvas = (width: number, height: number) =>
  ({ width, height }) as unknown as HTMLCanvasElement

describe('comporCanvas', () => {
  it('empilha na ORDEM recebida: basemap primeiro, camadas por cima', () => {
    const base = canvas(800, 600)
    const camadas = canvas(800, 600)
    const d = destino()

    expect(comporCanvas([base, camadas], comoDestino(d))).toBe('data:image/png;base64,FAKE')
    expect(d.desenhos.map((x) => x.fonte)).toEqual([base, camadas])
  })

  it('estica todos para o MAIOR quadro, para devicePixelRatio diferente não desalinhar', () => {
    const d = destino()
    comporCanvas([canvas(400, 300), canvas(800, 600)], comoDestino(d))

    expect(d.width).toBe(800)
    expect(d.height).toBe(600)
    expect(d.desenhos.every((x) => x.w === 800 && x.h === 600)).toBe(true)
  })

  it('pula canvas de tamanho zero em vez de derrubar a captura', () => {
    const bom = canvas(800, 600)
    const d = destino()

    expect(comporCanvas([canvas(0, 0), bom], comoDestino(d))).not.toBeNull()
    expect(d.desenhos).toHaveLength(1)
    expect(d.desenhos[0].fonte).toBe(bom)
  })

  it('sem nada capturável devolve null — slide sem mapa é melhor que retângulo preto', () => {
    expect(comporCanvas([], comoDestino(destino()))).toBeNull()
    expect(comporCanvas([canvas(0, 0)], comoDestino(destino()))).toBeNull()
  })

  it('sem contexto 2d devolve null em vez de estourar', () => {
    const semContexto = {
      width: 0,
      height: 0,
      getContext: () => null,
      toDataURL: () => 'nunca',
    }
    expect(comporCanvas([canvas(10, 10)], semContexto as unknown as HTMLCanvasElement)).toBeNull()
  })
})

describe('esperaDeCaptura', () => {
  it('soma as DUAS esperas: o voo e os tiles do novo enquadramento', () => {
    expect(esperaDeCaptura()).toBe(ESPERA_VOO_MS + ESPERA_TILES_MS)
  })

  it('é folga suficiente para não capturar mapa cinza', () => {
    // Sem margem o erro se repetiria nos 5 hexágonos da sequência, e um relatório com
    // cinco mapas cinza é pior que um sem mapa nenhum.
    expect(esperaDeCaptura()).toBeGreaterThanOrEqual(1200)
  })
})

/* Contorno de uma celula H3 res-7 REAL (87a8100c5ffffff, Bela Vista/SP), como o
   `cellToBoundary` devolve: [lat, lng]. Serve de referencia de tamanho — ~2,4 km de
   travessia — para as contas de enquadramento. */
const ANEL_RES7: [number, number][] = [
  [-23.5527, -46.6669],
  [-23.5462, -46.6592],
  [-23.5495, -46.6478],
  [-23.5594, -46.6441],
  [-23.5659, -46.6518],
  [-23.5626, -46.6632],
]

describe('recorteCentral', () => {
  it('recorta um quadrado no meio da faixa larga', () => {
    const r = recorteCentral(1600, 900)
    expect(r.lado).toBe(Math.round(900 * FATOR_RECORTE))
    // Centrado nos dois eixos: a camera voou ao centroide, o alvo esta' no meio.
    expect(r.x).toBe(Math.round((1600 - r.lado) / 2))
    expect(r.y).toBe(Math.round((900 - r.lado) / 2))
  })

  it('usa o lado MENOR, tambem quando o quadro e alto', () => {
    expect(recorteCentral(700, 1400).lado).toBe(Math.round(700 * FATOR_RECORTE))
  })
})

describe('larguraDoAnel', () => {
  it('mede a travessia de uma celula res-7 na casa dos 2 km', () => {
    const m = larguraDoAnel(ANEL_RES7)
    expect(m).toBeGreaterThan(2000)
    expect(m).toBeLessThan(3000)
  })

  it('anel degenerado nao explode — devolve zero', () => {
    expect(larguraDoAnel([])).toBe(0)
    expect(larguraDoAnel([[-23.5, -46.6]])).toBe(0)
  })
})

describe('metrosPorPixel', () => {
  it('ancora na escala do MapLibre/deck.gl (tile de 512), e nao na de 256', () => {
    /* Referencia INDEPENDENTE da funcao: no zoom 0 e no equador o mundo inteiro cabe em
       um tile, entao metros/pixel = circunferencia / lado do tile = 40.075.016,686/512.
       Este numero e' o que separa a convencao do deck.gl da do slippy map classico, e e'
       o unico teste aqui que o `zoomQueEnquadra` nao consegue satisfazer sozinho por ser
       consistente consigo mesmo. */
    expect(metrosPorPixel(0, 0)).toBeCloseTo(40_075_016.686 / 512, 3)
    expect(metrosPorPixel(0, 0)).not.toBeCloseTo(40_075_016.686 / 256, 0)
  })

  it('cai pela metade a cada nivel de zoom', () => {
    expect(metrosPorPixel(-23.5, 15)).toBeCloseTo(metrosPorPixel(-23.5, 14) / 2, 9)
  })

  it('encolhe com o cosseno da latitude', () => {
    expect(metrosPorPixel(60, 12)).toBeCloseTo(metrosPorPixel(0, 12) * Math.cos(Math.PI / 3), 6)
  })
})

describe('zoomQueEnquadra', () => {
  it('poe o hexagono na fatia pedida do recorte', () => {
    const largura = 1600
    const altura = 900
    const metros = larguraDoAnel(ANEL_RES7)
    const lat = -23.55
    const zoom = zoomQueEnquadra(metros, lat, largura, altura)

    // A conta de volta: quantos pixels o hexagono ocupa nesse zoom.
    const px = metros / metrosPorPixel(lat, zoom)
    const ladoDoRecorte = Math.min(largura, altura) * FATOR_RECORTE
    expect(px / ladoDoRecorte).toBeCloseTo(OCUPACAO_DO_HEXAGONO, 5)
  })

  it('nao depende do tamanho da janela — era o defeito do zoom fixo', () => {
    const metros = larguraDoAnel(ANEL_RES7)
    const lat = -23.55
    const fatia = (w: number, h: number) => {
      const z = zoomQueEnquadra(metros, lat, w, h)
      return metros / metrosPorPixel(lat, z) / (Math.min(w, h) * FATOR_RECORTE)
    }
    // Tres janelas bem diferentes, a MESMA fatia da foto ocupada pelo hexagono.
    expect(fatia(1200, 800)).toBeCloseTo(fatia(2560, 1440), 5)
    expect(fatia(1200, 800)).toBeCloseTo(fatia(900, 600), 5)
  })

  it('fecha o zoom nos limites em vez de pedir tile que nao existe', () => {
    expect(zoomQueEnquadra(1, -23.5, 1600, 900)).toBe(ZOOM_CAPTURA_MAX)
    expect(zoomQueEnquadra(5_000_000, -23.5, 1600, 900)).toBe(ZOOM_CAPTURA_MIN)
  })

  it('entrada sem grandeza cai no piso, sem NaN', () => {
    expect(zoomQueEnquadra(0, -23.5, 1600, 900)).toBe(ZOOM_CAPTURA_MIN)
    expect(zoomQueEnquadra(2400, -23.5, 0, 0)).toBe(ZOOM_CAPTURA_MIN)
  })
})

describe('comporCanvas com recorte', () => {
  it('entrega um quadrado do lado pedido, e nao a faixa inteira', () => {
    const d = destino()
    comporCanvas([canvas(1600, 900)], comoDestino(d), { recortar: true })
    const lado = recorteCentral(1600, 900).lado
    expect(d.width).toBe(lado)
    expect(d.height).toBe(lado)
  })

  it('recorta o MESMO trecho de fontes em devicePixelRatio diferente', () => {
    // O mapa e' dois canvas empilhados e eles podem ter densidade diferente (tela
    // externa). O recorte e' definido no quadro comum; cada fonte contribui com o
    // trecho equivalente, senao as camadas sairiam deslocadas uma da outra.
    const d = destino()
    comporCanvas([canvas(1600, 900), canvas(3200, 1800)], comoDestino(d), { recortar: true })
    const [um, dois] = d.desenhos
    expect(dois.origem!.sx).toBe(um.origem!.sx * 2)
    expect(dois.origem!.sy).toBe(um.origem!.sy * 2)
    expect(dois.origem!.sw).toBe(um.origem!.sw * 2)
    expect(dois.origem!.sh).toBe(um.origem!.sh * 2)
  })

  it('escala cada EIXO pelo proprio fator', () => {
    /* Guarda de regressao: a primeira versao usava o fator horizontal tambem no eixo Y.
       Com as fontes na MESMA proporcao os dois fatores coincidem e o erro ficava
       invisivel, entao aqui as duas fontes tem proporcoes diferentes de proposito —
       o quadro comum vira 1600x1800 e a primeira fonte precisa de ex=1 e ey=0,5. */
    const d = destino()
    comporCanvas([canvas(1600, 900), canvas(1600, 1800)], comoDestino(d), { recortar: true })
    const { x, y, lado } = recorteCentral(1600, 1800)
    const o = d.desenhos[0].origem!
    expect(o.sx).toBeCloseTo(x * 1, 6)
    expect(o.sy).toBeCloseTo(y * 0.5, 6)
    expect(o.sw).toBeCloseTo(lado * 1, 6)
    expect(o.sh).toBeCloseTo(lado * 0.5, 6)
    // O bug antigo daria `sy = x-scale * y` = o proprio `y`.
    expect(o.sy).not.toBeCloseTo(y, 6)
  })

  it('sem recorte, segue esticando cada fonte no quadro comum', () => {
    const d = destino()
    comporCanvas([canvas(800, 600)], comoDestino(d))
    expect(d.desenhos[0].origem).toBeUndefined()
  })
})

describe('quadroDaCaptura', () => {
  /* Os hexagonos do deck que expos o bug (comparacao-pontos.pdf, 10/09/2026): quatro
     pontos, dois em Posse/GO e dois em Jatai/GO. O mapa carrega hexagono de UM municipio
     por vez, entao so' os de Posse estavam na lista servida — e as duas colunas de Jatai
     sairam com "Mapa nao capturado para esta area." */
  const POSSE = '87812d89cffffff'
  const JATAI = '87a8ee815ffffff'

  it('enquadra um hexagono que o mapa NAO tem carregado', () => {
    /* O caso do bug: nenhuma lista de hexes entra aqui. O quadro sai do proprio id — se
       dependesse do que o mapa carregou, a coluna de Jatai voltaria vazia de novo. */
    const q = quadroDaCaptura(JATAI, 1200, 800)
    expect(q).not.toBeNull()
    const [lat, lng] = cellToLatLng(JATAI)
    expect(q!.lat).toBeCloseTo(lat, 10)
    expect(q!.lng).toBeCloseTo(lng, 10)
  })

  it('o zoom e o mesmo que `zoomQueEnquadra` daria para o anel do hexagono', () => {
    // Uma fonte so' para o enquadramento: o quadro nao pode ter uma segunda conta de zoom.
    const [lat] = cellToLatLng(POSSE)
    const esperado = zoomQueEnquadra(
      larguraDoAnel(cellToBoundary(POSSE) as [number, number][]),
      lat,
      1200,
      800,
    )
    expect(quadroDaCaptura(POSSE, 1200, 800)!.zoom).toBeCloseTo(esperado, 10)
  })

  it('respeita o piso e o teto de zoom da captura', () => {
    const q = quadroDaCaptura(POSSE, 1200, 800)!
    expect(q.zoom).toBeGreaterThanOrEqual(ZOOM_CAPTURA_MIN)
    expect(q.zoom).toBeLessThanOrEqual(ZOOM_CAPTURA_MAX)
  })

  it('hexId ausente ou invalido nao vira quadro', () => {
    // `null` aqui e' "nao ha' o que enquadrar", que e' diferente de "o mapa nao tinha".
    expect(quadroDaCaptura('', 1200, 800)).toBeNull()
    expect(quadroDaCaptura('nao-e-um-hexagono', 1200, 800)).toBeNull()
  })
})

describe('ordenarParaEmpilhar', () => {
  /* MEDIDO no piloto rodando, 10/09/2026: `document.querySelectorAll('canvas')` devolve o
     canvas do deck.gl PRIMEIRO (pai `deck-events-root`) e o `maplibregl-canvas` DEPOIS —
     o inverso do que este modulo assumia. Como o basemap e' opaco e as camadas do deck
     sao semitransparentes (alfa medio medido 59,4 de 255, so' 0,4% dos pixels em 255),
     empilhar na ordem do DOM pintava as ruas EM CIMA do hexagono e dos pins. Era o
     defeito das duas capturas de Posse do deck de 10/09: malha viaria e nada mais, num
     slide cujo assunto e' quem disputa o aluno ali. */
  const falso = (className: string) =>
    ({ width: 800, height: 600, className }) as unknown as HTMLCanvasElement

  it('poe o basemap embaixo mesmo quando o DOM entrega o deck primeiro', () => {
    const deck = falso('')
    const base = falso('maplibregl-canvas')
    expect(ordenarParaEmpilhar([deck, base])).toEqual([base, deck])
  })

  it('nao mexe no que ja esta na ordem de pintura', () => {
    const base = falso('maplibregl-canvas')
    const deck = falso('')
    expect(ordenarParaEmpilhar([base, deck])).toEqual([base, deck])
  })

  it('preserva a ordem relativa entre os canvas de camada', () => {
    // Se um dia houver mais de uma camada empilhada, elas mantem a ordem em que vieram.
    const base = falso('maplibregl-canvas')
    const a = falso('camada-a')
    const b = falso('camada-b')
    expect(ordenarParaEmpilhar([a, b, base])).toEqual([base, a, b])
  })

  it('lista sem basemap segue intacta', () => {
    const a = falso('camada-a')
    expect(ordenarParaEmpilhar([a])).toEqual([a])
    expect(ordenarParaEmpilhar([])).toEqual([])
  })
})

describe('chegouNoAlvo', () => {
  const jatai = { lat: -17.857641, lng: -51.728483 }

  it('reconhece a camera parada em cima do alvo', () => {
    expect(chegouNoAlvo(jatai, jatai)).toBe(true)
  })

  it('recusa o quadro ANTERIOR, que e o defeito que isto existe para pegar', () => {
    /* Posse fica a ~500 km de Jatai. Ate' 10/09/2026 a captura esperava 900 ms de voo e
       700 ms de tiles NO RELOGIO e fotografava o que estivesse na tela: com a aba
       estrangulada, tres das quatro colunas do deck sairam com o MESMO quadro de Posse,
       cada uma sob o nome de outra area. Foto do lugar errado sob o nome certo e' pior
       que foto nenhuma — por isso a checagem, e por isso ela reprova. */
    expect(chegouNoAlvo({ lat: -14.075941, lng: -46.344974 }, jatai)).toBe(false)
  })

  it('tolera o erro de arredondamento do fim do voo', () => {
    expect(chegouNoAlvo({ lat: jatai.lat + 0.0005, lng: jatai.lng - 0.0005 }, jatai)).toBe(true)
  })

  it('sem centro nao ha chegada', () => {
    expect(chegouNoAlvo(null, jatai)).toBe(false)
    expect(chegouNoAlvo(undefined, jatai)).toBe(false)
  })
})

describe('mapaPronto', () => {
  const alvo = { lat: -17.857641, lng: -51.728483 }
  const pronto = { estiloCarregado: true, tilesCarregados: true, centro: alvo }

  it('pronto e as tres coisas juntas', () => {
    expect(mapaPronto(pronto, alvo)).toBe(true)
  })

  it('estilo nao carregado reprova — e o caso da PRIMEIRA captura', () => {
    /* Medido em 10/09/2026: na captura 0 o canvas do basemap entrou na composicao com
       0% de tinta. O `<Map/>` acabara de ser remontado para ligar o `preserveDrawingBuffer`
       e ainda nao pintara — a espera era de 500 ms fixos. A coluna saiu sem ruas, com
       cara de outro relatorio. */
    expect(mapaPronto({ ...pronto, estiloCarregado: false }, alvo)).toBe(false)
  })

  it('tiles pendentes reprovam: quadro borrado nao e' + ' quadro', () => {
    expect(mapaPronto({ ...pronto, tilesCarregados: false }, alvo)).toBe(false)
  })

  it('camera ainda a caminho reprova', () => {
    expect(mapaPronto({ ...pronto, centro: { lat: -14.07, lng: -46.34 } }, alvo)).toBe(false)
  })

  it('sem alvo, basta o mapa estar pintado', () => {
    // A comparacao de HEXAGONOS nao marca imovel; ali so' importa que o quadro exista.
    expect(mapaPronto(pronto, null)).toBe(true)
    expect(mapaPronto({ ...pronto, estiloCarregado: false }, null)).toBe(false)
  })
})

describe('ordemDeVoo', () => {
  // Os quatro pontos do deck de 10/09/2026. Posse/GO e Jatai/GO estao a ~500 km.
  const posseA = { lat: -14.0759, lng: -46.3450 }
  const posseB = { lat: -14.0869, lng: -46.3664 }
  const jataiA = { lat: -17.8576, lng: -51.7285 }
  const jataiB = { lat: -17.8801, lng: -51.7293 }

  /** Quantas vezes a rota pula mais de 1 grau — o salto caro. */
  const saltosLongos = (ordem: number[], pts: ({ lat: number; lng: number } | null)[]) => {
    let n = 0
    for (let i = 1; i < ordem.length; i++) {
      const a = pts[ordem[i - 1]]
      const b = pts[ordem[i]]
      if (a && b && Math.hypot(a.lat - b.lat, a.lng - b.lng) > 1) n++
    }
    return n
  }

  it('agrupa as cidades mesmo com a colagem alternando entre elas', () => {
    /* A ordem de captura era a de COLAGEM. Colando Posse, Jatai, Posse, Jatai, a camera
       atravessava o pais TRES vezes, e cada travessia e' um voo que pode nao chegar
       dentro do teto — foi assim que a coluna "3 - Jatai" saiu vazia no deck das 14:10,
       no unico salto longo que aquela colagem tinha. Por proximidade, o salto longo e'
       sempre UM so'. */
    const pts = [posseA, jataiA, posseB, jataiB]
    expect(saltosLongos([0, 1, 2, 3], pts)).toBe(3)
    expect(saltosLongos(ordemDeVoo(pts, posseA), pts)).toBe(1)
  })

  it('visita todos os alvos, uma vez cada', () => {
    const pts = [posseA, jataiA, posseB, jataiB]
    expect([...ordemDeVoo(pts, posseA)].sort()).toEqual([0, 1, 2, 3])
  })

  it('comeca pelo mais PROXIMO de onde a camera ja esta', () => {
    const pts = [jataiA, posseA]
    expect(ordemDeVoo(pts, posseB)[0]).toBe(1)
    expect(ordemDeVoo(pts, jataiB)[0]).toBe(0)
  })

  it('alvo sem quadro vai para o fim, e nao arrasta a rota', () => {
    // `null` e' hexId invalido: nao se voa ate' ele, e ele nao pode puxar a ordem.
    const pts = [null, posseA, jataiA]
    const ordem = ordemDeVoo(pts, posseB)
    expect(ordem[ordem.length - 1]).toBe(0)
    expect(ordem.slice(0, 2)).toEqual([1, 2])
  })

  it('lista vazia e lista de um seguem triviais', () => {
    expect(ordemDeVoo([], posseA)).toEqual([])
    expect(ordemDeVoo([jataiA], posseA)).toEqual([0])
  })

  it('sem partida, mantem a ordem recebida como ponto de saida', () => {
    // Sem camera conhecida, o primeiro colado abre a rota — decisao, nao acaso.
    expect(ordemDeVoo([jataiA, posseA, posseB], null)[0]).toBe(0)
  })
})
