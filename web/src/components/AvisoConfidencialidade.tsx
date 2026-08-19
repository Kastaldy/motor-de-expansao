import { Botao, Eyebrow, Glass } from './primitives'

/* ---------------------------------------------------------------------------
   Aviso de confidencialidade — pop-up bloqueante de entrada (pedido do Felipe,
   2026-08-19, junto da marca d'água "ARQUIVO CONFIDENCIAL" dos PDFs).

   Aparece SEMPRE que o piloto carrega (estado local do App, sem persistência de
   propósito: cada entrada exige um novo OK) e trava o uso até o clique — não há
   fechar pelo backdrop nem por Esc. O texto é fixo de produto: deixa explícita a
   responsabilidade do usuário sobre os dados e sobre cada relatório exportado,
   que carrega registro (trilha DEC-027) e marca d'água de quem o exportou.
   --------------------------------------------------------------------------- */

export const TITULO_CONFIDENCIALIDADE = 'Aviso de confidencialidade'

export const PARAGRAFOS_CONFIDENCIALIDADE: readonly string[] = [
  'Todos os dados disponíveis neste sistema são confidenciais e de uso restrito ' +
    'da Ultra Academia. O vazamento dessas informações pode acarretar consequências ' +
    'severas para o responsável.',
  'Todos os relatórios exportados carregam registro e marca d’água de quem os ' +
    'exportou, e a responsabilidade sobre cada relatório é exclusivamente do usuário ' +
    'que o gerou.',
  'Ao clicar em OK, você declara estar ciente dessas condições.',
]

export default function AvisoConfidencialidade({ onConfirmar }: { onConfirmar: () => void }) {
  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label={TITULO_CONFIDENCIALIDADE}
      style={{
        position: 'fixed',
        inset: 0,
        zIndex: 100,
        display: 'grid',
        placeItems: 'center',
        background: 'color-mix(in srgb, var(--bg-base) 68%, transparent)',
        backdropFilter: 'blur(7px)',
      }}
    >
      <Glass
        style={{
          width: 'min(560px, calc(100vw - 48px))',
          padding: '26px 28px 24px',
          display: 'flex',
          flexDirection: 'column',
          gap: 14,
          boxShadow: 'var(--sh-pop)',
        }}
      >
        <Eyebrow dot cor="var(--warn)">
          Confidencial
        </Eyebrow>
        <h2 style={{ font: '700 19px/1.25 var(--f-ui)', color: 'var(--tx-max)', margin: 0 }}>
          {TITULO_CONFIDENCIALIDADE}
        </h2>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          {PARAGRAFOS_CONFIDENCIALIDADE.map((p) => (
            <p
              key={p.slice(0, 24)}
              style={{ font: '400 13px/1.55 var(--f-ui)', color: 'var(--tx-soft)', margin: 0 }}
            >
              {p}
            </p>
          ))}
        </div>
        <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: 4 }}>
          <Botao onClick={onConfirmar}>OK, estou ciente</Botao>
        </div>
      </Glass>
    </div>
  )
}
