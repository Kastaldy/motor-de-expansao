/**
 * A linha de procedência que aparece no pé das telas — derivada da BASE, não escrita à mão.
 *
 * O texto era fixo em três lugares: "27 estados · Censo 2022 (IBGE) + rede Ultra e
 * concorrentes mapeados · camada visual read-only". Servindo a Argentina, ele errava
 * três vezes na mesma frase (Juan, 2026-08-26):
 *
 *   "27 estados"    são 24 PROVÍNCIAS — e o número tem de vir da base, não de uma
 *                   constante, senão volta a mentir na próxima província que entrar.
 *   "IBGE"          o censo argentino é do INDEC. Creditar o instituto errado numa
 *                   linha de procedência é o pior lugar possível para um engano.
 *   "rede Ultra"    não existe rede na Argentina: o projeto é greenfield, e o
 *                   exportador crava `n_unidades_ultra = 0` de propósito ("zero é a
 *                   resposta CERTA, não dado faltando").
 *
 * A frase agora sai da lista de UFs que a tela já tem: o TAMANHO dela dá a contagem, e
 * `paisDaBase` dá o país. Sem contagem confiável não há frase — devolve `null` e quem
 * chama não desenha nada, em vez de anunciar "0 estados".
 */

import { paisDaBase } from './pais-da-base'

/** Como cada país nomeia a própria unidade federativa. O ARTIGO entra aqui, e não numa
 *  gambiarra de string mais adiante: "estado" é masculino e "província" é feminino, e
 *  isso é propriedade da palavra, não do lugar onde ela é usada. */
const UNIDADE = {
  BR: { um: 'estado', varios: 'estados', artigo: 'o', artigoPlural: 'os' },
  AR: { um: 'província', varios: 'províncias', artigo: 'a', artigoPlural: 'as' },
} as const

/** Quem publica o censo de cada base. */
const CENSO = { BR: 'Censo 2022 (IBGE)', AR: 'Censo 2022 (INDEC)' } as const

/** So a sigla do instituto. Tabela, e nao um ternario `pais === 'BR' ? ... : ...`,
 *  que era o que estava aqui ate 2026-09-02: com dois paises o ternario acerta por
 *  sorte, e no TERCEIRO a Colombia sairia creditando o INDEC. A DEC-047 proibe
 *  ramo de codigo por pais justamente por isso, e `test_fio_de_alarme_pais.py`
 *  passa a travar a volta. Acrescentar pais aqui e uma linha de dado. */
const INSTITUTO = { BR: 'IBGE', AR: 'INDEC' } as const

/**
 * O que a camada de pontos contém.
 *
 * A Argentina não tem unidade Ultra — prometer "rede Ultra" num mapa que não tem
 * nenhuma é a mesma classe de erro que creditar o IBGE pelo censo argentino.
 */
const PONTOS = {
  BR: 'rede Ultra e concorrentes mapeados',
  AR: 'concorrentes mapeados',
} as const

export function rodapeDaBase(ufs: readonly string[] | null | undefined): string | null {
  const n = ufs?.length ?? 0
  if (n === 0) return null

  const pais = paisDaBase(ufs)
  // País indefinido (base misturada, sigla nova): conta as unidades, que é fato, e cala
  // sobre censo e pontos, que dependem de saber o país. Meia frase certa vale mais que
  // uma frase inteira chutada.
  if (pais === null) {
    return `${n} unidades federativas · camada visual read-only`
  }

  const u = UNIDADE[pais]
  return `${n} ${n === 1 ? u.um : u.varios} · ${CENSO[pais]} + ${PONTOS[pais]} · camada visual read-only`
}

/** A mesma leitura, para a espera do ranking ("Comparando os N …"). */
export function nomeDasUnidades(ufs: readonly string[] | null | undefined): string {
  const n = ufs?.length ?? 0
  const pais = paisDaBase(ufs)
  if (n === 0 || pais === null) return 'as unidades federativas'
  const u = UNIDADE[pais]
  return n === 1 ? `${u.artigo} ${u.um}` : `${u.artigoPlural} ${n} ${u.varios}`
}

/**
 * O titulo da tela vazia do Explorar: "Escolha o estado" nao serve para a Argentina.
 *
 * Mesmo defeito do rodape, no lugar mais visivel da tela — e com concordancia de genero,
 * que e' propriedade da palavra (ver UNIDADE). Sem saber o pais, cai no termo neutro em
 * vez de escolher um dos dois.
 */
export function tituloEscolhaUnidade(ufs: readonly string[] | null | undefined): string {
  const pais = paisDaBase(ufs)
  if (pais === null) return 'Escolha a unidade federativa'
  const u = UNIDADE[pais]
  return `Escolha ${u.artigo} ${u.um}`
}

/**
 * Quem publica o censo desta base — para as fichas que citam a fonte no meio do texto.
 *
 * "Censo 2022 (IBGE)" aparecia fixo em seis lugares da interface. Servindo a Argentina,
 * todos creditavam o instituto errado: la' o censo e' do INDEC. Numa linha de
 * PROCEDENCIA, errar a fonte e' o pior engano possivel — e' exatamente o que ela existe
 * para garantir.
 *
 * `null` quando nao da' para afirmar: quem chama omite a nota em vez de chutar um
 * instituto.
 */
export function censoDaBase(ufs: readonly string[] | null | undefined): string | null {
  const pais = paisDaBase(ufs)
  return pais === null ? null : CENSO[pais]
}

/** So' a sigla do instituto ("IBGE" / "INDEC"), para compor frases proprias. */
export function institutoDoCenso(ufs: readonly string[] | null | undefined): string | null {
  const pais = paisDaBase(ufs)
  return pais === null ? null : INSTITUTO[pais]
}
