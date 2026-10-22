/**
 * O Top 10 da recomendação única (DEC-077) no mapa e nas telas — trava de LIGAÇÃO no fonte.
 *
 * As regras puras (vagas, rótulos, régua, cores, `hexesComTop10`) moram em `lib/top10.ts` e
 * são testadas lá. Aqui só se trava o que o vitest em ambiente `node` não consegue montar: o
 * espelho de cor do deck.gl contra os tokens do tema, e os fios entre as telas e a lib. Todo
 * fonte passa por `\r\n -> \n` antes, para o teste valer igual no checkout Windows (CRLF) e
 * no CI (LF).
 */
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'

import { describe, expect, it } from 'vitest'

const ler = (rel: string) =>
  readFileSync(fileURLToPath(new URL(rel, import.meta.url)), 'utf-8').replace(/\r\n/g, '\n')
const semComentario = (s: string) => s.replace(/\/\*[\s\S]*?\*\//g, '').replace(/\/\/.*$/gm, '')

const hexMap = ler('./HexMap.tsx')
const top10Regioes = ler('./Top10Regioes.tsx')
const heroTop10 = ler('./HeroTop10.tsx')
const narrativa = ler('./NarrativePanel.tsx')
const legenda = ler('./ScoreLegend.tsx')
const mapScreen = ler('../screens/MapScreen.tsx')
const oportunidades = ler('../screens/OportunidadesScreen.tsx')
const tokensCss = semComentario(ler('../styles/tokens.css'))

/** Declarações `--token: valor;` de um bloco de tema do tokens.css. */
function blocoDeTema(seletor: string): Record<string, string> {
  const ini = tokensCss.indexOf(`\n${seletor} {`)
  expect(ini, seletor).toBeGreaterThan(-1)
  const fim = tokensCss.indexOf('\n}', ini)
  const out: Record<string, string> = {}
  for (const m of tokensCss.slice(ini, fim).matchAll(/(--[a-z0-9-]+):\s*([^;]+);/g)) out[m[1]] = m[2].trim()
  return out
}

/** `#rrggbb` ou `rgba(r, g, b, a)` -> [r, g, b, a em 0..255]. */
function rgbaDoToken(v: string): [number, number, number, number] {
  const hex = v.match(/^#([0-9a-fA-F]{6})$/)
  if (hex) {
    const h = hex[1]
    return [parseInt(h.slice(0, 2), 16), parseInt(h.slice(2, 4), 16), parseInt(h.slice(4, 6), 16), 255]
  }
  const m = v.match(/^rgba?\((\d+),\s*(\d+),\s*(\d+)(?:,\s*([\d.]+))?\)$/)
  if (!m) throw new Error(`token em formato inesperado: ${v}`)
  const a = m[4] === undefined ? 1 : Number(m[4])
  return [Number(m[1]), Number(m[2]), Number(m[3]), Math.round(a * 255)]
}

/** O RGBA de um campo da `PELE` do HexMap, num dos dois temas. */
function rgbaDaPele(tema: 'escuro' | 'claro', campo: string): number[] {
  const ini = hexMap.indexOf('const PELE: Record<Tema, PeleDoMapa> = {')
  expect(ini, 'a tabela PELE mudou de forma — reveja este teste').toBeGreaterThan(-1)
  const tabela = hexMap.slice(ini, hexMap.indexOf('\n}\n', ini))
  const iEscuro = tabela.indexOf('escuro: {')
  const iClaro = tabela.indexOf('claro: {')
  const trecho = tema === 'escuro' ? tabela.slice(iEscuro, iClaro) : tabela.slice(iClaro)
  const m = trecho.match(new RegExp(`${campo}: \\[(\\d+), (\\d+), (\\d+), (\\d+)\\]`))
  expect(m, `${tema}.${campo} ausente na PELE`).not.toBeNull()
  return m!.slice(1, 5).map(Number)
}

const PARES = [
  ['--top10-mv', 'top10Mv'],
  ['--top10-premium', 'top10Premium'],
  ['--top10-fora', 'top10Fora'],
] as const

describe('cores do Top 10: token de tema e espelho do deck.gl', () => {
  it('os dois blocos de tema declaram os três tokens', () => {
    for (const seletor of [':root', "[data-tema='claro']"]) {
      const t = blocoDeTema(seletor)
      for (const [token] of PARES) expect(t[token], `${seletor} ${token}`).toBeTruthy()
    }
  })

  it('a PELE do HexMap espelha os tokens nos DOIS temas (RGB, e o alpha do "fora")', () => {
    const temas = [
      ['escuro', blocoDeTema(':root')],
      ['claro', blocoDeTema("[data-tema='claro']")],
    ] as const
    for (const [tema, tokens] of temas) {
      for (const [token, campo] of PARES) {
        const esperado = rgbaDoToken(tokens[token])
        const pele = rgbaDaPele(tema, campo)
        expect(pele.slice(0, 3), `${tema} ${campo} x ${token}`).toEqual(esperado.slice(0, 3))
        // O alpha só importa no "fora" (os segmentos usam o alphaHex do tema no fill).
        if (campo === 'top10Fora') expect(pele[3], `${tema} alpha do fora`).toBe(esperado[3])
      }
    }
  })

  it('Mata Virgem e Premium são duas matizes diferentes nos dois temas', () => {
    for (const seletor of [':root', "[data-tema='claro']"]) {
      const t = blocoDeTema(seletor)
      expect(t['--top10-mv']).not.toBe(t['--top10-premium'])
    }
  })

  it('o componente do Top 10 pinta só por token — nenhuma cor cravada', () => {
    for (const fonte of [top10Regioes, heroTop10]) {
      expect(fonte.match(/#[0-9a-fA-F]{6}\b|#[0-9a-fA-F]{3}\b/g)).toBeNull()
      expect(fonte).not.toMatch(/rgba?\(\s*\d/)
    }
    expect(top10Regioes).toContain('TOKEN_COR_TOP10[bloco.segmento]')
  })
})

describe('Top10Regioes/HeroTop10: o front NÃO reordena nem filtra (spec §2.2)', () => {
  /* A ordem fixa [Mata Virgem, Premium] e a ordem do servidor dentro de cada bloco são
     travadas na lib (`montarBlocosTop10`); aqui se trava o componente que as DESENHA nos três
     lugares (passo 5 do município, passo 5 da UF e o hero). Um `[...blocos].reverse()` ou um
     `.sort` por valor mudaria a resposta exibida com a lib verde. */
  const codigoTop10 = semComentario(top10Regioes)
  const codigoHero = semComentario(heroTop10)

  it('os blocos e as linhas são desenhados na ordem em que a lib os entrega', () => {
    expect(codigoTop10).toContain('blocos.map((b) =>')
    expect(codigoTop10).toContain('bloco.linhas.map((linha) =>')
  })

  it('nenhum sort, reverse ou filter no componente nem no hero', () => {
    for (const codigo of [codigoTop10, codigoHero]) {
      expect(codigo).not.toMatch(/\.sort\(/)
      expect(codigo).not.toMatch(/\.reverse\(/)
      expect(codigo).not.toMatch(/\.filter\(/)
      expect(codigo).not.toMatch(/\.toSorted\(|\.toReversed\(/)
    }
  })

  it('segmento sem candidato e segmento indisponível viram UMA mensagem cada', () => {
    expect(codigoTop10).toContain('bloco.semCandidato ? (')
    expect(codigoTop10).toContain(': bloco.indisponivel ? (')
    // Sem cálculo não há "0 candidatos" no cabeçalho do bloco nem no rótulo acessível.
    expect(codigoTop10).toContain('{bloco.textoCandidatos && (')
    expect(codigoTop10).toContain('bloco.textoCandidatos ?? bloco.indisponivel?.titulo')
  })

  it('o carimbo da régua é o rótulo de negócio; a versão crua fica só na dica', () => {
    expect(codigoTop10).toContain('{textoVersaoDaRegua(bloco.regra)}')
    expect(codigoTop10).toContain('title={referenciaTecnicaDaRegua(bloco.regra)}')
    expect(codigoTop10).not.toContain('{bloco.regra.versao}')
    expect(codigoTop10).not.toContain('{bloco.regra.dec}')
  })
})

describe('HexMap: o Top 10 na camada 5', () => {
  it('pinta pelo segmento só na camada 5, com o gatilho do Top 10', () => {
    expect(hexMap).toContain('const top10DoPasso = passo.n === PASSO_POR_FAIXA_M1 ? top10 : null')
    expect(hexMap).toContain('top10DoPasso ? { marca: top10DoPasso.porHex[d.id] ?? null, cores: coresTop10 } : null')
  })

  it('os rótulos MV1..P5 nascem do centro do H3, independentes do array de hexes', () => {
    const memo = hexMap.slice(hexMap.indexOf('const rotulosRank = useMemo('))
    expect(memo).toContain('for (const id of top10DoPasso.ids)')
    expect(memo.slice(0, memo.indexOf('for (const it of passo.itens)'))).toContain('cellToLatLng(id)')
    expect(hexMap).toContain('getBorderColor: (d) => d.borda ??')
  })

  it('o tooltip mostra segmento e chave, e o Score M1 deixa de ser o destaque com o Top 10', () => {
    expect(hexMap).toContain('rotulo={top10DoPasso.titulo}')
    expect(hexMap).toContain('valor={marcaDoHover.chaveValor}')
    expect(hexMap).toContain('forte={passo.n === 5 && !top10DoPasso}')
  })

  it('o Top 10 entra nas deps do memo das camadas', () => {
    const deps = hexMap.slice(hexMap.indexOf('    return base\n  }, ['))
    const lista = deps.slice(0, deps.indexOf('])'))
    for (const d of ['top10DoPasso,', 'top10Chave,', 'coresTop10,']) expect(lista).toContain(d)
  })
})

describe('MapScreen: as 10 regiões sempre no mapa', () => {
  it('o filtro de faixa M1 passa por `hexesComTop10`, e o mapa recebe o Top 10', () => {
    expect(mapScreen).toContain('return hexesComTop10(filtradosPelaFaixa, hs, top10?.ids ?? [])')
    expect(mapScreen).toContain('top10={top10}')
    expect(mapScreen).toContain('recomendacao={dados.recomendacao ?? null}')
    expect(mapScreen).toContain('passo.n === 5 && dados.recomendacao ? legendaTop10(dados.recomendacao) : null')
  })

  it('os textos de front que mudam com o Top 10 vêm da TABELA por país, com o legado de reserva', () => {
    expect(mapScreen).toContain("textosTop10()?.filtroFaixaRotulo ?? 'MELHORES'")
    expect(mapScreen).toContain("textosTop10()?.filtroFaixaLabel ?? 'Filtrar pelos melhores hexes'")
    expect(mapScreen).toContain('textosTop10()?.landingMapa ??')
  })
})

describe('NarrativePanel: o front não reordena nem filtra o Top 10', () => {
  it('`ordenarComDesempate`/`filtrarPorCrescimento` só na fila LEGADA', () => {
    expect(narrativa).toContain('const modoTop10 = passo.n === 5 && recomendacao != null')
    expect(narrativa).toContain('const filaLegada = passo.n === 5 && !modoTop10')
    const codigo = semComentario(narrativa)
    const chamada = codigo.indexOf('ordenarComDesempate(passo.itens')
    expect(chamada).toBeGreaterThan(-1)
    // A única chamada está no ramo `filaLegada ? ... : passo.itens`.
    expect(codigo.slice(codigo.lastIndexOf('filaLegada', chamada), chamada)).toMatch(/^filaLegada\s*\?\s*filtrarPorCrescimento\($/)
    expect(codigo.split('ordenarComDesempate(').length - 1).toBe(1)
  })

  it('o checkbox de crescimento some no modo Top 10, e o passo 5 vira o `Top10Regioes`', () => {
    expect(narrativa).toContain('{filaLegada && passo.itens.length > 0 && (')
    expect(narrativa).toContain('<Top10Regioes')
    expect(narrativa).toContain("onAbrirMunicipio={nivel === 'uf' ? onDrillMunicipio : undefined}")
    expect(narrativa).toContain('modoLeitura={recomendacao != null}')
  })

  it('com o Top 10, lista vazia das camadas 1 a 4 é leitura — sem "escolha outro município"', () => {
    const codigo = semComentario(narrativa)
    const vazio = codigo.slice(codigo.indexOf(') : itens.length === 0 ? ('))
    const ramoTop10 = vazio.slice(0, vazio.indexOf(') : ('))
    expect(ramoTop10).toContain('recomendacao ? (')
    expect(ramoTop10).toContain('textoLeituraVazia(nivel, recomendacao)')
    // A camada 4 do município não tem lista: o vazio ali só repetiria a narrativa.
    expect(ramoTop10).toContain("passo.n === 4 && nivel !== 'uf' ? null : (")
    expect(ramoTop10).not.toContain('outro município')
  })
})

describe('MethodologyPanel: leitura e Top 10 na mesma linguagem do mapa', () => {
  const metodologia = semComentario(ler('./MethodologyPanel.tsx'))

  it('o rótulo do corte vem da tabela por país (leitura / Top 10), com o legado de reserva', () => {
    expect(metodologia).toContain('textos.metodologiaCorteTop10')
    expect(metodologia).toContain('textos.metodologiaCorteLeitura')
    expect(metodologia).toContain(": 'passa no corte'")
    expect(metodologia).toContain('{rotuloCorte}')
  })

  it('os chips dos segmentos usam o token do Top 10 (a cor do mapa), não o `tom` do servidor', () => {
    expect(metodologia).toContain('corDaEtiquetaTop10(etiqueta)')
    expect(metodologia).toContain('cor={corDaFaixa(f.etiqueta, f.cor)}')
  })
})

describe('ScoreLegend: Mata Virgem / Premium / fora do Top 10', () => {
  it('a legenda do Top 10 substitui a da faixa M1 só na camada 5', () => {
    expect(legenda).toContain('const legTop10 = passoN === 5 ? top10 : null')
    expect(legenda).toContain('legTop10.itens.map(')
    expect(legenda).toContain('legTop10 ? legTop10.fora.nome :')
  })
})

describe('Oportunidades: uma resposta só', () => {
  it('o hero é o Top 10 do recorte, e o consolidado por contagem de camadas saiu', () => {
    expect(oportunidades).toContain('<HeroTop10 uf={uf} municipio={municipio} onVerNoMapa={onVerHexNoMapa} />')
    const codigo = semComentario(oportunidades)
    expect(codigo).not.toContain('consolidado')
    expect(codigo).not.toContain('RankingHexagonosBrasil')
    expect(codigo).not.toContain('A resposta')
    expect(codigo).not.toMatch(/top \{TOP_POR_CAMADA\}/)
  })

  it('as camadas aparecem como leitura, sem a camada 5', () => {
    expect(oportunidades).toContain('Leituras do recorte — não entram na recomendação')
    expect(oportunidades).toContain('const leituras = useMemo(() => leiturasDoRecorte(passos), [passos])')
  })

  it('o hero lê o bloco pelo discriminador e mostra o aviso quando a instância não tem régua', () => {
    expect(heroTop10).toContain('if (!temTop10(dados)) {')
    expect(heroTop10).toContain('Recomendação indisponível nesta instância')
    expect(heroTop10).toContain('api\n      .hexagonos({ uf, municipio })')
  })

  it('o Top 10 não reaproveita a ficha do ponto (`Recomendacao.tsx`)', () => {
    for (const fonte of [top10Regioes, heroTop10, narrativa]) {
      expect(fonte).not.toMatch(/from '\.\/Recomendacao'/)
    }
  })
})
