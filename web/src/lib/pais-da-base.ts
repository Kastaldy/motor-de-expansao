/**
 * Que PAÍS a base servida descreve — deduzido da lista de unidades federativas.
 *
 * POR QUE PRECISA EXISTIR. O mesmo binário do piloto serve o Brasil e a Argentina; o que
 * muda é o `MOTOR_DATA_DIR` (ver `piloto_rep/LEIA-ME.md` no repo Motor-Argentina). Sem
 * carimbo, as duas instâncias são idênticas na tela, e com as duas abertas o operador não
 * sabe em qual está — que é exatamente o que o carimbo do Dock existe para resolver. Um
 * carimbo FIXO do Brasil não resolve: ele fica errado justamente na instância em que a
 * dúvida existe (Juan, 2026-08-26: "está com o ícone do Brasil… é da Argentina").
 *
 * POR QUE PELA LISTA DE UFs, E NÃO POR UMA VARIÁVEL DO BACKEND. Porque a resposta já está
 * na tela: o app pede `/api/ufs` na abertura, de qualquer jeito. Derivar daí não custa
 * requisição, não acrescenta contrato entre front e back, e não precisa que ninguém lembre
 * de exportar uma variável de ambiente na hora de subir a instância — que é o modo de falhar
 * mais provável de um carimbo de identidade.
 *
 * O QUE TORNA ISTO SEGURO, e não um chute: o exportador da base argentina
 * (`pipelines/exportar_piloto_rep.py`) **garante** que nenhum código de província colida com
 * UF brasileira — ele ABORTA a exportação se colidir, e o motivo está escrito lá (o backend
 * valida `^[A-Za-z]{2}$` no sink, e cinco siglas óbvias colidiriam: PB, BA, RN, SC, SE).
 * Ou seja, os dois conjuntos são disjuntos por construção, com gate do lado que gera.
 *
 * E POR ISSO A FUNÇÃO SÓ AFIRMA O QUE CONSEGUE PROVAR. Ela não tem lista de províncias
 * argentinas — teria de ser mantida em dois repositórios e envelheceria calada. Ela decide
 * por DISJUNÇÃO: todas brasileiras → Brasil; nenhuma brasileira → a outra base. Qualquer
 * mistura devolve `null`, e `null` faz o Dock não carimbar nada. Um instante sem bandeira é
 * melhor do que uma bandeira errada — a leitura errada é o defeito que o carimbo combate.
 */

/** As 27 UFs do Brasil. Conjunto FECHADO — não muda desde 1988. */
export const UFS_BRASIL: ReadonlySet<string> = new Set([
  'AC', 'AL', 'AP', 'AM', 'BA', 'CE', 'DF', 'ES', 'GO', 'MA', 'MT', 'MS', 'MG',
  'PA', 'PB', 'PR', 'PE', 'PI', 'RJ', 'RN', 'RS', 'RO', 'RR', 'SC', 'SP', 'SE', 'TO',
])

/** Sigla do país da base, ou `null` quando a lista não permite afirmar. */
export type PaisDaBase = 'BR' | 'AR' | null

export function paisDaBase(ufs: readonly string[] | null | undefined): PaisDaBase {
  if (!ufs || ufs.length === 0) return null
  let brasileiras = 0
  for (const u of ufs) {
    if (typeof u !== 'string') return null
    if (UFS_BRASIL.has(u.trim().toUpperCase())) brasileiras += 1
  }
  if (brasileiras === ufs.length) return 'BR'
  if (brasileiras === 0) return 'AR'
  // Mistura dos dois universos: base montada errada, ou um país novo entrando. Não é hora
  // de escolher uma bandeira — é hora de não carimbar.
  return null
}
