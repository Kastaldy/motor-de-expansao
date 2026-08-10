import { COR_SEVERIDADE, rotuloMesCurto } from '../../lib/exec'
import { brlCurto, num, pct } from '../../lib/format'
import { caminhoSparkline, escalaDeBarras, fatiasDeRosca, percentualDaFatia } from '../../lib/sparkline'
import type { RedeCoorteComparacao } from '../../lib/types'

/* ---------------------------------------------------------------------------
   Gráficos da Visão Executiva. SVG escrito à mão, como o resto do produto —
   deriva de `CascataDre`/`RampaAlunos` (`ViabilityCharts.tsx`).

   Regra que vale para todos: a base da escala é ZERO. Começar no mínimo da série
   faz uma variação de 2% parecer queda pela metade, e é exatamente o defeito da
   escala congelada do bloco diário da planilha que o time usa hoje.
   --------------------------------------------------------------------------- */

const EIXO = 'var(--line-mid)'

export function BarrasPeriodo({
  meses,
  valores,
  altura = 132,
  cor = 'var(--ac)',
  formato = 'brl',
  titulo,
}: {
  meses: string[]
  valores: (number | null)[]
  altura?: number
  cor?: string
  formato?: 'brl' | 'int' | 'pct'
  titulo?: string
}) {
  const escala = escalaDeBarras(valores)
  const fmt = (v: number | null) =>
    v === null ? '—' : formato === 'brl' ? brlCurto(v) : formato === 'pct' ? pct(v, 1) : num(v)
  const largura = 100 / Math.max(meses.length, 1)

  return (
    <figure style={{ margin: 0 }}>
      {titulo && (
        <figcaption style={{ font: '500 11px/1.2 var(--f-ui)', color: 'var(--tx-label)', marginBottom: 8 }}>
          {titulo}
        </figcaption>
      )}
      <div style={{ display: 'flex', alignItems: 'flex-end', gap: 3, height: altura }}>
        {meses.map((m, i) => {
          const fracao = Math.max(escala[i] ?? 0, 0)
          const valor = valores[i] ?? null
          return (
            <div
              key={m}
              title={`${m}: ${fmt(valor)}`}
              style={{ width: `${largura}%`, display: 'flex', flexDirection: 'column', justifyContent: 'flex-end', height: '100%' }}
            >
              {/* O número vai SOBRE a barra. Comparar alturas responde "subiu ou caiu";
                  só o valor responde "quanto" — e é o valor que vai para a conversa com
                  o franqueado. */}
              <span
                className="num"
                style={{
                  font: '600 9px/1 var(--f-num)',
                  color: 'var(--tx-sub)',
                  textAlign: 'center',
                  marginBottom: 3,
                  whiteSpace: 'nowrap',
                  overflow: 'visible',
                }}
              >
                {valor === null ? '' : fmt(valor)}
              </span>
              <div
                style={{
                  height: `${Math.max(fracao * 100, valor === null ? 0 : 1.5)}%`,
                  background: i === meses.length - 1 ? cor : `color-mix(in srgb, ${cor} 55%, transparent)`,
                  borderRadius: '3px 3px 0 0',
                  minHeight: valor === null ? 0 : 2,
                }}
              />
            </div>
          )
        })}
      </div>
      <div style={{ display: 'flex', gap: 3, marginTop: 5 }}>
        {meses.map((m) => (
          <span
            key={m}
            className="num"
            style={{ width: `${largura}%`, font: '500 9px/1 var(--f-num)', color: 'var(--tx-muted)', textAlign: 'center' }}
          >
            {rotuloMesCurto(m)}
          </span>
        ))}
      </div>
    </figure>
  )
}

