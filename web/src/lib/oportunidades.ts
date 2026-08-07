/**
 * Fila de oportunidades (passo 5) — crescimento como LEITURA, nunca como peso.
 *
 * A fila em si NAO e' calculada aqui. Ela ja' vem pronta do servidor, pela cascata
 * que roda em producao: potencial socioeconomico >= 70, populacao >= 5.000, residual
 * >= 2.000 e ZERO concorrente mapeado (white space), ordenada por
 * `oferta_efetiva_disponivel` decrescente. Criar score novo em cima do M1 exigiria
 * gate humano (CLAUDE.md §2) e o piloto e' "sem recalculo de score em runtime".
 *
 * O QUE ESTE MODULO ACRESCENTA e' a camada de CONTEXTO que faltava na tela: dizer,
 * para cada item da fila, como a cidade dele esta indo — e deixar filtrar por isso,
 * sem mexer na ordem que o motor entregou.
 *
 * POR QUE `emp` E NAO `v_classe`. O veredito `v_classe`/`v_frase` combina CINCO
 * dimensoes, e uma delas (predios, por satelite) so' cobre 12 UFs — entao ele NAO
 * tem cobertura nacional uniforme, ao contrario do que parece. `cres_emp_pct` (aqui
 * `emp`) vem do CAGED e cobre o pais inteiro. Numa fila que o operador usa para
 * decidir onde abrir, cobertura desigual e' pior que dado mais simples.
 */

/** O que `MapaResposta.cres_mun[municipio]` traz. Todos opcionais: municipio sem
 *  medicao simplesmente nao esta no dicionario. */
export interface CrescimentoMunicipio {
  /** Rotulo de tendencia ja pronto pelo servidor. */
  tend?: string | null
  /** Crescimento do emprego formal (%), CAGED. */
  emp?: number | null
  /** Mediana da UF, para posicionar `emp` sem o operador ter de saber a escala. */
  uf_mediana?: number | null
  empresas?: number | null
  salario?: number | null
  setor?: string | null
}

export type ClasseCrescimento = 'acima' | 'na-mediana' | 'abaixo' | 'sem-dado'

export interface LeituraCrescimento {
  classe: ClasseCrescimento
  /** Texto curto para etiqueta. Acentuado — e' texto de usuario. */
  rotulo: string
  /** `emp` em pontos percentuais. */
  valor: number | null
  /** Distancia para a mediana da UF, em pontos percentuais. */
  delta: number | null
}

/**
 * Faixa morta em torno da mediana, em pontos percentuais.
 *
 * Sem ela, 7,61% contra mediana 7,60% viraria "acima da mediana" — diferenca que
 * nao sustenta decisao nenhuma e que so' serviria para dar falsa precisao a uma
 * etiqueta que o operador vai ler como sinal.
 */
export const MARGEM_MEDIANA_PP = 0.5

export function lerCrescimento(c: CrescimentoMunicipio | null | undefined): LeituraCrescimento {
  const valor = c?.emp ?? null
  const mediana = c?.uf_mediana ?? null

  if (valor == null) {
    return { classe: 'sem-dado', rotulo: 'Sem medição de crescimento', valor: null, delta: null }
  }
  if (mediana == null) {
    // Ha o numero, mas nao ha contra o que compara-lo: mostrar o numero cru e' mais
    // honesto do que classificar sem referencia.
    return { classe: 'sem-dado', rotulo: `Emprego ${fmtPp(valor)}`, valor, delta: null }
  }

  const delta = valor - mediana
  if (Math.abs(delta) < MARGEM_MEDIANA_PP) {
    return { classe: 'na-mediana', rotulo: 'Na mediana do estado', valor, delta }
  }
  return delta > 0
    ? { classe: 'acima', rotulo: 'Cresce acima da mediana', valor, delta }
    : { classe: 'abaixo', rotulo: 'Cresce abaixo da mediana', valor, delta }
}

