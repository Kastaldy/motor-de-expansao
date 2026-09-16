import { useState } from 'react'
import type { ReactNode } from 'react'

import { brl, num, pct, pctVar } from '../../lib/format'
import type {
  RedeMapaConcorrente,
  RedeParDePraca,
  RedeMovimentoEvento,
  RedeMovimentoTipo,
  RedePlanosEntorno,
  RedeUnidadeInteligencia,
} from '../../lib/types'
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
  const mov = dados.movimentacao
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
              {/* Layout em QUADROS (15/09): cada número, cada rede e cada agregador no seu próprio
                  quadro, com um visual pequeno que antecipa a leitura. Mesmos tokens do produto. */}
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))', gap: 10 }}>
                <Quadro>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                    <MiniRosca partes={[t.cadeias_1km ?? 0, t.independentes_1km ?? 0]} />
                    <Leitura
                      rotulo="Academias a 1 km"
                      valor={t.concorrentes_1km === null ? '—' : num(t.concorrentes_1km)}
                      nota={t.concorrentes_1km === null ? 'base ausente' : `${num(t.cadeias_1km)} rede · ${num(t.independentes_1km)} indep.`}
                      cor={(t.cadeias_1km ?? 0) >= 3 ? 'var(--gr-coral)' : undefined}
                    />
                  </div>
                </Quadro>
                <Quadro>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                    <MiniRosca partes={[t.cadeias_2km ?? 0, Math.max((t.concorrentes_2km ?? 0) - (t.cadeias_2km ?? 0), 0)]} />
                    <Leitura
                      rotulo="Academias a 2 km"
                      valor={t.concorrentes_2km === null ? '—' : num(t.concorrentes_2km)}
                      nota={t.concorrentes_2km === null ? 'base ausente' : `${num(t.cadeias_2km)} rede`}
                    />
                  </div>
                </Quadro>
                <Quadro>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                    <LogoRede
                      src={
                        t.cadeia_mais_proxima_rede
                          ? (t.redes_no_entorno.find((r) => r.rede === t.cadeia_mais_proxima_rede)?.logo ??
                            dados.mapa?.logos?.[t.cadeia_mais_proxima_rede] ??
                            null)
                          : null
                      }
                      tamanho={38}
                    />
                    <Leitura rotulo="Rede mais próxima" valor={metros(t.cadeia_mais_proxima_m)} nota={nomeRede(t.cadeia_mais_proxima_rede)} />
                  </div>
                </Quadro>
                <Quadro>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                    <MiniRosca
                      partes={[notaMedia.media ?? 0, 5 - (notaMedia.media ?? 0)]}
                      cores={['var(--warn)', 'var(--line-soft)']}
                    />
                    <Leitura
                      rotulo="Nota média no Wellhub"
                      valor={notaMedia.n ? num(notaMedia.media, 2) : '—'}
                      nota={notaMedia.n ? `${num(notaMedia.n)} avaliadas · 0 a 5` : 'nenhuma avaliada'}
                    />
                  </div>
                </Quadro>
              </div>

              {t.redes_no_entorno.length > 0 && (
                <>
                  <Secao>Redes a 2 km</Secao>
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(128px, 1fr))', gap: 10 }}>
                    {t.redes_no_entorno.map((rede) => (
                      <Quadro key={rede.rede} semPadding>
                        {/* Alturas RESERVADAS (16/09): sem elas, uma rede com dois planos empurrava o
                            rodapé para baixo e a fileira saía desalinhada; agora todo quadro tem o mesmo
                            espaço para nome e para planos, e o rodapé fica sempre no pé. */}
                        <div style={{ padding: '12px 8px 10px', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 6, flex: 1 }}>
                          <LogoRede src={rede.logo} tamanho={40} />
                          <span
                            style={{
                              font: '600 11.5px/1.2 var(--f-ui)',
                              color: 'var(--tx-strong)',
                              textAlign: 'center',
                              minHeight: 28,
                              display: 'flex',
                              alignItems: 'center',
                            }}
                          >
                            {nomeRede(rede.rede)}
                          </span>
                          <div style={{ width: '100%', minHeight: 27, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                          <PlanoDaRede
                            concorrentes={dados.mapa?.concorrentes ?? []}
                            rede={rede.rede}
                            totalpass={dados.planos.disponivel}
                            wellhub={dados.planos_wellhub?.disponivel ?? false}
                          />
                          </div>
                        </div>
                        <div
                          className="num"
                          style={{
                            borderTop: '1px solid var(--line-soft)',
                            padding: '6px 8px',
                            textAlign: 'center',
                            font: '500 10.5px/1 var(--f-num)',
                            color: 'var(--tx-muted)',
                          }}
                        >
                          {rede.n} {rede.n === 1 ? 'unidade' : 'unidades'}
                        </div>
                      </Quadro>
                    ))}
                  </div>
                </>
              )}

              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', columnGap: 16 }}>
                {/* As duas colunas fecham na MESMA linha de base: cada uma é flex-column e o bloco
                    de baixo (quadros de preço / quadro de movimentação) estica o que sobrar. */}
                <div style={{ minWidth: 0, display: 'flex', flexDirection: 'column' }}>
                  <Secao>Preço nos agregadores</Secao>
                  <div style={{ flex: 1, display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))', gap: 10, alignItems: 'stretch' }}>
                    <PrecoAgregador rotulo="TotalPass" icone="/logo-totalpass.jpg" p={dados.planos} />
                    <PrecoAgregador rotulo="Wellhub" icone="/logo-wellhub.png" p={dados.planos_wellhub} />
                  </div>
                </div>
                <div style={{ minWidth: 0, display: 'flex', flexDirection: 'column' }}>
                  <Secao>Movimentação a 2 km</Secao>
                  {/* A fileira de contadores (aberturas/saídas/em breve/Wellhub) saiu em 15/09: ela
                      empurrava o quadro para baixo e ele ficava mais baixo que os de preço ao lado.
                      A contagem segue no título de cada grupo da lista. */}
                  <Quadro estica>
                    {!mov?.disponivel ? (
                      <Vazio>Histórico de movimentação ausente.</Vazio>
                    ) : mov.eventos.length > 0 ? (
                      <MovimentacaoEntorno eventos={mov.eventos} logos={mov.logos ?? {}} />
                    ) : (
                      <Vazio>Nenhuma movimentação registrada a 2 km.</Vazio>
                    )}
                    {cn.itens.length > 0 && (
                      <div style={{ marginTop: 10, font: '400 11px/1.6 var(--f-ui)', color: 'var(--tx-narrative)' }}>
                        {cn.itens.map((i, k) => (
                          <div key={k}>
                            {i.nome ?? nomeRede(i.rede)} · {metros(i.distancia_m)} · no agregador desde {i.primeira_semana}
                          </div>
                        ))}
                      </div>
                    )}
                  </Quadro>
                </div>
              </div>
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
              {(q.pares?.length ?? 0) > 1 && <UnidadesPares pares={q.pares as RedeParDePraca[]} mediana={q.corte_desempenho} />}
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

/** Título de seção dentro do card: rótulo em caixa alta, igual em todas. */
function Secao({ children }: { children: ReactNode }) {
  return (
    <div
      style={{
        margin: '18px 0 9px',
        font: '600 9.5px/1 var(--f-ui)',
        letterSpacing: '.06em',
        textTransform: 'uppercase',
        color: 'var(--tx-muted)',
      }}
    >
      {children}
    </div>
  )
}

/** Quadro interno do card: fundo levemente elevado e fio fino, nos tokens do produto. */
function Quadro({ children, semPadding = false, estica = false }: { children: ReactNode; semPadding?: boolean; estica?: boolean }) {
  return (
    <div
      style={{
        background: 'var(--surf-raised)',
        border: '1px solid var(--line-soft)',
        borderRadius: 'var(--r-md)',
        padding: semPadding ? 0 : '11px 12px',
        minWidth: 0,
        display: 'flex',
        flexDirection: 'column',
        ...(estica ? { flex: 1 } : {}),
      }}
    >
      {children}
    </div>
  )
}

function Leitura({ rotulo, valor, nota, cor }: { rotulo: string; valor: ReactNode; nota?: ReactNode; cor?: string }) {
  return (
    <div style={{ minWidth: 0 }}>
      <div style={{ font: '500 10px/1.2 var(--f-ui)', color: 'var(--tx-label)', whiteSpace: 'nowrap' }}>{rotulo}</div>
      <div className="num" style={{ font: '700 20px/1.15 var(--f-num)', color: cor ?? 'var(--tx-max)', marginTop: 3 }}>
        {valor}
      </div>
      {nota && (
        <div style={{ font: '400 10px/1.35 var(--f-ui)', color: 'var(--tx-muted)', marginTop: 2, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
          {nota}
        </div>
      )}
    </div>
  )
}

/** Rosca de 38 px: a primeira parte pintada sobre a segunda. Total zero desenha só o trilho. */
function MiniRosca({
  partes,
  tamanho = 38,
  cores = ['var(--ac)', 'var(--gr-azul)'],
}: {
  partes: [number, number]
  tamanho?: number
  cores?: [string, string]
}) {
  const total = partes[0] + partes[1]
  const raio = tamanho / 2 - 4
  const volta = 2 * Math.PI * raio
  const primeira = total ? (partes[0] / total) * volta : 0
  const c = tamanho / 2
  return (
    <svg width={tamanho} height={tamanho} aria-hidden style={{ flexShrink: 0 }}>
      <circle cx={c} cy={c} r={raio} fill="none" stroke="var(--line-soft)" strokeWidth={6} />
      {total > 0 && (
        <>
          <circle cx={c} cy={c} r={raio} fill="none" stroke={cores[1]} strokeWidth={6} />
          <circle
            cx={c}
            cy={c}
            r={raio}
            fill="none"
            stroke={cores[0]}
            strokeWidth={6}
            strokeDasharray={`${primeira} ${volta}`}
            transform={`rotate(-90 ${c} ${c})`}
          />
        </>
      )}
    </svg>
  )
}

function LogoRede({ src, tamanho }: { src: string | null | undefined; tamanho: number }) {
  return src ? (
    <img src={src} alt="" width={tamanho} height={tamanho} style={{ display: 'block', flexShrink: 0, borderRadius: 8 }} />
  ) : (
    <span style={{ width: tamanho, height: tamanho, borderRadius: 8, background: 'var(--ac-a12)', flexShrink: 0 }} />
  )
}

function Vazio({ children }: { children: ReactNode }) {
  return (
    <div style={{ flex: 1, minHeight: 70, display: 'grid', placeItems: 'center', font: '400 11.5px/1.5 var(--f-ui)', color: 'var(--tx-muted)', textAlign: 'center' }}>
      {children}
    </div>
  )
}

/** Um agregador em quadro: média das concorrentes em destaque, a barra de posicionamento e o plano da Ultra embaixo. */
function PrecoAgregador({ rotulo, icone, p }: { rotulo: string; icone?: string; p: RedePlanosEntorno | undefined }) {
  const cabeca = (
    <div style={{ display: 'flex', alignItems: 'center', gap: 6, font: '600 11.5px/1.2 var(--f-ui)', color: 'var(--tx-strong)' }}>
      {icone && <img src={icone} alt="" width={14} height={14} style={{ display: 'block', borderRadius: 3 }} />}
      {rotulo}
    </div>
  )
  if (!p?.disponivel) {
    return (
      <Quadro estica>
        {cabeca}
        <Vazio>base não carregada</Vazio>
      </Quadro>
    )
  }
  const partes = [
    { n: p.mais_baratas ?? 0, cor: 'var(--gr-coral)', rotulo: 'mais baratas' },
    { n: p.mesmo_nivel ?? 0, cor: 'var(--tx-off)', rotulo: 'mesmo nível' },
    { n: p.mais_caras ?? 0, cor: 'var(--gr-azul)', rotulo: 'mais caras' },
  ]
  const total = partes.reduce((s, x) => s + x.n, 0)
  return (
    <Quadro estica>
      {cabeca}
      <div className="num" style={{ font: '700 20px/1.1 var(--f-num)', color: 'var(--tx-max)', marginTop: 6 }}>
        {p.media_preco != null ? brl(p.media_preco, false, 0) : '—'}
      </div>
      <div style={{ font: '400 10px/1.3 var(--f-ui)', color: 'var(--tx-muted)', marginBottom: 8 }}>
        média de {num(p.n_com_preco ?? 0)} concorrentes
      </div>
      {total > 0 && (
        <>
          <div style={{ display: 'flex', height: 5, borderRadius: 3, overflow: 'hidden', background: 'var(--line-soft)' }}>
            {partes.map((x) => (x.n ? <div key={x.rotulo} style={{ flex: x.n, background: x.cor }} /> : null))}
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 2, marginTop: 6, font: '400 10px/1.3 var(--f-ui)', color: 'var(--tx-muted)' }}>
            {partes.map((x) => (
              <span key={x.rotulo} style={{ display: 'inline-flex', alignItems: 'center', gap: 5 }}>
                <span style={{ width: 7, height: 7, borderRadius: 2, background: x.cor }} />
                <span className="num" style={{ color: 'var(--tx-strong)', fontWeight: 600 }}>{num(x.n)}</span> {x.rotulo}
              </span>
            ))}
          </div>
        </>
      )}
      <div
        style={{
          marginTop: 'auto',
          paddingTop: 10,
        }}
      >
        <div
          style={{
            padding: '7px 9px',
            borderRadius: 'var(--r-sm)',
            background: 'var(--surf-card)',
            border: '1px solid var(--line-soft)',
          }}
        >
        <div style={{ font: '500 9.5px/1.2 var(--f-ui)', color: 'var(--tx-label)' }}>Plano da Ultra</div>
        <div className="num" style={{ font: '600 12px/1.3 var(--f-num)', color: p.ultra ? 'var(--ac-text)' : 'var(--tx-muted)' }}>
          {p.ultra ? `${p.ultra.plano}${p.ultra.preco != null ? ` · ${brl(p.ultra.preco, false, 0)}` : ''}` : 'Não listada'}
        </div>
        </div>
      </div>
    </Quadro>
  )
}

const TIPOS_MOVIMENTO: { tipo: RedeMovimentoTipo; rotulo: string; cor: string }[] = [
  { tipo: 'abertura', rotulo: 'Aberturas', cor: 'var(--gr-coral)' },
  { tipo: 'inauguracao', rotulo: 'Inaugurações de "Em breve"', cor: 'var(--gr-coral)' },
  { tipo: 'em_breve', rotulo: 'Anunciadas "Em breve"', cor: 'var(--warn)' },
  { tipo: 'fechamento', rotulo: 'Fechamentos ou saídas do site', cor: 'var(--pos)' },
  { tipo: 'entrou_agregador', rotulo: 'Entraram no Wellhub', cor: 'var(--gr-azul)' },
  { tipo: 'saiu_agregador', rotulo: 'Saíram do Wellhub', cor: 'var(--tx-sub)' },
]

const dataCurta = (iso: string | null) => (iso && iso.length >= 10 ? `${iso.slice(8, 10)}/${iso.slice(5, 7)}` : '—')

/** Logo de 14 px ao lado do nome; sem logo, um quadradinho neutro do mesmo tamanho mantém o alinhamento. */
function LogoMiuda({ src }: { src: string | null | undefined }) {
  return src ? (
    <img src={src} alt="" width={14} height={14} style={{ display: 'block', flexShrink: 0, borderRadius: 3 }} />
  ) : (
    <span style={{ width: 14, height: 14, borderRadius: 3, background: 'var(--ac-a12)', flexShrink: 0 }} />
  )
}

/** Quem se mexeu a até 2 km, agrupado por tipo; cada grupo mostra até 4 e o resto em "+N". */
function MovimentacaoEntorno({ eventos, logos }: { eventos: RedeMovimentoEvento[]; logos: Record<string, string | null> }) {
  const grupos = TIPOS_MOVIMENTO.map((g) => ({ ...g, itens: eventos.filter((e) => e.tipo === g.tipo) })).filter((g) => g.itens.length)
  return (
    <div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
        {grupos.map((g) => (
          <div key={g.tipo} style={{ minWidth: 0 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 6, font: '600 11px/1.2 var(--f-ui)', color: 'var(--tx-strong)', marginBottom: 4 }}>
              <span style={{ width: 8, height: 8, borderRadius: 2, background: g.cor, flexShrink: 0 }} />
              {g.rotulo}
              <span className="num" style={{ font: '600 11px/1 var(--f-num)', color: 'var(--tx-muted)' }}>{g.itens.length}</span>
            </div>
            {g.itens.slice(0, 4).map((e, i) => (
              <div
                key={i}
                title={`${e.nome ?? ''}${e.rede ? ` (${nomeRede(e.rede)})` : ''} · ${dataCurta(e.de)} a ${dataCurta(e.ate)}`}
                style={{ display: 'flex', alignItems: 'center', gap: 6, font: '400 11px/1.6 var(--f-ui)', color: 'var(--tx-narrative)', minWidth: 0 }}
              >
                <LogoMiuda src={e.rede ? logos[e.rede] : e.fonte === 'wellhub' ? '/logo-wellhub.png' : null} />
                <span style={{ flex: 1, minWidth: 0, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                  {e.nome ?? nomeRede(e.rede)}
                  {e.rede && e.fonte !== 'wellhub' ? <span style={{ color: 'var(--tx-muted)' }}> · {nomeRede(e.rede)}</span> : null}
                </span>
                {e.confianca === 'cautela' && (
                  <span title="Foto não validada (28/05 a 02/08)" style={{ font: '500 9.5px/1.6 var(--f-ui)', color: 'var(--warn)' }}>
                    cautela
                  </span>
                )}
                <span className="num" style={{ font: '500 10.5px/1.6 var(--f-num)', color: 'var(--tx-muted)', whiteSpace: 'nowrap' }}>
                  {metros(e.distancia_m)} · {dataCurta(e.ate)}
                </span>
              </div>
            ))}
            {g.itens.length > 4 && (
              <div style={{ font: '400 10.5px/1.5 var(--f-ui)', color: 'var(--tx-muted)' }}>+{g.itens.length - 4}</div>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}

/**
 * Unidades de praça MAIS PARECIDA, com o faturamento de cada uma.
 *
 * O quadrante diz "praça boa, faturamento abaixo da mediana", mas não contra quem. Aqui
 * estão as que operam no mesmo tipo de chão — é a conversa de execução, não de mercado.
 */
function UnidadesPares({ pares, mediana }: { pares: RedeParDePraca[]; mediana: number | null }) {
  // Barras EM PÉ, canto reto, a unidade aberta em verde. A área do gráfico é UMA célula que
  // atravessa as colunas: é ela que permite a linha tracejada da mediana correr por cima de
  // todas as barras. Os rótulos ficam em linhas próprias da grade, então nada se sobrepõe.
  const esta = pares.find((p) => p.esta_unidade)
  const base = esta?.faturamento ?? 0
  const teto = Math.max(...pares.map((p) => p.faturamento), mediana ?? 0, 1)
  const alturaDe = (v: number) => `${Math.max((100 * v) / teto, 4)}%`
  const colunas = `repeat(${pares.length}, minmax(0, 1fr))`
  return (
    <div style={{ marginTop: 16 }}>
      <div style={{ font: '600 9.5px/1 var(--f-ui)', letterSpacing: '.06em', textTransform: 'uppercase', color: 'var(--tx-muted)', marginBottom: 10 }}>
        Unidades de praça parecida
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: colunas, gridTemplateRows: 'auto minmax(190px, 1fr) auto auto', columnGap: 8, rowGap: 4 }}>
        {pares.map((p) => (
          <span key={`v-${p.id}`} className="num" style={{ font: '600 10px/1 var(--f-num)', color: p.esta_unidade ? 'var(--tx-max)' : 'var(--tx-sub)', textAlign: 'center' }}>
            {brl(p.faturamento, true, 0)}
          </span>
        ))}

        <div style={{ gridColumn: '1 / -1', position: 'relative', display: 'grid', gridTemplateColumns: colunas, columnGap: 8, alignItems: 'end' }}>
          {pares.map((p) => {
            const delta = base > 0 && !p.esta_unidade ? (100 * (p.faturamento - base)) / base : null
            return (
              <div
                key={`b-${p.id}`}
                title={`${p.nome} — praça ${num(p.score_praca, 0)} · ${brl(p.faturamento)}${delta === null ? '' : ` (${pctVar(delta, 0)} contra esta unidade)`}`}
                style={{ height: alturaDe(p.faturamento), background: p.esta_unidade ? 'var(--pos)' : 'var(--line-mid)' }}
              />
            )
          })}
          {mediana !== null && (
            <div
              aria-hidden
              title={`Mediana de faturamento das maduras da rede: ${brl(mediana)}`}
              style={{ position: 'absolute', left: 0, right: 0, bottom: alturaDe(mediana), borderTop: '1px dashed var(--tx-muted)', pointerEvents: 'none' }}
            >
              <span
                className="num"
                style={{ position: 'absolute', right: 0, bottom: 2, font: '500 9px/1 var(--f-num)', color: 'var(--tx-muted)', background: 'var(--surf-card)', padding: '0 3px' }}
              >
                mediana da rede {brl(mediana, true, 0)}
              </span>
            </div>
          )}
        </div>

        {pares.map((p) => (
          <span
            key={`n-${p.id}`}
            style={{
              font: p.esta_unidade ? '600 9.5px/1.25 var(--f-ui)' : '400 9.5px/1.25 var(--f-ui)',
              color: p.esta_unidade ? 'var(--pos)' : 'var(--tx-label)',
              textAlign: 'center',
              display: '-webkit-box',
              WebkitLineClamp: 2,
              WebkitBoxOrient: 'vertical',
              overflow: 'hidden',
              minHeight: 24,
            }}
          >
            {p.nome}
          </span>
        ))}

        {pares.map((p) => {
          const delta = base > 0 && !p.esta_unidade ? (100 * (p.faturamento - base)) / base : null
          return (
            <span
              key={`d-${p.id}`}
              className="num"
              style={{ font: '600 9px/1 var(--f-num)', textAlign: 'center', color: delta === null ? 'var(--tx-off)' : delta > 0 ? 'var(--pos)' : 'var(--neg)' }}
            >
              {delta === null ? 'esta' : pctVar(delta, 0)}
            </span>
          )
        })}
      </div>
    </div>
  )
}

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
