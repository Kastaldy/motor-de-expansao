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
  /** Presente na visão de UF: clicar no item filtra para este município (drill-down). */
  municipio?: string | null
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
  /** "uf" = visão de estado inteiro (recomenda municípios); "municipio" = drill-down. */
  nivel: 'uf' | 'municipio'
  uf: string
  municipio: string | null
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
  /** Numero de studios extras (0..3); cada studio adiciona R$6.000/mes de folha. */
  n_studios?: number
  /** Obra (CAPEX, equity): base do ROIC/payback; parcelada sem juros. */
  obra?: number
  /** Parcelas da obra em meses (default 4, sem juros). */
  parcelas_obra?: number
  /** Equipamentos (OPEX): financiado; a PMT entra abaixo do EBITDA. */
  equipamentos?: number
  /** Prazo do financiamento de equipamentos em meses (36–60). */
  prazo_equipamentos?: number
  /** Juros mensal do financiamento de equipamentos (fração, ex.: 0.018 = 1,8% a.m.). */
  juros_equipamentos_am?: number
  /** LEGADO (compat): CAPEX único; sem valor o motor usa o default (R$ 2,34M). */
  capex?: number
  capex_financiado_pct?: number
  capex_financiado_valor?: number
  juros_financiamento_am?: number
  capex_parcelas_meses?: number
  /** LEGADO: não dirige mais o aluguel-teto (agora por clusters); só alunos-para-alvo. */
  margem_alvo?: number
  /** Meses iniciais sem pagar aluguel (beneficio de rampa; melhora payback/FCF). */
  carencia_aluguel_meses?: number
  /** Meses de rampa de maturacao do balcao (Simulador E13; default do motor = 8). */
  rampa_meses?: number
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
  /** lucro liquido/mes = EBITDA - IR/CSLL (motor: simulador.lucro_liquido_mensal) */
  lucro_liquido: number | null
  /** margem EBITDA em PERCENTUAL (ex.: 34.57 = 34,57%). */
  margem: number | null
  payback: number | null
  /** ROIC anual desalavancado, em FRAÇÃO (ex.: 0.18 = 18%). */
  roic: number | null
  /** viável? (decidido pelo motor; usado pelo slide de viabilidade do PDF). */
  flag_viavel?: boolean
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
  /** Aluguel-teto por clusters (% do faturamento bruto steady). */
  aluguel_teto: AluguelTeto | null
  flag_fora_envelope: boolean
  flag_zona_morta: boolean | null
  motivo_zona_morta: string | null
  split: { balcao: number | null; agregadores: number | null }
  dre: Dre
  /** FCF acumulado do investimento (payback): parte de −Obra, 60 meses. */
  fcf_serie: FcfPonto[]
  /** Resultado operacional MÊS A MÊS (não acumulado): o caixa que a operação gera por mês. */
  fco_serie: FcfPonto[]
  /** Mês em que a operação passa a fechar no positivo e assim permanece; null se nunca vira. */
  mes_operacao_positiva: number | null
  carencia_aluguel_meses: number
  /** Sugestões de melhoria quando o payback estoura (> 40 meses); null se ok. */
  melhoria_payback: MelhoriaPayback | null
  grade: Record<string, unknown>[]
}

/** Aluguel-teto por clusters sobre o faturamento bruto steady (Ideal/Teto/Exceção). */
export interface AluguelTeto {
  /** 15% do faturamento — faixa saudável. */
  ideal: number | null
  /** 20% do faturamento — teto recomendado. */
  teto: number | null
  /** 30% do faturamento — exceção (máximo tolerável). */
  excecao: number | null
}

/** Quanto cortar de CAPEX ou de aluguel para o payback cair para ~alvo_meses. */
export interface MelhoriaPayback {
  alvo_meses: number
  /** R$ a reduzir do CAPEX (null se um corte só de CAPEX não bastar). */
  reduzir_capex: number | null
  /** R$/mês a reduzir do aluguel (null se um corte só de aluguel não bastar). */
  reduzir_aluguel: number | null
}

/* ---- Visão Executiva por estado (rede Ultra real, camada paralela) ---- */

export interface ExecUnidade {
  nome: string
  lat: number | null
  lng: number | null
  ativos: number | null
  pagantes: number | null
  agregadores: number | null
  faturamento: number | null
  /** churn em % (ex.: 2.79 = 2,79%) */
  churn: number | null
  ticket: number | null
  nps: number | null
  inauguracao: string
}

/** Métrica com comparação M-1 (mesmo dia do mês anterior). */
export interface ExecMetric {
  atual: number | null
  m1: number | null
  delta_pct: number | null
}

export interface ExecTotais {
  unidades: number
  com_coordenada: number
  faturamento: ExecMetric
  ativos: ExecMetric
  pagantes: ExecMetric
  agregadores: ExecMetric
  /** churn rolling 30 dias, em % */
  churn: ExecMetric
  ticket: ExecMetric
  nps: ExecMetric
  pct_pagantes: number | null
  pct_agregadores: number | null
}

export interface ExecutivaPayload {
  uf: string
  /** competência selecionada, ex.: "2026-06" */
  mes: string | null
  /** competências disponíveis (mais recentes primeiro), ex.: ["2026-06","2026-05",…] */
  meses: string[]
  /** dia de referência (MTD), ex.: "12/06/2026" */
  referencia: string | null
  /** mesmo dia do mês anterior, ex.: "12/05/2026" */
  referencia_m1: string | null
  centro: { lat: number | null; lng: number | null }
  /** bandeira quadrada da Ultra (data URI SVG) para o centro das bolhas do mapa. */
  ultra_icon: string | null
  totais: ExecTotais
  unidades: ExecUnidade[]
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
