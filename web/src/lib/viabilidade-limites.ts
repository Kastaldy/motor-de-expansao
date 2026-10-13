/* ---------------------------------------------------------------------------
   Viabilidade: a faixa que o MOTOR aceita, campo a campo.

   POR QUE ISTO EXISTE. `CampoNumero` documenta, no próprio arquivo, que `min`/`max`
   nativos NUNCA impediram digitação — eles só valem para as setas. Então `min={1}` em
   "Parcelas franquia" não impede digitar `0`, o motor recusa com 422 e, até
   2026-10-13, o 422 chegava à tela como "[object Object]" (o `detail` é uma LISTA de
   erros do pydantic e o cliente fazia `String(...)` nela). O operador via um retângulo
   vermelho que não dizia nem o campo nem a regra.

   ESTA TABELA É A SEGUNDA REDAÇÃO DE UMA REGRA QUE JÁ EXISTE em
   `src/motor_expansao/dimensionamento/payload_viabilidade.py` (`ViabilidadeInputs`), e
   duas redações da mesma regra não dão erro: desencontram em SILÊNCIO. Por isso os
   nomes das chaves são os do pydantic (`gt`/`ge`/`lt`/`le`) e existe um teste de
   contrato — `tests/contracts/test_limites_da_tela_batem_com_o_motor.py` — que lê este
   arquivo e compara com o modelo. Mexer no limite de um lado só deixa o CI vermelho.

   Só entram campos que (a) o operador digita livremente e (b) têm faixa no motor. O
   resto fica coberto pela rede geral: qualquer 422 agora vira texto legível em
   `mensagemDoDetalhe` (`lib/api.ts`).
   --------------------------------------------------------------------------- */

/** Faixa de um campo, nos nomes do pydantic. Ausente = sem limite daquele lado. */
export interface Limite {
  /** Maior que (exclusivo). */
  gt?: number
  /** Maior ou igual a. */
  ge?: number
  /** Menor que (exclusivo). */
  lt?: number
  /** Menor ou igual a. */
  le?: number
  /** O `label` do `Campo` na tela — é assim que a pessoa enxerga o campo. */
  rotulo: string
}

export const LIMITES_DO_MOTOR = {
  m2: { gt: 0, rotulo: 'Metragem' },
  // A demanda é DIGITADA justamente onde não há faixa de comparáveis — o caso da
  // instância argentina. `min={1}` ali não impede digitar `0`, e `demandaUsar == null`
  // não barra o zero (0 não é null), então ele atravessava direto para o motor.
  demanda: { gt: 0, rotulo: 'Demanda' },
  parcelas_obra: { gt: 0, le: 12, rotulo: 'Parcelas obra' },
  parcelas_franquia: { gt: 0, le: 12, rotulo: 'Parcelas franquia' },
  prazo_equipamentos: { ge: 1, le: 60, rotulo: 'Prazo financ.' },
} as const satisfies Record<string, Limite>

export type ChaveComLimite = keyof typeof LIMITES_DO_MOTOR

/** Como escrever a faixa para quem lê: "entre 1 e 12", "maior que 0", "no máximo 60". */
export function faixaEmTexto(l: Limite): string {
  const piso = l.ge ?? (l.gt !== undefined ? l.gt + 1 : undefined)
  const teto = l.le ?? (l.lt !== undefined ? l.lt - 1 : undefined)
  if (piso !== undefined && teto !== undefined) return `entre ${piso} e ${teto}`
  if (piso !== undefined) return `${piso} ou mais`
  if (teto !== undefined) return `no máximo ${teto}`
  return 'um número'
}

/**
 * Mensagem se `v` estiver fora da faixa; `null` se estiver dentro.
 *
 * `undefined` é DENTRO: campo vazio significa "usa o padrão do motor" e a chave nem
 * entra no JSON. Não-finito também é barrado — o motor tem `allow_inf_nan=False`.
 */
export function foraDaFaixa(v: number | undefined, l: Limite): string | null {
  if (v === undefined) return null
  const dentro =
    Number.isFinite(v) &&
    (l.gt === undefined || v > l.gt) &&
    (l.ge === undefined || v >= l.ge) &&
    (l.lt === undefined || v < l.lt) &&
    (l.le === undefined || v <= l.le)
  return dentro ? null : `"${l.rotulo}" precisa ser ${faixaEmTexto(l)}.`
}
