import { describe, expect, it } from 'vitest'

import {
  ALTURA_CABECALHO,
  ALTURA_MINIMA,
  DEGRAU_X,
  DEGRAU_Y,
  LARGURA_FICHA_PONTO,
  LARGURA_MINIMA,
  LARGURA_PADRAO,
  MARGEM,
  VISIVEL_MINIMO,
  geometriaPadrao,
  mover,
  reajustar,
  redimensionar,
  topoMinimoSobCabecalho,
  type Geometria,
} from './janela'
import { FOLGA_ABAIXO_DO_CABECALHO } from './botao-ver-ficha'

const AREA = { largura: 1200, altura: 800 }
const TOPO = 88
const RECUO = 96

describe('geometriaPadrao', () => {
  it('nasce encostada à direita, entre o cabeçalho e o stepper', () => {
    const g = geometriaPadrao(AREA, TOPO, RECUO)
    expect(g.largura).toBe(LARGURA_PADRAO)
    expect(g.x + g.largura).toBe(AREA.largura - MARGEM)
    expect(g.y).toBe(TOPO)
    // O pé da janela para exatamente onde o stepper começa.
    expect(g.y + g.altura).toBe(AREA.altura - RECUO)
  })

  it('em área estreita encolhe em vez de vazar', () => {
    const g = geometriaPadrao({ largura: 400, altura: 800 }, TOPO, RECUO)
    expect(g.largura).toBeLessThanOrEqual(400 - 2 * MARGEM)
    expect(g.x).toBeGreaterThanOrEqual(0)
  })

  it('respeita a altura mínima mesmo sem espaço vertical', () => {
    const g = geometriaPadrao({ largura: 1200, altura: 150 }, TOPO, RECUO)
    expect(g.altura).toBe(ALTURA_MINIMA)
  })

  it('ancorada à esquerda nasce na margem oposta, sem tocar no tamanho', () => {
    const esq = geometriaPadrao(AREA, TOPO, RECUO, 'esquerda')
    const dir = geometriaPadrao(AREA, TOPO, RECUO, 'direita')
    expect(esq.x).toBe(MARGEM)
    expect(esq.largura).toBe(dir.largura)
    expect(esq.altura).toBe(dir.altura)
    // Duas janelas na mesma tela não podem nascer uma sobre a outra.
    expect(esq.x).not.toBe(dir.x)
  })

  it('em DEGRAU nasce uma barra de título abaixo e recuada para dentro, no mesmo lado', () => {
    const base = geometriaPadrao(AREA, TOPO, RECUO, 'esquerda')
    const cima = geometriaPadrao(AREA, TOPO, RECUO, 'esquerda', 1)
    // A barra de título inteira da de baixo continua à vista.
    expect(cima.y).toBe(base.y + DEGRAU_Y)
    expect(DEGRAU_Y).toBeGreaterThanOrEqual(ALTURA_CABECALHO)
    expect(cima.x).toBe(base.x + DEGRAU_X)
    // O pé continua parando no stepper.
    expect(cima.y + cima.altura).toBe(AREA.altura - RECUO)
    // À direita o recuo é para a ESQUERDA (para dentro da tela).
    const dir = geometriaPadrao(AREA, TOPO, RECUO, 'direita', 1)
    expect(dir.x).toBe(geometriaPadrao(AREA, TOPO, RECUO, 'direita').x - DEGRAU_X)
  })

  it('degrau 0 (o padrão) é exatamente a posição de sempre', () => {
    expect(geometriaPadrao(AREA, TOPO, RECUO, 'esquerda', 0)).toEqual(
      geometriaPadrao(AREA, TOPO, RECUO, 'esquerda'),
    )
  })
})

