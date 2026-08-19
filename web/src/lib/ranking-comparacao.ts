/**
 * Comparar N itens (2 a 5) e dizer qual e' o melhor e qual e' o pior.
 *
 * NAO SOMA AS DIMENSOES NUM SCORE. Um Borda count (somar posicoes) parece inocente e
 * nao e': ele assume que uma posicao em "residual" vale o mesmo que uma posicao em
 * "renda", o que e' um PESO — e peso entre camadas do M1 e' decisao que exige DEC. O
 * que se faz aqui e' CONTAR: em quantas dimensoes cada item e' o melhor, e em quantas
 * e' o pior. Contagem o operador confere a olho na propria tabela.
 *
 * DIMENSAO SEM SEPARACAO NAO DA PONTO. Se o melhor e o pior de uma dimensao estao
 * dentro do limiar (o mesmo par relativo+absoluto que a comparacao A x B usa), aquela
 * dimensao nao elege ninguem — declarar vencedor por 2% de diferenca seria transformar
 * ruido em argumento.
 *
 * O EMPATE E' UMA RESPOSTA. Quando dois itens tem a mesma contagem de vitorias, nao ha
 * "melhor": a funcao diz isso em vez de desempatar por um criterio inventado.
 */

import type { Dimensao } from './comparacao'

/** Teto de itens numa comparacao. Acima disto a tabela deixa de caber e de ser lida. */
export const MAX_COMPARADOS = 5

export interface PosicaoNaDimensao {
  chave: string
  rotulo: string
  unidade: string
  valor: number | null
  /** 1 = melhor desta dimensao. `null` quando o item nao tem o dado. */
  posicao: number | null
  melhor: boolean
  pior: boolean
}

export interface ItemRanqueado {
  indice: number
  rotulo: string
  /** Dimensoes em que este item e' o melhor (so' as que separam). */
  vitorias: number
  /** Dimensoes em que e' o pior. */
  derrotas: number
  /**
   * Colocacao no ranking, com empate COMPARTILHADO (1, 1, 3).
   *
   * Publicada aqui porque quem desenha nao pode recalcula-la. O deck em PDF tinha a
   * propria copia desta conta e as duas ja' divergiram duas vezes — imprimindo dois 1o
   * enquanto a frase apontava um vencedor, e depois o contrario. A regra e' uma so',
   * e ela e' esta.
   */
  posicao: number
  porDimensao: PosicaoNaDimensao[]
}

export interface RankingComparacao {
  itens: ItemRanqueado[]
  /** `null` quando ha empate no topo — nao se inventa desempate. */
  melhor: ItemRanqueado | null
  pior: ItemRanqueado | null
  /**
   * Dimensoes que efetivamente separaram alguem.
   *
   * NAO E' O DENOMINADOR do "lidera em X/N" — ver `porDimensao.length`, que e' o conjunto
   * FIXO de parametros comparados. Serve para de-enfatizar na tabela a linha que nao
   * separou ninguem: o numero continua visivel para auditoria, sem virar argumento.
   */
  dimensoesDecisivas: string[]
  frase: string
}

export interface OpcoesRanking<T> {
  /**
   * PORTAO do estudo: este item passa em TODOS os criterios avaliados?
   *
   * `true` = nenhum criterio avaliado reprovou; `false` = algum reprovou; `null` = nao ha'
   * criterio avaliado (e ai o portao nao fala).
   *
   * NAO E' UM SCORE, e a distincao importa. Ele nao conta quantos criterios cada item
   * cumpre nem soma nada: le uma unica pergunta binaria que o estudo ja' responde por
   * ponto, e que o proprio deck ja' imprime ao lado do nome ("passa nos 5 criterios" /
   * "reprova em: ..."). Somar criterios numa nota seria veredito novo de viabilidade e
   * exigiria DEC — ver `_criterios_do_ponto` no servidor.
   *
   * SO' FALA NO EMPATE. Enquanto a contagem de parametros liderados separa os itens, e'
   * ela que manda; o portao entra unicamente quando ela empata, porque dividir o topo
   * entre quem limpa todos os pisos do produto e quem reprova em dois nao descreve o que
   * o operador tem na mao (Juan, 2026-08-19).
   */
  aprovado?: (x: T) => boolean | null
}

/**
 * Ranqueia `itens` nas `dims` dadas.
 *
 * Generico pelo mesmo motivo do resto: hexagono, municipio e ponto usam as MESMAS
 * dimensoes e os MESMOS limiares que a comparacao de dois ja usa.
 */
