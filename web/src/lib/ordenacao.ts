/* ---------------------------------------------------------------------------
   Ordenação de tabela — a política escrita UMA vez.

   Existiam duas redações: `ordenarUnidades` (Visão Executiva, `lib/exec.ts`) e
   `ordenarUsuariosAcessos` (Acessos, `lib/acessos-ordem.ts`) eram a mesma função
   linha a linha — mesmo sinal, mesma cópia defensiva, mesma sequência de nulos,
   mesmo `localeCompare(..., 'pt-BR')` — e só mudava o acessor. Duas redações da
   mesma regra não dão erro: elas desencontram em SILÊNCIO, e nada no repositório
   reprovava quando desencontrassem — a única garantia de que as duas continuam
   sendo a mesma regra é elas serem, de fato, uma só.

   A regra, agora num lugar só:

     - NULO SEMPRE NO FIM, nas duas direções. "Sem dado" não é um extremo do
       valor; jogá-lo para o topo no `asc` empurra a informação útil para fora da
       tela (foi o defeito do `?? -Infinity` da primeira versão da Executiva).
     - EMPATE cai no rótulo, para a ordem não dançar entre renders.
     - A coluna de TEXTO (`chaveRotulo`) ordena pelo próprio rótulo, com colação
       pt-BR — senão "Ávila" cairia depois de "Zeca".
     - Devolve SEMPRE um array novo: a lista de origem é o payload memoizado da
       tela e não pode ser mutada no lugar.

   PURO e sem React de propósito, no padrão de `lib/exec.ts` e `lib/acesso.ts`: o
   vitest roda em ambiente node e a regra de ordem precisa ser testável sem DOM.
   --------------------------------------------------------------------------- */

export type DirecaoOrdem = 'asc' | 'desc'

export interface AcessoresOrdem<T> {
  /** Valor numérico comparável da coluna. `null` = sem dado, e vai para o fim. */
  escalar: (item: T, chave: string) => number | null
  /** Texto que ordena a coluna de rótulo e desempata todas as outras. */
  rotulo: (item: T) => string
  /**
   * Chave cuja ordenação É o rótulo (A-Z / Z-A), e não um escalar. As duas tabelas
   * do produto chamam essa coluna de `nome`; o parâmetro existe para a terceira.
   */
  chaveRotulo?: string
}

/** Aplica a ordem de uma coluna. Ver o bloco acima para a política inteira. */
export function ordenarPorEscalar<T>(
  itens: readonly T[],
  chave: string,
  direcao: DirecaoOrdem,
  { escalar, rotulo, chaveRotulo = 'nome' }: AcessoresOrdem<T>,
): T[] {
  const sinal = direcao === 'asc' ? 1 : -1
  const porRotulo = (a: T, b: T): number => rotulo(a).localeCompare(rotulo(b), 'pt-BR')
  return [...itens].sort((a, b) => {
    if (chave === chaveRotulo) return sinal * porRotulo(a, b)
    const va = escalar(a, chave)
    const vb = escalar(b, chave)
    if (va === null && vb === null) return porRotulo(a, b)
    if (va === null) return 1
    if (vb === null) return -1
    if (va === vb) return porRotulo(a, b)
    return sinal * (va - vb)
  })
}
