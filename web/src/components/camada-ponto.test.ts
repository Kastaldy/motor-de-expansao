/**
 * A ficha de ponto e as janelas do mapa no MESMO contexto de empilhamento (21/10/2026).
 *
 * Print do Vinicius: com a ficha de ponto aberta, ligar "Comparar hexágonos" abria a janela
 * da comparação ATRÁS da do ponto, quase inteira coberta (87,7% da largura), e clicar nela
 * não a trazia para frente. A causa era o `zIndex: 40` do contêiner da camada do ponto: um
 * `zIndex` num ancestral cria contexto próprio, e a pilha 26/27 da `JanelaFicha` só ordena
 * irmãos do mesmo contexto — a do ponto pintava por cima de todas, qualquer que fosse a
 * pilha. O Esc, que segue a pilha, fechava a janela ESCONDIDA.
 *
 * O Vitest roda sem DOM: a trava lê o FONTE (molde de `mapa-pins-e-ponto.test`).
 */
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'

import { describe, expect, it } from 'vitest'

const fonte = (rel: string) => readFileSync(fileURLToPath(new URL(rel, import.meta.url)), 'utf-8')
const ponto = fonte('../screens/PontoScreen.tsx')
const mapa = fonte('../screens/MapScreen.tsx')
const janela = fonte('./JanelaFicha.tsx')

/** O `style={{ ... }}` (ou o objeto de estilo multilinha) que começa em `inicio`. */
function blocoDeEstilo(texto: string, inicio: number): string {
  const abre = texto.indexOf('style={{', inicio)
  expect(abre).toBeGreaterThan(-1)
  return texto.slice(abre, texto.indexOf('}}', abre) + 2)
}

describe('a camada do ponto não cria contexto de empilhamento', () => {
  it('o contêiner de tela inteira (inset 0, sem mouse) NÃO tem zIndex', () => {
    const conteineres = [...ponto.matchAll(/<div style=\{\{ position: 'absolute', inset: 0[^}]*\}\}[^>]*>/g)].map((m) => m[0])
    const camada = conteineres.filter((c) => c.includes("pointerEvents: 'none'"))
    expect(camada, 'o contêiner da camada do ponto sumiu ou mudou de forma').toHaveLength(1)
    expect(camada[0], 'com zIndex, a pilha da JanelaFicha deixa de valer entre ponto e mapa').not.toMatch(/zIndex/)
  })

  it('a medida do cabeçalho sai da CAMADA, então vale também sem o botão "Ver a ficha"', () => {
    expect(ponto).toContain("<div style={{ position: 'absolute', inset: 0, pointerEvents: 'none' }} ref={setCamadaEl}>")
    // e é refeita quando o cabeçalho aparece depois (Explorar sem UF) ou é trocado
    expect(ponto).toContain('const cabecalhoRegistrado = useCabecalhoMapa()')
    expect(ponto).toContain('}, [camadaEl, cabecalhoRegistrado])')
    expect(ponto).not.toContain("querySelector<HTMLElement>('header.barra-ultra')")
  })

  it('o hero da tela vazia continua cobrindo a tela de propósito', () => {
    expect(ponto).toContain("<div style={{ position: 'absolute', inset: 0, zIndex: 40 }}>")
  })

  it('as peças soltas sobem por conta própria (senão cairiam sob o corpo do mapa, z 10)', () => {
    const coluna = blocoDeEstilo(ponto, ponto.indexOf('Caixa de colar'))
    // Abaixo do cabeçalho MEDIDO, nunca por baixo dele (o cabeçalho é z 29, acima destas).
    expect(coluna).toContain('top: Math.max(TOPO_BOTAO_PADRAO, topoBotaoFicha)')
    expect(coluna).toContain('zIndex: Z_FLUTUANTE_PONTO')
    const botao = blocoDeEstilo(ponto, ponto.indexOf('A ÚNICA opção que puxa a janela'))
    expect(botao).toContain('top: topoBotaoFicha')
    expect(botao).toContain('zIndex: Z_FLUTUANTE_PONTO')
  })

  it('ponto pedido de novo traz a janela do ponto para frente', () => {
    const abre = ponto.indexOf('<JanelaFicha')
    const props = ponto.slice(abre, ponto.indexOf('rodape={', abre))
    expect(props).toContain('pedidoDeFrente={revelar}')
  })
})

describe('a JanelaFicha', () => {
  it('usa as constantes de camadas-mapa, sem 26/27 cravados', () => {
    expect(janela).toContain("import { Z_JANELA_FICHA, Z_JANELA_FICHA_TOPO } from '../lib/camadas-mapa'")
    expect(janela).toContain('const Z_JANELA = Z_JANELA_FICHA')
    expect(janela).toContain('const Z_JANELA_TOPO = Z_JANELA_FICHA_TOPO')
    expect(janela).not.toMatch(/const Z_JANELA(_TOPO)? = \d/)
  })

  it('pedidoDeFrente sobe a janela na pilha quando o valor muda (e só se aberta)', () => {
    const inicio = janela.indexOf('const ultimoPedido = useRef(pedidoDeFrente)')
    expect(inicio).toBeGreaterThan(-1)
    const efeito = janela.slice(inicio, janela.indexOf('}, [pedidoDeFrente, aberta])', inicio))
    expect(efeito).toContain('if (pedidoDeFrente === ultimoPedido.current) return')
    expect(efeito).toContain('if (!aberta) return')
    expect(efeito).toContain('pilhaAbertas.push(id)')
    expect(efeito).toContain('avisarPilha()')
    // Depois do efeito que empilha ao abrir: abrir e pedir no mesmo render vira no-op.
    expect(inicio).toBeGreaterThan(janela.indexOf('pilhaAbertas.push(id)\n    avisarPilha()\n    const aoTeclar'))
  })
})

describe('as duas janelas da direita no mapa', () => {
  it('a da unidade nasce em degrau quando o imóvel está aberto', () => {
    const abre = mapa.indexOf('aberta={unidadeAberta != null}')
    const props = mapa.slice(abre, mapa.indexOf('>', mapa.indexOf('recuoInferior', abre)))
    expect(props).toContain('degrau={imovelAberto != null ? 1 : 0}')
  })
})