export function LinhaPeriodo({
  meses,
  valores,
  altura = 108,
  cor = 'var(--ac)',
  titulo,
  formato = 'int',
}: {
  meses: string[]
  valores: (number | null)[]
  altura?: number
  cor?: string
  titulo?: string
  formato?: 'brl' | 'int' | 'pct'
}) {
  const largura = 340
  const topo = 14 // espaço reservado para os rótulos de valor, que ficam ACIMA dos pontos
  const s = caminhoSparkline(valores, largura, altura - topo, 6)
  const fmt = (v: number) => (formato === 'brl' ? brlCurto(v) : formato === 'pct' ? pct(v, 1) : num(v, 1))
  const passo = valores.length > 1 ? (largura - 12) / (valores.length - 1) : 0
  // Com 12 meses os rótulos se encavalariam; alterna para caber sem sobrepor.
  const alternar = valores.filter((v) => v !== null).length > 7

  return (
    <figure style={{ margin: 0 }}>
      {titulo && (
        <figcaption style={{ font: '500 11px/1.2 var(--f-ui)', color: 'var(--tx-label)', marginBottom: 6 }}>
          {titulo}
        </figcaption>
      )}
      <svg viewBox={`0 0 ${largura} ${altura}`} width="100%" height={altura} role="img" aria-label={titulo}>
        <g transform={`translate(0 ${topo})`}>
          <line x1={0} y1={altura - topo - 1} x2={largura} y2={altura - topo - 1} stroke={EIXO} strokeWidth={1} />
          {s.area && <path d={s.area} fill={cor} opacity={0.12} />}
          <path d={s.linha} fill="none" stroke={cor} strokeWidth={1.8} strokeLinejoin="round" />
          {s.ultimo && <circle cx={s.ultimo.x} cy={s.ultimo.y} r={3} fill={cor} />}
        </g>
        {/* Valor MÊS A MÊS. Antes só saíam o mínimo e o máximo, e o operador não
            conseguia ler nenhum ponto do meio da série sem passar o mouse. */}
        {valores.map((v, i) => {
          if (v === null || !Number.isFinite(v)) return null
          if (alternar && i % 2 === 1 && i !== valores.length - 1) return null
          const x = 6 + passo * i
          const y =
            topo +
            (s.maximo === s.minimo
              ? (altura - topo) / 2
              : 6 + (altura - topo - 12) * (1 - (v - s.minimo) / (s.maximo - s.minimo)))
          return (
            <text
              key={i}
              x={Math.min(Math.max(x, 12), largura - 12)}
              y={Math.max(y - 6, 9)}
              textAnchor="middle"
              style={{ font: '600 8.5px/1 var(--f-num)', fill: 'var(--tx-sub)' }}
            >
              {fmt(v)}
            </text>
          )
        })}
      </svg>
      <div style={{ display: 'flex', gap: 2 }}>
        {meses.map((m) => (
          <span
            key={m}
            className="num"
            style={{
              flex: 1,
              font: '500 8.5px/1 var(--f-num)',
              color: 'var(--tx-muted)',
              textAlign: 'center',
            }}
          >
            {rotuloMesCurto(m)}
          </span>
        ))}
      </div>
    </figure>
  )
}

/**
 * Onde a unidade está dentro da distribuição dos pares — p25, mediana, p75 e a marca
 * dela. A degradação (`base_rotulo`) é impressa junto, SEMPRE: sem isso, "percentil 41"
 * não diz contra quem.
 */
