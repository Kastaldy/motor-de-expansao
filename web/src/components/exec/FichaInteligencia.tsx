import { useState } from 'react'
import type { ReactNode } from 'react'

import { brl, num, pct, pctVar } from '../../lib/format'
import type { RedeMapaConcorrente, RedeUnidadeInteligencia } from '../../lib/types'
import { Glass, Spinner } from '../primitives'
import {
  BarraLtv,
  CelulaSinal,
  Chip,
  COR_QUADRANTE,
  GraficoRampa,
  metros,
  nomeRede,
  Rodape,
  Titulo,
} from './Inteligencia'

/* ---------------------------------------------------------------------------
   Por trás dos números — a mesma leitura do recorte, para UMA unidade.

   A ficha já diz COMO a unidade está (quarteto, coorte, série). Estes blocos
   dizem o CHÃO dela: a praça e quem disputa o aluno ali, a posição no quadrante
   praça × execução, a retenção prevista, a rampa contra as pares da mesma idade
   e os sinais que vêm antes do churn. Busca própria: a ficha abre sem esperar.
   --------------------------------------------------------------------------- */

type MetricaRampa = 'faturamento' | 'ativos' | 'pagantes' | 'agregadores'

/** As quatro leituras da rampa. Recorrentes e agregadores separados: o total de ativos
 *  esconde qual das duas bases está puxando a unidade. */
const METRICAS_RAMPA: { chave: MetricaRampa; rotulo: string }[] = [
  { chave: 'faturamento', rotulo: 'Faturamento' },
  { chave: 'ativos', rotulo: 'Alunos ativos' },
  { chave: 'pagantes', rotulo: 'Recorrentes' },
  { chave: 'agregadores', rotulo: 'Agregadores' },
]

