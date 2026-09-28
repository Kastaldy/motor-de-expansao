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
/* O `:root` e' o tema ESCURO — e tambem onde moram as constantes que valem nos dois
   (paleta literal da marca, tipografia). */
const blocoRaiz = () => bloco(':root')
/* Bloco cujo seletor e' o PRIMEIRO de um grupo (`A,\nB {`). O `bloco()` ancora em ` {`
   logo depois do seletor e por isso nao acha grupo — e grupo e' exatamente a forma que
   `.rail-ultra` / `.painel-marca` usam. */
function blocoDeGrupo(seletor: string): Record<string, string> {
  const ini = css.indexOf(`\n${seletor},`)
  expect(ini, `${seletor} (grupo)`).toBeGreaterThan(-1)
  const abre = css.indexOf('{', ini)
  const fim = css.indexOf('\n}', abre)
  const tokens: Record<string, string> = {}
  for (const m of css.slice(abre, fim).matchAll(/(--[a-z0-9-]+):\s*([^;]+);/g)) {
    tokens[m[1]] = m[2].trim()
  }
  return tokens
}
/* O bloco escuro e' o :root; desde 2026-09-09 ele segue as MESMAS matizes da marca
   (o acento saiu do ~186° herdado do prototipo para o turquesa Ultra, e rosa/coral
   ancoram no magenta e no laranja de apoio, aclarados para o fundo escuro). */
const blocoEscuro = () => bloco(':root')

const hex2rgb = (h: string) => [1, 3, 5].map((i) => parseInt(h.slice(i, i + 2), 16))

/**
 * Segue `var(--outro)` ate' chegar numa cor literal, usando o fallback quando o token
 * nao existe no bloco (`var(--pos, #37b26b)` — o `--pos` e' declarado pelo COMPONENTE,
 * nao pelo tema, entao no CSS quem vale e' o fallback).
 *
 * Existe porque medir a string declarada e' medir nada: `contraste('var(--tx-label)')`
 * devolve NaN e `expect(NaN).toBeGreaterThanOrEqual(4.5)` REPROVA — mas o inverso, um
 * `toBeLessThan`, passaria calado. Resolver e' o que torna a regua honesta.
 */