describe('mover', () => {
  const base: Geometria = { x: 600, y: 100, largura: 520, altura: 400 }

  it('move pelo delta quando há espaço', () => {
    expect(mover(base, -50, 30, AREA)).toMatchObject({ x: 550, y: 130 })
  })

  it('deixa sair pela esquerda, mas guarda alça para o retorno', () => {
    const g = mover(base, -5000, 0, AREA)
    expect(g.x).toBe(VISIVEL_MINIMO - base.largura)
    // O que sobra visível é exatamente a alça mínima.
    expect(g.x + g.largura).toBe(VISIVEL_MINIMO)
  })

  it('nunca some pela direita', () => {
    const g = mover(base, 5000, 0, AREA)
    expect(g.x).toBe(AREA.largura - VISIVEL_MINIMO)
  })

  it('não deixa a barra de título subir acima do topo', () => {
    expect(mover(base, 0, -5000, AREA).y).toBe(0)
  })

  it('não deixa a barra de título afundar abaixo do pé', () => {
    expect(mover(base, 0, 5000, AREA).y).toBe(AREA.altura - ALTURA_CABECALHO)
  })

  it('não altera o tamanho', () => {
    const g = mover(base, 40, 40, AREA)
    expect(g.largura).toBe(base.largura)
    expect(g.altura).toBe(base.altura)
  })
})

describe('redimensionar', () => {
  const base: Geometria = { x: 200, y: 100, largura: 520, altura: 400 }

  it('cresce pelo canto sem mexer na posição', () => {
    const g = redimensionar(base, 80, 60, AREA)
    expect(g).toMatchObject({ x: 200, y: 100, largura: 600, altura: 460 })
  })

  it('para nos mínimos utilizáveis', () => {
    const g = redimensionar(base, -5000, -5000, AREA)
    expect(g.largura).toBe(LARGURA_MINIMA)
    expect(g.altura).toBe(ALTURA_MINIMA)
  })

  it('não cresce além da borda a partir da posição atual', () => {
    const g = redimensionar(base, 5000, 5000, AREA)
    expect(g.largura).toBe(AREA.largura - base.x)
    expect(g.altura).toBe(AREA.altura - base.y)
  })
})

describe('reajustar', () => {
  it('traz de volta a janela que ficou fora depois de a tela encolher', () => {
    const g = reajustar({ x: 1100, y: 700, largura: 520, altura: 400 }, { largura: 700, altura: 500 })
    expect(g.x).toBeLessThanOrEqual(700 - VISIVEL_MINIMO)
    expect(g.y).toBeLessThanOrEqual(500 - ALTURA_CABECALHO)
    expect(g.largura).toBeLessThanOrEqual(700)
  })

  it('não mexe em quem já cabe', () => {
    const dentro: Geometria = { x: 100, y: 100, largura: 520, altura: 400 }
    expect(reajustar(dentro, AREA)).toEqual(dentro)
  })

  it('sobrevive a uma área menor que os próprios mínimos', () => {
    const g = reajustar({ x: 10, y: 10, largura: 520, altura: 400 }, { largura: 100, altura: 80 })
    expect(g.largura).toBe(LARGURA_MINIMA)
    expect(g.altura).toBe(ALTURA_MINIMA)
    expect(Number.isFinite(g.x)).toBe(true)
    expect(Number.isFinite(g.y)).toBe(true)
  })
})

