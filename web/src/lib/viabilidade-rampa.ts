/* ---------------------------------------------------------------------------
   Viabilidade: a rampa de alunos (DEC-077, emenda de 21/10/2026).

   A tela tem UMA forma de rampa: a curva OBSERVADA nas unidades da rede (BLK-UNI-03) —
   o mês t tem uma fração da demanda madura, até 100% no PICO DE MATURAÇÃO. O operador
   escolhe o pico (o mês em que a unidade chega à demanda madura); o MOTOR reescala a
   mesma forma observada no tempo (`dimensionamento/simulador.py::curva_rampa_com_pico`).
   A tela não calcula a curva: lê o que o payload devolveu.

   QUAL é o padrão NÃO mora aqui: a forma (`SIM_FORMA_RAMPA_PADRAO`) e o pico observado
   (`SIM_MES_PICO_RAMPA_PADRAO`) são do servidor. Esta tela só manda `mes_pico_rampa`
   quando o operador escolhe; sem escolha, o seletor mostra o pico que o payload devolveu.
   As OPÇÕES do seletor espelham `SIM_MESES_PICO_RAMPA` (o servidor recusa outras com 422).

   Os identificadores são os do contrato (sem acento); os rótulos são texto de usuário.
   --------------------------------------------------------------------------- */

/** Opções do pico de maturação, em meses (espelho de `SIM_MESES_PICO_RAMPA`). */
export const MESES_PICO_RAMPA = [6, 8, 10, 12, 15, 18, 24] as const
export type MesPicoRampa = (typeof MESES_PICO_RAMPA)[number]

/** Campos do payload que esta lib lê (subconjunto de `PremissasViabilidade`). */
export interface PremissasRampa {
  maturacao_meses: number
  forma_rampa?: string | null
  mes_maturidade_rampa?: number | null
  mes_pico_rampa?: number | null
  /** Mês de operação do regime pleno (a DRE de steady-state); servido pelo motor. */
  mes_referencia_steady?: number | null
}

/** Forma servida pelo payload; ausente (backend anterior à DEC-077) = a rampa linear. */
export function formaDoPayload(p: PremissasRampa | null | undefined): 'curva_uni03' | 'reta' {
  return p?.forma_rampa === 'curva_uni03' ? 'curva_uni03' : 'reta'
}

/** Rótulo de uma opção do seletor. */
export function rotuloPico(meses: number): string {
  return `${meses} meses`
}

/**
 * Pico que o seletor marca: o ESCOLHIDO pelo operador ou, sem escolha, o que o servidor
 * usou no último cálculo. Antes de qualquer cálculo (ou com o servidor na rampa linear),
 * `null`: a tela não adivinha o padrão do servidor.
 */
export function picoExibido(
  escolhido: MesPicoRampa | null,
  p: PremissasRampa | null | undefined,
): number | null {
  if (escolhido != null) return escolhido
  if (!p || formaDoPayload(p) !== 'curva_uni03') return null
  const m = p.mes_pico_rampa ?? p.mes_maturidade_rampa
  return m != null && Number.isFinite(m) && m > 0 ? Math.round(m) : null
}

/**
 * O que vai no corpo do pedido: SÓ a escolha explícita. Sem escolha a chave some do JSON
 * e o servidor aplica o pico observado — é isso que deixa o padrão com uma fonte só.
 */
export function picoParaEnviar(escolhido: MesPicoRampa | null): MesPicoRampa | undefined {
  return escolhido ?? undefined
}

const RECALCULE = 'Recalcule para atualizar o payback.'

/**
 * Texto de ajuda sob o seletor. Escolher o pico NÃO recalcula sozinho (como os outros
 * campos da barra lateral): o texto diz isso. Os percentuais saem de `curva_rampa` do
 * payload (quando já houve cálculo) — a tela não crava número do motor.
 */
export function ajudaDaRampa(
  p: (PremissasRampa & { curva_rampa?: readonly number[] | null }) | null | undefined,
): string {
  const base =
    'Curva observada nas unidades da rede. O pico de maturação é o mês em que a unidade ' +
    'chega à demanda madura: o padrão é o pico observado; outro pico estica ou encurta a ' +
    'mesma curva no tempo, com a mesma abertura no mês 1.'
  if (p && formaDoPayload(p) !== 'curva_uni03') {
    return (
      `O servidor está usando a rampa linear de ${p.maturacao_meses} meses, e o pico de ` +
      `maturação só vale na curva observada. ${RECALCULE}`
    )
  }
  const curva = p?.curva_rampa
  let numeros = ''
  if (curva && curva.length > 0) {
    const fim = curva.findIndex((f) => f >= 1)
    numeros =
      ` No último cálculo: ${Math.round(curva[0] * 100)}% da demanda no mês 1` +
      (fim >= 0 ? ` e 100% a partir do mês ${fim + 1}.` : '.')
  }
  return (
    `${base}${numeros} Foi medida em unidades que abriram com agregador: sem agregador, ` +
    `tende a ser otimista. ${RECALCULE}`
  )
}

