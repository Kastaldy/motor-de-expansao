/**
 * O VISUAL do seletor de alcance da ficha de ponto (DEC-074): raio de 1 km, raio de 2 km e
 * 10 min de carro.
 *
 * Pedido do Vinicius (20/10/2026): "a caixa de troca entre 1km, 2km, 10min ainda está
 * muito escondida na lateral". Ela era uma fileira de pílulas vazadas de 12px, com o
 * marcado só no contorno e no texto turquesa, numa caixa cinza igual à de qualquer nota.
 * Agora é um CONTROLE SEGMENTADO da largura da ficha, dentro da identificação (logo abaixo
 * do nome e do endereço, antes dos números), com o marcado CHEIO na cor de ação do
 * sistema — o mesmo `--ac` / `--ac-on` do botão primário.
 *
 * Só a apresentação mora aqui. Quem decide QUAIS opções existem é `alcancesDisponiveis`
 * (o servidor, via `/api/me`), e quem troca é o `use-pontos` — nada disso mudou.
 *
 * Os estilos vivem num módulo puro porque o Vitest roda sem DOM: a decisão de cor só fica
 * travada se estiver num lugar que o teste alcança (o molde de `rodape-ponto`). Só
 * tokens, nunca hex cravado: o seletor tem de acompanhar os temas.
 */
import type { CSSProperties } from 'react'

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
 * Uma opção do trilho. `flex: 1` em todas: as três dividem a largura por igual, qualquer
 * que seja o rótulo — o controle se lê como UMA escolha entre partes iguais.
 *
 * Marcada: CHEIA no `--ac`, texto `--ac-on` (o par já medido para contraste nos dois
 * temas, o do botão primário). Desmarcada: sem fundo, texto `--tx-soft` em peso de botão,
 * legível sem competir com a marcada.
 */
export function estiloDaOpcaoAlcance(marcado: boolean): CSSProperties {
  return {
    flex: 1,
    minWidth: 0,
    minHeight: 38,
    padding: '9px 10px',
    borderRadius: 9,
    border: 'none',
    background: marcado ? 'var(--ac)' : 'transparent',
    color: marcado ? 'var(--ac-on)' : 'var(--tx-soft)',
    boxShadow: marcado ? 'var(--ac-glow)' : 'none',
    font: `${marcado ? 700 : 600} 13px/1.15 var(--f-ui)`,
    textAlign: 'center',
    whiteSpace: 'nowrap',
    overflow: 'hidden',
    textOverflow: 'ellipsis',
    cursor: 'pointer',
  }
}
