import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'

import { describe, expect, it } from 'vitest'

import {
  AVISO_RELENDO_ALCANCE,
  ESTILO_ROTULO_ALCANCE,
  ESTILO_TIPO_ALCANCE,
  ESTILO_TRILHO_ALCANCE,
  ROTULO_CURTO_ALCANCE,
  ROTULO_SELETOR_ALCANCE,
  estiloDaOpcaoAlcance,
} from './seletor-alcance'
import { ALCANCES, ROTULO_ALCANCE } from './alcance'
import { LARGURA_FICHA_PONTO, LARGURA_MINIMA } from './janela'

const pontoScreen = readFileSync(fileURLToPath(new URL('../screens/PontoScreen.tsx', import.meta.url)), 'utf-8')

/** Nenhuma cor cravada: o seletor acompanha os temas pelos tokens. */
const SEM_HEX = /#[0-9a-f]{3,8}\b|rgba?\(/i

describe('o seletor de alcance em destaque (pedido de 20/10/2026)', () => {
  it('a opção marcada é CHEIA no turquesa de texto do tema; a desmarcada, sem fundo', () => {
    const marcada = estiloDaOpcaoAlcance(true)
    expect(marcada.background).toBe('var(--ac-text)')
    expect(marcada.color).toBe('var(--ac-on)')
    const livre = estiloDaOpcaoAlcance(false)
    expect(livre.background).toBe('transparent')
    expect(livre.color).toBe('var(--tx-soft)')
  })

  it('as opções dividem a largura por igual (controle segmentado, não pílulas)', () => {
    for (const m of [true, false]) {
      expect(estiloDaOpcaoAlcance(m).flex).toBe(1)
      expect(Number(estiloDaOpcaoAlcance(m).minHeight)).toBeGreaterThanOrEqual(36)
    }
    expect(ESTILO_TRILHO_ALCANCE.display).toBe('flex')
    expect(ESTILO_TRILHO_ALCANCE.flexWrap).toBeUndefined()
  })

  it('só tokens, nenhuma cor cravada', () => {
    const estilos = [ESTILO_TRILHO_ALCANCE, ESTILO_ROTULO_ALCANCE, estiloDaOpcaoAlcance(true), estiloDaOpcaoAlcance(false)]
    for (const e of estilos) expect(JSON.stringify(e)).not.toMatch(SEM_HEX)
  })

  it('o rótulo é visível e forte; a releitura é dita em texto', () => {
    expect(ROTULO_SELETOR_ALCANCE).toBe('Alcance da análise')
    expect(ESTILO_ROTULO_ALCANCE.color).toBe('var(--tx-strong)')
    expect(AVISO_RELENDO_ALCANCE).toMatch(/^Atualizando/)
  })

  it('a ficha desenha o seletor DENTRO da identificação, antes dos chips e dos números', () => {
    const identificacao = pontoScreen.indexOf("<Eyebrow dot>{area ? 'Área desenhada' : 'Ponto analisado'}</Eyebrow>")
    const seletor = pontoScreen.indexOf('<SeletorAlcance\n')
    const chipHex = pontoScreen.indexOf('<Chip>hex {ficha.hex_id}</Chip>')
    const socio = pontoScreen.indexOf("? 'Quem mora na área'")
    expect(identificacao).toBeGreaterThan(-1)
    expect(seletor).toBeGreaterThan(identificacao)
    expect(seletor).toBeLessThan(chipHex)
    expect(seletor).toBeLessThan(socio)
    // Um lugar só: o antigo, abaixo da identificação, saiu.
    expect(pontoScreen.split('<SeletorAlcance\n')).toHaveLength(2)
  })

  it('a ficha usa os estilos travados aqui e diz a releitura em voo', () => {
    expect(pontoScreen).toContain('style={estiloDaOpcaoAlcance(marcado)}')
    expect(pontoScreen).toContain('style={ESTILO_TRILHO_ALCANCE}')
    expect(pontoScreen).toContain('{ROTULO_SELETOR_ALCANCE}')
    expect(pontoScreen).toContain('{AVISO_RELENDO_ALCANCE}')
    expect(pontoScreen).toContain('aria-busy={trocando}')
    // A lógica não mudou: quem troca é o mesmo callback.
    expect(pontoScreen).toContain('onClick={() => onTrocar(a)}')
  })
})