export function ranquear<T>(
  dims: readonly Dimensao<T>[],
  itens: readonly T[],
  rotulos: readonly string[],
  opcoes: OpcoesRanking<T> = {},
): RankingComparacao {
  const base: ItemRanqueado[] = itens.map((_, i) => ({
    indice: i,
    rotulo: rotulos[i] ?? `Item ${i + 1}`,
    vitorias: 0,
    derrotas: 0,
    posicao: 1,
    porDimensao: [],
  }))

  const decisivas: string[] = []

  for (const dim of dims) {
    const valores = itens.map((it) => dim.ler(it))
    const comDado = valores
      .map((v, i) => ({ v, i }))
      .filter((x): x is { v: number; i: number } => x.v != null)

    // Ordena do MELHOR para o pior, ja considerando `maiorEhMelhor`.
    const ordenados = [...comDado].sort((x, y) =>
      dim.maiorEhMelhor ? y.v - x.v : x.v - y.v,
    )

    /* A dimensao SEPARA? Mede-se pelo par melhor x pior, com os mesmos dois limiares
       da comparacao A x B. Sem isso, cinco itens praticamente iguais elegeriam um
       "melhor" por diferenca que nao sustenta decisao. */
    let separa = false
    if (ordenados.length >= 2) {
      const vMelhor = ordenados[0].v
      const vPior = ordenados[ordenados.length - 1].v
      const diff = Math.abs(vMelhor - vPior)
      const escala = Math.max(Math.abs(vMelhor), Math.abs(vPior))
      const relativo = escala === 0 ? 0 : diff / escala
      separa = relativo >= dim.limiarRelativo && diff >= dim.limiarAbsoluto
    }
    if (separa) decisivas.push(dim.chave)

    // Empate no topo (ou na base) NAO elege ninguem naquela ponta.
    const topoUnico =
      ordenados.length >= 2 && ordenados[0].v !== ordenados[1].v
    const baseUnica =
      ordenados.length >= 2 &&
      ordenados[ordenados.length - 1].v !== ordenados[ordenados.length - 2].v

    itens.forEach((_, i) => {
      const v = valores[i]
      /* POSICAO COM EMPATE COMPARTILHADO (1, 2, 2, 4): "quantos estao estritamente a
         frente, mais um" — e nao o indice na lista ordenada. Com o indice, dois itens de
         valor IDENTICO saiam como 2o e 3o, e a diferenca entre eles vinha so' da ordem em
         que foram colados. Medido em 18/08 num deck real: dois pontos com residual 0
         apareciam como 2o e 3o, o 3o pintado de "pior" na matriz; trocando a ordem de
         colagem, trocavam de lugar. Ordem de digitacao nao e' leitura de territorio. */
      const pos =
        v == null
          ? null
          : ordenados.filter((o) => (dim.maiorEhMelhor ? o.v > v : o.v < v)).length + 1
      const ehMelhor = separa && topoUnico && pos === 1
      const ehPior = separa && baseUnica && pos === ordenados.length && pos !== 1
      if (ehMelhor) base[i].vitorias += 1
      if (ehPior) base[i].derrotas += 1
      base[i].porDimensao.push({
        chave: dim.chave,
        rotulo: dim.rotulo,
        unidade: dim.unidade,
        valor: v,
        posicao: pos,
        melhor: ehMelhor,
        pior: ehPior,
      })
    })
  }

  /* PORTAO do estudo por item, quando o chamador o oferece. `1` passa em tudo, `0` nao,
     `-1` sem criterio avaliado — so' para ordenar; ver `OpcoesRanking.aprovado`. */
  const portao = base.map((it) => {
    const v = opcoes.aprovado?.(itens[it.indice])
    return v == null ? -1 : v ? 1 : 0
  })
  /** Maior contagem de vitorias da comparacao: quem a tem esta' disputando o TOPO. */
  const topoVitorias = base.length ? Math.max(...base.map((it) => it.vitorias)) : 0

  /**
   * Os dois lados do portao falaram, falaram coisas diferentes, e ISTO E' O TOPO?
   *
   * A ultima condicao nao e' detalhe. Sem ela o portao valia como criterio global de
   * ordenacao e reordenava tambem o fundo da lista: com A(3v,0d,passa),
   * B(0v,0d,reprova) e C(0v,3d,passa), o portao punha C na frente de B — e B, que fica
   * no MEIO de todos os parametros e nao perde nenhum, saia impresso em ultimo, atras
   * de quem perdeu os tres. O portao decide quem leva o primeiro lugar; ele nao tem o
   * que dizer sobre quem e' o pior.
   */
  const portaoSepara = (a: ItemRanqueado, b: ItemRanqueado) =>
    a.vitorias === topoVitorias &&
    b.vitorias === topoVitorias &&
    portao[a.indice] >= 0 &&
    portao[b.indice] >= 0 &&
    portao[a.indice] !== portao[b.indice]

  /* Ordena por vitorias desc; entre quem disputa o TOPO, pelo portao do estudo; so'
     entao por MENOS derrotas. Fora do topo as derrotas dao ordem estavel a quem empatou,
     para a tabela e o deck nao trocarem de linha entre duas montagens do mesmo conjunto. */
  const ordenado = [...base].sort(
    (a, b) =>
      b.vitorias - a.vitorias ||
      (a.vitorias === topoVitorias ? portao[b.indice] - portao[a.indice] : 0) ||
      a.derrotas - b.derrotas,
  )

  /* EMPATE E' A METRICA DA PONTA, e cada ponta tem a sua.
     No TOPO a metrica e' VITORIAS — duas areas que lideram o mesmo numero de parametros
     empatam —, com uma ressalva: se uma delas passa em TODOS os criterios do estudo e a
     outra reprova, nao ha' empate. Sao pisos do produto, nao mais um parametro comparado:
     dividir o primeiro lugar entre quem limpa todos e quem nao limpa afirmaria uma
     equivalencia que o proprio slide desmente duas linhas abaixo (Juan, 2026-08-19).
     Na BASE a metrica e' DERROTAS, pelo raciocinio invertido: "pior" e' quem fica atras,
     nao quem deixa de liderar. Medir a base por vitorias apagaria o pior de quase toda
     comparacao — num trio e' normal um item levar tudo e os outros dois ficarem com zero
     vitoria cada, e ainda assim um deles perder em tres dimensoes e o outro em nenhuma. */
  const topoEmpatado =
    ordenado.length >= 2 &&
    ordenado[0].vitorias === ordenado[1].vitorias &&
    !portaoSepara(ordenado[0], ordenado[1])
  /* O PIOR sai da METRICA, e nao da ultima linha da lista. Tomar `ordenado[last]` fazia
     a resposta depender da ordenacao — que serve ao desenho, nao ao veredito —, e assim
     um item de zero derrotas podia ser chamado de pior enquanto outro, que perdeu em
     todas as dimensoes, aparecia acima dele. Empate no maximo = ninguem e' o pior; maximo
     zero significa que o fundo nao separou ninguem, e cai no mesmo lugar. */
  const maxDerrotas = ordenado.length ? Math.max(...ordenado.map((it) => it.derrotas)) : 0
  const naBase = ordenado.filter((it) => it.derrotas === maxDerrotas)
  const baseEmpatada = maxDerrotas === 0 || naBase.length !== 1

  /* POSICAO com empate compartilhado (1, 1, 3): mesma definicao do `topoEmpatado`, para
     o numero impresso nunca contradizer a frase. */
  ordenado.forEach((it, i) => {
    const anterior = ordenado[i - 1]
    const empataComAnterior =
      i > 0 && it.vitorias === anterior.vitorias && !portaoSepara(anterior, it)
    it.posicao = empataComAnterior ? anterior.posicao : i + 1
  })

  const melhor = decisivas.length && !topoEmpatado ? ordenado[0] : null
  const pior = decisivas.length && !baseEmpatada ? naBase[0] : null

  return {
    itens: ordenado,
    melhor,
    pior,
    dimensoesDecisivas: decisivas,
    frase: montarFrase(ordenado, melhor, pior, decisivas.length, portaoSepara),
  }
}

