import type { Tela } from '../App'

/* Dock vertical fixo. No piloto so as duas telas do escopo estao ativas; as
   demais aparecem desabilitadas para o operador entender que o mapa e a
   viabilidade sao um recorte, nao o produto inteiro. */

const ICONES: Record<string, React.JSX.Element> = {
  inicio: (
    <>
      <path d="M4 10.5 12 4l8 6.5V20a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1v-9.5Z" />
      <path d="M9.5 21v-6h5v6" />
    </>
  ),
  mapa: (
    <>
      <path d="M12 21s7-5.6 7-11a7 7 0 1 0-14 0c0 5.4 7 11 7 11Z" />
      <circle cx="12" cy="10" r="2.6" />
    </>
  ),
  exec: (
    <>
      <path d="M4 19V9M10 19V5M16 19v-7M22 19H2" />
    </>
  ),
  dom: (
    <>
      <circle cx="12" cy="12" r="8.5" />
      <circle cx="12" cy="12" r="4" />
    </>
  ),
  cart: (
    <>
      <path d="M4 6h16M4 12h16M4 18h10" />
    </>
  ),
  viab: (
    <>
      <path d="M3 17l5.5-6 4 3.5L21 6" />
      <path d="M15 6h6v6" />
    </>
  ),
}

const ITENS: { id: string; tela: Tela | null; titulo: string }[] = [
  // O inicio abre a fila do Dock: e' a porta de entrada e, ao mesmo tempo, o caminho de
  // volta ao menu presente em TODAS as telas — o botao "Início" do header e o par dele.
  { id: 'inicio', tela: 'inicio', titulo: 'Início — escolher a análise' },
  { id: 'mapa', tela: 'mapa', titulo: 'Mapa territorial' },
  { id: 'exec', tela: 'executiva', titulo: 'Visão executiva' },
  { id: 'dom', tela: null, titulo: 'Expansão de domínio (fora do piloto)' },
  { id: 'cart', tela: null, titulo: 'Carteira e plano (fora do piloto)' },
  { id: 'viab', tela: 'viabilidade', titulo: 'Viabilidade do ponto' },
]

export default function Dock({
  tela,
  onTela,
}: {
  tela: Tela
  onTela: (t: Tela) => void
}) {
  return (
    <nav
      aria-label="Navegação principal"
      style={{
        width: 70,
        flexShrink: 0,
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        gap: 8,
        padding: '14px 8px',
        background: 'var(--surf-chrome)',
        borderRight: '1px solid var(--line-soft)',
        backdropFilter: 'blur(14px)',
        zIndex: 20,
      }}
    >
      <div
        aria-hidden
        style={{
          width: 42,
          height: 42,
          borderRadius: 11,
          overflow: 'hidden',
          marginBottom: 6,
          flexShrink: 0,
          background: '#fff',
          display: 'grid',
          placeItems: 'center',
        }}
      >
        <img
          src="/logo-ultra.png"
          alt="Ultra Academia"
          style={{ width: '100%', height: '100%', objectFit: 'cover' }}
        />
      </div>

      {ITENS.map((it) => {
        const ativo = it.tela !== null && it.tela === tela
        const disponivel = it.tela !== null
        return (
          <button
            key={it.id}
            type="button"
            title={it.titulo}
            aria-label={it.titulo}
            aria-current={ativo ? 'page' : undefined}
            disabled={!disponivel}
            onClick={() => it.tela && onTela(it.tela)}
            style={{
              width: 42,
              height: 42,
              borderRadius: 11,
              display: 'grid',
              placeItems: 'center',
              background: ativo ? 'var(--ac-a16)' : 'transparent',
              color: ativo
                ? 'var(--ac-text)'
                : disponivel
                  ? 'var(--tx-muted)'
                  : 'var(--tx-rank)',
              opacity: disponivel ? 1 : 0.5,
              transition: 'background .15s ease, color .15s ease',
            }}
          >
            <svg
              width="19"
              height="19"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="1.6"
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              {ICONES[it.id]}
            </svg>
          </button>
        )
      })}
    </nav>
  )
}
