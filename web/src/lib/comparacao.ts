/**
 * Comparacao entre hexagonos — a regra, PURA e testavel.
 *
 * POR QUE NAO E' O "CENARIO MULTI-HEX". O botao que ja existe no mapa SOMA: junta
 * N hexes num bloco unico (residual somado, populacao somada, concorrentes somados,
 * media simples do score censitario). Isso responde "quanto vale este pedaco de
 * cidade junto". Comparar responde outra pergunta — "qual destes dois e' melhor, e
 * por que" — e as duas continuam existindo lado a lado.
 *
 * ORDENAR PELO BRUTO, NUNCA PELO SCORE. `score_oportunidade_residual` (`hex.res`) e'
 * `clip(100 * oferta / 2500, 0, 100)`: todo hexagono com mais de 2.500 alunos de
 * residual empata em 100. Medido no payload real de GO: `res: 100.0` com
 * `oferta: 8694`. Comparar por `res` apagaria justamente a diferenca no topo, que e'
 * onde estao os candidatos. Por isso a dimensao de residual le `oferta`, em alunos.
 *
 * TEXTO POR REGRA, NAO POR MODELO. O produto nao usa LLM em lugar nenhum (zero SDK,
 * zero chave); todo texto automatico daqui e' cadeia de regra deterministica, como
 * `_narrativa_concorrencia` no backend. A frase comparativa segue o mesmo padrao:
 * mesma entrada, mesma saida, auditavel e testavel.
 */

import type { Hex } from './types'

/**
 * Uma dimensao comparavel: de onde ler, como chamar, e o que significa "melhor".
 *
 * GENERICA de proposito. As regras que importam — dois limiares, no maximo 3
 * dimensoes na frase, separar vantagem de desvantagem com "porem" — valem igual
 * comparando hexagonos ou municipios. Duplicar o nucleo para o segundo caso seria
 * garantir que os dois divirjam no primeiro ajuste.
 */
export interface Dimensao<T> {
  chave: string
  /** Rotulo de exibicao (acentuado — texto de usuario). */
  rotulo: string
  /** Le o valor do item. `null` = dimensao ausente neste item. */
  ler: (x: T) => number | null
  unidade: string
  /** `true` = numero maior e' melhor. Concorrentes e' o unico onde menor ganha. */
  maiorEhMelhor: boolean
  /**
   * Diferenca minima para a dimensao ENTRAR na frase.
   * `relativa` = fracao (0.1 = 10%); `absoluta` = unidades, para contagem pequena,
   * onde 1 concorrente contra 2 e' +100% e nao significa quase nada.
   */
  limiarRelativo: number
  limiarAbsoluto: number
}

/**
 * Ordem de PRIORIDADE, nao de exibicao: quando mais de 3 dimensoes passam do
 * limiar, a frase fica com as 3 primeiras desta lista. Residual vem antes de tudo
 * porque e' a pergunta do produto ("cabe quanta gente ainda?"); crescimento vem por
 * ultimo porque e' contexto municipal, nao atributo do hexagono.
 */