/* ---------------- Achados do revisor do 89ab23b3 ---------------- */
const tokens = readFileSync(fileURLToPath(new URL('../styles/tokens.css', import.meta.url)), 'utf-8')

/** O valor de `--nome` no PRIMEIRO bloco que começa em `seletor` (o tema). */
function token(seletor: string, nome: string): string {
  const inicio = tokens.indexOf(`${seletor} {`)
  expect(inicio).toBeGreaterThan(-1)
  const bloco = tokens.slice(inicio, tokens.indexOf('\n}', inicio))
  const m = new RegExp(`\\s${nome}:\\s*(#[0-9a-fA-F]{6})\\s*;`).exec(bloco)
  expect(m, `${nome} em ${seletor}`).not.toBeNull()
  return m![1]
}

function luminancia(hex: string): number {
  const [r, g, b] = [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16) / 255)
  const lin = (c: number) => (c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4)
  return 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b)
}

function contraste(a: string, b: string): number {
  const [x, y] = [luminancia(a), luminancia(b)].sort((p, q) => q - p)
  return (x + 0.05) / (y + 0.05)
}

/** `var(--ac-text)` -> `--ac-text`. */
const nomeDoToken = (v: unknown) => /^var\((--[a-z0-9-]+)\)$/.exec(String(v))![1]

describe('contraste da opção marcada (texto de 13px pede 4,5:1)', () => {
  const marcada = estiloDaOpcaoAlcance(true)
  const fundo = nomeDoToken(marcada.background)
  const texto = nomeDoToken(marcada.color)

  it.each([
    [':root', 'tema escuro'],
    ["[data-tema='claro']", 'tema claro'],
  ])('%s (%s) passa 4,5:1', (seletor) => {
    expect(contraste(token(seletor, fundo), token(seletor, texto))).toBeGreaterThanOrEqual(4.5)
  })

  it('o par antigo (--ac / --ac-on) reprovava no tema claro: é o que esta régua pega', () => {
    const claro = "[data-tema='claro']"
    expect(contraste(token(claro, '--ac'), token(claro, '--ac-on'))).toBeLessThan(4.5)
  })
})

