/**
 * Leituras da ficha da unidade no mapa — a parte PURA (2026-10-01).
 *
 * A janela (`components/FichaUnidadeNoMapa.tsx`) so' desenha; o que cada concorrente
 * "oferece" e em que agregador ele esta' e' decidido aqui, testavel sem DOM, pelo mesmo
 * motivo de `lib/inicio.ts`.
 */

import { distanciaMetros, type Coord } from './medicao'
import type {
  RedeComodidadeItem,
  RedeComodidadesCanal,
  RedeMapaConcorrente,
  RedeUnidade,
} from './types'

/** A unidade cuja ficha o mapa abre em janela: o id busca os dados, o nome e' o titulo. */
export interface UnidadeNoMapa {
  id: string
  nome: string
}

/**
 * As unidades da rede NAQUELE estado, por nome — o que o seletor do mapa lista.
 *
 * Por nome e nao pela prioridade com que a carteira chega: aqui a pergunta e' "onde esta'
 * a unidade X", a mesma do passo de unidade do Inicio.
 */
export function unidadesDaUf(unidades: readonly RedeUnidade[], uf: string): RedeUnidade[] {
  const alvo = uf.trim().toUpperCase()
  if (!alvo) return []
  return unidades
    .filter((u) => (u.uf ?? '').trim().toUpperCase() === alvo)
    .sort((a, b) => a.nome.localeCompare(b.nome, 'pt-BR'))
}

/**
 * Distancia maxima entre o pin da Ultra no mapa e a coordenada da unidade na carteira para
 * as duas serem a MESMA unidade. As duas saem do mesmo cadastro, entao o normal e' 0 m; a
 * folga cobre a coordenada corrigida a mao no backend (`_EXEC_COORD_CORRIGIDA`), sem chegar
 * perto da distancia minima entre duas unidades da rede (1 km, `DIST_MIN_ULTRA_KM`).
 */
export const TOLERANCIA_PIN_UNIDADE_M = 150

/**
 * Qual unidade da rede e' este pin do mapa. O pin nao tem id — so' ponto e nome —, entao o
 * casamento e' pelo PONTO: a unidade mais proxima dentro da tolerancia. Sem par devolve
 * `null`: o mapa desenha unidades que ainda nao estao na base da rede, e para elas nao ha'
 * ficha a abrir.
 */
export function unidadeDoPin(
  pin: Coord,
  unidades: readonly RedeUnidade[],
  toleranciaM: number = TOLERANCIA_PIN_UNIDADE_M,
): RedeUnidade | null {
  let melhor: RedeUnidade | null = null
  let menor = Infinity
  for (const u of unidades) {
    if (u.lat == null || u.lng == null) continue
    const d = distanciaMetros(pin, { lat: u.lat, lng: u.lng })
    if (d <= toleranciaM && d < menor) {
      melhor = u
      menor = d
    }
  }
  return melhor
}

/** Camada de LABEL dos itens (CLAUDE.md §2): o valor bruto nao tem acento, o rotulo tem. */
export const ROTULO_COMODIDADE: Readonly<Record<RedeComodidadeItem, string>> = Object.freeze({
  musculacao: 'Musculação',
  luta: 'Lutas',
  armario: 'Armário',
  chuveiro: 'Chuveiro',
  vestiario: 'Vestiário',
  massagem: 'Massagem',
  cadeira_massagem: 'Cadeira de massagem',
})

/** Ordem em que os itens aparecem — a do coletor. */
export const ORDEM_COMODIDADES = Object.freeze(
  Object.keys(ROTULO_COMODIDADE) as RedeComodidadeItem[],
)

/** Rotulo da fonte de um canal, como o operador a conhece. */
export const ROTULO_FONTE: Readonly<Record<string, string>> = Object.freeze({
  site: 'Site da rede',
  wellhub: 'Wellhub',
  totalpass: 'TotalPass',
})

