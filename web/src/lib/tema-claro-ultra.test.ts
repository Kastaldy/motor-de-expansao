import { describe, expect, it } from 'vitest'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'

/* O tema claro carrega as cores base da Ultra (Juan, 2026-09-08): turquesa #00A99E
   no fundo e no acento, magenta #C23C8E e laranja #EF7F1F como matizes de apoio na
   paleta de serie. Este teste le' o bloco [data-tema='claro'] de styles/tokens.css e
   verifica MATIZ (a identidade da marca) e CONTRASTE (as reguas que o proprio arquivo
   documenta) — numero em comentario envelhece, assercao nao. */

/* Os comentarios saem ANTES de qualquer coisa: eles carregam `--token: valor` em prosa
   (o bloco das camadas cita `--l1..--l4`, o do rail cita alfas) e um parser ingenuo os
   colhe como declaracao, misturando bloco com bloco. */
const css = readFileSync(fileURLToPath(new URL('../styles/tokens.css', import.meta.url)), 'utf-8').replace(
  /\/\*[\s\S]*?\*\//g,
  '',
)

function bloco(seletor: string): Record<string, string> {
  /* `\n` na frente e ` {` atras ancoram o seletor INTEIRO. Sem isso, procurar
     "[data-tema='claro'] {" nunca acha "[data-tema='claro'] .cromo-escuro {" — foi
     assim que as ~100 linhas do escopo do cromo ficaram sem uma unica assercao. */
  const ini = css.indexOf(`\n${seletor} {`)
  expect(ini, seletor).toBeGreaterThan(-1)
  const fim = css.indexOf('\n}', ini)
  const tokens: Record<string, string> = {}
  for (const m of css.slice(ini, fim).matchAll(/(--[a-z0-9-]+):\s*([^;]+);/g)) {
    tokens[m[1]] = m[2].trim()
  }
  return tokens
}

const blocoClaro = () => bloco("[data-tema='claro']")
const blocoCromo = () => bloco("[data-tema='claro'] .cromo-escuro")
/* O bloco escuro e' o :root; desde 2026-09-09 ele segue as MESMAS matizes da marca
   (o acento saiu do ~186° herdado do prototipo para o turquesa Ultra, e rosa/coral
   ancoram no magenta e no laranja de apoio, aclarados para o fundo escuro). */
const blocoEscuro = () => bloco(':root')

const hex2rgb = (h: string) => [1, 3, 5].map((i) => parseInt(h.slice(i, i + 2), 16))

/* Base rgb de um token de superficie (`rgba(r, g, b, a)` ou hex chapado), como hex. */
function baseDaSuperficie(valor: string): string {
  const m = valor.match(/rgba?\((\d+),\s*(\d+),\s*(\d+)/)
  if (!m) return valor
  return '#' + m.slice(1, 4).map((v) => Number(v).toString(16).padStart(2, '0')).join('')
}

/* Superficie REAL de um token translucido: `rgba(r,g,b,a)` composto sobre o fundo que
   fica atras. E' o que separa a cor declarada da cor que o olho recebe — e onde o
   defeito do cromo morava, porque um alfa de 0,95 ainda deixa passar 5% do gelo claro. */
function compor(valor: string, fundo: string): string {
  const m = valor.match(/rgba?\((\d+),\s*(\d+),\s*(\d+)(?:,\s*([\d.]+))?\)/)
  if (!m) return valor
  const a = m[4] === undefined ? 1 : Number(m[4])
  const atras = hex2rgb(fundo)
  return (
    '#' +
    m
      .slice(1, 4)
      .map((v, i) => Math.round(Number(v) * a + atras[i] * (1 - a)))
      .map((v) => v.toString(16).padStart(2, '0'))
      .join('')
  )
}

function hsl(hex: string): [number, number, number] {
  let [r, g, b] = hex2rgb(hex).map((v) => v / 255)
  const max = Math.max(r, g, b)
  const min = Math.min(r, g, b)
  const l = (max + min) / 2
  if (max === min) return [0, 0, l]
  const d = max - min
  const s = l > 0.5 ? d / (2 - max - min) : d / (max + min)
  let h: number
  if (max === r) h = (g - b) / d + (g < b ? 6 : 0)
  else if (max === g) h = (b - r) / d + 2
  else h = (r - g) / d + 4
  return [h * 60, s, l]
}

const luminancia = (hex: string) => {
  const [r, g, b] = hex2rgb(hex).map((v) => {
    const c = v / 255
    return c <= 0.03928 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4)
  })
  return 0.2126 * r + 0.7152 * g + 0.0722 * b
}

const contraste = (a: string, b: string) => {
  const [x, y] = [luminancia(a), luminancia(b)].sort((p, q) => q - p)
  return (x + 0.05) / (y + 0.05)
}

const difMatiz = (a: number, b: number) => Math.min(Math.abs(a - b), 360 - Math.abs(a - b))