function resolverVar(valor: string | undefined, b: Record<string, string>): string {
  let v = (valor ?? '').trim()
  for (let volta = 0; volta < 5 && v.startsWith('var('); volta++) {
    const dentro = v.slice(4, v.lastIndexOf(')'))
    const virgula = dentro.indexOf(',')
    const nome = (virgula < 0 ? dentro : dentro.slice(0, virgula)).trim()
    const alternativa = virgula < 0 ? '' : dentro.slice(virgula + 1).trim()
    v = (b[nome] ?? alternativa).trim()
    if (!v) return ''
  }
  return v
}

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

  /* MUDANCA DE REGRA (2026-09-25) — e' uma REVERSAO deliberada, nao um ajuste.
     Ate' aqui estes testes exigiam o oposto: fundo e superficies com a MATIZ do
     turquesa ("nao um neutro", "nao branco puro"). Aquilo foi uma leitura do guia; o
     Felipe relatou o resultado como "um pouco bagunçado" e o guia, lido ao pe' da
     letra, pede o contrario: neutros cinza (#F2F2F2 em fundo e divisorias, #3A3A3A no
     texto) com o teal como cor DOMINANTE DE DESTAQUE.

     O diagnostico que sustenta a troca: turquesa no papel de parede tira do teal
     justamente o papel que o guia lhe da'. Quando tudo e' teal, nada e' destaque.
     Se a avaliacao visual disser o contrario, o caminho de volta e' este bloco. */
  it('o fundo e NEUTRO — o teal e acento, nao papel de parede', () => {
    const [, s] = hsl(t['--bg-base'])
    expect(s).toBeLessThanOrEqual(0.06)
    expect(hsl(t['--bg-lift'])[1]).toBeLessThanOrEqual(0.06)
  })

  it('o acento e a camada 4 (par deliberado) seguem o turquesa Ultra', () => {
    expect(difMatiz(hsl(t['--ac'])[0], H_TURQUESA)).toBeLessThanOrEqual(8)
    expect(t['--l4']).toBe(t['--ac'])
  })

  it('magenta e laranja Ultra sao as matizes de apoio da paleta de serie', () => {
    expect(difMatiz(hsl(t['--gr-rosa'])[0], H_MAGENTA)).toBeLessThanOrEqual(8)
    expect(difMatiz(hsl(t['--gr-coral'])[0], H_LARANJA)).toBeLessThanOrEqual(20)
  })

  it('as superficies sao NEUTRAS — o teal nao pinta o fundo', () => {
    for (const nome of ['--surf-panel', '--surf-card', '--surf-sidebar', '--surf-mapa']) {
      expect(hsl(baseDaSuperficie(t[nome]))[1], nome).toBeLessThanOrEqual(0.06)
    }
  })

  it('o texto e cinza neutro, e nunca preto puro', () => {
    /* Duas regras do guia na mesma trava. A COR: "use os cinzas de apoio", com
       #3A3A3A como texto principal — a rampa antiga era esverdeada (#06171a,
       #21424a...). O PRETO: o guia proibe preto puro em texto de destaque, e o #000
       tambem nao existe na paleta. */
    for (const nome of ['--tx-max', '--tx-strong', '--tx-soft', '--tx-narrative']) {
      const [, s, l] = hsl(t[nome])
      expect(s, nome).toBeLessThanOrEqual(0.06)
      expect(l, nome).toBeGreaterThan(0) // preto puro tem L = 0
    }
    expect(t['--tx-soft'].toLowerCase()).toBe('#3a3a3a')
  })

  it('a paleta LITERAL da marca existe e bate com o guia', () => {
    /* Sao constantes de marca, nao decisoes de tema: moram no :root e valem nos dois.
       Ficam para uso grafico — o cromo continua nos tokens de interface, que obedecem
       contraste. */
    const raiz = blocoRaiz()
    expect(raiz['--marca-teal'].toLowerCase()).toBe('#00a99e')
    expect(raiz['--marca-laranja'].toLowerCase()).toBe('#ef7f1f')
    expect(raiz['--marca-magenta'].toLowerCase()).toBe('#c23c8e')
    expect(raiz['--marca-cinza-900'].toLowerCase()).toBe('#3a3a3a')
  })

  it('o acento do tema NAO usa o hex exato — por contraste, nao por descuido', () => {
    /* Branco sobre #00A99E da' 2,93:1 e reprova o piso de 3,0 para texto grande, e
       este token e' o FUNDO do botao primario com --ac-on branco. Um passo mais
       escuro, na mesma matiz, resolve. Quem "consertar" para o hex exato quebra o
       botao em silencio — daqui sai o aviso. */
    expect(contraste('#ffffff', t['--ac'])).toBeGreaterThanOrEqual(3)
    expect(difMatiz(hsl(t['--ac'])[0], H_TURQUESA)).toBeLessThanOrEqual(8)
  })

  it('as reguas de contraste do bloco continuam passando', () => {
    const superficie = baseDaSuperficie(t['--surf-panel'])
    expect(contraste(t['--ac-text'], superficie)).toBeGreaterThanOrEqual(4.5)
    expect(contraste(t['--tx-muted'], superficie)).toBeGreaterThanOrEqual(4.5)
    expect(contraste(t['--gr-coral'], superficie)).toBeGreaterThanOrEqual(3)
    expect(contraste(t['--tx-muted'], t['--bg-base'])).toBeGreaterThanOrEqual(4.5)
  })

  /* O par de PREENCHIMENTO continua existindo e continua na regua de 3:1 — a separacao
     so' faz sentido enquanto os dois valores forem diferentes neste tema. */
  it('o laranja tem par proprio de TEXTO, distinto do de preenchimento', () => {
    expect(t['--gr-coral-tx']).not.toBe(t['--gr-coral'])
    expect(difMatiz(hsl(t['--gr-coral-tx'])[0], H_LARANJA)).toBeLessThanOrEqual(20)
  })
})

