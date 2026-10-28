/* ---------------------------------------------------------------------------
   Viabilidade: a rampa de alunos (DEC-078, emenda de 21/10/2026).

   A tela tem UMA forma de rampa: a curva OBSERVADA nas unidades da rede (BLK-UNI-03) —
   o mês t tem uma fração da demanda madura, até 100% no PICO DE MATURAÇÃO. O operador
   escolhe o pico (o mês em que a unidade chega à demanda madura); o MOTOR reescala a
   mesma forma observada no tempo (`dimensionamento/simulador.py::curva_rampa_com_pico`).
   A tela não calcula a curva: lê o que o payload devolveu.

   QUAL é o padrão NÃO mora aqui: a forma (`SIM_FORMA_RAMPA_PADRAO`) e o pico observado
   (`SIM_MES_PICO_RAMPA_PADRAO`) são do servidor. Esta tela só manda `mes_pico_rampa`
   quando o operador escolhe; sem escolha, o contador mostra o pico que o payload devolveu.
   O contador "−/+" anda de mês em mês, no intervalo de `SIM_MES_PICO_RAMPA_MIN/MAX` (o
   servidor recusa fora dele com 422) — o mesmo controle da rampa antiga (22/10/2026).

   Os identificadores são os do contrato (sem acento); os rótulos são texto de usuário.
   --------------------------------------------------------------------------- */

/** Intervalo do contador, em meses (espelho de `SIM_MES_PICO_RAMPA_MIN/MAX`). */
export const PICO_RAMPA_MIN = 1
export const PICO_RAMPA_MAX = 36
/** Pico observado na rede, em mês de vida (0 = inauguração; espelho de
 *  `SIM_MES_PICO_RAMPA_OBSERVADO`, travado por teste contra o `config.py`). Só serve para o contador ter de onde partir ANTES do 1º cálculo;
 *  o pedido segue sem `mes_pico_rampa` enquanto o operador não mexe. */
export const PICO_RAMPA_OBSERVADO = 10
export type MesPicoRampa = number

/** Um passo do contador (−1 ou +1), preso ao intervalo do servidor. */
export function passoPico(atual: number, delta: -1 | 1): number {
  return Math.min(PICO_RAMPA_MAX, Math.max(PICO_RAMPA_MIN, atual + delta))
}

/** Campos do payload que esta lib lê (subconjunto de `PremissasViabilidade`). */
export interface PremissasRampa {
  maturacao_meses: number
  forma_rampa?: string | null
  mes_maturidade_rampa?: number | null
  mes_pico_rampa?: number | null
  /** Mês de operação do regime pleno (a DRE de steady-state); servido pelo motor. */
  mes_referencia_steady?: number | null
}

/** Forma servida pelo payload; ausente (backend anterior à DEC-078) = a rampa linear. */
export function formaDoPayload(p: PremissasRampa | null | undefined): 'curva_uni03' | 'reta' {
  return p?.forma_rampa === 'curva_uni03' ? 'curva_uni03' : 'reta'
}

/** Rótulo do contador. */
export function rotuloPico(meses: number): string {
  return `${meses} ${meses === 1 ? 'mês' : 'meses'}`
}

/**
 * Pico que o contador mostra: o ESCOLHIDO pelo operador ou, sem escolha, o que o servidor
 * usou no último cálculo. Antes de qualquer cálculo, o observado na rede (é o que o
 * servidor aplica a um pedido sem pico). Com o servidor na rampa linear, `null`.
 */