/**
 * Os tres estados que a tela NAO pode confundir:
 *   `indisponivel`  a base de comodidades nao foi ingerida (ou o backend e' anterior a ela)
 *   `nao_coletada`  a base existe, esta academia nao esta' nela
 *   `coletada`      ao menos um canal declarou algo
 */
export type EstadoComodidades = 'indisponivel' | 'nao_coletada' | 'coletada'

export function estadoDasComodidades(
  c: Pick<RedeMapaConcorrente, 'comodidades'>,
): EstadoComodidades {
  if (c.comodidades == null) return 'indisponivel'
  return c.comodidades.recorrente || c.comodidades.agregador ? 'coletada' : 'nao_coletada'
}

/** Itens DECLARADOS por um canal, ja' rotulados e na ordem do coletor. */
export function itensDeclarados(canal: RedeComodidadesCanal | null | undefined): string[] {
  if (!canal) return []
  return ORDEM_COMODIDADES.filter((item) => canal.itens?.[item] === true).map(
    (item) => ROTULO_COMODIDADE[item],
  )
}

/**
 * As MODALIDADES que um canal declara (musculacao, lutas, danca...), no texto e na ordem da
 * fonte. E' texto livre do agregador, sem lista fixa: so' sai o vazio e a repeticao (que a
 * fonte escreve com caixa diferente). Lista vazia e' "nao declarado" — o site das redes nao
 * publica modalidade, e payload de backend anterior nem traz a chave.
 */
export function modalidadesDoCanal(canal: RedeComodidadesCanal | null | undefined): string[] {
  const vistas = new Set<string>()
  const saida: string[] = []
  for (const bruta of canal?.atividades ?? []) {
    const texto = bruta.trim()
    const chave = texto.toLocaleLowerCase('pt-BR')
    if (!texto || vistas.has(chave)) continue
    vistas.add(chave)
    saida.push(texto)
  }
  return saida
}

export interface PlanoNoAgregador {
  /** Valor bruto do agregador. */
  agregador: 'wellhub' | 'totalpass'
  rotulo: string
  plano: string
  preco: number | null
}

/**
 * Em que agregadores a academia esta', com o plano exigido e o preco dele.
 *
 * So' entra agregador com PLANO casado: sem par a academia pode simplesmente nao estar no
 * app, e a tela diz "sem plano identificado" em vez de afirmar que ela nao aceita.
 */
export function planosDoConcorrente(c: RedeMapaConcorrente): PlanoNoAgregador[] {
  const planos: PlanoNoAgregador[] = []
  /* `agregadores` e' a leitura mais completa (acha o plano tambem pela listagem da mesma
     rede, quando o pino do app diverge do nosso). As chaves soltas abaixo ficam como
     fallback para payload de backend anterior a ela. */
  if (c.agregadores) {
    for (const agregador of ['wellhub', 'totalpass'] as const) {
      const bloco = c.agregadores[agregador]
      if (bloco?.plano) {
        planos.push({
          agregador,
          rotulo: ROTULO_FONTE[agregador],
          plano: bloco.plano,
          preco: bloco.preco ?? null,
        })
      }
    }
    return planos
  }
  if (c.plano_wellhub) {
    planos.push({
      agregador: 'wellhub',
      rotulo: ROTULO_FONTE.wellhub,
      plano: c.plano_wellhub,
      preco: c.preco_plano_wellhub ?? null,
    })
  }
  if (c.plano) {
    planos.push({
      agregador: 'totalpass',
      rotulo: ROTULO_FONTE.totalpass,
      plano: c.plano,
      preco: c.preco_plano ?? null,
    })
  }
  return planos
}

/** Nome de exibicao: o da academia; sem ele, a rede; sem os dois, o generico. */
export function nomeDoConcorrente(c: Pick<RedeMapaConcorrente, 'nome' | 'rede'>): string {
  return (c.nome ?? '').trim() || (c.rede ?? '').trim() || 'Academia sem nome na base'
}
