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
 *   5 'Para onde crescer'        -> `valor` = indice de praca da fila (0-100, DEC-041)
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