export function ComparativoCoorte({
  comparacao,
  metricas,
  rotulos,
  formato,
}: {
  comparacao: RedeCoorteComparacao
  metricas: string[]
  rotulos: Record<string, string>
  formato: Record<string, 'brl' | 'int' | 'pct' | 'nota'>
}) {
  const fmt = (v: number | null, f: string) =>
    v === null ? '—' : f === 'brl' ? brlCurto(v) : f === 'pct' ? pct(v, 1) : num(v, f === 'nota' ? 0 : 0)

  return (
    <div>
      <div style={{ font: '400 10.5px/1.4 var(--f-ui)', color: 'var(--tx-muted)', marginBottom: 10 }}>
        Comparada com {comparacao.n} unidades · {comparacao.base_rotulo}
      </div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
        {metricas.map((chave) => {
          const r = comparacao.metricas[chave]
          if (!r || r.unidade === null) return null
          const escala = [r.p25, r.p50, r.p75, r.unidade].filter(
            (v): v is number => v !== null && Number.isFinite(v),
          )
          const min = Math.min(0, ...escala)
          const max = Math.max(...escala, 1)
          const posicao = (v: number | null) =>
            v === null ? null : (100 * (v - min)) / (max - min || 1)
          const f = formato[chave] ?? 'int'
          return (
            <div key={chave}>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 5 }}>
                <span style={{ font: '500 11px/1 var(--f-ui)', color: 'var(--tx-label)' }}>
                  {rotulos[chave] ?? chave}
                </span>
                <span className="num" style={{ font: '600 11px/1 var(--f-num)', color: 'var(--tx-strong)' }}>
                  {fmt(r.unidade, f)}
                  {r.percentil !== null && (
                    <span style={{ color: 'var(--tx-muted)', fontWeight: 400 }}>
                      {' '}
                      · percentil {Math.round(r.percentil)}
                    </span>
                  )}
                </span>
              </div>
              <div style={{ position: 'relative', height: 14 }}>
                <div
                  style={{
                    position: 'absolute',
                    left: `${posicao(r.p25) ?? 0}%`,
                    width: `${(posicao(r.p75) ?? 0) - (posicao(r.p25) ?? 0)}%`,
                    top: 4,
                    height: 6,
                    background: 'var(--surf-raised)',
                    borderRadius: 3,
                  }}
                  title={`Metade das unidades da base fica entre ${fmt(r.p25, f)} e ${fmt(r.p75, f)}`}
                />
                {r.p50 !== null && (
                  <div
                    title={`Mediana da base: ${fmt(r.p50, f)}`}
                    style={{
                      position: 'absolute',
                      left: `${posicao(r.p50)}%`,
                      top: 1,
                      width: 2,
                      height: 12,
                      background: 'var(--tx-soft)',
                    }}
                  />
                )}
                <div
                  title={`Esta unidade: ${fmt(r.unidade, f)}`}
                  style={{
                    position: 'absolute',
                    left: `calc(${posicao(r.unidade)}% - 4px)`,
                    top: 0,
                    width: 8,
                    height: 14,
                    borderRadius: 2,
                    background: 'var(--ac)',
                  }}
                />
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}

/**
 * Funil comercial do mês. NUNCA clampado em 100%: na base real, `vendas > convertidos`
 * em 75% das linhas. Clampar esconderia um problema de coleta em vez de mostrá-lo — por
 * isso o aviso vem do servidor e é impresso como está.
 */
export function FunilComercial({
  visitas,
  convertidos,
  vendas,
  novosAlunos,
  conversao,
  aviso,
}: {
  visitas: number | null
  convertidos: number | null
  vendas: number | null
  novosAlunos: number | null
  conversao: number | null
  aviso: string | null
}) {
  const etapas = [
    { rotulo: 'Visitas', valor: visitas, cor: 'var(--ac)' },
    { rotulo: 'Convertidos', valor: convertidos, cor: '#6fa4f7' },
    { rotulo: 'Vendas', valor: vendas, cor: '#d94a86' },
    { rotulo: 'Novos alunos', valor: novosAlunos, cor: '#5fd08c' },
  ]
  const base = Math.max(...etapas.map((e) => e.valor ?? 0), 1)
  return (
    <div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        {etapas.map((e) => (
          <div key={e.rotulo} style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <span style={{ width: 96, font: '400 11px/1 var(--f-ui)', color: 'var(--tx-label)' }}>
              {e.rotulo}
            </span>
            <div style={{ flex: 1, height: 14, background: 'var(--surf-raised)', borderRadius: 3 }}>
              <div
                style={{
                  width: `${(100 * (e.valor ?? 0)) / base}%`,
                  height: '100%',
                  background: e.cor,
                  borderRadius: 3,
                }}
              />
            </div>
            <span className="num" style={{ width: 56, textAlign: 'right', font: '600 11.5px/1 var(--f-num)', color: 'var(--tx-strong)' }}>
              {num(e.valor)}
            </span>
          </div>
        ))}
      </div>
      <div style={{ marginTop: 10, font: '400 11px/1.5 var(--f-ui)', color: 'var(--tx-sub)' }}>
        Conversão de visita em aluno: <strong style={{ color: 'var(--tx-strong)' }}>{pct(conversao, 1)}</strong>
        {/* O par absoluto vem junto do percentual: "40%" de 10 visitas e "40%" de 900 são
            problemas de tamanho diferente, e sem os dois números o operador refazia a
            conta de cabeça para saber de qual dos dois se tratava. */}
        {visitas !== null && convertidos !== null && (
          <span style={{ color: 'var(--tx-muted)' }}>
            {' '}({num(convertidos)} de {num(visitas)} visitas)
          </span>
        )}
        {aviso && (
          <div style={{ marginTop: 4, color: COR_SEVERIDADE.media }}>{aviso}</div>
        )}
      </div>
    </div>
  )
}

/** Banner do diagnóstico: uma cor, uma frase e o que fazer. */
export function BannerRecomendacao({
  severidade,
  titulo,
  resumo,
  recomendacoes,
  competencia,
}: {
  severidade: keyof typeof COR_SEVERIDADE
  titulo: string
  resumo: string
  recomendacoes: { codigo: string; titulo: string; corpo: string }[]
  competencia: string | null
}) {
  const cor = COR_SEVERIDADE[severidade]
  return (
    <div
      style={{
        border: `1px solid ${cor}55`,
        background: `${cor}12`,
        borderRadius: 'var(--r-lg)',
        padding: '14px 16px',
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        <span style={{ width: 9, height: 9, borderRadius: '50%', background: cor, flexShrink: 0 }} />
        <span style={{ font: '700 12px/1 var(--f-ui)', color: cor, textTransform: 'uppercase', letterSpacing: '.05em' }}>
          {titulo}
        </span>
        {competencia && (
          <span className="num" style={{ font: '500 10px/1 var(--f-num)', color: 'var(--tx-muted)' }}>
            base: {competencia}
          </span>
        )}
      </div>
      <p style={{ margin: '10px 0 0', font: '400 12.5px/1.6 var(--f-ui)', color: 'var(--tx-narrative)' }}>
        {resumo}
      </p>
      {recomendacoes.length > 0 && (
        <div style={{ marginTop: 12, display: 'flex', flexDirection: 'column', gap: 10 }}>
          {recomendacoes.map((r) => (
            <div key={r.codigo}>
              <div style={{ font: '600 12px/1.2 var(--f-ui)', color: 'var(--tx-strong)' }}>{r.titulo}</div>
              <div style={{ font: '400 11.5px/1.55 var(--f-ui)', color: 'var(--tx-narrative)', marginTop: 3 }}>
                {r.corpo}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}


/**
 * Rosca de duas fatias — recorrentes x agregadores.
 *
 * Duas fatias não pedem um gráfico, e uma barra segmentada bastaria; a rosca entra
 * porque a composição da base é uma pergunta que o time faz sozinha ("quanto da minha
 * base é agregador?"), e uma forma própria a separa do resto da leitura. O número vai no
 * miolo: a fatia responde "muito ou pouco", só o número responde "quanto".
 */
export function Rosca({
  partes,
  tamanho = 132,
  espessura = 20,
  centroRotulo,
  centroValor,
}: {
  partes: { rotulo: string; valor: number; cor: string }[]
  tamanho?: number
  espessura?: number
  centroRotulo?: string
  centroValor?: string
}) {
  const raio = (tamanho - espessura) / 2
  const centro = tamanho / 2
  // A conta vive em `lib/sparkline` porque existe DUAS vezes no produto — aqui e no
  // gerador de PDF, em Python — e as duas precisam concordar sobre 100%, fatia vazia e
  // total zero. Foi exatamente nesses três casos que a versão Python errou.
  const { fatias, total } = fatiasDeRosca(partes, raio)

  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 16, flexWrap: 'wrap' }}>
      <svg width={tamanho} height={tamanho} role="img" aria-label={centroRotulo ?? 'Composição'}>
        <circle
          cx={centro}
          cy={centro}
          r={raio}
          fill="none"
          stroke="var(--surf-raised)"
          strokeWidth={espessura}
        />
        {total > 0 &&
          fatias
            .filter((f) => f.fracao > 0)
            .map((f) => (
              <circle
                key={f.rotulo}
                cx={centro}
                cy={centro}
                r={raio}
                fill="none"
                stroke={f.cor}
                strokeWidth={espessura}
                strokeDasharray={f.traco}
                strokeDashoffset={f.deslocamento}
                // -90° põe o início da primeira fatia no topo, que é onde o olho começa.
                transform={`rotate(-90 ${centro} ${centro})`}
              >
                <title>{`${f.rotulo}: ${num(f.valor)} (${pct(percentualDaFatia(f.valor, total) ?? 0, 0)})`}</title>
              </circle>
            ))}
        {centroValor && (
          <text
            x={centro}
            y={centro - 1}
            textAnchor="middle"
            style={{ font: '700 19px/1 var(--f-num)', fill: 'var(--tx-max)' }}
          >
            {centroValor}
          </text>
        )}
        {centroRotulo && (
          <text
            x={centro}
            y={centro + 14}
            textAnchor="middle"
            style={{ font: '500 8.5px/1 var(--f-ui)', fill: 'var(--tx-muted)' }}
          >
            {centroRotulo}
          </text>
        )}
      </svg>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8, minWidth: 132 }}>
        {partes.map((p) => (
          <div key={p.rotulo} style={{ display: 'flex', alignItems: 'baseline', gap: 8 }}>
            <span
              style={{ width: 9, height: 9, borderRadius: 2, background: p.cor, flexShrink: 0 }}
            />
            <span style={{ font: '400 11px/1.3 var(--f-ui)', color: 'var(--tx-label)', flex: 1 }}>
              {p.rotulo}
            </span>
            <span className="num" style={{ font: '600 12px/1 var(--f-num)', color: 'var(--tx-strong)' }}>
              {num(p.valor)}
            </span>
            <span className="num" style={{ font: '500 10px/1 var(--f-num)', color: 'var(--tx-muted)', width: 34, textAlign: 'right' }}>
              {percentualDaFatia(p.valor, total) === null ? '—' : pct(percentualDaFatia(p.valor, total)!, 0)}
            </span>
          </div>
        ))}
      </div>
    </div>
  )
}