/**
 * Mês em que a rampa de fato termina. Lê `mes_maturidade_rampa` (servido pelo motor);
 * backend anterior à DEC-077 não o manda, e lá a rampa era sempre a linear de
 * `maturacao_meses` — o fallback reproduz exatamente aquilo.
 */
export function mesFimDaRampa(p: PremissasRampa | null | undefined): number | null {
  if (!p) return null
  const m = p.mes_maturidade_rampa ?? p.maturacao_meses
  return Number.isFinite(m) && m > 0 ? Math.round(m) : null
}

/**
 * O que a rampa muda no steady-state. Com o regime pleno até o mês 12 ela só move o
 * caixa e o payback. Depois do mês 12 (pico tardio), o motor mede o regime pleno no
 * próprio pico, que já tem o reajuste anual de preços (degrau a partir do mês 13): o
 * DRE de steady-state sai a preços do 2º ano e fica ACIMA do de um pico curto — dizer
 * "não muda o steady-state" seria falso (revisão de 21/10/2026).
 */
export function efeitoDaRampaNoSteady(p: PremissasRampa): string {
  const ref = p.mes_referencia_steady
  if (ref != null && Number.isFinite(ref) && ref > 12) {
    const ano = Math.floor((Math.round(ref) - 1) / 12) + 1
    return (
      `Afeta o caixa e o payback. Como a demanda cheia só chega no mês ${Math.round(ref)}, ` +
      `o steady-state é medido nesse mês, já com o reajuste anual de preços (preços do ` +
      `${ano}º ano): por isso o faturamento e o EBITDA de steady-state ficam acima dos de ` +
      'um pico até o mês 12.'
    )
  }
  return 'Afeta o caixa e o payback, não a margem de steady-state.'
}

/** Frase da nota metodológica sobre a rampa. */
export function notaDaRampa(p: PremissasRampa): string {
  const fim = mesFimDaRampa(p)
  if (formaDoPayload(p) === 'curva_uni03') {
    return (
      'Curva observada nas unidades da rede: cada mês tem uma fração da demanda madura, ' +
      `até a demanda cheia no pico de maturação, mês ${fim ?? '?'}. Outro pico reescala a ` +
      'mesma curva no tempo. O faturamento segue alunos × ticket: o ticket menor dos ' +
      'primeiros meses (promoções) não é modelado, e por isso o caixa do 1º ano tende a ' +
      `sair otimista. ${efeitoDaRampaNoSteady(p)}`
    )
  }
  return (
    `${p.maturacao_meses} meses para a demanda sair do piso inicial e chegar ao ` +
    `valor assumido. ${efeitoDaRampaNoSteady(p)}`
  )
}

/**
 * Como a nota da FOLHA descreve o mês 1. Na rampa linear o mês 1 parte dos alunos
 * iniciais (a "casa vazia" de sempre); na curva observada ele já abre com boa parte da
 * demanda, e dizer "casa vazia" seria falso.
 */
export function casaNoMes1(p: PremissasRampa): string {
  return formaDoPayload(p) === 'curva_uni03' ? 'com a casa ainda enchendo' : 'com a casa vazia'
}

/**
 * Como a nota do EBITDA descreve os primeiros meses. Na rampa linear o EBITDA deles é bem
 * negativo; na curva o mês 1 pode já ser positivo (+R$ 37 mil no caso de referência),
 * então a frase não afirma o sinal.
 */
export function ebitdaDosPrimeirosMeses(p: PremissasRampa): string {
  return formaDoPayload(p) === 'curva_uni03'
    ? 'então o EBITDA dos primeiros meses fica ABAIXO do de regime enquanto a casa não ' +
        'enche (na curva observada ele pode já sair positivo no mês 1).'
    : 'então o EBITDA dos primeiros meses é bem NEGATIVO enquanto a casa não enche.'
}
