import { describe, expect, it } from 'vitest'

import { ESPERA_TILES_MS, ESPERA_VOO_MS, comporCanvas, esperaDeCaptura } from './captura-mapa'

/* Os falsos abaixo entram por `as unknown as HTMLCanvasElement`: a lib e' tipada contra o
   DOM de verdade (e' o que a producao usa), e o casting fica no TESTE, que e' o unico
   lugar onde ele e' honesto. */

/** Canvas de destino falso: registra o que foi desenhado, na ordem. */
function destino() {
  const desenhos: { fonte: unknown; w: number; h: number }[] = []
  return {
    width: 0,
    height: 0,
    desenhos,
    getContext: () => ({
      drawImage: (fonte: unknown, _x: number, _y: number, w: number, h: number) => {
        desenhos.push({ fonte, w, h })
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
