import type { Pin } from './types'

/* ---------------------------------------------------------------------------
   Regras de leitura dos pinos de concorrente.

   Mora em `lib/` e nao dentro do `HexMap` porque sao DECISOES, nao detalhe de
   render — e o `HexMap` nao tem teste de componente. Uma regra sem teste vira,
   com o tempo, um `&&` no meio de um `getRadius` que ninguem defende.
   --------------------------------------------------------------------------- */

/**
 * Esta unidade tem numero de alunos REAL (informado pela rede)?
 *
 * `!= null` cobre `null` e `undefined` de uma vez e — de proposito — deixa passar
 * o zero. O servidor ja' descarta `alunos_total <= 0` antes de montar o payload
 * (`_alunos_reais_por_id`), entao zero nao chega aqui; se um dia chegar, ele e'
 * uma MEDIDA e nao uma ausencia, e esconde-lo seria a tela discordando do balao,
 * que usa exatamente o mesmo teste.
 *
 * Truthiness (`!!p.alunos`) seria o erro classico aqui: transformaria esse zero
 * em "nao temos dado", que e' outra afirmacao.
 */
export function temAlunos(p: Pick<Pin, 'alunos'>): boolean {
  return p.alunos != null
}

/**
 * Tamanho, em PIXELS, da moldura de destaque de um pino com alunos.
 *
 * A moldura e' um QUADRADO ARREDONDADO colado na bandeira, e nao um circulo
 * afastado dela. A primeira versao era um aro solto (raio 23/28 px) e o dono
 * reprovou olhando a tela: "quando vamos para camada 3 ele se perde totalmente".
 * O motivo e' que um circulo a 8 px da aresta lê como ELEMENTO PROPRIO — mais um
 * ponto no mapa — e some no meio dos hexagonos coloridos da camada de pressao.
 * Colado, ele lê como o que e': a borda daquela bandeira, mais forte.
 *
 * O molde e' o halo do agregador (`_quadrado_logo(halo=True)` em
 * `web/server/app.py`), que ja' resolve isso com um anel rente ao quadrado
 * separado por um respiro transparente estreito.
 *
 * Os numeros: o pino normal e' desenhado com `getSize` 30 e o de agregador com
 * 38 (que existe so' para o quadrado sair do mesmo tamanho apesar do viewBox 160
 * do halo). `+8` poe a moldura ~3 px alem da aresta nos dois casos — o mesmo
 * respiro do halo.
 *
 * O pino que virou FOTO usa a mesma geometria do normal (viewBox 128, `getSize`
 * 30), entao nao precisa de um terceiro ramo. E' o caso em que uma variante de
 * ICONE POR REDE teria sumido em silencio, porque a foto vence a cascata do
 * `getIcon` — aqui a moldura e' uma camada propria e nao depende dessa cascata.
 */
export function tamanhoMolduraAlunos(p: Pick<Pin, 'diag'>): number {
  return (p.diag ? 38 : 30) + 8
}

/** Linha escura fina por TRAS do branco. Ver `svgMolduraAlunos`. */
const KEYLINE = 'rgb(10,16,24)'

/**
 * A moldura em si: UM SVG generico, igual para as 107 redes.
 *
 * Generico e' o ponto: uma variante por rede re-embutiria o PNG da marca em
 * base64 (as variantes de halo ja' custam ~1,44 MB em Sao Paulo) e cresceria o
 * atlas de textura por rede. Aqui e' UMA entrada de atlas no mapa inteiro.
 *
 * `stroke-width` 7 no viewBox 128 e' o MESMO tracado da borda de marca do pino
 * — por isso lê como "a borda ficou mais forte" e nao como um objeto novo.
 *
 * DOIS TRACOS, e o de baixo nao e' enfeite. A moldura e' BRANCA por decisao do
 * dono (2026-09-10): ela e o halo do agregador passam a dizer a MESMA frase —
 * "temos informacao sobre esta academia" —, e unificar o sinal foi escolha de
 * produto, nao acidente. So' que branco puro sobre o basemap CLARO (Positron)
 * desaparece, que e' exatamente o defeito que o halo do agregador tem hoje por
 * ter sido calibrado so' contra o Dark Matter. A linha escura de baixo, 3
 * unidades mais larga, sobra ~0,4 px de cada lado e da' o contraste — no tema
 * escuro ela some contra o fundo, entao um caminho de codigo serve aos dois.
 */
export function svgMolduraAlunos(cor: string, opacidade = 1): string {
  const moldura = (traco: string, largura: number, alfa: number | string) =>
    `<rect x="5.5" y="5.5" width="117" height="117" rx="27" fill="none" ` +
    `stroke="${traco}" stroke-opacity="${alfa}" stroke-width="${largura}" ` +
    `stroke-linejoin="round"/>`
  return (
    'data:image/svg+xml;utf8,' +
    encodeURIComponent(
      /* `width`/`height` EXPLICITOS, e nao so' `viewBox`: um SVG sem dimensao
         intrinseca e' rasterizado pelo navegador no default de 300x150, e o
         deck.gl — que declara o icone como 128x128 em `iconeDeck` — amostra a
         textura errada e nao desenha nada. Foi exatamente o que aconteceu na
         primeira tentativa: a camada existia, sem erro nenhum no console, e o
         mapa saia sem moldura. */
      `<svg xmlns="http://www.w3.org/2000/svg" width="128" height="128" ` +
        `viewBox="0 0 128 128">` +
        moldura(KEYLINE, 10, 0.34) +
        moldura(cor, 7, opacidade) +
        `</svg>`,
    )
  )
}