export const DIMENSOES: readonly Dimensao<Hex>[] = Object.freeze([
  Object.freeze({
    chave: 'oferta',
    rotulo: 'Residual disponível',
    ler: (h: Hex) => h.oferta,
    unidade: 'alunos',
    maiorEhMelhor: true,
    limiarRelativo: 0.1,
    limiarAbsoluto: 100,
  }),
  Object.freeze({
    chave: 'pop',
    rotulo: 'População',
    ler: (h: Hex) => h.pop,
    unidade: 'pessoas',
    maiorEhMelhor: true,
    limiarRelativo: 0.1,
    limiarAbsoluto: 500,
  }),
  Object.freeze({
    chave: 'conc',
    rotulo: 'Concorrentes',
    ler: (h: Hex) => h.conc,
    unidade: '',
    // Unica dimensao invertida: menos concorrente e' melhor.
    maiorEhMelhor: false,
    limiarRelativo: 0.1,
    /**
     * Precisa de 2 concorrentes de diferenca, nao 1.
     *
     * O numero que chega aqui (`hex.conc`) NAO e' contagem: e'
     * `round(oferta_consumida_ponderada_por_distancia / 2500)`. Um concorrente a
     * 1,9 km entra valendo ~0,05 e some no arredondamento, entao +-1 e' ruido do
     * proprio estimador. Dizer "tem menos concorrentes" para 2 contra 1 seria
     * afirmar sobre a precisao que este campo nao tem.
     */
    limiarAbsoluto: 2,
  }),
  Object.freeze({
    chave: 'renda',
    rotulo: 'Renda per capita',
    ler: (h: Hex) => h.renda,
    unidade: 'R$',
    maiorEhMelhor: true,
    limiarRelativo: 0.1,
    limiarAbsoluto: 100,
  }),
  Object.freeze({
    chave: 'cres',
    rotulo: 'Crescimento',
    ler: (h: Hex) => h.cres_hex_taxa ?? null,
    unidade: '%',
    maiorEhMelhor: true,
    limiarRelativo: 0.1,
    limiarAbsoluto: 2,
  }),
])

export interface Delta<T = Hex> {
  dimensao: Dimensao<T>
  a: number | null
  b: number | null
  /** Diferenca absoluta (a - b). `null` se algum lado nao tem o dado. */
  diferenca: number | null
  /** |a-b| / max(|a|,|b|). `null` quando nao da para calcular. */
  desvioRelativo: number | null
  /** Passou dos DOIS limiares (relativo E absoluto)? */
  relevante: boolean
  /** Quem leva esta dimensao, ja considerando `maiorEhMelhor`. */
  vencedor: 'a' | 'b' | 'empate'
}

/** Compara A e B nas dimensoes dadas, na ordem de prioridade. */
export function comparar<T>(dims: readonly Dimensao<T>[], a: T, b: T): Delta<T>[] {
  return dims.map((dim) => {
    const va = dim.ler(a)
    const vb = dim.ler(b)

    if (va == null || vb == null) {
      return {
        dimensao: dim, a: va, b: vb,
        diferenca: null, desvioRelativo: null,
        relevante: false, vencedor: 'empate' as const,
      }
    }

    const diferenca = va - vb
    const escala = Math.max(Math.abs(va), Math.abs(vb))
    // Ambos zero: nao ha diferenca nem desvio definido — desvio 0, nao NaN.
    const desvioRelativo = escala === 0 ? 0 : Math.abs(diferenca) / escala

    const relevante =
      desvioRelativo >= dim.limiarRelativo &&
      Math.abs(diferenca) >= dim.limiarAbsoluto

    let vencedor: 'a' | 'b' | 'empate' = 'empate'
    if (diferenca !== 0) {
      const aGanha = dim.maiorEhMelhor ? diferenca > 0 : diferenca < 0
      vencedor = aGanha ? 'a' : 'b'
    }

    return { dimensao: dim, a: va, b: vb, diferenca, desvioRelativo, relevante, vencedor }
  })
}

/** Fachada para hexagonos — o caso mais usado. */
export function compararHexes(a: Hex, b: Hex): Delta<Hex>[] {
  return comparar(DIMENSOES, a, b)
}

/**
 * Uma cor por item comparado, para a aba, a barra e o desenho no mapa falarem a mesma
 * coisa.
 *
 * POR QUE NAO E' O TURQUESA DA MARCA. Turquesa e' ACAO neste produto (botoes, pin de
 * busca): usa-lo para identificar um item o faria competir com o que ja' significa
 * "clique aqui". Estas cinco sao IDENTIDADE — a mesma funcao das cores de serie num
 * grafico —, escolhidas para se distinguirem entre si no fundo escuro.
 *
 * NAO SAO VEREDITO. Nenhuma delas diz bom ou ruim: a leitura de qualidade vem da rampa
 * publicada (`lib/faixas.ts`), que colore os medidores. Um item vermelho aqui e' o
 * terceiro da lista, nao um item ruim — por isso o vermelho da rampa (`#B92323`) fica
 * fora desta paleta.
 *
 * Cinco porque os dois tetos sao 5 (`MAX_PONTOS` e `MAX_COMPARADOS`). Se algum subir, a
 * lista precisa subir junto: o `%` evita quebrar, mas repetir cor derruba o proposito.
 *
 * MORAVA em `comparacao-pontos` ate 2026-08-13. Saiu de la' quando os hexagonos em
 * comparacao passaram a usar a mesma paleta: a fonte da verdade nao podia continuar num
 * modulo que so' descreve pontos.
 */