describe('a ficha de ponto nasce mais estreita (pedido de 20/10/2026)', () => {
  it('480px na nascença, e as outras janelas seguem nos 520 de sempre', () => {
    expect(LARGURA_FICHA_PONTO).toBe(480)
    expect(LARGURA_FICHA_PONTO).toBeGreaterThanOrEqual(LARGURA_MINIMA)
    expect(geometriaPadrao(AREA, TOPO, RECUO, 'esquerda', 0, LARGURA_FICHA_PONTO).largura).toBe(480)
    expect(geometriaPadrao(AREA, TOPO, RECUO, 'esquerda').largura).toBe(LARGURA_PADRAO)
  })

  it('a ancoragem à direita usa a largura pedida, não a padrão', () => {
    const g = geometriaPadrao(AREA, TOPO, RECUO, 'direita', 0, LARGURA_FICHA_PONTO)
    expect(g.x + g.largura).toBe(AREA.largura - MARGEM)
  })

  it('largura pedida abaixo do mínimo vira o mínimo; área estreita ainda encolhe', () => {
    expect(geometriaPadrao(AREA, TOPO, RECUO, 'esquerda', 0, 100).largura).toBe(LARGURA_MINIMA)
    const g = geometriaPadrao({ largura: 400, altura: 800 }, TOPO, RECUO, 'esquerda', 0, LARGURA_FICHA_PONTO)
    expect(g.largura).toBeLessThanOrEqual(400 - 2 * MARGEM)
  })

  it('só a nascença: redimensionar continua livre, para mais e para menos', () => {
    const g = geometriaPadrao(AREA, TOPO, RECUO, 'esquerda', 0, LARGURA_FICHA_PONTO)
    expect(redimensionar(g, 200, 0, AREA).largura).toBe(680)
    expect(redimensionar(g, -100, 0, AREA).largura).toBe(380)
    expect(redimensionar(g, -1000, 0, AREA).largura).toBe(LARGURA_MINIMA)
  })

  it('a janela respeita o cabeçalho do mapa (topo mínimo medido)', async () => {
    const { readFileSync } = await import('node:fs')
    const { fileURLToPath } = await import('node:url')
    const fonte = readFileSync(fileURLToPath(new URL('../components/JanelaFicha.tsx', import.meta.url)), 'utf-8')
    expect(fonte).toContain("anc.querySelector<HTMLElement>('header.barra-ultra')")
    expect(fonte).toContain('onPointerDown={gesto((g, dx, dy, a) => mover(g, dx, dy, a, topoMinimo))}')
    expect(fonte).toContain('setGeo((g) => (g ? reajustar(g, area, topoMinimo) : g))')
  })

  it('a ficha de ponto passa a largura dela à janela', async () => {
    const { readFileSync } = await import('node:fs')
    const { fileURLToPath } = await import('node:url')
    const ler = (r: string) => readFileSync(fileURLToPath(new URL(r, import.meta.url)), 'utf-8')
    expect(ler('../screens/PontoScreen.tsx')).toContain('larguraInicial={LARGURA_FICHA_PONTO}')
    expect(ler('../components/JanelaFicha.tsx')).toContain(
      'geometriaPadrao(area, Math.max(TOPO_PADRAO, topoMinimo), recuoInferior, ancora, degrau, larguraInicial)',
    )
  })
})

/* O cabeçalho do mapa passou a ficar ACIMA das janelas (21/10/2026). Uma barra de título
   arrastada para baixo dele ficaria sem alça -- e a barra é a única. */
describe('topo mínimo sob o cabeçalho do mapa', () => {
  it('é a borda de baixo do cabeçalho, relativa ao contêiner, em px de layout, mais a folga', () => {
    expect(topoMinimoSobCabecalho(70, 0)).toBe(70 + FOLGA_ABAIXO_DO_CABECALHO)
    expect(topoMinimoSobCabecalho(170, 100)).toBe(70 + FOLGA_ABAIXO_DO_CABECALHO)
    // #root encolhido a 85%: 59,5 px de tela são 70 de layout.
    expect(topoMinimoSobCabecalho(59.5, 0, 0.85)).toBe(70 + FOLGA_ABAIXO_DO_CABECALHO)
  })

  it('sem cabeçalho medido, 0 -- a trava de sempre', () => {
    expect(topoMinimoSobCabecalho(null, 0)).toBe(0)
    expect(topoMinimoSobCabecalho(70, null)).toBe(0)
    expect(topoMinimoSobCabecalho(Number.NaN, 0)).toBe(0)
    expect(topoMinimoSobCabecalho(70, 0, 0)).toBe(70 + FOLGA_ABAIXO_DO_CABECALHO)
  })

  it('o arrasto não sobe a barra de título para baixo do cabeçalho', () => {
    const g: Geometria = { x: 100, y: 200, largura: 400, altura: 300 }
    expect(mover(g, 0, -1000, AREA, 120).y).toBe(120)
    // descer continua livre
    expect(mover(g, 0, 50, AREA, 120).y).toBe(250)
    // sem topo mínimo, o de sempre: até 0
    expect(mover(g, 0, -1000, AREA).y).toBe(0)
  })

  it('o cabeçalho que quebra em duas linhas empurra a janela já aberta para baixo dele', () => {
    const g: Geometria = { x: 100, y: 88, largura: 400, altura: 300 }
    expect(reajustar(g, AREA, 126).y).toBe(126)
    expect(reajustar(g, AREA, 60).y).toBe(88)
  })

  it('área menor que o topo mínimo não inverte a trava', () => {
    const g: Geometria = { x: 0, y: 10, largura: 400, altura: 300 }
    expect(mover(g, 0, 500, { largura: 1200, altura: 100 }, 120).y).toBe(120)
  })
})