const H_TURQUESA = hsl('#00a99e')[0] // ~176
const H_MAGENTA = hsl('#c23c8e')[0] // ~323
const H_LARANJA = hsl('#ef7f1f')[0] // ~28

describe('tema claro nas cores base da Ultra', () => {
  const t = blocoClaro()

  it('o fundo tem a matiz do turquesa Ultra, nao um neutro azulado', () => {
    const [h, s] = hsl(t['--bg-base'])
    expect(difMatiz(h, H_TURQUESA)).toBeLessThanOrEqual(12)
    expect(s).toBeGreaterThanOrEqual(0.35)
    expect(difMatiz(hsl(t['--bg-lift'])[0], H_TURQUESA)).toBeLessThanOrEqual(12)
  })

  it('o acento e a camada 4 (par deliberado) seguem o turquesa Ultra', () => {
    expect(difMatiz(hsl(t['--ac'])[0], H_TURQUESA)).toBeLessThanOrEqual(8)
    expect(t['--l4']).toBe(t['--ac'])
  })

  it('magenta e laranja Ultra sao as matizes de apoio da paleta de serie', () => {
    expect(difMatiz(hsl(t['--gr-rosa'])[0], H_MAGENTA)).toBeLessThanOrEqual(8)
    expect(difMatiz(hsl(t['--gr-coral'])[0], H_LARANJA)).toBeLessThanOrEqual(20)
  })

  it('as superficies glass sao gelo turquesa, nao branco puro', () => {
    for (const nome of ['--surf-panel', '--surf-card', '--surf-sidebar', '--surf-mapa']) {
      const base = baseDaSuperficie(t[nome])
      const [h, s, l] = hsl(base)
      expect(s, nome).toBeGreaterThan(0)
      expect(difMatiz(h, H_TURQUESA), nome).toBeLessThanOrEqual(12)
      expect(l, nome).toBeLessThan(1) // branco puro tem L = 1
    }
  })

  it('as reguas de contraste do bloco continuam passando', () => {
    const superficie = baseDaSuperficie(t['--surf-panel'])
    expect(contraste(t['--ac-text'], superficie)).toBeGreaterThanOrEqual(4.5)
    expect(contraste(t['--tx-muted'], superficie)).toBeGreaterThanOrEqual(4.5)
    expect(contraste(t['--gr-coral'], superficie)).toBeGreaterThanOrEqual(3)
    expect(contraste(t['--tx-muted'], t['--bg-base'])).toBeGreaterThanOrEqual(4.5)
  })

  /* As tres cores que a Executiva cicla nos ROTULOS de KPI (10,5px = texto pequeno, sem
     excecao de texto grande). O --gr-coral passava na trava de cima com a regua de
     ELEMENTO GRAFICO (3:1) e era justamente o token que o ciclo promovia a texto: dava
     3,28:1 em "Churn" e "Saldo operacional". A regua do USO, nao a do token. */
  it('o ciclo de cor dos rotulos de KPI passa como TEXTO sobre o card', () => {
    const card = compor(t['--surf-card'], t['--bg-base'])
    for (const nome of ['--ac-text', '--gr-rosa', '--gr-coral-tx']) {
      expect(contraste(t[nome], card), `${nome} no rotulo de KPI`).toBeGreaterThanOrEqual(4.5)
    }
    /* O par de PREENCHIMENTO continua existindo e continua na regua de 3:1 — a separacao
       so' faz sentido enquanto os dois valores forem diferentes neste tema. */
    expect(t['--gr-coral-tx']).not.toBe(t['--gr-coral'])
    expect(difMatiz(hsl(t['--gr-coral-tx'])[0], H_LARANJA)).toBeLessThanOrEqual(20)
  })
})

/* ---------------------------------------------------------------------------------
   CROMO ESCURO DENTRO DO TEMA CLARO — o escopo `.cromo-escuro`.

   Ele re-declara os tokens do tema escuro dentro de uma pagina clara, e por isso todo
   token que ele ESQUECE vira uma composicao hibrida: tinta escura sobre superficie
   clara, ou o contrario. Nao adianta medir os que estao la' — o que quebra sao os que
   NAO estao. Por isso o primeiro teste e' de FECHAMENTO por classe, e nao uma lista de
   casos: ele pega o proximo token esquecido sem que ninguem precise prever qual sera'.
   --------------------------------------------------------------------------------- */