export const CORES_IDENTIDADE = [
  '#4FA3F7',
  '#F2A73B',
  '#9B7BF0',
  '#2FBF9E',
  '#E8618C',
] as const

/** A cor do item na posicao `i`. Cicla se um dia houver mais itens que cores. */
export function corDeIdentidade(i: number): string {
  return CORES_IDENTIDADE[
    ((i % CORES_IDENTIDADE.length) + CORES_IDENTIDADE.length) % CORES_IDENTIDADE.length
  ]
}

/**
 * A mesma cor em `[r, g, b, a]`, que e' o que o deck.gl aceita.
 *
 * Existe para o CONTORNO do hexagono no mapa usar exatamente a cor da barra dele no
 * painel. Sem isso o mapa pintaria os cinco de turquesa e o operador nao teria como ligar
 * "esta barra" a "aquele hexagono na tela" — que e' justamente o ponto de dar cor.
 */
export function corDeIdentidadeRgb(i: number, alfa = 255): [number, number, number, number] {
  const h = corDeIdentidade(i)
  return [
    parseInt(h.slice(1, 3), 16),
    parseInt(h.slice(3, 5), 16),
    parseInt(h.slice(5, 7), 16),
    alfa,
  ]
}

/**
 * Desambigua rotulos REPETIDOS, numerando so' quem empata.
 *
 * POR QUE E' GENERICO. A comparacao de PONTOS ja' resolvia isto (`rotulosDosPontos`), mas
 * a de HEXAGONOS nunca resolveu: o rotulo dela e' o nome do municipio, e comparar cinco
 * hexagonos de Sao Paulo produzia cinco itens chamados "Sao Paulo" — na tela, na tabela e
 * no PDF (relato do Juan, 2026-08-14, ao perguntar se cinco funcionaria). Com nomes iguais
 * a leitura inteira desmonta: a frase do veredito vira "Sao Paulo e' o melhor, Sao Paulo e'
 * o pior", e nenhuma barra pode ser ligada ao seu hexagono.
 *
 * O numero e' a POSICAO na lista, e nao a ordem do empate: e' assim que o rotulo casa com a
 * aba, com a cor de identidade e com o contorno no mapa.
 */
export function rotulosUnicos(nomes: readonly string[]): string[] {
  const vezes = new Map<string, number>()
  for (const n of nomes) vezes.set(n, (vezes.get(n) ?? 0) + 1)
  return nomes.map((n, i) => ((vezes.get(n) ?? 0) > 1 ? `${i + 1} · ${n}` : n))
}

/** O valor de UM item dentro do bloco de um parametro. */
export interface ValorNoBloco {
  /** Indice na lista recebida — e' por ele que a tela acha a cor e o rotulo do item. */
  indice: number
  valor: number | null
}

/** Um parametro, com TODOS os itens dentro dele. */
export interface BlocoParametro<T = Hex> {
  dimensao: Dimensao<T>
  valores: ValorNoBloco[]
  /** Indices que ganham este parametro. Empate mantem todos os empatados. */
  melhores: number[]
  /** Indices que perdem. Vazio quando so' ha' um valor comparavel. */
  piores: number[]
  /** Passou dos dois limiares entre o melhor e o pior? */
  relevante: boolean
}

