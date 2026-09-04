/**
 * A fila de destinos do Dock, PURA — no padrão de `lib/inicio.ts` e `lib/acesso.ts`:
 * o vitest do piloto roda em ambiente `node` e só casa `src/**\/*.test.ts`, então a
 * REGRA (quais destinos existem, em que ordem, para onde cada um leva) vive aqui,
 * testável sem DOM, e `Dock.tsx` fica deliberadamente burro: desenha o que está
 * declarado, com os ícones que continuam lá (SVG é desenho, não regra).
 *
 * `TelaControlada` vem de `lib/acesso.ts` de propósito: todo item navegável novo
 * nasce coberto pelo gate de abas — um destino fora do controle de acesso nem
 * compila, e o teste confere que o gate conhece cada tela da fila.
 */

import type { TelaControlada } from './acesso'

export interface ItemDock {
  /** Identificador SEM acento (regra do CLAUDE.md §2) — casa com a chave do ícone. */
  id: string
  /** Destino da navegação; `null` = fora do piloto (ícone desabilitado). */
  tela: TelaControlada | null
  /** Título visível (tooltip/aria), com acentuação correta. */
  titulo: string
}

/**
 * O Dock NAO lista os MODOS DE ANALISE — com uma exceção deliberada, o mapa.
 *
 * "Análise de ponto" e "Explorar uma região" sairam daqui a pedido do Juan (2026-08-12):
 * eles sao escolha de PERGUNTA, e essa escolha se faz na tela de inicio, onde cada card
 * explica o que o modo responde e do que ele precisa. Repetidos como dois ícones sem
 * rótulo, viravam um segundo caminho mudo para a mesma decisão — e dois pinos quase
 * iguais, ainda por cima.
 *
 * O ícone de início tambem saiu: quem volta ao menu agora clica na LOGO, que ja estava
 * ali em cima e nao fazia nada.
 *
 * O MAPA VOLTOU em 2026-09-04, também a pedido do Juan: não como segundo caminho mudo,
 * mas como ATALHO do destino default do piloto — quem saiu do Explorar para outra tela
 * volta por aqui ao mapa COMO O DEIXOU (a foto do mapa mora no App e sobrevive à troca
 * de tela; ver `estadoMapa` no `App.tsx`). O card do Início continua sendo quem explica
 * o modo; card e ícone levam à MESMA tela `mapa`, com o MESMO estado — um caminho só.
 * "Análise de ponto" segue fora do Dock.
 */
export const ITENS_DOCK: readonly ItemDock[] = Object.freeze([
  /* Primeiro da fila: é a superfície default do piloto (App.tsx §5 do CLAUDE.md). */
  Object.freeze({ id: 'mapa', tela: 'mapa' as const, titulo: 'Explorar uma região' }),
  Object.freeze({ id: 'exec', tela: 'executiva' as const, titulo: 'Visão executiva' }),
  /* "Expansão de domínio" e "Carteira e plano" SAIRAM (Juan, 2026-09-02: "eles não
     estão sendo utilizados, então tirar os ícones deles"). Eram os dois únicos itens
     com `tela: null` — existiam para anunciar que o piloto é um recorte do produto,
     mas dois botões permanentemente apagados viraram só ruído no rail. O suporte a
     `tela: null` fica no tipo: é o que permite reintroduzir um destino futuro sem
     reabrir esta lista. */
  Object.freeze({
    id: 'oport',
    tela: 'oportunidades-imob' as const,
    titulo: 'Oportunidades imobiliárias',
  }),
  Object.freeze({ id: 'viab', tela: 'viabilidade' as const, titulo: 'Viabilidade do ponto' }),
  /* Aba restrita (emenda DEC-027): telaLiberada e deny-by-default — para quem não
     está na allowlist o ícone simplesmente não existe, como toda tela vetada. */
  Object.freeze({ id: 'acessos', tela: 'acessos' as const, titulo: 'Acessos e uso do piloto' }),
])
