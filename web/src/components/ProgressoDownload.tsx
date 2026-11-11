import { useEffect, useState } from 'react'

import { assinarProgressoDownload, type ProgressoDownload as Progresso } from '../lib/api'

/* ---------------------------------------------------------------------------
   Faixa de PROGRESSO dos downloads (11/11/2026).

   O Estudo pontual chegava a ~6 MB e, numa conexão lenta, levava minutos para chegar. O
   botão só dizia "Gerando…", e a pessoa recarregava a página achando que tinha travado —
   o que cortava o download no meio (Daniele, 11/11). Esta faixa diz em que pé está: o
   servidor ainda gerando, ou quanto do arquivo já chegou. Vale para TODO download que
   passa por `pedirArquivo` (estudo, relatório municipal, PDFs da rede, planilhas), sem
   tocar em cada tela.
   --------------------------------------------------------------------------- */

const MB = 1024 * 1024

/** O texto da faixa — puro, testável sem DOM. */
export function textoDoProgresso(p: Progresso): string {
  if (p.recebidos === 0) return 'Gerando o arquivo no servidor… não recarregue a página.'
  const recebidos = (p.recebidos / MB).toLocaleString('pt-BR', { maximumFractionDigits: 1 })
  if (p.total == null) return `Baixando o arquivo… ${recebidos} MB recebidos.`
  const pct = Math.min(100, Math.floor((p.recebidos / p.total) * 100))
  const total = (p.total / MB).toLocaleString('pt-BR', { maximumFractionDigits: 1 })
  return `Baixando o arquivo… ${pct}% (${recebidos} de ${total} MB).`
}

export default function ProgressoDownload() {
  const [p, setP] = useState<Progresso | null>(null)
  useEffect(() => assinarProgressoDownload(setP), [])
  if (!p) return null
  const fracao = p.total ? Math.min(1, p.recebidos / p.total) : null
  return (
    <div
      role="status"
      aria-live="polite"
      style={{
        position: 'fixed',
        left: '50%',
        bottom: 24,
        transform: 'translateX(-50%)',
        zIndex: 90,
        minWidth: 280,
        maxWidth: 'calc(100vw - 32px)',
        padding: '10px 16px',
        borderRadius: 10,
        background: 'var(--surf-raised)',
        color: 'var(--tx-strong)',
        boxShadow: '0 6px 24px rgba(0,0,0,.25)',
        font: '500 13px/1.4 var(--f-ui)',
      }}
    >
      {textoDoProgresso(p)}
      {fracao != null && (
        <div style={{ marginTop: 8, height: 4, borderRadius: 2, background: 'rgba(127,127,127,.3)' }}>
          <div
            style={{
              width: `${fracao * 100}%`,
              height: '100%',
              borderRadius: 2,
              background: 'var(--acc, #3fb6a8)',
            }}
          />
        </div>
      )}
    </div>
  )
}
