import { describe, expect, it } from 'vitest'

import { svgMolduraAlunos, tamanhoMolduraAlunos, temAlunos } from './pins'

/* As regras que decidem a moldura de destaque dos pinos com alunos reais. Sao
   testadas aqui porque o `HexMap` nao tem teste de componente: sem isto, a regra
   volta a ser uma expressao solta dentro de um `getSize`. */

describe('temAlunos', () => {
  it('reconhece a unidade com numero informado pela rede', () => {
    expect(temAlunos({ alunos: 1875 })).toBe(true)
  })

  it('nao destaca quem nao tem o numero — ausencia nao e academia vazia', () => {
    expect(temAlunos({ alunos: null })).toBe(false)
    expect(temAlunos({ alunos: undefined })).toBe(false)
    expect(temAlunos({})).toBe(false)
  })

  it('zero e MEDIDA, nao ausencia: o balao mostra, o aro tambem', () => {
    /* O servidor ja' filtra `alunos_total > 0`, entao zero nao chega hoje. O teste
       existe contra o erro classico de trocar `!= null` por truthiness, que faria a
       tela discordar do balao no dia em que aquele filtro mudar. */
    expect(temAlunos({ alunos: 0 })).toBe(true)
  })
})

describe('tamanhoMolduraAlunos', () => {
  it('fica COLADA na bandeira, nao solta como um aro', () => {
    /* O `+8` sobre o tamanho do pino poe a moldura ~3 px alem da aresta — o mesmo
       respiro do halo do agregador. A versao anterior era um circulo a 8 px da
       aresta e o dono reprovou olhando a tela: na camada 3 ele lia como mais um
       PONTO no mapa e sumia entre os hexagonos de pressao. */
    expect(tamanhoMolduraAlunos({ diag: false })).toBe(38)
    expect(tamanhoMolduraAlunos({})).toBe(38)
  })

  it('acompanha o pino maior do agregador', () => {
    /* O pino `diag` e' desenhado com getSize 38 porque nasce de um viewBox 160. */
    expect(tamanhoMolduraAlunos({ diag: true })).toBe(46)
  })

  it('a folga sobre o pino e a MESMA nos dois casos', () => {
    /* Se as folgas divergissem, o destaque teria dois pesos visuais e o operador
       leria "mais forte" onde e' so' geometria de icone. */
    expect(tamanhoMolduraAlunos({ diag: true }) - 38).toBe(
      tamanhoMolduraAlunos({ diag: false }) - 30,
    )
  })
})

describe('svgMolduraAlunos', () => {
  it('e um SVG generico, sem nada da rede dentro', () => {
    /* E' o que torna a moldura UMA entrada de atlas para as 107 redes, em vez de
       uma por rede re-embutindo o PNG da marca (~1,44 MB so' de halo em SP). */
    const uri = svgMolduraAlunos('rgb(140,108,255)')
    expect(uri.startsWith('data:image/svg+xml;utf8,')).toBe(true)
    const svg = decodeURIComponent(uri.split(',').slice(1).join(','))
    expect(svg).toContain('viewBox="0 0 128 128"')
    expect(svg).toContain('fill="none"')
    expect(svg).not.toContain('<image')
  })

  it('declara width/height, senao o deck.gl nao desenha nada', () => {
    /* REGRESSAO MEDIDA NA TELA: sem dimensao intrinseca o navegador rasteriza o
       SVG no default de 300x150, o deck.gl amostra a textura errada (ele declara
       o icone como 128x128) e a moldura simplesmente nao aparece — camada viva,
       console limpo, mapa sem destaque. */
    const svg = decodeURIComponent(
      svgMolduraAlunos('rgb(140,108,255)').split(',').slice(1).join(','),
    )
    expect(svg).toContain('width="128"')
    expect(svg).toContain('height="128"')
  })

  it('leva a cor e a opacidade recebidas — quem manda no tema e a tabela PELE', () => {
    const svg = decodeURIComponent(
      svgMolduraAlunos('rgb(91,63,209)', 0.94).split(',').slice(1).join(','),
    )
    expect(svg).toContain('stroke="rgb(91,63,209)"')
    expect(svg).toContain('stroke-opacity="0.94"')
  })

  it('desenha a keyline escura ANTES do traco claro, e mais larga', () => {
    /* A moldura e' BRANCA nos dois temas por decisao do dono, e branco puro sobre
       o Positron desaparece — e' o defeito que o halo do agregador tem hoje por
       ter sido calibrado so' contra o Dark Matter. Quem segura o contraste no
       tema claro e' esta linha; se ela vier DEPOIS, cobre o branco em vez de
       emoldura-lo, e se nao for mais larga, nao sobra nada dela para ver. */
    const svg = decodeURIComponent(
      svgMolduraAlunos('rgb(255,255,255)').split(',').slice(1).join(','),
    )
    const iKey = svg.indexOf('stroke-width="10"')
    const iBranco = svg.indexOf('stroke-width="7"')
    expect(iKey).toBeGreaterThan(-1)
    expect(iBranco).toBeGreaterThan(-1)
    expect(iKey).toBeLessThan(iBranco)
  })
})