export function picoExibido(
  escolhido: MesPicoRampa | null,
  p: PremissasRampa | null | undefined,
): number | null {
  if (escolhido != null) return escolhido
  if (!p) return PICO_RAMPA_OBSERVADO
  if (formaDoPayload(p) !== 'curva_uni03') return null
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
 * Ajuda sob o contador: UMA linha (pedido de 22/10/2026 — o texto longo ocupava a barra
 * lateral). O detalhe (abertura medida, amarra do agregador) mora na nota metodológica
 * (`notaDaRampa`). Escolher o pico NÃO recalcula sozinho, e a linha diz isso.
 */
export function ajudaDaRampa(p: PremissasRampa | null | undefined): string {
  if (p && formaDoPayload(p) !== 'curva_uni03') {
    return `O servidor usou a rampa linear de ${p.maturacao_meses} meses. ${RECALCULE}`
  }
  return `Meses desde a inauguração até a demanda madura. ${RECALCULE}`
}

/**
 * Mês em que a rampa de fato termina. Lê `mes_maturidade_rampa` (servido pelo motor);
 * backend anterior à DEC-078 não o manda, e lá a rampa era sempre a linear de
 * `maturacao_meses` — o fallback reproduz exatamente aquilo.
 */
export function mesFimDaRampa(p: PremissasRampa | null | undefined): number | null {
  if (!p) return null
  const m = p.mes_maturidade_rampa ?? p.maturacao_meses
  return Number.isFinite(m) && m > 0 ? Math.round(m) : null
}

/** Meses que o eixo do gráfico "Rampa de alunos" mostra DEPOIS do pico (pedido de 28/10/2026). */
export const MESES_DEPOIS_DO_PICO = 2

/** Um ponto da série de alunos, com o mês JÁ na unidade do eixo do gráfico. */
export interface PontoDaRampa {
  mes: number
  v: number
}

/** 1º mês em que a série atinge o seu máximo (a série vem em ordem de mês). */
function mesDoMaximo(pontos: readonly PontoDaRampa[]): number {
  let melhor = pontos[0]
  for (const p of pontos) if (p.v > melhor.v) melhor = p
  return melhor.mes
}

/**
 * Eixo X do gráfico "Rampa de alunos": vai até 2 meses depois do pico (pedido do dono do
 * produto em 28/10/2026: "12 meses mostra 14, 8 meses mostra 10"). Antes o eixo ia a no
 * mínimo 18 meses (`max(platô + 6, 18)`), largo demais: num pico de 8 a subida ocupava
 * menos da metade da largura.
 *
 * `fimDaRampa` é o `mes_maturidade_rampa` servido (via `mesFimDaRampa`), o 1º mês de
 * OPERAÇÃO com a demanda cheia. Na curva observada o eixo conta o MÊS DE VIDA (mês 0 = a
 * inauguração) e o platô cai em `fimDaRampa - 1`, que é o pico escolhido: o motor serve
 * `mes_maturidade_rampa` = pico + 1. Na rampa linear (só pela API) o eixo é o mês de
 * operação e o platô é o próprio `fimDaRampa`. Nos dois casos o eixo termina no platô + 2,
 * sem piso nem teto: pico 1 mostra 3 meses; pico 36, 38.
 *
 * O eixo nunca passa do último mês da série: série mais curta que o platô + 2 termina
 * nela, e o marcador do platô some quando ele fica fora (quem desenha testa
 * `plato <= limite`). Sem fim servido (premissas ausentes), o eixo ancora no 1º mês em que
 * a própria série atinge o seu máximo: a mesma regra sem número fixo, e o máximo da série,
 * que é o valor do cabeçalho, nunca fica fora do eixo. Esse mês LIDO da série não vira
 * `plato`: o rótulo "platô no mês N" e o marcador só afirmam o que o payload serviu.
 *
 * `pontos` vem em ordem de mês, já na unidade do eixo, e não é vazio (o gráfico só desenha
 * com 2 pontos ou mais).
 */
export function eixoDaRampa(
  fimDaRampa: number | null,
  curva: boolean,
  pontos: readonly PontoDaRampa[],
): { plato: number | null; limite: number } {
  const plato =
    fimDaRampa != null && Number.isFinite(fimDaRampa) && fimDaRampa > 0
      ? Math.round(fimDaRampa) - (curva ? 1 : 0)
      : null
  const ancora = plato ?? mesDoMaximo(pontos)
  return { plato, limite: Math.min(pontos[pontos.length - 1].mes, ancora + MESES_DEPOIS_DO_PICO) }
}

/**
 * Meses com linha de grade vertical no gráfico "Rampa de alunos" (pedido do dono do
 * produto em 28/10/2026: "uma linha tracejada vertical para cada mês"). São os meses
 * inteiros do eixo, do 0 ao `limite - 1`, e com eles todo mês do eixo, menos o último, tem
 * exatamente UMA linha vertical:
 * - o mês do platô (o `plato` de `eixoDaRampa`) fica de fora: ele já tem o marcador
 *   próprio, tracejado na cor de destaque, e duas linhas no mesmo x embaralhariam os dois
 *   tracejados. Platô ausente ou fora do eixo (série curta) não tira mês nenhum, e aí
 *   também não há marcador;
 * - o mês 0, a borda esquerda, ganha linha (pedido do mesmo dia: "a linha do mês 0 para o
 *   1 completa"), com o traço mais largo de `larguraDaLinhaDaGrade`;
 * - o `limite`, a borda direita, não ganha ("pode ser cortada, visto que vira uma reta"):
 *   no fim do eixo a curva já está no platô, plana, e o mês está rotulado embaixo ("mês N").
 *
 * Pico 1 (eixo de 0 a 3, marcador no 1) dá os meses 0 e 2; pico 10 (eixo de 0 a 12), do 0
 * ao 9 e o 11. Eixo degenerado (`limite` <= 0 ou não finito) não tem grade.
 */
export function mesesDaGrade(limite: number, plato: number | null): number[] {
  const meses: number[] = []
  if (!Number.isFinite(limite)) return meses
  for (let m = 0; m < limite; m++) if (m !== plato) meses.push(m)
  return meses
}

/**
 * Largura do traço da linha de grade de um mês, em px de tela (o traço não escala com o
 * SVG). O mês 0 cai na borda esquerda, e o `<svg>` recorta o que passa do próprio
 * contorno: com o traço centrado na borda, a metade de fora some, e uma linha de 1 px
 * sairia com metade da tinta das outras (medido a 100% em 28/10/2026). Com 2 px, a metade
 * que fica tem 1 px, como as demais.
 */
export function larguraDaLinhaDaGrade(mes: number): number {
  return mes === 0 ? 2 : 1
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
      `Afeta o caixa e o payback. Como a demanda cheia só chega no mês ${Math.round(ref)} ` +
      'de operação, ' +
      `o steady-state é medido nesse mês, já com o reajuste anual de preços (preços do ` +
      `${ano}º ano): por isso o faturamento e o EBITDA de steady-state ficam acima dos de ` +
      'um pico até o mês 11 (o regime pleno no mês 12 de operação).'
    )
  }
  return 'Afeta o caixa e o payback, não a margem de steady-state.'
}

