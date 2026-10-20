/* ---------------------------------------------------------------------------
   Viabilidade: a FORMA da rampa de alunos (DEC-075).

   Duas formas, calculadas SÓ no motor (`dimensionamento/simulador.py`):
   - `reta`: a rampa histórica da planilha, dos alunos iniciais até a demanda em N meses
     (o controle de meses só vale aqui);
   - `curva_uni03`: a curva OBSERVADA na rede pelo BLK-UNI-03 — o mês t tem uma fração da
     demanda madura (68% no mês 1, 100% a partir do mês 10).

   QUAL é o padrão NÃO mora aqui: é do servidor (`SIM_FORMA_RAMPA_PADRAO`, hoje a reta,
   porque a curva só é padrão com a demanda da Viabilidade v2 — decisão do dono de
   2026-10-20). Esta tela só manda `forma_rampa` quando o operador escolhe; sem escolha,
   mostra a forma que o payload devolveu. Assim uma constante do servidor reverte tudo.

   Os identificadores são os do contrato (sem acento); os rótulos são texto de usuário.
   --------------------------------------------------------------------------- */

export const FORMAS_RAMPA = ['curva_uni03', 'reta'] as const
export type FormaRampa = (typeof FORMAS_RAMPA)[number]

export const ROTULO_FORMA_RAMPA: Record<FormaRampa, string> = {
  curva_uni03: 'Curva observada',
  reta: 'Reta',
}

/** Campos do payload que esta lib lê (subconjunto de `PremissasViabilidade`). */
export interface PremissasRampa {
  maturacao_meses: number
  forma_rampa?: string | null
  mes_maturidade_rampa?: number | null
}

/** Forma servida pelo payload; ausente (backend anterior à DEC-075) = reta. */
export function formaDoPayload(p: PremissasRampa | null | undefined): FormaRampa {
  return p?.forma_rampa === 'curva_uni03' ? 'curva_uni03' : 'reta'
}

/**
 * Forma que o seletor mostra: a ESCOLHIDA pelo operador ou, sem escolha, a que o
 * servidor usou no último cálculo. Antes de qualquer cálculo, `null` (nenhuma marcada):
 * a tela não adivinha o padrão do servidor.
 */
export function formaExibida(
  escolhida: FormaRampa | null,
  p: PremissasRampa | null | undefined,
): FormaRampa | null {
  if (escolhida) return escolhida
  return p ? formaDoPayload(p) : null
}

/**
 * O que vai no corpo do pedido: SÓ a escolha explícita. Sem escolha a chave some do JSON
 * e o servidor aplica o padrão dele — é isso que torna a constante do servidor a única.
 */
export function formaParaEnviar(escolhida: FormaRampa | null): FormaRampa | undefined {
  return escolhida ?? undefined
}

/**
 * O controle de meses só faz sentido na reta (na curva o motor o ignora). Sem forma
 * conhecida (antes do 1º cálculo) ele aparece: é o controle que vale no padrão de hoje.
 */
export function usaMesesDeRampa(forma: FormaRampa | null): boolean {
  return forma !== 'curva_uni03'
}

const RECALCULE = 'Recalcule para atualizar o payback.'

/**
 * Texto de ajuda sob o controle, conforme a forma mostrada. Trocar a forma NÃO recalcula
 * sozinho (como os meses da rampa e os outros campos da barra lateral): o texto diz isso.
 * Os percentuais da curva saem de `curva_rampa` do payload (quando já houve cálculo) — a
 * tela não crava número do motor.
 */
export function ajudaDaRampa(forma: FormaRampa | null, curva?: readonly number[] | null): string {
  if (forma === null) {
    return (
      'Curva observada nas unidades da rede ou reta dos alunos iniciais até a demanda. ' +
      RECALCULE
    )
  }
  if (forma === 'reta') {
    return (
      'Reta dos alunos iniciais até a demanda no número de meses escolhido ' +
      '(Simulador E13, padrão 8). Alonga a curva de maturação e o fluxo de caixa; ' +
      'recalcule para atualizar o payback.'
    )
  }
  const fim = curva ? curva.findIndex((f) => f >= 1) : -1
  const numeros =
    curva && curva.length > 0
      ? ` ${Math.round(curva[0] * 100)}% da demanda no mês 1` +
        (fim >= 0 ? ` e 100% a partir do mês ${fim + 1}.` : '.')
      : ''
  return (
    `Curva medida nas unidades da rede (BLK-UNI-03).${numeros} Foi medida em unidades ` +
    `que abriram com agregador: sem agregador, tende a ser otimista. ${RECALCULE}`
  )
}

/**
 * Mês em que a rampa de fato termina. Lê `mes_maturidade_rampa` (servido pelo motor);
 * backend anterior à DEC-075 não o manda, e lá a rampa era sempre a reta de
 * `maturacao_meses` — o fallback reproduz exatamente aquilo.
 */
export function mesFimDaRampa(p: PremissasRampa | null | undefined): number | null {
  if (!p) return null
  const m = p.mes_maturidade_rampa ?? p.maturacao_meses
  return Number.isFinite(m) && m > 0 ? Math.round(m) : null
}

/** Frase da nota metodológica sobre a rampa. */
export function notaDaRampa(p: PremissasRampa): string {
  const fim = mesFimDaRampa(p)
  if (formaDoPayload(p) === 'curva_uni03') {
    return (
      `Curva observada na rede (BLK-UNI-03, DEC-075): cada mês tem uma fração da ` +
      `demanda madura, até a demanda cheia no mês ${fim ?? '?'}. O faturamento segue ` +
      'alunos × ticket: o ticket menor dos primeiros meses (promoções) não é modelado, ' +
      'e por isso o caixa do 1º ano tende a sair otimista. Afeta o caixa e o payback, ' +
      'não a margem de steady-state.'
    )
  }
  return (
    `${p.maturacao_meses} meses para a demanda sair do piso inicial e chegar ao ` +
    'valor assumido. Afeta o caixa e o payback, não a margem de steady-state.'
  )
}

/**
 * Como a nota da FOLHA descreve o mês 1. Na reta o mês 1 parte dos alunos iniciais (a
 * "casa vazia" de sempre); na curva observada ele já abre com 68% da demanda, e dizer
 * "casa vazia" seria falso.
 */
export function casaNoMes1(p: PremissasRampa): string {
  return formaDoPayload(p) === 'curva_uni03' ? 'com a casa ainda enchendo' : 'com a casa vazia'
}

/**
 * Como a nota do EBITDA descreve os primeiros meses. Na reta o EBITDA deles é bem
 * negativo (texto de antes da DEC-075, intacto); na curva o mês 1 pode já ser positivo
 * (+R$ 37 mil no caso de referência), então a frase não afirma o sinal.
 */
export function ebitdaDosPrimeirosMeses(p: PremissasRampa): string {
  return formaDoPayload(p) === 'curva_uni03'
    ? 'então o EBITDA dos primeiros meses fica ABAIXO do de regime enquanto a casa não ' +
        'enche (na curva observada ele pode já sair positivo no mês 1).'
    : 'então o EBITDA dos primeiros meses é bem NEGATIVO enquanto a casa não enche.'
}
