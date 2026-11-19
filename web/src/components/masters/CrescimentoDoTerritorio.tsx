import { useEffect, useState } from 'react'

import { api, ApiError } from '../../lib/api'
import { num } from '../../lib/format'
import type { MasterCrescimento } from '../../lib/masters'
import { alunosCurto, pct } from '../../lib/masters'
import { Glass } from '../primitives'

/* ---------------------------------------------------------------------------
   A primeira linha do painel do master: quanto ele pode crescer (BLK-MASTERS-04).

   18/11/2026, Juan: "a primeira linha (em operação, inauguração etc.), troque por
   quanto ele pode crescer na região, mostrando o residual, espaços para academias".
   Os números são os da página de regiões do relatório (`analise.comparar_regioes`
   sobre o mercado do motor): o mercado fitness, quanto redes e Ultra já atendem, o
   espaço livre (o residual do motor) e quantas academias de 2.500 alunos cabem nele.
   --------------------------------------------------------------------------- */

export default function CrescimentoDoTerritorio({ masterId }: { masterId: string }) {
  const [dados, setDados] = useState<MasterCrescimento | null>(null)
  const [erro, setErro] = useState<string | null>(null)

  useEffect(() => {
    let vivo = true
    setDados(null)
    setErro(null)
    api
      .masterCrescimento(masterId)
      .then((d) => vivo && setDados(d))
      .catch((e: ApiError) => vivo && setErro(e.message))
    return () => {
      vivo = false
    }
  }, [masterId])

  if (erro) {
    return <div style={{ font: '400 12px/1.5 var(--f-ui)', color: 'var(--warn-text)' }}>{erro}</div>
  }
  const t = dados?.total ?? null
  const maior = dados && dados.regioes.length > 1 ? dados.regioes[0] : null
  const carregando = '…'
  return (
    <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
      {/* Os quatro em destaque (18/11/2026, Juan: "mercado fitness e já atendido, deixe destacado";
          "falta os outros dois"), cada um com uma cor: turquesa para o mercado, rosa para o que já
          é atendido, verde para o espaço livre e coral para as academias que cabem nele. */}
      <KpiDestaque
        label="Mercado fitness"
        valor={t ? `${alunosCurto(t.mercado_alunos)} alunos` : carregando}
        sub="potencial do território, pelo motor"
        cor="var(--ac)"
      />
      <KpiDestaque
        label="Já atendido"
        valor={t ? pct(t.pct_atendido) : carregando}
        sub="por redes e Ultra (as independentes ficam fora da conta)"
        cor="var(--gr-rosa)"
      />
      <KpiDestaque
        label="Espaço livre (residual)"
        valor={t ? `${alunosCurto(t.espaco_livre_alunos)} alunos` : carregando}
        sub={
          // Soma por hexágono só onde sobra mercado: onde a oferta já passa dele, o hexágono conta
          // zero e não desconta dos outros. Por isso não é "mercado menos atendido" (Juan, 18/11).
          `soma de onde sobra mercado (onde a oferta já passa, conta zero)${
            maior ? `; o maior em ${maior.nome} (${alunosCurto(maior.espaco_livre_alunos)})` : ''
          }`
        }
        cor="var(--gr-verde)"
      />
      <KpiDestaque
        label="Academias que cabem"
        valor={t ? num(t.academias_que_cabem) : carregando}
        sub={`no espaço livre, de ${num(dados?.capacidade_por_academia ?? 2500)} alunos cada`}
        cor="var(--gr-coral)"
      />
    </div>
  )
}

/** Um número em destaque na linha de crescimento: cartão maior, borda e fundo na cor dele. */
function KpiDestaque({ label, valor, sub, cor }: { label: string; valor: string; sub: string; cor: string }) {
  return (
    <Glass
      style={{
        flex: 1,
        minWidth: 220,
        padding: '15px 18px',
        border: `1.5px solid ${cor}`,
        background: `color-mix(in srgb, ${cor} 9%, var(--surf-card))`,
      }}
    >
      <div
        style={{
          font: '700 11px/1.2 var(--f-ui)',
          color: cor,
          textTransform: 'uppercase',
          letterSpacing: '0.06em',
        }}
      >
        {label}
      </div>
      <div
        className="num"
        style={{
          font: '700 34px/1 var(--f-num)',
          color: cor,
          marginTop: 8,
          whiteSpace: 'nowrap',
          overflow: 'hidden',
          textOverflow: 'ellipsis',
        }}
      >
        {valor}
      </div>
      <div style={{ font: '400 11px/1.3 var(--f-ui)', color: 'var(--tx-sub)', marginTop: 6 }}>{sub}</div>
    </Glass>
  )
}
