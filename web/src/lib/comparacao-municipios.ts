/**
 * Comparacao entre MUNICIPIOS, na visao de estado.
 *
 * DE ONDE VEM O NUMERO. Nao de agregacao no cliente. O payload traz `hexes`, e somar
 * por municipio ali seria tentador — mas esse array e' um RECORTE (em GO, 15.049 de
 * 59.954 hexes). Um total calculado sobre a amostra nao bateria com a fila que o
 * servidor mostra ao lado, e numero que se contradiz na mesma tela e' pior que numero
 * ausente. Entao cada dimensao le o `valor` que o proprio servidor ja calculou para
 * aquele municipio, no passo correspondente do funil.
 *
 * O QUE CADA PASSO ENTREGA (medido no payload real de GO):
 *   1 'Potencial socioeconomico' -> `valor` = hexagonos quentes (label "hexágonos")
 *   2 'Demanda nao atendida'     -> `valor` = residual bruto, em alunos
 *   3 'Pressao concorrencial'    -> `valor` = residual do que comporta entrada
 *   4 'Como as cidades estao indo'-> `valor` = % de emprego (CAGED)
 *   5 'Para onde crescer'        -> `valor` = indice de praca da fila (0-100, DEC-041) —
 *                                   so' no payload SEM o Top 10 (AR). Com a recomendacao
 *                                   unica o passo 5 e' de HEXAGONOS: ver MODO LEITURA abaixo.
 *
 * CRESCIMENTO SO' CONTRA MARGEM ESTADUAL. O passo 4 traz o % de emprego cru. Compara-lo
 * aqui e' legitimo porque os dois municipios sao da MESMA UF — e' leitura estadual, nao
 * nacional (regra do Juan, 2026-08-07). A dimensao le o desvio para `uf_mediana`, e nao
 * o numero solto, para deixar isso explicito no proprio dado.
 *
 * Municipio que nao aparece num passo simplesmente nao tem aquela dimensao: `null`, que
 * o nucleo ja trata como "nao comparavel" em vez de zero.
 */

import { compararDimensoesComFrase, type Comparacao, type Dimensao } from './comparacao'
import { valorComUnidade } from './format'
import { lerCrescimento, type CrescimentoMunicipio } from './oportunidades'
import type { Passo } from './types'

/** Um municipio, ja montado a partir dos passos do funil. */
export interface MunicipioComparavel {
  nome: string
  /** `valor` do municipio em cada passo, chaveado pelo `n` do passo. */
  porPasso: Record<number, number | null>
  crescimento: CrescimentoMunicipio | null
}

/**
 * Monta o municipio a partir do payload. Le SO' o que o servidor calculou.
 */
export function montarMunicipio(
  nome: string,
  passos: readonly Passo[],
  cresMun: Record<string, CrescimentoMunicipio> | null | undefined,
): MunicipioComparavel {
  const porPasso: Record<number, number | null> = {}
  for (const p of passos) {
    const item = p.itens.find((it) => (it.titulo ?? it.municipio) === nome)
    porPasso[p.n] = item?.valor ?? null
  }
  return { nome, porPasso, crescimento: cresMun?.[nome] ?? null }
}

/**
 * Municipios que aparecem em ao menos um passo — os unicos comparaveis.
 *
 * Ordenado por `localeCompare('pt-BR')`, e nao pelo `sort()` padrao: aquele compara
 * por code-unit e poe "Goianesia" antes de "Goiania" (o 'a' cru vem antes do 'a'
 * circunflexo). Numa lista de nomes acentuados isso le como bug de ordenacao.
 */
export function municipiosDisponiveis(passos: readonly Passo[]): string[] {
  const vistos = new Set<string>()
  for (const p of passos) {
    for (const it of p.itens) {
      const nome = it.titulo ?? it.municipio
      if (nome) vistos.add(nome)
    }
  }
  return [...vistos].sort((a, b) => a.localeCompare(b, 'pt-BR'))
}

/**
 * Dimensoes do municipio, na mesma ordem de prioridade dos hexagonos: residual
 * primeiro (a pergunta do produto), contexto por ultimo.
 */
