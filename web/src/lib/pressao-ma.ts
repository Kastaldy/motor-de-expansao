/* ---------------------------------------------------------------------------
   Camada de LABEL do overlay de pressão competitiva (BLK-MA-13 / DEC-028).

   `sinais_disponiveis` chega do backend como `"s1,s6"` — valor BRUTO de enum,
   produzido pelo pipeline e comparado por igualdade lá dentro. Exibi-lo cru
   ("Sinais medidos: s1,s6") não é neutro: ele ocupa a linha do tooltip que
   deveria dizer ao operador SOB QUAL RÉGUA aquele número foi composto, e não diz
   nada — a informação existe e fica ilegível.

   Regra do CLAUDE.md §2: nunca acentuar identificadores; para exibir acentuado,
   usar uma camada de LABEL `{valor_bruto: "Texto Acentuado"}`. É o que este
   módulo é. O valor bruto segue intocado no payload e no parquet.
   --------------------------------------------------------------------------- */

/** Rótulo de exibição de cada sinal do score (contrato `SINAIS_ORDEM`, `contrato.py`). */
export const SINAL_ROTULO: Record<string, string> = {
  s1: 'presença em agregador',
  // Nunca chega à tela hoje (`SINAIS_INATIVOS`), mas o mapa é do CONTRATO, não do
  // que está ativo — reativar o s2 não pode fazer o rótulo sumir em silêncio.
  s2: 'nota do agregador',
  s3: 'churn',
  s4: 'cadastro parado',
  s6: 'pressão competitiva',
}

/**
 * `"s1,s6"` -> `"presença em agregador · pressão competitiva"`.
 *
 * Token desconhecido é DEVOLVIDO CRU em vez de descartado: um sinal novo no backend
 * (o s5, por exemplo) apareceria como `s5` na tela — feio, mas honesto e visível.
 * Descartá-lo faria a declaração de regime mentir por omissão, que é o defeito que
 * esta linha do tooltip existe para evitar.
 */
export function rotuloDoRegime(bruto: string | null | undefined): string {
  if (!bruto) return ''
  return bruto
    .split(',')
    .map((t) => t.trim())
    .filter(Boolean)
    .map((t) => SINAL_ROTULO[t] ?? t)
    .join(' · ')
}