function fmtPp(v: number): string {
  // Ponto decimal do JS -> virgula do pt-BR. Texto de usuario.
  return `${v.toFixed(1).replace('.', ',')}%`
}

/** Item minimo da fila que este modulo precisa enxergar. */
export interface ItemFila {
  rank: number
  municipio?: string | null
  titulo?: string | null
  valor?: number | null
}

/**
 * Reordena APENAS o desempate.
 *
 * A chave primaria continua sendo `valor` (residual em alunos, do servidor). O
 * crescimento so' decide entre itens de residual IGUAL — ele nunca vira peso, nunca
 * reordena quem tem mais residual para baixo. Transformar contexto em componente de
 * ordenacao seria, na pratica, um score novo.
 */
export function ordenarComDesempate<T extends ItemFila>(
  itens: readonly T[],
  cresPorMunicipio: Record<string, CrescimentoMunicipio> | null | undefined,
): T[] {
  const crescimentoDe = (it: T) => {
    const c = cresPorMunicipio?.[it.municipio ?? it.titulo ?? '']
    return c?.emp ?? Number.NEGATIVE_INFINITY
  }
  return [...itens].sort((a, b) => {
    const dv = (b.valor ?? 0) - (a.valor ?? 0)
    if (dv !== 0) return dv
    const dc = crescimentoDe(b) - crescimentoDe(a)
    if (dc !== 0) return dc
    return a.rank - b.rank // ultimo criterio: preserva a ordem do servidor
  })
}

/** Filtro OPCIONAL: só cidades crescendo acima da mediana da UF. */
export function filtrarPorCrescimento<T extends ItemFila>(
  itens: readonly T[],
  cresPorMunicipio: Record<string, CrescimentoMunicipio> | null | undefined,
  somenteAcima: boolean,
): T[] {
  if (!somenteAcima) return [...itens]
  return itens.filter(
    (it) => lerCrescimento(cresPorMunicipio?.[it.municipio ?? it.titulo ?? '']).classe === 'acima',
  )
}

/**
 * Leitura de UM item da fila, deterministica.
 *
 * Diz o que o item JA' garante por estar na fila (residual, e zero concorrente
 * mapeado — a cascata do passo 5 so' aceita white space) e acrescenta o contexto de
 * crescimento. Nao promete o que o dado nao sustenta.
 */
export function leituraDoItem(
  item: ItemFila,
  cres: CrescimentoMunicipio | null | undefined,
): string {
  const nome = item.titulo ?? item.municipio ?? 'Este item'
  const residual =
    item.valor != null
      ? `${item.valor.toLocaleString('pt-BR')} alunos de residual`
      : 'residual acima do corte'

  const base = `${nome} entra com ${residual} e nenhum concorrente mapeado no recorte.`

  const c = lerCrescimento(cres)
  if (c.classe === 'acima') return `${base} A cidade cresce acima da mediana do estado.`
  if (c.classe === 'abaixo') return `${base} A cidade cresce abaixo da mediana do estado.`
  if (c.classe === 'na-mediana') return `${base} A cidade cresce na mediana do estado.`
  return `${base} Sem medição de crescimento para a cidade.`
}

/**
 * UFs com cobertura de satelite na camada de crescimento POR HEXAGONO.
 *
 * Fora destas, `cres_hex_classe` vem vazio e os hexagonos acendem CINZA no passo 4.
 * Nao e' defeito, e' ausencia de dado — e sem aviso explicito vira chamado. Esta
 * lista NAO afeta `emp` (CAGED), que e' nacional.
 */
export const UFS_COM_SATELITE: readonly string[] = Object.freeze([
  'BA', 'CE', 'DF', 'ES', 'GO', 'MG', 'PE', 'PR', 'RJ', 'RS', 'SC', 'SP',
])

export function temCoberturaSatelite(uf: string | null | undefined): boolean {
  return !!uf && UFS_COM_SATELITE.includes(uf.toUpperCase())
}
