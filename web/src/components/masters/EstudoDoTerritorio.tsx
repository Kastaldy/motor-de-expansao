import { useEffect, useState } from 'react'

import { api, ApiError } from '../../lib/api'
import type { MasterEstudo } from '../../lib/masters'
import { corDoCartao } from '../../lib/masters'
import { Eyebrow, Glass, Spinner } from '../primitives'

/* ---------------------------------------------------------------------------
   O "Onde expandir" da aba Expansão do master (BLK-MASTERS-04).

   18/11/2026, Juan: "a recomendação (igual está no relatório) para onde expandir".
   Os cartões saem da MESMA função do PDF (`relatorio_pdf.cartoes_da_analise`), pelo
   servidor: a tela só desenha. Camada de leitura, READ-ONLY.
   --------------------------------------------------------------------------- */

export default function EstudoDoTerritorio({ masterId }: { masterId: string }) {
  const [estudo, setEstudo] = useState<MasterEstudo | null>(null)
  const [erro, setErro] = useState<string | null>(null)

  useEffect(() => {
    let vivo = true
    setEstudo(null)
    setErro(null)
    api
      .masterEstudo(masterId)
      .then((e) => vivo && setEstudo(e))
      .catch((e: ApiError) => vivo && setErro(e.message))
    return () => {
      vivo = false
    }
  }, [masterId])

  return (
    <Glass style={{ padding: '14px 16px', minWidth: 0 }}>
      <Eyebrow>Onde expandir</Eyebrow>
      <div style={{ font: '400 11px/1.4 var(--f-ui)', color: 'var(--tx-sub)', margin: '3px 0 12px' }}>
        a análise de oportunidade do relatório, com os dados do motor
      </div>
      {erro ? (
        <div style={{ font: '400 12px/1.5 var(--f-ui)', color: 'var(--warn-text)' }}>{erro}</div>
      ) : !estudo ? (
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 8,
            font: '400 12px/1.5 var(--f-ui)',
            color: 'var(--tx-sub)',
          }}
        >
          <Spinner tamanho={13} />
          Calculando a análise do território; na primeira vez do dia leva até meio minuto.
        </div>
      ) : (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: 12 }}>
          {estudo.analise.map((c) => (
            <div
              key={c.titulo}
              style={{
                padding: '12px 14px 13px 16px',
                borderRadius: 'var(--r-md)',
                border: '1px solid var(--line-soft)',
                borderLeft: `4px solid ${corDoCartao(c.cor)}`,
                background: 'var(--surf-card)',
              }}
            >
              <div style={{ font: '700 14px/1.3 var(--f-ui)', color: corDoCartao(c.cor) }}>{c.titulo}</div>
              <div style={{ font: '400 12.5px/1.55 var(--f-ui)', color: 'var(--tx-soft)', marginTop: 6 }}>
                {c.texto}
              </div>
            </div>
          ))}
        </div>
      )}
    </Glass>
  )
}