describe('cromo escuro dentro do tema claro', () => {
  const claro = blocoClaro()
  const cromo = blocoCromo()
  const escuro = blocoEscuro()

  /* Tokens do bloco claro que NAO precisam de par aqui. A lista existe para ser
     comentada um a um: excecao sem motivo escrito e' token esquecido com alibi. */
  const SEM_PAR_NO_CROMO: Record<string, string> = {}

  it('todo token do tema claro tem par no escopo (ou excecao declarada)', () => {
    const semPar = Object.keys(claro).filter((k) => !(k in cromo) && !(k in SEM_PAR_NO_CROMO))
    expect(semPar, 'tokens do tema claro sem par no .cromo-escuro').toEqual([])
  })

  /* Desvios DELIBERADOS contra o :root, cada um com o motivo que esta' no CSS. Trava a
     lista do comentario do bloco: mudar um valor sem passar por aqui quebra o teste. */
  const DESVIOS: Record<string, string> = {
    '--surf-chrome': 'opaco: 0,95 deixava 5% do gelo claro passar e derrubava --tx-muted a 4,28:1',
    '--surf-mapa': 'preto chapado seria a unica mancha escura da tela clara',
    '--surf-raised': 'alfa +0,02: branco sobre caixa escura recortada contra papel claro',
    '--surf-input': 'idem --surf-raised',
    '--surf-pending': 'idem --surf-raised',
    '--line': 'hairline mais forte: a borda que basta no escuro some com moldura clara',
    '--line-soft': 'idem --line',
    '--line-mid': 'idem --line',
    '--line-strong': 'idem --line',
    '--line-dashed': 'idem --line',
  }

  it('o escopo espelha o :root, salvo os desvios declarados', () => {
    const divergem = Object.keys(cromo).filter((k) => cromo[k] !== escuro[k])
    expect(divergem.sort(), 'desvios do espelho contra o :root').toEqual(Object.keys(DESVIOS).sort())
  })

  /* O popup do `Select` e' `position: absolute` sem `createPortal`: ele DESCENDE do
     cabecalho `.cromo-escuro`, entao le' o --surf-panel daqui. Enquanto o token faltou,
     a lista abria com o gelo claro do tema e o texto do tema escuro por cima: 1,31:1 nas
     opcoes, 1,07:1 no campo de busca, 1,59:1 na opcao ativa, em 7 seletores das duas
     telas (UF, Municipio e Melhores no Mapa; UF, Consultor, Master e Maturidade na
     Executiva). O fundo de composicao e' o --bg-base CLARO, que e' o que fica atras. */
  it('o popup do Select fica legivel: texto do escuro sobre superficie do escuro', () => {
    const popup = compor(cromo['--surf-panel'], claro['--bg-base'])
    for (const nome of ['--tx-soft', '--tx-strong', '--ac-text']) {
      expect(contraste(cromo[nome], popup), `${nome} no popup do Select`).toBeGreaterThanOrEqual(4.5)
    }
  })

  /* A caixa do cabecalho. O --surf-chrome nao pode voltar a ser translucido sem levar
     junto a legenda de periodo do cabecalho executivo. */
  it('o texto do cabecalho passa sobre a caixa escura', () => {
    const caixa = compor(cromo['--surf-chrome'], claro['--bg-base'])
    for (const nome of ['--tx-muted', '--tx-sub', '--tx-narrative', '--ac-text']) {
      expect(contraste(cromo[nome], caixa), `${nome} no cabecalho`).toBeGreaterThanOrEqual(4.5)
    }
  })

  /* O chrome NATIVO (glifo do calendario do `<input type="date">` do PeriodoPicker) nao
     le' token: ele segue o `color-scheme`, que no <html> continua `light`. */
  it('o escopo declara color-scheme dark para o chrome nativo', () => {
    const ini = css.indexOf("\n[data-tema='claro'] .cromo-escuro {")
    expect(css.slice(ini, css.indexOf('\n}', ini))).toContain('color-scheme: dark')
  })
})

describe('tema escuro nas mesmas cores base da Ultra', () => {
  const t = blocoEscuro()

  it('o acento e a camada 4 (par deliberado) seguem o turquesa Ultra', () => {
    expect(difMatiz(hsl(t['--ac'])[0], H_TURQUESA)).toBeLessThanOrEqual(8)
    expect(t['--l4']).toBe(t['--ac'])
  })

  it('magenta e laranja Ultra sao as matizes de apoio da paleta de serie', () => {
    expect(difMatiz(hsl(t['--gr-rosa'])[0], H_MAGENTA)).toBeLessThanOrEqual(8)
    expect(difMatiz(hsl(t['--gr-coral'])[0], H_LARANJA)).toBeLessThanOrEqual(20)
  })

  /* O tema escuro so' tinha trava de MATIZ, e matiz nao diz se o texto se le'. A
     recalibragem de 2026-09-09 mexeu no acento e nos dois apoios; sem estas reguas, a
     proxima mexida pode escurecer um deles ate' o rotulo sumir e o CI continua verde. */
  it('as reguas de contraste do escuro se sustentam', () => {
    const painel = compor(t['--surf-panel'], t['--bg-base'])
    const card = compor(t['--surf-card'], t['--bg-base'])
    for (const nome of ['--ac-text', '--tx-muted', '--tx-sub', '--tx-narrative']) {
      expect(contraste(t[nome], painel), `${nome} no painel escuro`).toBeGreaterThanOrEqual(4.5)
    }
    for (const nome of ['--ac-text', '--gr-rosa', '--gr-coral-tx']) {
      expect(contraste(t[nome], card), `${nome} no rotulo de KPI`).toBeGreaterThanOrEqual(4.5)
    }
  })
})
