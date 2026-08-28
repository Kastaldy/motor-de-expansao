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
 * dimensoes, e uma delas (predios, por satelite) so' cobre 12 UFs — entao ele mistura
 * numa etiqueta so' dimensoes com coberturas diferentes. `cres_emp_pct` (aqui `emp`)
 * e' uma leitura unica, do CAGED, e o que ela significa fica explicito.
 *
 * O CAGED SO' VALE CONTRA UMA MARGEM ESTADUAL OU MUNICIPAL, NUNCA NACIONAL.
 * (regra do Juan, 2026-08-07.) O numero cru de crescimento do emprego nao diz nada
 * sozinho: 8,7% e' muito ou pouco dependendo do estado e do ano. Toda leitura daqui
 * e' RELATIVA — `emp` contra `uf_mediana`, a mediana da propria UF. Sem essa
 * referencia, `lerCrescimento` NAO classifica e NAO mostra o numero: devolve
 * `sem-referencia`, porque exibir "8,7%" solto convida a comparar municipio de
 * estados diferentes, que e' exatamente a leitura nacional que a regra proibe.
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

/**
 * `sem-dado` = o municipio nao tem medicao de emprego.
 * `sem-referencia` = ha o numero, mas nao ha margem estadual/municipal contra a qual
 *   le-lo. Sao coisas diferentes e a tela precisa dizer qual das duas e'.
 */
export type ClasseCrescimento =
  | 'acima'
  | 'na-mediana'
  | 'abaixo'
  | 'sem-dado'
  | 'sem-referencia'

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
    /* Ha o numero, mas nao ha margem estadual para le-lo. NAO exibir o valor cru:
       "8,7%" solto e' um numero sem escala, e duas cidades de UFs diferentes lado a
       lado convidariam a comparacao NACIONAL que a regra proibe. O campo `valor`
       segue preenchido para auditoria; quem desenha e' que nao deve mostra-lo. */
    return {
      classe: 'sem-referencia',
      rotulo: 'Sem mediana estadual para comparar',
      valor,
      delta: null,
    }
  }

  const delta = valor - mediana
  if (Math.abs(delta) < MARGEM_MEDIANA_PP) {
    return { classe: 'na-mediana', rotulo: 'Na mediana do estado', valor, delta }
  }
  return delta > 0
    ? { classe: 'acima', rotulo: 'Cresce acima da mediana', valor, delta }
    : { classe: 'abaixo', rotulo: 'Cresce abaixo da mediana', valor, delta }
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
  if (c.classe === 'sem-referencia')
    return `${base} Há medição de emprego, mas sem mediana estadual para comparar.`
  return `${base} Sem medição de crescimento para a cidade.`
}

/**
 * UFs com cobertura de satelite na camada de crescimento POR HEXAGONO.
 *
 * Fora destas, `cres_hex_classe` vem vazio e os hexagonos acendem CINZA no passo 4.
 * Nao e' defeito, e' ausencia de dado — e sem aviso explicito vira chamado.
 *
 * Esta lista e' de OUTRA camada e nao tem relacao com `emp` (CAGED): satelite colore
 * o hexagono, CAGED mede o emprego do municipio. Nem por isso o CAGED vira leitura
 * nacional — ele continua so' valendo contra a mediana da propria UF.
 */
export const UFS_COM_SATELITE: readonly string[] = Object.freeze([
  'BA', 'CE', 'DF', 'ES', 'GO', 'MG', 'PE', 'PR', 'RJ', 'RS', 'SC', 'SP',
])

export function temCoberturaSatelite(uf: string | null | undefined): boolean {
  return !!uf && UFS_COM_SATELITE.includes(uf.toUpperCase())
}


/**
 * Um item do ranking nacional vira DESTINO no mapa — ou `null` quando não pode.
 *
 * POR QUE ISTO É UMA REGRA, E NÃO UM `onClick`. O "Ver no mapa" da lista levava só ao
 * MUNICÍPIO do hexágono: o operador escolhia um ponto específico no ranking e chegava
 * numa cidade inteira, tendo de reencontrar a olho o que acabara de escolher. Levar o
 * pin junto é o que faz o `MapScreen` amarrar as três leituras que ele já sabe amarrar
 * — a câmera voa até a coordenada, o hexágono ganha o contorno de seleção, e a ficha
 * dele abre.
 *
 * POR QUE PODE DEVOLVER `null`. O backend declara `uf`, `municipio`, `lat` e `lng` como
 * ANULÁVEIS: a coluna pode não existir na partição, e o `_num` do servidor devolve
 * `None` para NaN em vez de propagar o NaN. Um pin com coordenada ausente não erra — ele
 * leva a câmera para o meio do oceano em silêncio, que é pior. Sem os quatro campos, o
 * item não é navegável e quem chama deve desligar o botão.
 *
 * Mora aqui, e não no `.tsx`, pela mesma razão de `lib/inicio.ts`: o vitest do piloto
 * roda em ambiente `node` e só casa `src/**\/*.test.ts`. Regra em `lib/` é regra testável.
 */
export interface DestinoHex {
  uf: string
  municipio: string
  pin: { lat: number; lng: number; hexId: string }
}

export function destinoDoHex(h: {
  uf: string | null
  municipio: string | null
  lat: number | null
  lng: number | null
  hex_id: string
}): DestinoHex | null {
  if (!h.uf || !h.municipio || !h.hex_id) return null
  if (h.lat === null || h.lng === null) return null
  if (!Number.isFinite(h.lat) || !Number.isFinite(h.lng)) return null
  return {
    uf: h.uf,
    municipio: h.municipio,
    pin: { lat: h.lat, lng: h.lng, hexId: h.hex_id },
  }
}