/** Quem busca é a `FichaUnidade`: o mesmo payload alimenta estes blocos E o mapa. */
export default function FichaInteligencia({
  dados,
  erro,
}: {
  dados: RedeUnidadeInteligencia | null
  erro: string | null
}) {
  const [metricaRampa, setMetricaRampa] = useState<MetricaRampa>('faturamento')

  if (erro) {
    return (
      <Glass style={{ padding: '14px 18px' }}>
        <Titulo>Território e retenção</Titulo>
        <div style={{ font: '400 12px/1.5 var(--f-ui)', color: 'var(--tx-sub)' }}>{erro}</div>
      </Glass>
    )
  }
  if (!dados) {
    return (
      <Glass style={{ padding: '14px 18px', display: 'flex', alignItems: 'center', gap: 8, color: 'var(--tx-sub)' }}>
        <Spinner tamanho={12} /> Lendo território, retenção e rampa da unidade…
      </Glass>
    )
  }

  const t = dados.territorio
  const q = dados.quadrante
  const r = dados.retencao
  const rampa = dados.rampa[metricaRampa]
  const posicao = dados.rampa.posicao
  const cn = dados.concorrencia_nova
  // Nota média das concorrentes DIRETAS a 2 km: sem estúdios (DEC-056) e só quem tem nota.
  const notas = (dados.mapa?.concorrentes ?? []).filter((c) => !c.estudio && c.nota_wellhub !== null).map((c) => c.nota_wellhub as number)
  const notaMedia = { n: notas.length, media: notas.length ? notas.reduce((a, b) => a + b, 0) / notas.length : null }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
      <div style={{ display: 'flex', gap: 14, flexWrap: 'wrap' }}>
        {/* ---------- Concorrência ---------- */}
        <Glass style={{ flex: '3 1 560px', padding: '16px 18px', minWidth: 0 }}>
          <Titulo>Praça e concorrência</Titulo>
          {!t ? (
            <div style={{ font: '400 12px/1.5 var(--f-ui)', color: 'var(--tx-sub)' }}>
              Unidade sem coordenada no cadastro: concorrência indisponível.
            </div>
          ) : (
            <>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(118px, 1fr))', gap: 12 }}>
                <Numero
                  rotulo="Academias a 1 km"
                  valor={t.concorrentes_1km === null ? '—' : num(t.concorrentes_1km)}
                  nota={t.concorrentes_1km === null ? 'base ausente' : `${num(t.cadeias_1km)} de rede · ${num(t.independentes_1km)} independentes`}
                  cor={(t.cadeias_1km ?? 0) >= 3 ? 'var(--gr-coral)' : undefined}
                />
                <Numero
                  rotulo="Academias a 2 km"
                  valor={t.concorrentes_2km === null ? '—' : num(t.concorrentes_2km)}
                  nota={t.concorrentes_2km === null ? 'base ausente' : `${num(t.cadeias_2km)} de rede`}
                />
                <Numero
                  rotulo="Rede mais próxima"
                  valor={metros(t.cadeia_mais_proxima_m)}
                  nota={nomeRede(t.cadeia_mais_proxima_rede)}
                />
                <Numero
                  rotulo="Nota média no Wellhub"
                  valor={notaMedia.n ? num(notaMedia.media, 2) : '—'}
                  nota={notaMedia.n ? `${num(notaMedia.n)} concorrentes avaliadas a 2 km` : 'nenhuma concorrente avaliada'}
                />
                <Numero
                  rotulo="Entradas recentes"
                  valor={cn.disponivel ? num(cn.itens.length) : '—'}
                  nota={cn.disponivel ? `a 2 km, últimas 8 semanas` : 'sem série semanal neste ambiente'}
                  cor={cn.itens.length > 0 ? 'var(--gr-coral)' : undefined}
                />
              </div>

              <div style={{ marginTop: 16 }}>
                <div style={{ font: '500 10.5px/1 var(--f-ui)', color: 'var(--tx-label)', marginBottom: 6 }}>
                  Ticket dos agregadores a 2 km
                </div>
                <div style={{ overflowX: 'auto' }}>
                  <table style={{ width: '100%', borderCollapse: 'collapse', font: '400 11.5px/1.2 var(--f-ui)' }}>
                    <thead>
                      <tr style={{ color: 'var(--tx-muted)', font: '500 10px/1 var(--f-ui)' }}>
                        <th style={celTicket('left')}></th>
                        <th style={celTicket('right')}>Média das concorrentes</th>
                        <th style={celTicket('right')}>Plano da Ultra</th>
                        <th style={celTicket('center')}>Mais baratas</th>
                        <th style={celTicket('center')}>Mesmo nível</th>
                        <th style={celTicket('center')}>Mais caras</th>
                      </tr>
                    </thead>
                    <tbody>
                      {([
                        ['TotalPass', dados.planos],
                        ['Wellhub', dados.planos_wellhub],
                      ] as const).map(([rotulo, p]) => (
                        <tr key={rotulo} style={{ height: 28 }}>
                          <td style={{ ...celTicket('left'), color: 'var(--tx-label)' }}>{rotulo}</td>
                          {!p?.disponivel ? (
                            <td colSpan={5} style={{ ...celTicket('right'), color: 'var(--tx-muted)' }}>
                              base não carregada neste ambiente
                            </td>
                          ) : (
                            <>
                              <td className="num" style={{ ...celTicket('right'), font: '700 12px/1 var(--f-num)', color: 'var(--tx-max)' }}>
                                {p.media_preco != null ? brl(p.media_preco, false, 0) : '—'}
                                <span style={{ font: '500 10px/1 var(--f-num)', color: 'var(--tx-muted)' }}> ({num(p.n_com_preco ?? 0)})</span>
                              </td>
                              <td className="num" style={{ ...celTicket('right'), color: 'var(--tx-strong)' }}>
                                {p.ultra ? `${p.ultra.plano}${p.ultra.preco != null ? ` · ${brl(p.ultra.preco, false, 0)}` : ''}` : 'não listada'}
                              </td>
                              {[p.mais_baratas, p.mesmo_nivel, p.mais_caras].map((v, k) => (
                                <td key={k} className="num" style={{ ...celTicket('center'), font: '600 12px/1 var(--f-num)', color: 'var(--tx-sub)' }}>
                                  {v != null ? num(v) : '—'}
                                </td>
                              ))}
                            </>
                          )}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>

              {t.redes_no_entorno.length > 0 && (
                <div style={{ marginTop: 16 }}>
                  <div style={{ font: '500 10.5px/1 var(--f-ui)', color: 'var(--tx-label)', marginBottom: 8 }}>Redes a 2 km</div>
                  <div style={{ display: 'flex', gap: 19, flexWrap: 'wrap', justifyContent: 'center' }}>
                    {t.redes_no_entorno.map((rede) => (
                      <div key={rede.rede} style={{ width: 104, display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 4 }}>
                        {rede.logo ? (
                          <img src={rede.logo} alt="" width={44} height={44} style={{ display: 'block' }} />
                        ) : (
                          <div style={{ width: 44, height: 44, borderRadius: 10, background: 'var(--ac-a12)' }} />
                        )}
                        <span style={{ font: '600 10.5px/1.2 var(--f-ui)', color: 'var(--tx-strong)', textAlign: 'center' }}>
                          {nomeRede(rede.rede)}
                        </span>
                        <PlanoDaRede
                          concorrentes={dados.mapa?.concorrentes ?? []}
                          rede={rede.rede}
                          totalpass={dados.planos.disponivel}
                          wellhub={dados.planos_wellhub?.disponivel ?? false}
                        />
                        <span className="num" style={{ font: '500 10px/1 var(--f-num)', color: 'var(--tx-muted)' }}>
                          {rede.n} {rede.n === 1 ? 'unidade' : 'unidades'}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {cn.itens.length > 0 && (
                <div style={{ marginTop: 16 }}>
                  <div style={{ font: '500 10.5px/1 var(--f-ui)', color: 'var(--tx-label)', marginBottom: 6 }}>
                    Entraram no agregador a até 2 km (série até {cn.ultima_semana})
                  </div>
                  <ul style={{ margin: 0, paddingLeft: 18, font: '400 12px/1.7 var(--f-ui)', color: 'var(--tx-narrative)' }}>
                    {cn.itens.map((i, k) => (
                      <li key={k}>
                        <strong style={{ color: 'var(--tx-strong)' }}>{i.nome ?? nomeRede(i.rede)}</strong>
                        {i.rede ? ` (${nomeRede(i.rede)})` : ''} a {metros(i.distancia_m)} · desde a semana {i.primeira_semana}
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              <Rodape>
                Sem estúdios boutique, pela mesma lista que os tira do residual (DEC-056). Ticket = preço do plano do
                agregador exigido para frequentar, só academias com musculação; não é a mensalidade de balcão. Entrar no
                agregador pode ser credenciamento, não inauguração.
              </Rodape>
            </>
          )}
        </Glass>

        {/* ---------- Quadrante ---------- */}
        <Glass style={{ flex: '2 1 420px', padding: '16px 18px', minWidth: 0 }}>
          <Titulo>Praça × execução</Titulo>
          {t && (
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(110px, 1fr))', gap: 12, marginBottom: 14 }}>
              <Numero rotulo="Score da praça" valor={num(t.score_praca, 1)} nota="0–100, régua absoluta" />
              <Numero rotulo="Renda domiciliar" valor={brl(t.renda_domiciliar)} nota="média por domicílio no raio de 1 km" />
              <Numero rotulo="População a 1 km" valor={num(t.populacao_entorno)} nota="pela área dos hexágonos no círculo" />
            </div>
          )}
          {q.ponto?.quadrante ? (
            <>
              <div style={{ font: '400 22px/1.15 var(--f-story)', color: COR_QUADRANTE[q.ponto.quadrante] }}>
                {q.ponto.quadrante_rotulo}
              </div>
              <div style={{ margin: '8px 0 12px', font: '400 12px/1.55 var(--f-ui)', color: 'var(--tx-narrative)' }}>
                {q.explicacao[q.ponto.quadrante]}
              </div>
              <Comparacao
                rotulo="Praça"
                valor={num(q.ponto.score_praca, 1)}
                corte={num(q.corte_praca, 1)}
                acima={q.corte_praca !== null && q.ponto.score_praca >= q.corte_praca}
              />
              <Comparacao
                rotulo="Faturamento do mês fechado"
                valor={brl(q.ponto.faturamento)}
                corte={brl(q.corte_desempenho)}
                acima={q.corte_desempenho !== null && q.ponto.faturamento >= q.corte_desempenho}
              />
            </>
          ) : (
            <div style={{ font: '400 12px/1.5 var(--f-ui)', color: 'var(--tx-sub)' }}>
              Fora do quadrante: ele compara só unidades com {q.meses_madura}+ meses de operação, praça conhecida e mês
              fechado — a coorte explicaria a diferença antes da praça.
            </div>
          )}
          <Rodape>
            Cortes = medianas das {q.n} unidades maduras da rede. Leitura diagnóstica, não previsão (DEC-043).
            {t ? ` Residual de mercado a 1 km: ${num(t.residual_entorno)} alunos, já descontada a própria Ultra (contexto, não potencial).` : ''}
          </Rodape>
        </Glass>
      </div>

      <div style={{ display: 'flex', gap: 14, flexWrap: 'wrap' }}>
        {/* ---------- Rampa ---------- */}
        {/* MESMO flex da linha de cima (Praça e concorrência): as bordas das duas linhas
            correm na mesma coluna (pedido do Felipe, 15/09). */}
        <Glass style={{ flex: '3 1 560px', padding: '16px 18px', minWidth: 0 }}>
          <Titulo
            extra={
              <span style={{ display: 'flex', gap: 6 }}>
                {METRICAS_RAMPA.map((m) => (
                  <Chip key={m.chave} ativo={metricaRampa === m.chave} onClick={() => setMetricaRampa(m.chave)}>
                    {m.rotulo}
                  </Chip>
                ))}
              </span>
            }
          >
            Trajetória contra a rampa da rede
          </Titulo>
          {posicao && metricaRampa === 'faturamento' && (
            <div style={{ marginBottom: 8, font: '400 12px/1.5 var(--f-ui)', color: 'var(--tx-narrative)' }}>
              No mês {posicao.meses_operacao} de vida, a unidade está{' '}
              <strong style={{ color: posicao.faixa === 'abaixo' ? 'var(--neg)' : posicao.faixa === 'acima' ? 'var(--pos)' : 'var(--tx-strong)' }}>
                {pctVar(posicao.desvio_pct, 0)}
              </strong>{' '}
              contra a mediana das unidades na mesma idade ({brl(posicao.p50)}).
            </div>
          )}
          <GraficoRampa
            curva={rampa.curva}
            trajetoria={rampa.unidade}
            formato={metricaRampa === 'faturamento' ? 'brl' : 'int'}
            altura={200}
          />
          <Rodape>
            Linha laranja: a unidade, mês a mês desde a inauguração (até o 24º). Faixa: p25 a p75 da rede na mesma idade;
            linha: mediana. {rampa.unidade.length === 0 ? 'Sem meses fechados de operação cheia para desenhar.' : ''}
          </Rodape>
        </Glass>

        {/* ---------- Retenção + sinais ---------- */}
        <Glass style={{ flex: '2 1 420px', padding: '16px 18px', minWidth: 0 }}>
          <Titulo>Retenção e sinais antes do churn</Titulo>
          {r.risco_percentil === undefined || r.utilizavel === false ? (
            <div style={{ font: '400 12px/1.5 var(--f-ui)', color: 'var(--tx-sub)', marginBottom: 12 }}>
              {!r.data_artefato
                ? 'Modelo de retenção indisponível neste ambiente.'
                : r.utilizavel === false
                  ? `O modelo de retenção não é confiável para esta unidade (${r.confiabilidade ?? 'sem classificação'}): poucos alunos ou poucos cancelamentos para estimar o risco.`
                  : 'Unidade fora do modelo de retenção (sem código no cadastro ou sem base).'}
            </div>
          ) : (
            <div style={{ marginBottom: 14 }}>
              <div style={{ display: 'flex', alignItems: 'baseline', gap: 8 }}>
                <span className="num" style={{ font: '700 26px/1 var(--f-num)', color: (r.risco_percentil ?? 0) >= 75 ? 'var(--neg)' : 'var(--tx-max)' }}>
                  {r.prob_cancel_90d_pct != null ? pct(r.prob_cancel_90d_pct, 1) : `p${num(r.risco_percentil)}`}
                </span>
                <span style={{ font: '400 11.5px/1.4 var(--f-ui)', color: 'var(--tx-sub)' }}>
                  {r.prob_cancel_90d_pct != null
                    ? `chance média de cancelar em 90 dias · mais arriscada que ${num(r.risco_percentil)}% da rede`
                    : 'percentil de risco na rede (o modelo não valida a probabilidade absoluta aqui)'}
                </span>
              </div>
              <div style={{ margin: '10px 0 4px' }}>
                <BarraLtv fragil={r.ltv_fragil_pct} risco={r.ltv_em_risco_pct} duravel={r.ltv_duravel_pct} alta={r.ltv_alta_durabilidade_pct} />
              </div>
              <div style={{ font: '400 10.5px/1.5 var(--f-ui)', color: 'var(--tx-muted)' }}>
                LTV de 12 meses (mediano) {brl(r.ltv_12m_mediano)} · {num(r.meses_ativos_12m, 1)} meses ativos esperados ·{' '}
                {pct(r.ltv_fragil_pct, 0)} da base frágil · confiabilidade: {r.confiabilidade ?? '—'}
              </div>
            </div>
          )}

          {dados.sinais ? (
            <table style={{ width: '100%', borderCollapse: 'collapse', font: '400 11.5px/1.2 var(--f-ui)' }}>
              <tbody>
                {dados.sinais.sinais.map((s) => (
                  <tr key={s.chave} style={{ height: 26 }}>
                    <td style={{ borderBottom: '1px solid var(--line-soft)', color: 'var(--tx-label)' }} title={s.detalhe}>
                      {s.rotulo}
                    </td>
                    <td style={{ borderBottom: '1px solid var(--line-soft)', textAlign: 'right' }}>
                      <CelulaSinal sinal={s} />
                    </td>
                  </tr>
                ))}
                {dados.agregadores && (
                  <tr style={{ height: 26 }}>
                    <td style={{ borderBottom: '1px solid var(--line-soft)', color: 'var(--tx-label)' }}>Agregadores</td>
                    <td className="num" style={{ borderBottom: '1px solid var(--line-soft)', textAlign: 'right', font: '500 11.5px/1 var(--f-num)', color: 'var(--tx-sub)' }}>
                      Wellhub {num(dados.agregadores.wellhub)} · TotalPass {num(dados.agregadores.totalpass)}
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          ) : (
            <div style={{ font: '400 11.5px/1.5 var(--f-ui)', color: 'var(--tx-sub)' }}>
              Sinais indisponíveis: a unidade não operou o mês-base inteiro.
            </div>
          )}
          <Rodape>Em vermelho, pior quartil da rede no mês {dados.competencia ?? ''} (sem régua absoluta validada).</Rodape>
        </Glass>
      </div>

    </div>
  )
}

/**
 * Planos dos agregadores de uma REDE no entorno, embaixo do logo dela: as linhas do TotalPass
 * e depois as do Wellhub (réguas diferentes, nunca comparadas nível a nível).
 *
 * Sai dos próprios pinos do mapa (que já carregam o plano da unidade): uma rede com duas
 * unidades a 2 km pode estar em planos diferentes, e aí cada plano ganha a SUA linha com o
 * preço dele, em vez de uma faixa que escondia o valor de cada um.
 */
function PlanoDaRede({
  concorrentes,
  rede,
  totalpass,
  wellhub,
}: {
  concorrentes: RedeMapaConcorrente[]
  rede: string
  totalpass: boolean
  wellhub: boolean
}) {
  if (!totalpass && !wellhub) return null
  const daRede = concorrentes.filter((c) => c.classe === 'cadeia' && c.rede === rede)
  const tp = totalpass ? planosDistintos(daRede.map((c) => [c.plano, c.preco_plano])) : []
  const wh = wellhub ? planosDistintos(daRede.map((c) => [c.plano_wellhub, c.preco_plano_wellhub])) : []
  if (!tp.length && !wh.length) {
    // "Sem plano identificado", e não "fora do agregador": o pino casa com a linha do agregador
    // só a até 60 m, e a coordenada do cadastro da rede pode divergir da do agregador.
    return (
      <span style={{ display: 'block', width: '100%', textAlign: 'center', font: '500 10px/1.2 var(--f-ui)', color: 'var(--tx-muted)' }}>
        sem plano identificado
      </span>
    )
  }
  const linha = (p: { plano: string; preco: number | null }, fonte: string) => (
    <span
      key={`${fonte}-${p.plano}`}
      className="num"
      style={{ display: 'block', width: '100%', textAlign: 'center', whiteSpace: 'nowrap', font: '700 10.5px/1.2 var(--f-num)', color: 'var(--ac-text)' }}
    >
      {p.plano}
      {p.preco !== null && <span style={{ fontWeight: 500, color: 'var(--tx-muted)' }}> · {brl(p.preco, false, 0)}</span>}
    </span>
  )
  return (
    <span style={{ display: 'flex', flexDirection: 'column', gap: 2, width: '100%' }}>
      {tp.map((p) => linha(p, 'tp'))}
      {wh.map((p) => linha(p, 'wh'))}
    </span>
  )
}

/** Planos distintos da rede, do mais barato ao mais caro, cada um com o próprio preço. */
function planosDistintos(pares: [string | null | undefined, number | null | undefined][]) {
  const planos = pares.filter((p): p is [string, number | null] => !!p[0]).map(([plano, preco]) => ({ plano, preco: preco ?? null }))
  return [...new Map(planos.map((p) => [p.plano, p])).values()].sort((a, b) => (a.preco ?? 0) - (b.preco ?? 0))
}

const celTicket = (alinhar: 'left' | 'right' | 'center') =>
  ({ borderBottom: '1px solid var(--line-soft)', textAlign: alinhar, padding: '0 6px', whiteSpace: 'nowrap' }) as const

function Numero({ rotulo, valor, nota, cor }: { rotulo: string; valor: ReactNode; nota?: ReactNode; cor?: string }) {
  return (
    <div style={{ minWidth: 0 }}>
      <div style={{ font: '500 10px/1.2 var(--f-ui)', color: 'var(--tx-label)' }}>{rotulo}</div>
      <div className="num" style={{ font: '700 18px/1.2 var(--f-num)', color: cor ?? 'var(--tx-max)', marginTop: 3 }}>
        {valor}
      </div>
      {nota && <div style={{ font: '400 10px/1.35 var(--f-ui)', color: 'var(--tx-muted)', marginTop: 2 }}>{nota}</div>}
    </div>
  )
}

function Comparacao({ rotulo, valor, corte, acima }: { rotulo: string; valor: string; corte: string; acima: boolean }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8, padding: '6px 0', borderBottom: '1px solid var(--line-soft)', font: '400 11.5px/1.3 var(--f-ui)' }}>
      <span style={{ color: 'var(--tx-label)' }}>{rotulo}</span>
      <span className="num" style={{ font: '600 11.5px/1 var(--f-num)', color: 'var(--tx-strong)', whiteSpace: 'nowrap' }}>
        {valor}{' '}
        <span style={{ color: acima ? 'var(--pos)' : 'var(--neg)', fontWeight: 500 }}>
          {acima ? '≥' : '<'} {corte}
        </span>
      </span>
    </div>
  )
}
