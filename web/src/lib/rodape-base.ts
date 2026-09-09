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
 * A frase sai de duas fontes, e desde 2026-09-02 elas são diferentes: o TAMANHO da lista
 * de UFs dá a contagem, e o PERFIL DA INSTÂNCIA dá o país. Sem contagem confiável não há
 * frase — devolve `null` e quem chama não desenha nada, em vez de anunciar "0 estados".
 *
 * O país vinha de `paisDaBase(ufs)`, que o deduzia por disjunção binária: todas as siglas
 * brasileiras → Brasil, nenhuma → Argentina. A dedução era boa no seu tempo e a docstring
 * dela dizia por quê — não havia canal do backend, e depender de variável de ambiente é
 * "o modo de falhar mais provável de um carimbo de identidade".
 *
 * Essa objeção morreu com o Bloco A (DEC-047): o país não é mais uma env que alguém
 * esquece de exportar, é um ARQUIVO sem o qual o container não sobe, e `/api/me` já o
 * entrega ao front. E a dedução tinha prazo de validade — com dois países ela acerta;
 * com a Colômbia entrando, "nenhuma sigla brasileira" passaria a carimbar Argentina.
 */

import { perfilDoCliente } from './perfil'

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

/** Sigla do país da instância, quando estas tabelas sabem falar dele.
 *
 * `null` = país sem vocabulário aqui. É o ÚNICO lugar do módulo que conhece o perfil, e
 * `PaisComVocabulario` é o tipo que garante, em compilação, que ninguém indexe `UNIDADE`,
 * `CENSO` ou `INSTITUTO` com uma sigla que elas não têm. */
type PaisComVocabulario = keyof typeof UNIDADE

function paisDoPerfil(): PaisComVocabulario | null {
  const pais = perfilDoCliente().pais
  return pais in UNIDADE ? (pais as PaisComVocabulario) : null
}

export function rodapeDaBase(ufs: readonly string[] | null | undefined): string | null {
  const n = ufs?.length ?? 0
  if (n === 0) return null

  const pais = paisDoPerfil()
  // País que ainda não tem vocabulário nestas tabelas (a Colômbia, quando entrar): conta
  // as unidades, que é fato, e cala sobre censo e pontos. Meia frase certa vale mais que
  // uma frase inteira chutada. O ramo é o mesmo de antes; o MOTIVO é melhor — era "não
  // sei o país", passou a ser "sei o país e ainda não traduzi a palavra dele".
  if (pais === null) {
    return `${n} unidades federativas · camada visual read-only`
  }

  const u = UNIDADE[pais]
  return `${n} ${n === 1 ? u.um : u.varios} · ${CENSO[pais]} + ${PONTOS[pais]} · camada visual read-only`
}

/** A mesma leitura, para a espera do ranking ("Comparando os N …"). */
export function nomeDasUnidades(ufs: readonly string[] | null | undefined): string {
  const n = ufs?.length ?? 0
  const pais = paisDoPerfil()
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
export function tituloEscolhaUnidade(): string {
  const pais = paisDoPerfil()
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
export function censoDaBase(): string | null {
  const pais = paisDoPerfil()
  return pais === null ? null : CENSO[pais]
}

/** So' a sigla do instituto ("IBGE" / "INDEC"), para compor frases proprias. */
export function institutoDoCenso(): string | null {
  const pais = paisDoPerfil()
  return pais === null ? null : INSTITUTO[pais]
}
