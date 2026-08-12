import type { Tema } from '../../lib/tema'
import { outroTema } from '../../lib/tema'

/* ---------------------------------------------------------------------------
   Sol/lua da Visão Executiva.

   Mostra o ícone do tema para o qual se VAI, não o do tema em que se está: é o
   que o botão faz, e é como todo alternador de tema que a pessoa já usou se
   comporta. Estando no escuro, aparece o sol.

   O ícone sozinho não conta a história para quem usa leitor de tela nem para
   quem passa o mouse em dúvida, então `aria-label` e `title` dizem a AÇÃO por
   extenso. Não é `aria-pressed`: o botão não liga nem desliga nada, ele troca
   entre dois estados nomeados, e "pressionado" não diria qual dos dois.
   --------------------------------------------------------------------------- */

export default function BotaoTema({ tema, onTema }: { tema: Tema; onTema: (t: Tema) => void }) {
  const alvo = outroTema(tema)
  const rotulo = alvo === 'claro' ? 'Mudar para o tema claro' : 'Mudar para o tema escuro'

  return (
    <button
      type="button"
      title={rotulo}
      aria-label={rotulo}
      onClick={() => onTema(alvo)}
      style={{
        width: 28,
        height: 28,
        flexShrink: 0,
        display: 'grid',
        placeItems: 'center',
        borderRadius: 'var(--r-sm)',
        border: '1px solid var(--line-soft)',
        background: 'var(--surf-raised)',
        color: 'var(--tx-soft)',
        cursor: 'pointer',
      }}
    >
      {alvo === 'claro' ? <Sol /> : <Lua />}
    </button>
  )
}

/* Os dois traçados são `currentColor` e `stroke`, sem preenchimento: assim o ícone
   herda a cor do botão e não precisa de uma variante por tema. 15 px é o tamanho em
   que o miolo do sol e os oito raios ainda se separam. */

function Sol() {
  return (
    <svg width={15} height={15} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.9} strokeLinecap="round" aria-hidden>
      <circle cx={12} cy={12} r={4.2} />
      <path d="M12 2.4v2.3M12 19.3v2.3M4.2 4.2l1.6 1.6M18.2 18.2l1.6 1.6M2.4 12h2.3M19.3 12h2.3M4.2 19.8l1.6-1.6M18.2 5.8l1.6-1.6" />
    </svg>
  )
}

function Lua() {
  // Crescente por SUBTRAÇÃO de dois círculos, e não um arco desenhado à mão: o arco
  // fechava com as pontas grossas e a lua lia como uma vírgula.
  return (
    <svg width={15} height={15} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.9} strokeLinejoin="round" aria-hidden>
      <path d="M20.5 14.6A8.9 8.9 0 0 1 9.4 3.5a8.9 8.9 0 1 0 11.1 11.1Z" />
    </svg>
  )
}
