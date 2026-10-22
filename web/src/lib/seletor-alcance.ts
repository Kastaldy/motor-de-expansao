/**
 * O VISUAL do seletor de alcance da ficha de ponto (DEC-074): raio de 1 km, raio de 2 km,
 * 5 e 10 min de carro.
 *
 * Pedido do Vinicius (20/10/2026): "a caixa de troca entre 1km, 2km, 10min ainda está
 * muito escondida na lateral". Ela era uma fileira de pílulas vazadas de 12px, com o
 * marcado só no contorno e no texto turquesa, numa caixa cinza igual à de qualquer nota.
 * Agora é um CONTROLE SEGMENTADO da largura da ficha, dentro da identificação (logo abaixo
 * do nome e do endereço, antes dos números), com o marcado CHEIO no turquesa de texto do
 * tema (`--ac-text`) e o texto em `--ac-on` — ver `estiloDaOpcaoAlcance` para o porquê.
 *
 * Só a apresentação mora aqui. Quem decide QUAIS opções existem é `alcancesDisponiveis`
 * (o servidor, via `/api/me`), e quem troca é o `use-pontos` — nada disso mudou.
 *
 * Os estilos vivem num módulo puro porque o Vitest roda sem DOM: a decisão de cor só fica
 * travada se estiver num lugar que o teste alcança (o molde de `rodape-ponto`). Só
 * tokens, nunca hex cravado: o seletor tem de acompanhar os temas.
 */
import type { CSSProperties } from 'react'

import type { Alcance } from './alcance'

/** O rótulo visível do grupo (é também o nome acessível do `radiogroup`). */
export const ROTULO_SELETOR_ALCANCE = 'Alcance da análise'

/**
 * A releitura em voo, DITA em texto e não só no spinner: trocar o alcance relê o ponto no
 * servidor, e a isócrona leva alguns segundos — um spinner mudo ao lado do rótulo passava
 * despercebido, e o operador clicava de novo achando que nada tinha acontecido.
 */
export const AVISO_RELENDO_ALCANCE = 'Atualizando a ficha…'

/**
 * O trilho do controle: uma faixa só, com as opções dentro, da largura da ficha. O fundo
 * levemente turquesa é o que tira o seletor do cinza das notas em volta.
 */
export const ESTILO_TRILHO_ALCANCE: CSSProperties = {
  display: 'flex',
  gap: 4,
  padding: 4,
  borderRadius: 12,
  border: '1px solid var(--ac-a45)',
  background: 'var(--ac-a08)',
}

/** O rótulo acima do trilho: forte o bastante para ser lido como título do controle. */
export const ESTILO_ROTULO_ALCANCE: CSSProperties = {
  display: 'inline-flex',
  alignItems: 'center',
  gap: 8,
  font: '600 12.5px/1.3 var(--f-ui)',
  color: 'var(--tx-strong)',
}

/**
 * O par de cores da opção MARCADA: fundo `--ac-text`, texto `--ac-on`.
 *
 * Contraste medido (WCAG 2.1, luminância relativa) para texto de 13px, que pede 4,5:1:
 *  - tema claro: branco sobre `--ac-text` #087a72 = 5,20:1 (o `--ac` #00a294 do botão
 *    primário dava só 3,18:1 — ele passa no piso de 3:1 de texto GRANDE, não aqui);
 *  - tema escuro: #06232a sobre `--ac-text` #4ad8cb = 9,34:1 (o `--ac` dava 8,45:1);
 *  - escopos de superfície teal do tema claro, onde `--ac-text` vira branco: `--ac-on`
 *    #00736c (`.rail-ultra`/`.painel-marca`) = 5,72:1 e #006158 (`.barra-ultra`) = 7,37:1.
 * O comentário anterior chamava o par `--ac`/`--ac-on` de "já medido nos dois temas": a
 * medida que existia era a do botão primário, de texto grande, e não valia para 13px.
 */
export const FUNDO_OPCAO_MARCADA = 'var(--ac-text)'

/**
 * O rótulo VISÍVEL de cada opção, em duas linhas curtas: o valor ("5 min") e o tipo
 * ("de carro"). Pedido do Vinicius (print de 21/10/2026): na largura de nascença da ficha
 * (480 px) cada opção tem ~77 px de texto, e "5 min de carro"/"10 min de carro" saíam
 * cortados em reticências. O rótulo INTEIRO (`ROTULO_ALCANCE`) continua sendo o nome
 * acessível e o `title` do botão.
 */
export const ROTULO_CURTO_ALCANCE: Readonly<Record<Alcance, { valor: string; tipo: string }>> = Object.freeze({
  raio_1km: { valor: '1 km', tipo: 'raio' },
  raio_2km: { valor: '2 km', tipo: 'raio' },
  carro_5min: { valor: '5 min', tipo: 'de carro' },
  carro_10min: { valor: '10 min', tipo: 'de carro' },
})

/** A segunda linha (o tipo): menor e mais leve, na cor do botão (marcado ou não). */
export const ESTILO_TIPO_ALCANCE: CSSProperties = {
  font: '500 10.5px/1.1 var(--f-ui)',
  opacity: 0.85,
  overflow: 'hidden',
  textOverflow: 'ellipsis',
  maxWidth: '100%',
}
export const TEXTO_OPCAO_MARCADA = 'var(--ac-on)'

/**
 * Uma opção do trilho. `flex: 1` em todas: as opções dividem a largura por igual, qualquer
 * que seja o rótulo — o controle se lê como UMA escolha entre partes iguais.
 *
 * Marcada: CHEIA em `FUNDO_OPCAO_MARCADA` com `TEXTO_OPCAO_MARCADA` (contraste medido
 * acima). Desmarcada: sem fundo, texto `--tx-soft` em peso de botão, legível sem competir
 * com a marcada.
 */
export function estiloDaOpcaoAlcance(marcado: boolean): CSSProperties {
  return {
    flex: 1,
    minWidth: 0,
    minHeight: 38,
    /* Duas linhas (valor + tipo) empilhadas e centradas. Recuo lateral de 4 px: cabe
       "10 min" até na largura MÍNIMA da janela (320 px). */
    display: 'grid',
    placeItems: 'center',
    alignContent: 'center',
    gap: 1,
    padding: '6px 4px',
    borderRadius: 9,
    border: 'none',
    background: marcado ? FUNDO_OPCAO_MARCADA : 'transparent',
    color: marcado ? TEXTO_OPCAO_MARCADA : 'var(--tx-soft)',
    boxShadow: marcado ? 'var(--ac-glow)' : 'none',
    font: `${marcado ? 700 : 600} 13px/1.15 var(--f-ui)`,
    textAlign: 'center',
    whiteSpace: 'nowrap',
    overflow: 'hidden',
    textOverflow: 'ellipsis',
    cursor: 'pointer',
  }
}