/**
 * Vira a comparacao de lado: um BLOCO POR PARAMETRO, com todos os itens dentro.
 *
 * POR QUE EXISTE (pedido do Juan, 2026-08-13). A tabela A x B obriga a escolher um par
 * antes de comparar — com 5 pontos na tela sao 10 pares, e a pergunta "qual e' o melhor em
 * residual?" exige percorrer todos. Por parametro, a resposta esta' num bloco so'.
 *
 * DESTACA MELHOR E PIOR, E NAO RANQUEIA A LISTA (decisao do Juan). Uma ordenacao geral
 * exigiria somar os parametros num numero unico — isso e' SCORE NOVO, e peso entre camadas
 * do M1 so' muda por DEC. Aqui cada parametro diz quem ganha NELE, e a leitura de conjunto
 * fica com quem decide, que e' onde ela deve ficar.
 *
 * EMPATE MANTEM TODOS. Com dois pontos de residual identico, eleger um "melhor" pela ordem
 * da lista seria inventar desempate que o dado nao tem.
 *
 * `relevante` usa os MESMOS dois limiares de `comparar`, medidos entre o melhor e o pior:
 * diferenca que nao passa deles continua visivel (auditoria) mas nao vira destaque — 1
 * concorrente contra 2 e' +100% e nao significa quase nada.
 */
export function blocosPorParametro<T>(
  dims: readonly Dimensao<T>[],
  itens: readonly T[],
): BlocoParametro<T>[] {
  return dims.map((dim) => {
    const valores: ValorNoBloco[] = itens.map((x, indice) => ({ indice, valor: dim.ler(x) }))
    const comDado = valores.filter((v): v is { indice: number; valor: number } => v.valor != null)

    if (comDado.length < 2) {
      return { dimensao: dim, valores, melhores: [], piores: [], relevante: false }
    }

    const nums = comDado.map((v) => v.valor)
    const maior = Math.max(...nums)
    const menor = Math.min(...nums)
    const vMelhor = dim.maiorEhMelhor ? maior : menor
    const vPior = dim.maiorEhMelhor ? menor : maior

    const diferenca = maior - menor
    const escala = Math.max(Math.abs(maior), Math.abs(menor))
    const desvioRelativo = escala === 0 ? 0 : diferenca / escala
    const relevante = desvioRelativo >= dim.limiarRelativo && diferenca >= dim.limiarAbsoluto

    // Todos iguais: nao ha' melhor nem pior, so' um patamar comum. Marcar todo mundo de
    // vencedor pintaria a tela inteira de destaque e nao diria nada.
    if (vMelhor === vPior) {
      return { dimensao: dim, valores, melhores: [], piores: [], relevante: false }
    }

    return {
      dimensao: dim,
      valores,
      melhores: comDado.filter((v) => v.valor === vMelhor).map((v) => v.indice),
      piores: comDado.filter((v) => v.valor === vPior).map((v) => v.indice),
      relevante,
    }
  })
}

/** Quantas dimensoes cabem numa frase antes de ela virar tabela em prosa. */
export const MAX_DIMENSOES_NA_FRASE = 3

export interface Comparacao<T = Hex> {
  deltas: Delta<T>[]
  /** As que entram na frase: relevantes, na ordem de prioridade, no maximo 3. */
  destaques: Delta<T>[]
  /** Quem leva mais dimensoes relevantes. `empate` quando nenhuma passa do limiar. */
  vencedor: 'a' | 'b' | 'empate'
  frase: string
}

/**
 * Frase comparativa DETERMINISTICA.
 *
 * Regra de ouro: nunca afirmar diferenca que nao passou do limiar. Sem isso a frase
 * diria "tem mais populacao" para 2% de diferenca, que e' ruido do dado, e o
 * operador tomaria decisao em cima de nada.
 */
export function compararComFrase(
  a: Hex,
  b: Hex,
  rotuloA = 'O primeiro',
  rotuloB = 'o segundo',
): Comparacao<Hex> {
  return compararDimensoesComFrase(DIMENSOES, a, b, rotuloA, rotuloB)
}

