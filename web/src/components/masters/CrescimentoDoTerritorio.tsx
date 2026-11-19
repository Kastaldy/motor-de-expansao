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
      {/* Os quatro no cartão da carteira (19/11/2026, Juan: escuros, com as letras brancas). */}
      <KpiDestaque
        label="Mercado fitness"
        valor={t ? `${alunosCurto(t.mercado_alunos)} alunos` : carregando}
        sub="potencial do território, pelo motor"
      />
      <KpiDestaque
        label="Já atendido"
        valor={t ? pct(t.pct_atendido) : carregando}
        sub="por redes e Ultra (as independentes ficam fora da conta)"
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
      />
      <KpiDestaque
        label="Academias que cabem"
        valor={t ? num(t.academias_que_cabem) : carregando}
        sub={`no espaço livre, de ${num(dados?.capacidade_por_academia ?? 2500)} alunos cada`}
      />
    </div>
  )
}

/** Um número da linha de crescimento no cartão da carteira (19/11/2026, Juan: "deixe ela escura
 *  com as letras brancas, igual a da carteira"): os mesmos tokens `--kpi-*`, que já sabem do tema. */
function KpiDestaque({ label, valor, sub }: { label: string; valor: string; sub: string }) {
  return (
    <Glass
      style={{
        flex: '1 1 200px',
        minWidth: 0,
        padding: '13px 15px',
        background: 'var(--kpi-fundo)',
        border: '1px solid var(--kpi-borda)',
      }}
    >
      <div style={{ font: '600 10.5px/1.2 var(--f-ui)', color: 'var(--kpi-rotulo)' }}>{label}</div>
      <div
        className="num"
        style={{
          font: '700 22px/1 var(--f-num)',
          color: 'var(--kpi-valor)',
          marginTop: 7,
          whiteSpace: 'nowrap',
          overflow: 'hidden',
          textOverflow: 'ellipsis',
        }}
      >
        {valor}
      </div>
      <div style={{ font: '400 10.5px/1.3 var(--f-ui)', color: 'var(--kpi-apoio)', marginTop: 6 }}>{sub}</div>
    </Glass>
  )
}
