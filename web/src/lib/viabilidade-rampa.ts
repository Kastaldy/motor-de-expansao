/* ---------------------------------------------------------------------------
   Viabilidade: a FORMA da rampa de alunos (DEC-075).

   Duas formas, escolhidas pelo operador e calculadas SÓ no motor
   (`dimensionamento/simulador.py`):
   - `curva_uni03` (padrão): a curva OBSERVADA na rede pelo BLK-UNI-03 — o mês t tem uma
     fração da demanda madura (68% no mês 1, 100% a partir do mês 10);
   - `reta`: a rampa histórica da planilha, dos alunos iniciais até a demanda em N meses
     (o controle de meses só vale aqui).

   Esta tela não calcula a rampa: lê `forma_rampa`, `mes_maturidade_rampa` e
   `curva_rampa` do payload. Os identificadores são os do contrato (sem acento); os
   rótulos são texto de usuário (com acento).
   --------------------------------------------------------------------------- */

export const FORMAS_RAMPA = ['curva_uni03', 'reta'] as const
export type FormaRampa = (typeof FORMAS_RAMPA)[number]

/** Padrão do produto (`SIM_FORMA_RAMPA_PADRAO` no config do motor). */
export const FORMA_RAMPA_PADRAO: FormaRampa = 'curva_uni03'

export const ROTULO_FORMA_RAMPA: Record<FormaRampa, string> = {
  curva_uni03: 'Curva observada',
  reta: 'Reta',
}

/** O controle de meses só faz sentido na reta (na curva o motor o ignora). */
export function usaMesesDeRampa(forma: FormaRampa): boolean {
  return forma === 'reta'
}

/**
 * Texto de ajuda sob o controle, conforme a forma escolhida. Os percentuais da curva
 * saem de `curva_rampa` do payload (quando já houve cálculo) — a tela não crava número
 * do motor.
 */
export function ajudaDaRampa(forma: FormaRampa, curva?: readonly number[] | null): string {
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
    'que abriram com agregador: sem agregador, tende a ser otimista.'
  )
}

/** Campos do payload que esta lib lê (subconjunto de `PremissasViabilidade`). */
export interface PremissasRampa {
  maturacao_meses: number
  forma_rampa?: string | null
  mes_maturidade_rampa?: number | null
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

/** Forma servida pelo payload; ausente (backend antigo) = reta. */
export function formaDoPayload(p: PremissasRampa | null | undefined): FormaRampa {
  return p?.forma_rampa === 'curva_uni03' ? 'curva_uni03' : 'reta'
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