/** O nucleo: vale para qualquer conjunto de dimensoes. */
export function compararDimensoesComFrase<T>(
  dims: readonly Dimensao<T>[],
  a: T,
  b: T,
  rotuloA = 'O primeiro',
  rotuloB = 'o segundo',
): Comparacao<T> {
  const deltas = comparar(dims, a, b)

  /**
   * QUAIS 3 dimensoes entram na frase.
   *
   * Pegar simplesmente as 3 primeiras da ordem de prioridade parecia certo e nao era:
   * medido nas cidades de GO, as tres primeiras (residual na fila, demanda nao
   * atendida, areas de alto potencial) sao CORRELACIONADAS — cidade maior ganha as
   * tres —, entao toda comparacao saia com a mesma frase e o crescimento, que era a
   * unica leitura realmente distinta, nunca aparecia.
   *
   * Regra: a dimensao de MAIOR PRIORIDADE relevante entra sempre (e' a pergunta do
   * produto, e uma frase que nao fala de residual nao serve); as vagas restantes vao
   * para as de MAIOR DESVIO, que sao as que de fato separam os dois. A APRESENTACAO
   * volta para a ordem de prioridade, para a frase ler estavel.
   */
  const relevantes = deltas.filter((d) => d.relevante)
  const prioridade = (d: Delta<T>) => deltas.indexOf(d)
  const destaques = (
    relevantes.length <= MAX_DIMENSOES_NA_FRASE
      ? relevantes
      : [
          relevantes[0],
          ...relevantes
            .slice(1)
            .sort((x, y) => (y.desvioRelativo ?? 0) - (x.desvioRelativo ?? 0))
            .slice(0, MAX_DIMENSOES_NA_FRASE - 1),
        ]
  ).sort((x, y) => prioridade(x) - prioridade(y))

  if (!destaques.length) {
    return {
      deltas,
      destaques,
      vencedor: 'empate',
      frase: 'Os dois pontos são equivalentes nas leituras disponíveis.',
    }
  }

  const pontosA = destaques.filter((d) => d.vencedor === 'a').length
  const pontosB = destaques.filter((d) => d.vencedor === 'b').length
  const vencedor: 'a' | 'b' | 'empate' =
    pontosA === pontosB ? 'empate' : pontosA > pontosB ? 'a' : 'b'

  // Cada destaque vira um trecho na voz de A ("mais X", "menos Y").
  const trecho = (d: Delta<T>) =>
    `${(d.diferenca ?? 0) > 0 ? 'mais' : 'menos'} ${d.dimensao.rotulo.toLowerCase()}`

  /**
   * Separa por QUEM GANHA, e nao pela direcao do numero.
   *
   * Sem isto a frase enfileira "menos população, menos concorrentes e menos renda"
   * como se as tres fossem deficits — mas menos concorrente e' VANTAGEM. Medido num
   * par real de GO (Goiatuba x Anapolis), a frase corrida dava a entender que
   * Goiatuba perdia em tudo, inclusive naquilo em que ganhava. O "porém" e' o que
   * devolve a direcao a leitura.
   */
  const vantagens = destaques.filter((d) => d.vencedor === 'a').map(trecho)
  const desvantagens = destaques.filter((d) => d.vencedor === 'b').map(trecho)

  const juntar = (xs: string[]) =>
    xs.length === 1 ? xs[0] : `${xs.slice(0, -1).join(', ')} e ${xs[xs.length - 1]}`

  const corpo =
    vantagens.length && desvantagens.length
      ? `${juntar(vantagens)}, porém ${juntar(desvantagens)}`
      : `${juntar(vantagens.length ? vantagens : desvantagens)}`

  const veredito =
    vencedor === 'empate'
      ? 'os dois se equilibram: cada um ganha em uma leitura diferente.'
      : vencedor === 'a'
        ? `${rotuloA} leva a comparação.`
        : `${rotuloB} leva a comparação.`

  return {
    deltas,
    destaques,
    vencedor,
    frase: `${rotuloA} tem ${corpo} que ${rotuloB} — ${veredito}`,
  }
}
