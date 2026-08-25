/* ---------------------------------------------------------------------------
   Marcador local "para visita" (localStorage, sem backend).

   Extraido da OportunidadesImobiliariasScreen quando a janela de detalhe do
   imovel no Mapa Territorial ganhou o botao "Marcar visita" (design dos paineis,
   2026-08-21): as duas telas leem e escrevem a MESMA chave, entao o helper vira
   modulo — duas copias divergiriam na primeira mudanca de formato.

   Best-effort por desenho: modo privado/cota cheia degradam para "sem marcador",
   nunca para tela quebrada.
   --------------------------------------------------------------------------- */

export const CHAVE_VISITAS = 'op-imob-visitas'

export function lerVisitas(): Set<string> {
  try {
    return new Set(JSON.parse(localStorage.getItem(CHAVE_VISITAS) ?? '[]') as string[])
  } catch {
    return new Set()
  }
}

export function salvarVisitas(s: Set<string>) {
  try {
    localStorage.setItem(CHAVE_VISITAS, JSON.stringify([...s]))
  } catch {
    /* modo privado / cota cheia — o marcador some no reload, sem quebrar a tela */
  }
}

/** Liga/desliga um imovel no conjunto e PERSISTE; devolve o conjunto novo. */
export function alternarVisita(prev: Set<string>, id: string): Set<string> {
  const prox = new Set(prev)
  if (prox.has(id)) prox.delete(id)
  else prox.add(id)
  salvarVisitas(prox)
  return prox
}
