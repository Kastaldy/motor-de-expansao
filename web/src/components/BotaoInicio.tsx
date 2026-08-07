/**
 * "Voltar ao início" — o mesmo botao, na MESMA posicao, no header das tres telas.
 *
 * Existe como componente proprio (e nao copiado em cada tela) porque o pedido era
 * literalmente "adicionar em TODOS um botao de voltar para o menu principal": se cada
 * header desenhar o seu, eles divergem no primeiro ajuste de estilo.
 *
 * NAO limpa estado nenhum. A foto do mapa (`lib/mapa-estado`) continua valendo, e
 * `fotoAplicavel` ja descarta sozinha quando UF/municipio nao batem — voltar ao menu e
 * reentrar no mapa devolve a tela como estava.
 */
export default function BotaoInicio({ onInicio }: { onInicio: () => void }) {
  return (
    <button
      type="button"
      onClick={onInicio}
      title="Voltar ao menu principal"
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: 6,
        flexShrink: 0,
        padding: '6px 10px',
        borderRadius: 8,
        border: '1px solid var(--line-soft)',
        background: 'var(--surf-raised)',
        color: 'var(--tx-soft)',
        font: '600 11.5px/1 var(--f-ui)',
        transition: 'filter .15s ease',
      }}
      onMouseEnter={(e) => {
        e.currentTarget.style.filter = 'brightness(1.15)'
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.filter = 'none'
      }}
    >
      <svg
        width="13"
        height="13"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
        aria-hidden
      >
        <path d="M19 12H5M12 19l-7-7 7-7" />
      </svg>
      Início
    </button>
  )
}