export const DIMENSOES_MUNICIPIO: readonly Dimensao<MunicipioComparavel>[] = Object.freeze([
  Object.freeze({
    chave: 'residual_fila',
    rotulo: 'Residual na fila',
    ler: (m: MunicipioComparavel) => m.porPasso[5] ?? null,
    unidade: 'alunos',
    maiorEhMelhor: true,
    limiarRelativo: 0.1,
    limiarAbsoluto: 500,
  }),
  Object.freeze({
    chave: 'residual_bruto',
    rotulo: 'Demanda não atendida',
    ler: (m: MunicipioComparavel) => m.porPasso[2] ?? null,
    unidade: 'alunos',
    maiorEhMelhor: true,
    limiarRelativo: 0.1,
    limiarAbsoluto: 500,
  }),
  Object.freeze({
    chave: 'hexes_quentes',
    rotulo: 'Áreas de alto potencial',
    ler: (m: MunicipioComparavel) => m.porPasso[1] ?? null,
    unidade: '',
    maiorEhMelhor: true,
    limiarRelativo: 0.1,
    // Contagem pequena: 3 contra 4 hexagonos nao sustenta uma frase.
    limiarAbsoluto: 2,
  }),
  Object.freeze({
    chave: 'cres_vs_mediana',
    rotulo: 'Crescimento vs. mediana do estado',
    /* O DESVIO, nao o numero cru. Comparar "8,7%" com "22%" sem ancorar na mediana
       convidaria a ler o CAGED como grandeza absoluta — e ele so' vale contra uma
       margem estadual ou municipal. */
    ler: (m: MunicipioComparavel) => lerCrescimento(m.crescimento).delta,
    unidade: 'p.p.',
    maiorEhMelhor: true,
    limiarRelativo: 0.1,
    limiarAbsoluto: 1,
  }),
])

export function compararMunicipios(
  a: MunicipioComparavel,
  b: MunicipioComparavel,
): Comparacao<MunicipioComparavel> {
  return compararDimensoesComFrase(DIMENSOES_MUNICIPIO, a, b, a.nome, b.nome)
}

/* ---------------------------------------------------------------------------------------
   MODO LEITURA (recomendação única, DEC-077).

   Com o Top 10, o passo 5 deixou de ser uma fila de MUNICÍPIOS: os itens dele são
   hexágonos (com `municipio` preenchido só para o drill-down), e o `valor` é o residual ou
   a população de UM hexágono. Lido como número da cidade, ele atribuiria a um hexágono o
   peso do município inteiro — e os nomes de bairro entrariam na lista de "cidades". Por isso
   o modo leitura ignora o passo 5, tira a dimensão "Residual na fila" e devolve os números
   lado a lado, SEM vencedor nem perdedor: as camadas 1 a 4 são leitura, não recomendação.

   O legado (`DIMENSOES_MUNICIPIO`, `montarMunicipio`, `municipiosDisponiveis`,
   `compararMunicipios`) fica intacto: é o que a instância sem régua (AR) continua usando.
   --------------------------------------------------------------------------------------- */

/** Os passos que o comparador lê no modo leitura: tudo menos o Top 10 (passo 5). */
export function passosDeLeitura<P extends Pick<Passo, 'n'>>(passos: readonly P[]): P[] {
  return passos.filter((p) => p.n !== 5)
}

/** As dimensões do modo leitura: as de sempre, menos a que lia o passo 5. */
export const DIMENSOES_MUNICIPIO_LEITURA: readonly Dimensao<MunicipioComparavel>[] = Object.freeze(
  DIMENSOES_MUNICIPIO.filter((d) => d.chave !== 'residual_fila'),
)

/** Uma linha da tabela descritiva: o rótulo e o valor de cada cidade, já formatado. */
export interface LinhaLadoALado {
  chave: string
  rotulo: string
  unidade: string
  /** Um valor por município, na ordem em que foram escolhidos. */
  valores: string[]
}

/**
 * Os números lado a lado, sem ranquear: nenhuma marca de melhor ou pior, nenhum "lidera em
 * N/M", nenhuma frase. Dimensão que nenhum dos municípios tem fica de fora (linha vazia não
 * informa nada); quem não tem o valor aparece com o texto de "sem dado", nunca zero.
 */
export function linhasLadoALado(
  dimensoes: readonly Dimensao<MunicipioComparavel>[],
  municipios: readonly MunicipioComparavel[],
): LinhaLadoALado[] {
  const linhas: LinhaLadoALado[] = []
  for (const d of dimensoes) {
    const brutos = municipios.map((m) => d.ler(m))
    if (!brutos.some((v) => v != null)) continue
    linhas.push({
      chave: d.chave,
      rotulo: d.rotulo,
      unidade: d.unidade,
      valores: brutos.map((v) => valorComUnidade(v, d.unidade)),
    })
  }
  return linhas
}