/** Frase da nota metodológica sobre a rampa — onde mora o detalhe que saiu da ajuda. */
export function notaDaRampa(
  p: PremissasRampa & { curva_rampa?: readonly number[] | null },
): string {
  const fim = mesFimDaRampa(p)
  if (formaDoPayload(p) === 'curva_uni03') {
    // Percentuais dos meses 0 e 1 saem da curva SERVIDA; a tela não crava número do motor.
    const c = p.curva_rampa
    const abertura =
      c && c.length > 1
        ? ` A unidade fecha o mês da inauguração (mês 0, o 1º mês de operação) com ` +
          `${Math.round(c[0] * 100)}% da demanda, com a pré-venda, e o mês 1 com ` +
          `${Math.round(c[1] * 100)}%, como no estudo.`
        : ''
    const pico = p.mes_pico_rampa ?? (fim != null ? fim - 1 : null)
    return (
      'Curva observada nas unidades da rede, contada em meses desde a inauguração: cada ' +
      'mês tem uma fração da demanda madura, até a demanda cheia no pico de maturação, ' +
      `mês ${pico ?? '?'}.${abertura} Outro pico estica ou encurta a mesma curva no ` +
      'tempo, com os mesmos meses 0 e 1. A curva foi ' +
      'medida em unidades que abriram com agregador: sem agregador, tende a ser otimista. ' +
      'O faturamento segue alunos × ticket: o ticket menor dos ' +
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