describe('o aviso de releitura não faz parte do nome do grupo', () => {
  const inicio = pontoScreen.indexOf('function SeletorAlcance(')
  const seletor = pontoScreen.slice(inicio, pontoScreen.indexOf('\n}\n', inicio))
  const abreRotulo = seletor.indexOf('<span id="rotulo-alcance-ponto"')
  const rotulo = seletor.slice(abreRotulo, seletor.indexOf('</span>', abreRotulo))

  it('o rótulo que nomeia o radiogroup tem só o nome', () => {
    expect(abreRotulo).toBeGreaterThan(-1)
    expect(seletor).toContain('aria-labelledby="rotulo-alcance-ponto"')
    expect(rotulo).toContain('{ROTULO_SELETOR_ALCANCE}')
    expect(rotulo).not.toContain('AVISO_RELENDO_ALCANCE')
    expect(rotulo).not.toContain('role="status"')
  })

  it('a região viva fica MONTADA o tempo todo; só o conteúdo depende da releitura', () => {
    const regiao = seletor.indexOf('role="status"')
    expect(regiao).toBeGreaterThan(-1)
    expect(seletor).toContain('aria-live="polite"')
    // Nada de `{trocando && (<span role="status" ...` — a região nasceria junto com o texto.
    expect(seletor).not.toMatch(/trocando && \(\s*<span\s+role="status"/)
    expect(seletor.indexOf('{AVISO_RELENDO_ALCANCE}')).toBeGreaterThan(regiao)
  })
})

/* ---------------- Rótulos sem reticências (print do Vinicius, 21/10/2026) ---------------- */

/**
 * Largura de TEXTO de cada opção, a partir da largura da janela, descontando o que está
 * entre a borda dela e o texto do botão: borda da janela (2), recuo do corpo (16 x 2), o
 * cartão da identificação (`Glass` com padding 18 e borda 1, x 2), o trilho (padding 4 e
 * borda 1, x 2), os 3 vãos de 4 entre as 4 opções e, por opção, o recuo lateral do botão.
 */
function larguraDoTextoPorOpcao(larguraJanela: number, recuoLateralBotao: number): number {
  const trilho = larguraJanela - 2 - 32 - 38 - 10
  return (trilho - 3 * 4) / 4 - 2 * recuoLateralBotao
}

/** Estimativa conservadora de largura de texto: ~0,55 em por caractere (0,6 em no negrito). */
function larguraEstimada(texto: string, px: number, negrito: boolean): number {
  return texto.length * px * (negrito ? 0.6 : 0.55)
}

const recuoLateral = (padding: unknown) => Number(/^\d+px (\d+)px$/.exec(String(padding))![1])

describe('os rótulos do seletor cabem sem reticências', () => {
  const recuo = recuoLateral(estiloDaOpcaoAlcance(true).padding)

  it('a régua reproduz o defeito: o rótulo inteiro numa linha NÃO cabia na largura de nascença', () => {
    const antes = larguraDoTextoPorOpcao(LARGURA_FICHA_PONTO, 10)
    expect(larguraEstimada(ROTULO_ALCANCE.carro_10min, 13, false)).toBeGreaterThan(antes)
  })

  it.each([
    ['nascença da ficha', LARGURA_FICHA_PONTO],
    ['largura mínima', LARGURA_MINIMA],
  ])('na %s, valor (13px negrito) e tipo (10,5px) de TODAS as opções cabem', (_n, largura) => {
    const cabe = larguraDoTextoPorOpcao(largura, recuo)
    for (const a of ALCANCES) {
      expect(larguraEstimada(ROTULO_CURTO_ALCANCE[a].valor, 13, true), a).toBeLessThanOrEqual(cabe)
      expect(larguraEstimada(ROTULO_CURTO_ALCANCE[a].tipo, 10.5, false), a).toBeLessThanOrEqual(cabe)
    }
  })

  it('valor + tipo dizem o mesmo que o rótulo inteiro', () => {
    expect(ROTULO_CURTO_ALCANCE).toEqual({
      raio_1km: { valor: '1 km', tipo: 'raio' },
      raio_2km: { valor: '2 km', tipo: 'raio' },
      carro_5min: { valor: '5 min', tipo: 'de carro' },
      carro_10min: { valor: '10 min', tipo: 'de carro' },
    })
    expect(Object.keys(ROTULO_CURTO_ALCANCE).sort()).toEqual([...ALCANCES].sort())
  })

  it('as duas linhas empilhadas; a de baixo só com tokens', () => {
    expect(estiloDaOpcaoAlcance(false).display).toBe('grid')
    expect(String(ESTILO_TIPO_ALCANCE.font)).toMatch(/^500 10\.5px/)
    expect(JSON.stringify(ESTILO_TIPO_ALCANCE)).not.toMatch(SEM_HEX)
  })

  it('o botão desenha as duas linhas curtas e mantém o rótulo inteiro como nome acessível', () => {
    const inicio = pontoScreen.indexOf('function SeletorAlcance(')
    const seletor = pontoScreen.slice(inicio, pontoScreen.indexOf('\n}\n', inicio))
    expect(seletor).toContain('aria-label={ROTULO_ALCANCE[a]}')
    expect(seletor).toContain('title={ROTULO_ALCANCE[a]}')
    expect(seletor).toContain('<span>{ROTULO_CURTO_ALCANCE[a].valor}</span>')
    expect(seletor).toContain('<span style={ESTILO_TIPO_ALCANCE}>{ROTULO_CURTO_ALCANCE[a].tipo}</span>')
    // O rótulo inteiro não é mais o CONTEÚDO visível do botão.
    expect(seletor).not.toContain('>\n              {ROTULO_ALCANCE[a]}\n            </button>')
  })
})
