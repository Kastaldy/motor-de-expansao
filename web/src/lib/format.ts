/** Formatacao do PAIS DA INSTANCIA. Todo numero exibido passa por aqui.
 *
 *  O locale e o simbolo de moeda saem do perfil (Bloco A / DEC-047). Ate 2026-09-02
 *  eram 'pt-BR' e 'R$' cravados — oito literais so neste arquivo. */

import { TEXTO_SEM_DADO } from './constants'
import { moeda, moedaRenda, perfilDoCliente } from './perfil'

// Sem memo por locale de proposito: `perfilDoCliente()` e um acesso a variavel de
// modulo, e `Intl.NumberFormat` ja e barato o bastante para o volume desta tela.
const nf = (casas: number) =>
  new Intl.NumberFormat(perfilDoCliente().locale, {
    minimumFractionDigits: casas,
    maximumFractionDigits: casas,
  })

/** Numero inteiro com separador de milhar. `null` vira TEXTO_SEM_DADO, nunca "0". */
export function num(v: number | null | undefined, casas = 0): string {
  if (v === null || v === undefined || Number.isNaN(v)) return TEXTO_SEM_DADO
  return nf(casas).format(v)
}

/**
 * Distancia em metros -> texto curto, com a unidade que o leitor usaria.
 *
 * Abaixo de 1 km em metros arredondados (`850 m`); daí para cima em quilometros com 2 casas
 * (`1,05 km`). O corte e' de LEITURA, nao de precisao: "1.047 m" obriga a converter de cabeca
 * para saber se e' perto, e a pergunta que esta distancia responde e' exatamente essa.
 */
export function distanciaCurta(v: number | null | undefined): string {
  if (v === null || v === undefined || Number.isNaN(v)) return TEXTO_SEM_DADO
  if (v < 1000) return `${nf(0).format(Math.round(v))} m`
  return `${nf(2).format(v / 1000)} km`
}

/**
 * Reais. `compacto` usa mil/mi para caber em card estreito; `casas` serve para
 * valores em que o centavo importa (ticket: R$ 88,20 e nao R$ 88).
 */
export function brl(v: number | null | undefined, compacto = false, casas = 0): string {
  if (v === null || v === undefined || Number.isNaN(v)) return TEXTO_SEM_DADO
  if (compacto) {
    const abs = Math.abs(v)
    if (abs >= 1_000_000) return `${moeda()} ${nf(1).format(v / 1_000_000)} mi`
    if (abs >= 1_000) return `${moeda()} ${nf(0).format(v / 1_000)} mil`
  }
  return `${moeda()} ${nf(casas).format(v)}`
}

/**
 * Valor de RENDA — nunca `brl()`. Mesma forma de `brl()`, mas com o simbolo de
 * `moedaRenda()` em vez de `moeda()`.
 *
 * A distincao existe porque a coluna de renda do pacote (`renda_estimada_usd` /
 * `renda_per_capita`) pode estar numa moeda DIFERENTE da moeda oficial do pais — a
 * Argentina reporta renda em USD com moeda oficial ARS. `brl()` imprimiria "$ 508" (o
 * simbolo do peso) para um numero que sao 508 DOLARES; esta funcao imprime "USD 508".
 * No Brasil as duas moedas coincidem e o resultado e' identico ao de `brl()`.
 */
export function renda(v: number | null | undefined, compacto = false, casas = 0): string {
  if (v === null || v === undefined || Number.isNaN(v)) return TEXTO_SEM_DADO
  if (compacto) {
    const abs = Math.abs(v)
    if (abs >= 1_000_000) return `${moedaRenda()} ${nf(1).format(v / 1_000_000)} mi`
    if (abs >= 1_000) return `${moedaRenda()} ${nf(0).format(v / 1_000)} mil`
  }
  return `${moedaRenda()} ${nf(casas).format(v)}`
}

/**
 * Reais em notacao CURTA: "R$ 38k", "R$ 2,2M". Para readout de sidebar, onde o valor
 * tem de caber numa linha so — mais enxuto que `brl(v, true)`, que escreve "mil"/"mi"
 * por extenso e quebrava a linha no bloco de investimento.
 */
export function brlCurto(v: number | null | undefined): string {
  if (v === null || v === undefined || Number.isNaN(v)) return TEXTO_SEM_DADO
  const abs = Math.abs(v)
  if (abs >= 1_000_000) return `${moeda()} ${nf(abs >= 10_000_000 ? 0 : 1).format(v / 1_000_000)}M`
  if (abs >= 1_000) return `${moeda()} ${nf(0).format(v / 1_000)}k`
  return `${moeda()} ${nf(0).format(v)}`
}

