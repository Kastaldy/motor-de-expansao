/** Contrato entre o front e o backend do piloto (web/server/app.py). */

export type Tom = 'blue' | 'green' | 'amber' | 'red' | 'gray'

export interface Hex {
  id: string
  lat: number
  lng: number
  /** score_priorizacao — camada executiva M1 */
  m1: number | null
  /** score_setor_2022_calibrado — camada censitaria (primaria no dia a dia) */
  censo: number | null
  /** score_expansao_hibrido */
  hib: number | null
  /** score_oportunidade_residual */
  res: number | null
  /** oferta_efetiva_disponivel, em alunos */
  oferta: number | null
  /** sam_fitness_potencial, em alunos */
  sam: number | null
  pop: number | null
  /** renda per capita (R$/mes) */
  renda: number | null
  /** renda media domiciliar (R$/mes) = renda per capita x fator municipal */
  renda_dom: number | null
  /** rotulo da faixa de oportunidade M1 (ex.: "Alta") */
  faixa: string | null
  conc: number
  ultra: number
}

export interface RankItem {
  rank: number
  hex_id: string
  titulo: string
  sub: string | null
  valor: number | null
  label: string
  /** Rótulo curto que muda entre linhas (Quente / White space / Agora…). */
  tag: string
  tom: Tom
}

export interface Passo {
  n: 1 | 2 | 3 | 4
  mode: string
  titulo: string
  narrativa: string
  funil_big: number
  funil_unit: string
  funil_from: string
  metrica: string
  itens: RankItem[]
  hexes: string[]
}

export interface Resumo {
  residual_total: number | null
  pop_total: number | null
  score_m1_medio: number | null
  n_concorrentes: number
  n_ultra: number
  espaco_academias: number
}

/** Pin de mapa (concorrente ou Ultra). `rede`/`label` só em concorrentes. */
export interface Pin {
  lat: number
  lng: number
  rede?: string
  label?: string
  nome: string
}

/** Pins do município + ícones quadrados por rede (data URI SVG). */
export interface Pins {
  concorrentes: Pin[]
  ultra: Pin[]
  icones: Record<string, string>
}

export interface MunicipioPayload {
  uf: string
  municipio: string
  n_hex_total: number
  n_hex_mapa: number
  centro: { lat: number | null; lng: number | null }
  resumo: Resumo
  passos: Passo[]
  hexes: Hex[]
  pins: Pins
}

export interface MunicipioItem {
  nome: string
  n_hex: number
  residual: number | null
  score: number | null
}

/** Viabilidade — a demanda e PREMISSA do operador, nunca prevista (DEC-009). */
export interface ViabilidadeIn {
  lat: number
  lng: number
  m2: number
  aluguel: number
  demanda: number
  ticket?: number
  formato?: string
  /** CAPEX opcional; sem valor, o motor usa o default (R$ 2,34M). */
  capex?: number
  capex_financiado_pct?: number
  capex_parcelas_meses?: number
  /** Meses iniciais sem pagar aluguel (beneficio de rampa; melhora payback/FCF). */
  carencia_aluguel_meses?: number
}

/** Ponto da serie mensal de fluxo de caixa acumulado. */
export interface FcfPonto {
  mes: number
  fcf: number | null
}

/** Faixa de alunos por metragem (curva tamanho->densidade), independe da demanda. */
export interface FaixaAlunos {
  p10: number | null
  p50: number | null
  p90: number | null
  n_comparaveis: number
}

export interface Dre {
  faturamento: number | null
  deducoes: number | null
  impostos: number | null
  custos: number | null
  ebitda: number | null
  margem: number | null
  payback: number | null
  roic: number | null
}

export interface ViabilidadeOut {
  demanda_premissa: number
  demanda_fonte: string
  faixa_alunos: {
    p10: number | null
    p50: number | null
    p90: number | null
    n_comparaveis: number | null
  }
  alunos_breakeven: number | null
  alunos_para_margem_alvo: number | null
  aluguel_teto: number | null
  flag_fora_envelope: boolean
  flag_zona_morta: boolean | null
  motivo_zona_morta: string | null
  split: { balcao: number | null; agregadores: number | null }
  dre: Dre
  fcf_serie: FcfPonto[]
  carencia_aluguel_meses: number
  grade: Record<string, unknown>[]
}

/** Campos opcionais do imovel que enriquecem o PDF do Relatorio Pontual. */
export interface InfoImovel {
  nome?: string
  valor_venda?: string
  pe_direito?: string
  vagas?: string
  tipo?: string
  observacoes?: string
}