/* ---------------------------------------------------------------------------------
   O CARD DE KPI DA VISAO EXECUTIVA — a familia `--kpi-*`.

   ATE' 2026-09-25 O GUARDA DAQUI MEDIA OUTRA COISA. Ele cobrava 4,5:1 de
   `--ac-text`/`--gr-rosa`/`--gr-coral-tx` contra o cartao de vidro, porque o rotulo
   ciclava essas tres cores. O cartao virou superficie CHEIA de cor com texto branco, os
   tokens medidos deixaram de aparecer ali, e a familia que os substituiu nasceu sem
   UMA medida — foi assim que 4 dos 5 papeis do card ficaram abaixo de 4,5 com o CI
   verde (rotulo 4,10, apoio 3,65, delta 3,69 e 3,19).

   A regua e' 4,5:1 para TODOS os quatro papeis de tinta, inclusive os dois pasteis de
   delta: o `Delta` os pinta em TEXTO de 11px (`primitives.tsx`), que nao alcanca a
   excecao de texto grande (>=18,66px em negrito). Foi essa medida que obrigou o fundo
   do card a descer um passo — sobre o magenta exato do guia, nem o branco chega a 4,5
   para o delta, porque o proprio branco so' da' 4,85. --------------------------------- */
describe('o card de KPI se le nos dois temas', () => {
  const TINTAS = ['--kpi-rotulo', '--kpi-valor', '--kpi-apoio', '--kpi-pos', '--kpi-neg']

  for (const [nome, obter] of [
    ['claro', blocoClaro],
    ['escuro', blocoEscuro],
  ] as const) {
    it(`no tema ${nome}, as cinco tintas passam 4,5:1 sobre o fundo do card`, () => {
      const b = obter()
      /* A familia `--kpi-*` aponta para OUTRO token em quase todo papel do tema escuro
         (`var(--surf-card)`, `var(--tx-label)`) e traz fallback nos dois pasteis
         (`var(--pos, #37b26b)` — o valor que o componente usa quando o card nao
         redefine). Resolver a indirecao AQUI e' o que faz a medida ser do que o olho
         recebe, e nao da string declarada: sem isso o `contraste` recebe "var(--x)",
         devolve NaN, e `NaN >= 4,5` nao levanta — passa por medida e nao mede nada. */
      const fundo = compor(resolverVar(b['--kpi-fundo'], b), b['--bg-base'])

      for (const tinta of TINTAS) {
        const valor = resolverVar(b[tinta], b)
        expect(valor, `${tinta} nao resolve para uma cor no tema ${nome}`).toMatch(/^(#|rgb)/)
        expect(
          contraste(compor(valor, fundo), fundo),
          `${tinta} sobre o card do tema ${nome}`,
        ).toBeGreaterThanOrEqual(4.5)
      }
    })
  }

  it('o delta guarda a leitura bom/ruim: os dois pasteis seguem verde e vermelho', () => {
    /* Fechar contraste subindo os dois para branco passaria no teste acima e apagaria o
       principal do indicador. A matiz e' o que impede essa "correcao". */
    const b = blocoClaro()
    const [hPos] = hsl(b['--kpi-pos'])
    const [hNeg] = hsl(b['--kpi-neg'])
    expect(difMatiz(hPos, 140), 'o delta positivo deixou de ser verde').toBeLessThanOrEqual(45)
    expect(difMatiz(hNeg, 0), 'o delta negativo deixou de ser vermelho').toBeLessThanOrEqual(45)
    expect(hsl(b['--kpi-pos'])[1], 'o verde do delta perdeu a cor').toBeGreaterThan(0.25)
    expect(hsl(b['--kpi-neg'])[1], 'o vermelho do delta perdeu a cor').toBeGreaterThan(0.25)
  })
})

/* ---------------------------------------------------------------------------------
   OS ESCOPOS DE MARCA — `.rail-ultra`, `.painel-marca`, `.barra-ultra` (2026-09-25).

   Sao as tres superficies CHEIAS na cor da Ultra: o rail, o painel de cenario da
   Viabilidade e a barra de filtros. Substituiram o `.cromo-escuro`, que mantinha essas
   mesmas areas ESCURAS dentro do tema claro (decisao do Juan de 2026-09-09) e foi
   revogado pelo Felipe — "aplicar o guia visual da marca em tudo, mesmo que altere os
   pontos escuros e fundos pretos".

   POR QUE ESTE BLOCO MEDE CONTRASTE, e por que isso e' a licao mais cara do ciclo. Os
   tres escopos nasceram com o hex do fundo escolhido por MEDIDA — "branco sobre #00A99E
   da' 2,93:1, #007a72 entrega 5,22" — e com todo o texto declarado como branco com
   ALFA, que sobre o mesmo fundo cai para 4,41..2,52. O comentario afirmava conformidade
   AA que os tokens do proprio bloco nao entregavam, e nada ficava vermelho: a unica
   assercao que tocava estes escopos conferia o PREFIXO de tema. E' a mesma familia do
   defeito que este arquivo ja' nomeia na linha do `bloco()` — "foi assim que as ~100
   linhas do escopo do cromo ficaram sem uma unica assercao" —, reaberta nos escopos que
   substituiram aquele.

   A regua e' a do USO: 4,5:1 para todo papel de texto sobre toda superficie do escopo,
   com os translucidos COMPOSTOS sobre o fundo real. Fora dela ficam so' `--tx-off` e
   `--tx-rank`, que pintam estado DESABILITADO (`Dock.tsx` usa `--tx-rank` para o item
   indisponivel) e que a WCAG 1.4.3 dispensa. --------------------------------------- */
describe('os escopos de marca se leem', () => {
  /* `--surf-chrome` e' o fundo do escopo; `--surf-sidebar`/`--surf-bar` sao o mesmo
     valor com outro nome, entao nao entram como superficie separada. */
  const BASE = ['--surf-chrome', '--surf-sidebar', '--surf-bar']
  const TEXTOS = [
    '--tx-max',
    '--tx-strong',
    '--tx-soft',
    '--tx-narrative',
    '--tx-label',
    '--tx-muted',
    '--tx-sub',
  ]

  const ESCOPOS = [
    ['.rail-ultra / .painel-marca', () => blocoDeGrupo("[data-tema='claro'] .rail-ultra")],
    ['.barra-ultra', () => bloco("[data-tema='claro'] .barra-ultra")],
  ] as const

  for (const [nome, obter] of ESCOPOS) {
    it(`${nome}: todo papel de texto passa 4,5:1 sobre toda superficie do escopo`, () => {
      const b = obter()
      const fundo = b['--surf-chrome']
      expect(fundo, `${nome} sem --surf-chrome`).toMatch(/^#[0-9a-fA-F]{6}$/)

      /* O fundo nu MAIS cada superficie do escopo composta sobre ele. Medir so' o nu era
         o furo: o campo de busca (`--surf-input`) clareava o proprio fundo e derrubava
         o texto DENTRO do controle enquanto ele passava fora. */
      const superficies: Array<[string, string]> = [['(fundo do escopo)', fundo]]
      for (const [chave, valor] of Object.entries(b)) {
        if (!chave.startsWith('--surf-') || BASE.includes(chave)) continue
        if (valor.startsWith('var(')) continue
        superficies.push([chave, compor(valor, fundo)])
      }
      /* A lavagem do rail nao e' `--surf-*` mas e' fundo de verdade: o Dock a pinta como
         gradiente por cima de `--surf-chrome`, e o topo dela e' o ponto mais claro da
         peca — era ali que branco CHAPADO media 4,34 e reprovava. */
      for (const lavagem of ['--rail-a08', '--rail-a16']) {
        if (b[lavagem]) superficies.push([lavagem, compor(b[lavagem], fundo)])
      }

      expect(superficies.length, `${nome}: nenhuma superficie medida`).toBeGreaterThan(1)
      for (const [ondeNome, onde] of superficies) {
        for (const tinta of TEXTOS) {
          if (!b[tinta]) continue
          expect(
            contraste(compor(b[tinta], onde), onde),
            `${nome}: ${tinta} sobre ${ondeNome}`,
          ).toBeGreaterThanOrEqual(4.5)
        }
      }
    })

    it(`${nome}: o acento inverte e o que vai sobre ele tambem se le`, () => {
      const b = obter()
      /* Sobre a cor cheia quem marca o item aceso e' o branco, e entao `--ac-on` vira
         TEXTO sobre branco. Sem esta regua ele podia ficar no teal claro e sumir. */
      expect(contraste(b['--ac-on'], b['--ac']), `${nome}: --ac-on sobre --ac`).toBeGreaterThanOrEqual(4.5)
    })

    it(`${nome}: declara color-scheme LIGHT — o chrome nativo acompanha`, () => {
      /* O glifo do calendario do `<input type="date">` nao le' token: ele segue o
         `color-scheme`. Com `dark` aqui, ele sairia claro sobre campo claro. */
      const b = obter()
      expect(Object.keys(b).length, `${nome} vazio`).toBeGreaterThan(0)
      const bruto = css.slice(css.indexOf(`.${nome.split(' ')[0].slice(1)}`))
      expect(bruto.slice(0, 400)).toContain('color-scheme: light')
    })
  }

  it('cor de tema nao mora em componente — os escopos de marca sao do CLARO', () => {
    /* O MESMO defeito aconteceu TRES vezes em 2026-09-25, e por isso vira teste:

       1. `.rail-ultra` e `.barra-ultra` nasceram sem `[data-tema='claro']` e pintaram
          o rail do tema ESCURO com a cor pensada para o claro;
       2. o card de KPI da Visao Executiva recebeu `#c23c8e` CRAVADO no componente, e
          continuou rosa depois de trocar de tema — cor em componente nao sabe de tema;
       3. a mesma familia da regressao do `--surf-chrome`.

       Nada disso quebra teste de comportamento: a tela renderiza, o app funciona, e a
       cor errada so' aparece para quem troca o tema e olha. Daqui sai o aviso. */
    const globalCss = readFileSync(
      fileURLToPath(new URL('../styles/global.css', import.meta.url)),
      'utf-8',
    ).replace(/\/\*[\s\S]*?\*\//g, '')

    const MARCAS = ['.rail-ultra', '.barra-ultra', '.painel-marca']
    for (const escopo of MARCAS) {
      expect(css, `${escopo} precisa ser do tema claro`).toContain(`[data-tema='claro'] ${escopo}`)
    }

    /* A TRAVA NEGATIVA MUDOU DE FORMA em 2026-09-25. Ela era
       `css.includes("\n" + escopo + " {")`, que so' casa seletor SOLITARIO com a chave na
       mesma linha — e o arquivo escreve os escopos de marca como GRUPO de duas linhas
       (`A,\nB {`). Ou seja: a forma que o codigo usa era exatamente a que a trava nao
       via. Agora varre seletor a seletor, nos DOIS arquivos de estilo. */
    for (const folha of [css, globalCss]) {
      for (const m of folha.matchAll(/(^|\n)([^{}@\n][^{}]*?)\{/g)) {
        for (const seletor of m[2].split(',')) {
          const limpo = seletor.trim()
          if (!MARCAS.some((marca) => limpo.includes(marca))) continue
          expect(
            limpo.startsWith("[data-tema='claro']"),
            `${limpo} vale nos DOIS temas — a cor de marca e' do claro`,
          ).toBe(true)
        }
      }
    }

    /* O card de KPI pinta por TOKEN, nunca por hex no `ExecutiveScreen`. */
    const exec = readFileSync(
      fileURLToPath(new URL('../screens/ExecutiveScreen.tsx', import.meta.url)),
      'utf-8',
    )
    const ini = exec.indexOf('{KPIS.map((k) => {')
    expect(ini, 'a fileira de KPIs mudou de forma — reveja este teste').toBeGreaterThan(-1)
    const cartao = exec.slice(ini, exec.indexOf('</Glass>', ini))
    expect(cartao.match(/#[0-9a-fA-F]{6}/g), 'hex cravado no card de KPI').toBeNull()
    expect(cartao).toContain('var(--kpi-fundo)')
  })

  it('o escopo `.cromo-escuro` nao volta — ele era um no-op com cara de mecanismo', () => {
    /* Removido em 2026-09-25. Depois que o rail passou para `.rail-ultra`, o bloco so'
       declarava `color-scheme: light` (que `[data-tema='claro']` ja' impoe) e tres
       `--rail-a*` sem um unico leitor. Escopo que nao pinta pixel convida a "consertar o
       tema claro aqui" e devolve a ilha escura sem nada ficar vermelho. */
    expect(css).not.toContain('.cromo-escuro {')
    for (const arquivo of ['../screens/ExecutiveScreen.tsx', '../components/Dock.tsx']) {
      const tsx = readFileSync(fileURLToPath(new URL(arquivo, import.meta.url)), 'utf-8')
      expect(tsx, `${arquivo} ainda usa a classe removida`).not.toContain('"cromo-escuro"')
    }
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
    /* O ciclo de cor do rotulo de KPI saiu nos dois temas (ver o describe do card); o
       que resta medir aqui e' a paleta de SERIE sobre o cartao de vidro, que continua
       pintando grafico e legenda. */
    for (const nome of ['--ac-text', '--gr-rosa', '--gr-coral-tx']) {
      expect(contraste(t[nome], card), `${nome} sobre o cartao de vidro`).toBeGreaterThanOrEqual(4.5)
    }
  })
})

/* ---------------------------------------------------------------------------------
   O CARTAO DE VEREDITO DA FICHA DO HEXAGONO.

   Ele era a unica peca da janela com a cor CRAVADA no componente
   (`FichaHex.tsx`, `FUNDO_VEREDITO` = um gradiente teal quase preto). Todo o interior
   ja' era token — `--tx-strong` na frase, `--tx-sub` na nota, `--line-soft` no rodape.
   No claro os tokens de TEXTO viram escuros e o fundo cravado NAO virava nada: texto
   escuro sobre fundo escuro, o retangulo preto que o Juan viu na analise pontual de
   Brasilia (2026-09-10, hexagono do Guara).

   A trava e' de CONTRASTE, nao de valor: quem trocar o gelo do cartao por um teal mais
   saturado ve' a regua do --tx-sub cair (o #dff2ef que parecia bonito da' 4,43:1) e o
   teste reprova antes do print.
   --------------------------------------------------------------------------------- */
describe('o cartao de veredito da ficha segue o tema', () => {
  const claro = blocoClaro()
  const escuro = blocoEscuro()

  /* As paradas de cor de um `linear-gradient(...)`, na ordem em que aparecem. */
  const paradas = (grad: string) => grad.match(/#[0-9a-fA-F]{6}/g) ?? []

  it('os dois temas declaram o par --grad-verdict / --line-verdict', () => {
    for (const [nome, bloco] of [
      ['escuro', escuro],
      ['claro', claro],
      /* O `cromo` SAIU desta lista em 2026-09-25: ele deixou de redeclarar tokens e
         passou a herdar o tema claro, entao exigir o par aqui pediria de volta
         exatamente a duplicacao que a mudanca removeu. */
    ] as const) {
      expect(bloco['--grad-verdict'], `--grad-verdict no ${nome}`).toBeTruthy()
      expect(bloco['--line-verdict'], `--line-verdict no ${nome}`).toBeTruthy()
    }
  })

  it('no claro, a nota e a frase do cartao se leem sobre TODAS as paradas do gradiente', () => {
    const stops = paradas(claro['--grad-verdict'])
    expect(stops.length).toBeGreaterThanOrEqual(2)
    for (const parada of stops) {
      for (const nome of ['--tx-sub', '--tx-strong', '--ac-text']) {
        expect(contraste(claro[nome], parada), `${nome} sobre ${parada}`).toBeGreaterThanOrEqual(4.5)
      }
    }
  })

  it('no claro, o cartao e gelo turquesa como o resto do tema', () => {
    for (const parada of paradas(claro['--grad-verdict'])) {
      const [h, s, l] = hsl(parada)
      expect(difMatiz(h, H_TURQUESA), parada).toBeLessThanOrEqual(12)
      expect(s, parada).toBeGreaterThan(0)
      expect(l, parada).toBeGreaterThan(0.5) // e' um cartao CLARO
    }
  })

  /* O escuro e' o tema padrao do produto: esta mudanca nao pode mexer num pixel dele. */
  it('o escuro mantem exatamente o gradiente que ja tinha', () => {
    expect(escuro['--grad-verdict']).toBe('linear-gradient(120deg, #11282a, #0d1a1e 70%)')
    expect(escuro['--line-verdict']).toBe('#24474a')
    /* As duas linhas que comparavam o CROMO com o escuro cairam em 2026-09-25. Elas
       existiam porque o cromo era uma copia do tema escuro dentro da pagina clara;
       agora ele herda o tema claro, e o cartao de veredito dentro dele deve ser
       CLARO — comparar com o escuro pediria de volta a ilha preta. */
  })

  it('FichaHex nao crava mais cor nenhuma no cartao', () => {
    const tsx = readFileSync(fileURLToPath(new URL('../components/FichaHex.tsx', import.meta.url)), 'utf-8')
    const cartao = tsx.slice(tsx.indexOf('<CardPainel'), tsx.indexOf('<CardPainel') + 200)
    expect(cartao).toContain('var(--grad-verdict)')
    expect(cartao).toContain('var(--line-verdict)')
    /* Fora de comentario: o literal nao pode voltar por uma constante nova no topo. */
    const codigo = tsx.replace(/\/\*[\s\S]*?\*\//g, '').replace(/\/\/.*/g, '')
    expect(codigo).not.toContain('linear-gradient(')
    expect(codigo).not.toContain('#11282a')
    expect(codigo).not.toContain('#0d1a1e')
    expect(codigo).not.toContain('#24474a')
  })
})

/* ---------------------------------------------------------------------------------
   TINTA DE ACENTO SOBRE LAVAGEM DE ACENTO.

   Todas as reguas acima medem texto sobre SUPERFICIE (card, painel, cabecalho, parada
   de gradiente). Faltava o caso em que o proprio acento entra ATRAS do texto: chip de
   filtro ativo, botao selecionado, pilula de estado — todos pintam --ac-a16 de fundo, e
   um alfa de 0,16 clareia a superficie o bastante para derrubar a tinta que passava
   sobre ela nua. E' a regua do USO, nao a do token, a mesma licao do --gr-coral.

   Medido em 2026-09-14 na aba Acessos, onde os dois pontos moravam: --ac-text sobre
   --ac-a16/--surf-card/--bg-base (#c5e8e4) da 3,97:1 e sobre --ac-a16/--surf-chrome
   (#c6e8e5) da 3,98:1 — os dois abaixo do piso de 4,5:1 que o Dock ja cobra (ele
   recusou tokens por 3,06 e 4,37). --ac-chip da 4,87 e 4,88 no claro e 9,53 e 9,18 no
   escuro, e e' o token que o produto ja usa por cima de acento em 6 telas.
   --------------------------------------------------------------------------------- */
describe('tinta de acento sobre lavagem de acento', () => {
  const claro = blocoClaro()
  const escuro = blocoEscuro()

  /* A composicao INTEIRA, que e' o que o olho recebe: a lavagem de acento sobre a
     superficie translucida, e a superficie sobre o fundo da tela. Medir --ac-a16 contra
     a superficie nua (ou pior, contra o token declarado) e' o que deixa o buraco passar. */
  const lavagem = (t: Record<string, string>, superficie: string) =>
    compor(t['--ac-a16'], compor(t[superficie], t['--bg-base']))

  const SUPERFICIES = ['--surf-card', '--surf-chrome']

  it('no claro, --ac-chip se le sobre a lavagem nas duas superficies', () => {
    for (const sup of SUPERFICIES) {
      expect(contraste(claro['--ac-chip'], lavagem(claro, sup)), sup).toBeGreaterThanOrEqual(4.5)
    }
  })

  it('no escuro, a mesma escolha continua valendo', () => {
    for (const sup of SUPERFICIES) {
      expect(contraste(escuro['--ac-chip'], lavagem(escuro, sup)), sup).toBeGreaterThanOrEqual(4.5)
    }
  })

  /* Se um dia --ac-chip e --ac-text convergirem, a distincao sumiu e alguem precisa
     reabrir a escolha em vez de herdar um par que nao separa mais nada. */
  it('a tinta do chip e a tinta de texto continuam sendo cores diferentes', () => {
    expect(claro['--ac-chip']).not.toBe(claro['--ac-text'])
    expect(escuro['--ac-chip']).not.toBe(escuro['--ac-text'])
  })
})
