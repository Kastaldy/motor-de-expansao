/* ---------------------------------------------------------------------------
   Logica PURA do filtro do <Select> — extraida para ser testavel sem DOM.
   O componente `Select.tsx` reusa estas funcoes; comportamento inalterado.
   --------------------------------------------------------------------------- */

/** Normaliza para busca insensivel a acento e caixa (NFD + tira diacritico). */
export function norm(s: string): string {
  return s
    .normalize('NFD')
    .replace(/\p{Diacritic}/gu, '')
    .toLowerCase()
    .trim()
}

/**
 * Filtra opcoes por substring insensivel a acento, PRESERVANDO a ordem de
 * entrada (as opcoes ja chegam ordenadas). Busca vazia -> a mesma lista (sem copia).
 */
export function filtrarOpcoes<T extends { label: string }>(
  options: T[],
  busca: string,
): T[] {
  if (!busca.trim()) return options
  const q = norm(busca)
  return options.filter((o) => norm(o.label).includes(q))
}
