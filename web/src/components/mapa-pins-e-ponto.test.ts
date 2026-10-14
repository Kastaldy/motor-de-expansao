import { latLngToCell } from 'h3-js'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'

import { corDeIdentidadeRgb } from '../lib/comparacao'
import { PONTOS_VAZIO, chegou, pedir, pinsDoEstado, type EstadoPontos } from '../lib/pontos-estado'
import type { PontoPayload } from '../lib/types'

/* O MAPA DESENHA TODOS OS PONTOS e ganha o "Selecionar ponto" (decisões 3 e 6 do dono,
   2026-10-14).

   Duas metades, como o resto do mapa:
   - a REGRA que o clique no pin usa (`pedir` de um ponto já lido abre a aba dele e sobe o
     `revelar`) é pura e testada de verdade aqui;
   - a FIAÇÃO (camadas do deck.gl, ordem do trilho, saídas cedo dos `onClick`) é asserção
     sobre TEXTO-FONTE, pela mesma razão do `mapa-unificado.test.ts`: o vitest deste repo
     roda em node, sem jsdom, e não monta React nem WebGL.
   --------------------------------------------------------------------------------- */

const ler = (rel: string) => readFileSync(fileURLToPath(new URL(rel, import.meta.url)), 'utf-8')
const hexMap = ler('./HexMap.tsx')
const barra = ler('./BarraCamadas.tsx')
const mapScreen = ler('../screens/MapScreen.tsx')
const app = ler('../App.tsx')

function ficha(lat: number, lng: number, bairro = 'Centro') {
  return {
    lat,
    lng,
    raio_km: 1,
    hex_id: latLngToCell(lat, lng, 7),
    local: { uf: 'SP', municipio: 'São Paulo', bairro },
  } as unknown as PontoPayload
}

function lido(e: EstadoPontos, lat: number, lng: number, bairro?: string): EstadoPontos {
  return chegou(pedir(e, lat, lng), { lat, lng }, ficha(lat, lng, bairro))
}

describe('clique no pin colorido: abre a aba daquele ponto', () => {
  const tres = lido(lido(lido(PONTOS_VAZIO, -23.5, -46.6), -23.55, -46.65), -22.9, -43.17)

  it('pedir de novo a coordenada da FICHA abre a aba dela e revela a janela', () => {
    // O App responde ao clique no pin com `pedirPonto(ficha.lat, ficha.lng)`.
    expect(tres.aberto).toBe(2)
    const depois = pedir(tres, tres.fichas[0].lat, tres.fichas[0].lng)
    expect(depois.aberto).toBe(0)
    expect(depois.revelar).toBe(tres.revelar + 1)
    // E não lê nada de novo: nem pendente, nem ficha a mais.
    expect(depois.pendentes).toHaveLength(0)
    expect(depois.fichas).toHaveLength(3)
  })

  it('cada pin sai na cor da aba, e só o da aba aberta é o ativo', () => {
    const pins = pinsDoEstado(pedir(tres, tres.fichas[1].lat, tres.fichas[1].lng))
    expect(pins.map((p) => p.rgb)).toEqual([0, 1, 2].map((i) => corDeIdentidadeRgb(i)))
    expect(pins.map((p) => p.ativo)).toEqual([false, true, false])
  })

  it('dois pontos de mesmo nome levam o rótulo desambiguado ao mapa', () => {
    const e = lido(lido(PONTOS_VAZIO, -23.5, -46.6, 'Centro'), -23.55, -46.65, 'Centro')
    expect(pinsDoEstado(e).map((p) => p.rotulo)).toEqual(['Centro #1', 'Centro #2'])
  })

  it('o App liga o clique do pin ao pedido da coordenada da ficha', () => {
    expect(app).toContain('onPontoComparado={(i) => {')
    expect(app).toContain('if (f) pedirPonto(f.lat, f.lng)')
    expect(mapScreen).toContain('onPontoClicado={onPontoComparado}')
  })
})