function montarFrase(
  ordenado: ItemRanqueado[],
  melhor: ItemRanqueado | null,
  pior: ItemRanqueado | null,
  nDecisivas: number,
  portaoSepara: (a: ItemRanqueado, b: ItemRanqueado) => boolean,
): string {
  if (!nDecisivas) {
    return 'Os itens comparados são equivalentes nas leituras disponíveis — nenhuma diferença passa do limiar.'
  }
  if (!melhor) {
    return `Não há um melhor: ${ordenado[0].rotulo} e ${ordenado[1].rotulo} vencem o mesmo número de leituras.`
  }

  const venceEm = melhor.porDimensao
    .filter((d) => d.melhor)
    .map((d) => d.rotulo.toLowerCase())

  let base = venceEm.length
    ? `${melhor.rotulo} é o melhor: lidera em ${enumerar(venceEm)}.`
    : `${melhor.rotulo} é o melhor das leituras disponíveis.`

  /* QUANDO FOI O PORTAO QUE DECIDIU, a frase precisa dizer isso. Sem esta linha o leitor
     ve dois itens liderando o mesmo numero de parametros e um deles chamado "o melhor",
     sem nada na frase explicando de onde saiu a diferenca. */
  const vice = ordenado[1]
  if (vice && vice.vitorias === melhor.vitorias && portaoSepara(melhor, vice)) {
    base =
      `${melhor.rotulo} e ${vice.rotulo} lideram o mesmo número de parâmetros, ` +
      `mas ${melhor.rotulo} passa em todos os critérios do estudo e ${vice.rotulo} não.`
  }

  if (!pior || pior.indice === melhor.indice) return base

  const perdeEm = pior.porDimensao.filter((d) => d.pior).map((d) => d.rotulo.toLowerCase())
  if (!perdeEm.length) return base

  return `${base} ${pior.rotulo} é o pior: fica atrás em ${enumerar(perdeEm)}.`
}

/**
 * "a", "a e b", "a, b e c" — a enumeracao em portugues, com LISTA VAZIA tratada.
 *
 * Estava escrita duas vezes inline e as duas quebravam no vazio: `[].slice(0, -1)` da'
 * `''` e `lista[-1]` da' `undefined`, entao a frase saia com " e undefined" no meio —
 * dentro do PDF que vai ao locador. Uma funcao so', e o vazio devolve string vazia para
 * quem chama decidir (os dois chamadores checam antes).
 */
function enumerar(itens: readonly string[]): string {
  if (!itens.length) return ''
  if (itens.length === 1) return itens[0]
  return `${itens.slice(0, -1).join(', ')} e ${itens[itens.length - 1]}`
}
