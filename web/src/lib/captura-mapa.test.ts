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
  larguraDoAnel,
  metrosPorPixel,
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