describe('HexMap: os pontos da comparação no mapa', () => {
  it('a lista chega ao HexMap pelo MapScreen', () => {
    expect(mapScreen).toContain('pontosComparados={pontosComparados}')
  })

  it('durante a captura do PDF a lista some — só a marca do alvo fica na foto', () => {
    expect(hexMap).toContain('() => (capturando ? [] : (pontosComparados ?? []))')
    // E é dessa lista filtrada, não da prop crua, que as camadas leem.
    expect(hexMap).toContain('if (pontosNoMapa.length) {')
    expect(hexMap).not.toMatch(/data: pontosComparados/)
  })

  it('anel na cor de identidade, ativo maior, pin clicável que abre a aba', () => {
    expect(hexMap).toContain("id: 'comparacao-pin-anel'")
    expect(hexMap).toContain("id: 'comparacao-pin-miolo'")
    expect(hexMap).toContain('getRadius: (d) => (d.ativo ? 13 : 10)')
    expect(hexMap).toContain('onPontoClicado?.(d.indice)')
  })

  it('o pin neutro do ponto ativo não é desenhado por cima do colorido', () => {
    expect(hexMap).toContain('if (marcaNoMapa?.pin && !pinDoSearch) {')
    expect(hexMap).toContain('getLineColor: pinDoSearch ? pinDoSearch.rgb : pele.selecao')
  })

  it('a régua imanta todos os pontos com o rótulo desambiguado', () => {
    expect(hexMap).toContain("lista.push({ lat: p.lat, lng: p.lng, rotulo: p.rotulo, tipo: 'ponto' })")
  })

  it('a lista entra nas deps do memo das camadas', () => {
    const deps = hexMap.slice(hexMap.indexOf('    return base\n  }, ['))
    for (const d of ['cliqueOcupado,', 'pontosNoMapa,', 'pinDoSearch,', 'onPontoClicado,']) {
      expect(deps.slice(0, deps.indexOf('])'))).toContain(d)
    }
  })
})

describe('Selecionar ponto: o clique é da ferramenta, por cima de tudo', () => {
  it('as camadas clicáveis saem cedo com ferramenta ligada (hexágono, imóvel, Ultra)', () => {
    // Sem isto, um clique sobre o pin abriria a ficha do que está embaixo E marcaria o ponto.
    expect(hexMap).toContain('const cliqueOcupado = medindo || selecionandoPonto')
    expect(hexMap.split('if (cliqueOcupado) return').length - 1).toBeGreaterThanOrEqual(3)
    expect(hexMap).not.toMatch(/^\s*if \(medindo\) return$/m)
  })

  it('o clique do DeckGL vira ponto ONDE caiu, com a coordenada em [lng, lat]', () => {
    expect(hexMap).toContain('const [lng, lat] = info.coordinate as number[]')
    expect(hexMap).toContain('onSelecionarPonto?.(lat, lng)')
    expect(hexMap).toContain("cliqueOcupado ? 'crosshair'")
  })

  it('o MapScreen manda o clique pelo MESMO caminho da lupa e liga pela ferramenta única', () => {
    expect(mapScreen).toContain("selecionandoPonto={ferramenta === 'ponto'}")
    expect(mapScreen).toContain('onSelecionarPonto={aplicarPonto}')
    expect(mapScreen).toContain("alternarFerramenta(f, 'ponto')")
  })

  it('Esc desliga a ferramenta, antes da janela que estiver por cima', () => {
    expect(mapScreen).toContain("window.addEventListener('keydown', aoTeclar, true)")
    expect(mapScreen).toContain("setFerramenta('nenhuma')")
  })
})

describe('Trilho e painel: a ordem do dono', () => {
  it('no trilho, "Selecionar ponto" vem ACIMA da régua, e a régua antes do comparar', () => {
    const ponto = barra.indexOf('icone="alvo"')
    const regua = barra.indexOf('icone="regua"')
    const geometria = barra.indexOf('ANALISAR GEOMETRIA entra AQUI')
    const comparar = barra.indexOf('icone="comparar"')
    expect(ponto).toBeGreaterThan(barra.indexOf('icone="camadas"'))
    expect(ponto).toBeLessThan(regua)
    // A vaga da geometria está reservada entre a régua e o comparar.
    expect(geometria).toBeGreaterThan(regua)
    expect(geometria).toBeLessThan(comparar)
  })

  it('cor própria, diferente do rosa da régua', () => {
    const bloco = barra.slice(barra.indexOf('icone="alvo"'), barra.indexOf('icone="regua"'))
    expect(bloco).toContain('cor="var(--gr-azul)"')
    expect(bloco).not.toContain('--gr-rosa')
  })

  it('no painel, a chave do ponto vem antes da régua', () => {
    const ponto = mapScreen.indexOf("id: 'selecionar-ponto'")
    expect(ponto).toBeGreaterThan(0)
    expect(ponto).toBeLessThan(mapScreen.indexOf("id: 'medir'"))
  })
})