export function pct(v: number | null | undefined, casas = 1): string {
  if (v === null || v === undefined || Number.isNaN(v)) return TEXTO_SEM_DADO
  return `${nf(casas).format(v)}%`
}

/**
 * Percentual a partir de uma FRACAO — a unidade em que o motor entrega TODA taxa
 * (margem, retorno, TIR, reajuste, share). O x100 e RENDER, nao calculo: a tela
 * nao pode derivar numero financeiro (FIN-VIAB-01).
 */
export function pctFrac(v: number | null | undefined, casas = 1): string {
  if (v === null || v === undefined || !Number.isFinite(v)) return TEXTO_SEM_DADO
  return pct(v * 100, casas)
}

/**
 * Percentual de VARIACAO, com o sinal sempre explicito: `+8,8%`, `-3,1%`, `0,0%`.
 *
 * Existe porque `pct` serve a duas familias que se leem diferente. Numa PARTICIPACAO
 * (margem, share, conversao, mix) o valor e' um pedaco de um todo e o `+` viraria ruido —
 * "margem +18%" nao quer dizer nada. Numa VARIACAO (crescimento de emprego, obra nova,
 * desvio contra a media da rede) o sinal E' a informacao: sem ele, "8,8%" fica ambiguo,
 * porque o leitor nao sabe se a cidade CRESCEU 8,8% ou se aquilo e' um patamar.
 *
 * O negativo ja' vinha do `Intl`; o que faltava era tornar o positivo VISIVEL. Zero nao
 * recebe sinal — `+0,0%` afirmaria um crescimento que nao houve.
 *
 * Estava improvisado em dois lugares (`exec/FichaUnidade` e `exec/PainelRede`) com o mesmo
 * `v > 0 ? '+' : ''` colado a mao. Virou funcao para o terceiro caso nao repetir a conta
 * nem divergir na casa decimal.
 */
export function pctVar(v: number | null | undefined, casas = 1): string {
  if (v === null || v === undefined || !Number.isFinite(v)) return TEXTO_SEM_DADO
  return `${v > 0 ? '+' : ''}${pct(v, casas)}`
}

/**
 * Unidade "dinheiro" de uma `Dimensao`. Sentinela, e nao o simbolo: ate 2026-09-02 as
 * duas telas de comparacao cravavam `unidade: 'R$'` e o `valorComUnidade` comparava com
 * o literal — ou seja, o simbolo da moeda era ao mesmo tempo o VALOR exibido e a CHAVE
 * de despacho. Numa instancia com outra moeda os dois se separam, e comparar com o
 * simbolo passaria a nao casar em silencio, caindo no `num(v)` sem unidade nenhuma.
 *
 * IDENTIFICADOR, entao sem acento e nunca exibido (CLAUDE.md §2).
 */
export const UNIDADE_MOEDA = 'moeda'

/**
 * O valor de uma `Dimensao` na unidade dela.
 *
 * Vive aqui porque a comparacao passou a ter DOIS desenhos — a tabela A x B e os blocos
 * por parametro — e os dois precisam escrever o mesmo numero do mesmo jeito. Com a funcao
 * duplicada, a primeira mudanca de casa decimal faria as duas telas discordarem sobre o
 * mesmo dado.
 *
 * `p.p.` sai assinado: ponto percentual e' VARIACAO, e ali o sinal e' a informacao.
 */
export function valorComUnidade(v: number | null, unidade: string): string {
  if (v == null) return num(v)
  if (unidade === UNIDADE_MOEDA) return `${moeda()} ${num(v)}`
  if (unidade === '%') return `${num(v, 1)}%`
  if (unidade === 'p.p.') return `${pctVar(v, 1).replace('%', '')} p.p.`
  return num(v)
}

/**
 * Rotulo de um mes da linha do tempo do motor (M-4..M+60). Mes negativo e
 * pre-abertura (obra); a partir de 1 e operacao. Nao existe mes 0.
 */
export function rotuloMes(v: number | null | undefined): string {
  if (v === null || v === undefined || !Number.isFinite(v)) return TEXTO_SEM_DADO
  const m = Math.round(v)
  return m < 0 ? `M${m} (obra)` : `mês ${m}`
}

/** Coordenada no padrao pt-BR (virgula decimal), como o template mostra. */
export function coord(lat: number, lng: number): string {
  const f = nf(5)
  return `${f.format(lat)}, ${f.format(lng)}`
}

/** Alunos — a unidade de conta do residual e da demanda. */
export function alunos(v: number | null | undefined): string {
  if (v === null || v === undefined || Number.isNaN(v)) return TEXTO_SEM_DADO
  return nf(0).format(Math.round(v))
}
