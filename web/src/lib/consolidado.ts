/**
 * Quem aparece no topo de MAIS camadas — a leitura consolidada do funil.
 *
 * NAO E' UM SCORE NOVO, e isso e' o ponto. Somar ou ponderar as cinco camadas num
 * numero unico criaria uma sexta definicao de prioridade no sistema, em cima do M1 —
 * criticidade Alta pela regua do CLAUDE.md §2, e o piloto e' "sem recalculo de score
 * em runtime". O que se faz aqui e' CONTAR presencas: em quantas camadas a cidade
 * aparece no topo. Contagem e' auditavel a olho — o operador confere somando os
 * cartoes acima — e nao inventa peso nenhum entre camadas que medem coisas
 * diferentes (potencial, residual, concorrencia, crescimento).
 *
 * O DESEMPATE tambem nao e' novo: e' a posicao na FILA OFICIAL (passo 5), que ja e'
 * a recomendacao do motor. Cidade fora da fila desempata por tras, porque a fila e'
 * justamente o filtro de white space — estar fora dela significa que ha concorrente
 * mapeado, e isso pesa.
 */

import type { Passo, RankItem } from './types'

/** Quantos itens de cada camada entram na leitura. */
export const TOP_POR_CAMADA = 5

/** A camada em que a cidade apareceu, com a posicao que ela teve la. */
export interface PresencaCamada {
  n: number
  titulo: string
  posicao: number
  /** `valor` do item naquela camada, na unidade da camada. */
  valor: number | null
  rotuloMetrica: string
}

export interface CidadeConsolidada {
  nome: string
  presencas: PresencaCamada[]
  /** Posicao na fila oficial (passo 5). `null` = ficou de fora dela. */
  posicaoFila: number | null
}

function nomeDoItem(it: RankItem): string {
  return it.titulo ?? it.municipio ?? ''
}

/** Os `TOP_POR_CAMADA` primeiros de cada camada, na ordem que o servidor mandou. */
export function topPorCamada(passos: readonly Passo[]): { passo: Passo; itens: RankItem[] }[] {
  return passos.map((p) => ({ passo: p, itens: p.itens.slice(0, TOP_POR_CAMADA) }))
}

/**
 * Consolida: quem aparece no topo de mais camadas, desempatado pela fila oficial.
 *
 * `minPresencas` existe para a tela poder pedir "so quem aparece em 2 ou mais": uma
 * cidade que aparece numa camada so' nao e' uma leitura consolidada, e' um destaque
 * pontual — que ja esta visivel no cartao daquela camada.
 */
export function consolidar(
  passos: readonly Passo[],
  minPresencas = 2,
): CidadeConsolidada[] {
  const porCidade = new Map<string, CidadeConsolidada>()

  for (const { passo, itens } of topPorCamada(passos)) {
    itens.forEach((it, i) => {
      const nome = nomeDoItem(it)
      if (!nome) return
      const atual =
        porCidade.get(nome) ?? { nome, presencas: [], posicaoFila: null }
      atual.presencas.push({
        n: passo.n,
        titulo: passo.titulo,
        posicao: i + 1,
        valor: it.valor ?? null,
        rotuloMetrica: it.label ?? passo.metrica ?? '',
      })
      porCidade.set(nome, atual)
    })
  }

  // A fila oficial e o passo 5 — e ela vale INTEIRA no desempate, nao so o top 5.
  const fila = passos.find((p) => p.n === 5)
  if (fila) {
    fila.itens.forEach((it, i) => {
      const c = porCidade.get(nomeDoItem(it))
      if (c) c.posicaoFila = i + 1
    })
  }

  return [...porCidade.values()]
    .filter((c) => c.presencas.length >= minPresencas)
    .sort((a, b) => {
      const dp = b.presencas.length - a.presencas.length
      if (dp !== 0) return dp
      // Fora da fila vai para tras: estar fora dela significa concorrente mapeado.
      const fa = a.posicaoFila ?? Number.POSITIVE_INFINITY
      const fb = b.posicaoFila ?? Number.POSITIVE_INFINITY
      if (fa !== fb) return fa - fb
      // Ultimo criterio: a melhor colocacao que a cidade teve em qualquer camada.
      return melhorPosicao(a) - melhorPosicao(b)
    })
}

function melhorPosicao(c: CidadeConsolidada): number {
  return Math.min(...c.presencas.map((p) => p.posicao))
}

/**
 * Frase da leitura consolidada, deterministica.
 *
 * Diz EM QUANTAS e QUAIS camadas — sem isso "1º lugar" viraria um veredito sem
 * lastro, exatamente o score que este modulo se recusa a criar.
 */
export function fraseConsolidada(c: CidadeConsolidada, totalCamadas: number): string {
  const nomes = c.presencas.map((p) => p.titulo.toLowerCase())
  const lista =
    nomes.length === 1
      ? nomes[0]
      : `${nomes.slice(0, -1).join(', ')} e ${nomes[nomes.length - 1]}`

  const base = `Aparece no top ${TOP_POR_CAMADA} de ${c.presencas.length} das ${totalCamadas} camadas: ${lista}.`

  return c.posicaoFila != null
    ? `${base} É a ${c.posicaoFila}ª da fila de recomendação.`
    : `${base} Não entra na fila de recomendação — há concorrente mapeado no recorte.`
}
