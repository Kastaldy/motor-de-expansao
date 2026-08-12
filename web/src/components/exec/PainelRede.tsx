import type { ReactNode } from 'react'

import type { BaseDoDestaque, DestaqueDoRecorte, DestaquesDoRecorte } from '../../lib/exec'
import { rotuloMesCompetencia, rotuloMesCurto } from '../../lib/exec'
import { brl, brlCurto, num, pct } from '../../lib/format'
import type { RedeCoorteResumo, RedeFaixas, RedeSss, RedeUnidade } from '../../lib/types'
import { BarraSegmentada, Glass, Semaforo } from '../primitives'
import { BarrasPeriodo, LinhaPeriodo } from './ExecCharts'

/* ---------------------------------------------------------------------------
   Panorama do RECORTE — o que a carteira, unidade a unidade, não responde.

   A tabela responde "com quem falar hoje". Estes painéis respondem as perguntas
   que só existem no agregado, e cada um está aqui por uma delas:

   - Evolução: "para onde este recorte anda?" Uma métrica POR VEZ, e não seis
     gráficos empilhados — o time lê uma série, decide, e só então troca.
   - Crescimento comparável: "crescemos ou só abrimos loja?" A rede abriu 33
     unidades em 2025; total contra total mede expansão, não desempenho.
   - Distribuição por faixa: onde a massa do recorte cai na régua ABSOLUTA do time
     de campo, a mesma que eles levam para a reunião.
   - Maturidade: com que carteira o recorte foi montado. Oito unidades de menos de
     um ano não se comparam a oito maduras, e sem isso o SSS e as faixas acima
     levam a culpa de uma diferença que é de composição.
   - Destaques: quem puxa e quem segura. É o painel que vira ação — cada linha
     abre a ficha da unidade.

   Todos são função pura de props: nenhum estado, nenhum fetch. Quem é dono do
   recorte é a tela. E cada painel já vem no seu próprio `Glass`: a grade se monta
   em volta deles, não um segundo card por cima.
   --------------------------------------------------------------------------- */

/**
 * Métricas do painel de evolução, na ordem em que o time lê.
 *
 * VOLUME vira barras, TAXA vira linha — a distinção que o produto já faz na ficha da
 * unidade. Barra afirma "isto se soma"; somar churn de doze meses não significa nada,
 * e a linha diz justamente que o número é um nível, não um acúmulo.
 */
export const METRICAS_EVOLUCAO: {
  chave: string
  rotulo: string
  formato: 'brl' | 'int' | 'pct' | 'nota'
  forma: 'barras' | 'linha'
}[] = [
  { chave: 'faturamento', rotulo: 'Faturamento', formato: 'brl', forma: 'barras' },
  { chave: 'ativos', rotulo: 'Alunos ativos', formato: 'int', forma: 'barras' },
  { chave: 'pagantes', rotulo: 'Recorrentes', formato: 'int', forma: 'barras' },
  { chave: 'novos_alunos', rotulo: 'Novos alunos', formato: 'int', forma: 'barras' },
  { chave: 'saldo_operacional', rotulo: 'Saldo operacional', formato: 'int', forma: 'barras' },
  { chave: 'churn_pct', rotulo: 'Churn', formato: 'pct', forma: 'linha' },
  { chave: 'nps', rotulo: 'NPS', formato: 'nota', forma: 'linha' },
  { chave: 'receita_por_recorrente', rotulo: 'Receita por recorrente', formato: 'brl', forma: 'linha' },
  { chave: 'conversao_pct', rotulo: 'Conversão de visitas', formato: 'pct', forma: 'linha' },
]

export function EvolucaoRecorte({
  meses,
  series,
  metrica,
  onMetrica,
}: {
  meses: string[]
  series: Record<string, (number | null)[]>
  metrica: string
  onMetrica: (chave: string) => void
}) {
  // Chave desconhecida cai na primeira métrica em vez de apagar o gráfico: o painel é
  // controlado pela tela, e um estado fora do catálogo não pode virar tela em branco.
  const escolhida = METRICAS_EVOLUCAO.find((m) => m.chave === metrica) ?? METRICAS_EVOLUCAO[0]
  const valores = series[escolhida.chave] ?? []
  const temSerie = meses.length > 0 && valores.some((v) => v !== null && Number.isFinite(v))
  // Os gráficos só conhecem brl/int/pct. NPS é um índice de -100 a 100 e se desenha como
  // inteiro — o rótulo da métrica já diz que não é contagem de gente.
  const formato = escolhida.formato === 'nota' ? 'int' : escolhida.formato
  // Churn é a única série em que SUBIR é ruim. No turquesa das outras, uma curva de churn
  // crescendo passaria por boa notícia à primeira vista.
  const cor = escolhida.chave === 'churn_pct' ? 'var(--neg)' : 'var(--ac)'

  return (
    <Glass style={{ padding: '15px 17px', minWidth: 0 }}>
      <Rotulo>Evolução do recorte</Rotulo>
      <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginBottom: 13 }}>
        {METRICAS_EVOLUCAO.map((m) => {
          const ativo = m.chave === escolhida.chave
          return (
            <button
              key={m.chave}
              type="button"
              aria-pressed={ativo}
              onClick={() => onMetrica(m.chave)}
              style={{
                padding: '5px 9px',
                borderRadius: 'var(--r-sm)',
                border: `1px solid ${ativo ? 'var(--ac)' : 'var(--line-soft)'}`,
                background: ativo ? 'var(--ac-a12)' : 'transparent',
                color: ativo ? 'var(--ac-text)' : 'var(--tx-soft)',
                font: '600 10.5px/1 var(--f-ui)',
                cursor: 'pointer',
                whiteSpace: 'nowrap',
              }}
            >
              {m.rotulo}
            </button>
          )
        })}
      </div>

      {/* Série vazia sai como uma linha de texto, e não como um gráfico com eixo e
          nenhuma barra: eixo desenhado sobre o nada parece falha de carregamento, e
          manda a pessoa recarregar em vez de trocar de métrica. */}
      {/* Altura maior que o padrão dos gráficos da ficha (132/108) porque este card divide
          a faixa com o do SSS, que é alto por natureza — número grande, três linhas de
          ano contra ano e a série mês a mês. Com a altura padrão sobravam ~145 px de vão
          no pé deste card, e vão no meio de uma faixa lê como card quebrado. */}
      {temSerie ? (
        escolhida.forma === 'barras' ? (
          <BarrasPeriodo meses={meses} valores={valores} formato={formato} cor={cor} altura={236} />
        ) : (
          <LinhaPeriodo meses={meses} valores={valores} formato={formato} cor={cor} altura={212} />
        )
      ) : (
        <div style={{ font: '400 11.5px/1.6 var(--f-ui)', color: 'var(--tx-muted)', padding: '16px 0' }}>
          sem série no recorte
        </div>
      )}

      <div style={{ marginTop: 9, font: '400 10.5px/1.5 var(--f-ui)', color: 'var(--tx-muted)' }}>
        Meses FECHADOS do recorte. Volume é soma; taxa é média ponderada — as mesmas regras
        dos KPIs do topo.
      </div>
    </Glass>
  )
}

/** Linhas abaixo do número grande.
 *
 *  `faturamento_sem_agregador` entra junto de propósito: o faturamento total sobe só
 *  porque um agregador mandou mais gente, e é a receita de recorrente que diz se a MESMA
 *  loja melhorou. Alunos e recorrentes fecham a leitura — receita crescendo sem base
 *  crescendo é reajuste de preço, não crescimento. */
const LINHAS_SSS: { chave: string; rotulo: string; formato: 'brl' | 'int' }[] = [
  { chave: 'faturamento_sem_agregador', rotulo: 'Receita de recorrentes', formato: 'brl' },
  { chave: 'ativos', rotulo: 'Alunos ativos', formato: 'int' },
  { chave: 'pagantes', rotulo: 'Recorrentes', formato: 'int' },
]

/** Metade da caixa da série divergente, em px. O eixo zero corta no meio. */
const METADE_SSS = 30

export function CrescimentoComparavel({ sss }: { sss: RedeSss }) {
  const base = rotuloMesCompetencia(sss.competencia_base)

  if (!sss.disponivel) {
    return (
      <Glass style={{ padding: '15px 17px', minWidth: 0 }}>
        <Rotulo>Crescemos ou só abrimos loja?</Rotulo>
        <div style={{ font: '400 11.5px/1.65 var(--f-ui)', color: 'var(--tx-narrative)' }}>
          Nenhuma das {num(sss.unidades_recorte)} unidades deste recorte operou o mês inteiro
          nos dois períodos (agora e em {base}). Sem base comparável não há crescimento a
          medir: o total de hoje contra o total de um ano atrás mediria abertura de loja,
          não desempenho.
        </div>
      </Glass>
    )
  }

  const faturamento = sss.metricas?.faturamento
  const variacao = faturamento?.var_pct ?? null
  const serie = sss.serie
  // Pico em MÓDULO, com piso de 1 ponto: sem o piso, um ano inteiro variando 0,2% viraria
  // uma serra de barras cheias, e a leitura "o recorte está parado" se perderia.
  const pico = Math.max(
    ...serie.var_pct.filter((v): v is number => v !== null && Number.isFinite(v)).map(Math.abs),
    1,
  )

  return (
    <Glass style={{ padding: '15px 17px', minWidth: 0 }}>
      <Rotulo>Crescemos ou só abrimos loja?</Rotulo>

      <div style={{ display: 'flex', alignItems: 'baseline', gap: 10, flexWrap: 'wrap' }}>
        <span className="num" style={{ font: '700 24px/1 var(--f-num)', color: corDaVariacao(variacao) }}>
          {sinalPct(variacao)}
        </span>
        <span style={{ font: '400 11.5px/1.4 var(--f-ui)', color: 'var(--tx-label)' }}>
          de faturamento contra {base}
        </span>
      </div>

      <div style={{ marginTop: 9, font: '400 11.5px/1.65 var(--f-ui)', color: 'var(--tx-narrative)' }}>
        Mesma base: <strong style={{ color: 'var(--tx-strong)' }}>
          {num(sss.unidades)} de {num(sss.unidades_recorte)}
        </strong>{' '}
        unidades do recorte.
        {sss.unidades_fora > 0 && (
          <>
            {' '}
            {sss.unidades_fora === 1 ? 'A outra não existia' : `As outras ${num(sss.unidades_fora)} não existiam`}{' '}
            há um ano, ou não operaram o mês inteiro nos dois períodos, e por isso{' '}
            {sss.unidades_fora === 1 ? 'fica' : 'ficam'} fora da conta.
          </>
        )}
      </div>

      <div style={{ marginTop: 12, display: 'flex', flexDirection: 'column', gap: 7 }}>
        {LINHAS_SSS.map((l) => {
          const m = sss.metricas?.[l.chave]
          if (!m || m.atual === null) return null
          const fmt = (v: number | null) => (l.formato === 'brl' ? brlCurto(v) : num(v))
          return (
            <div key={l.chave} style={{ display: 'flex', alignItems: 'baseline', gap: 8 }}>
              <span style={{ flex: 1, minWidth: 0, font: '400 11.5px/1.3 var(--f-ui)', color: 'var(--tx-label)' }}>
                {l.rotulo}
              </span>
              <span className="num" style={{ font: '600 12px/1 var(--f-num)', color: 'var(--tx-strong)' }}>
                {fmt(m.atual)}
              </span>
              <span className="num" style={{ font: '500 10px/1 var(--f-num)', color: 'var(--tx-muted)' }}>
                vs {fmt(m.ano_anterior)}
              </span>
              <span
                className="num"
                style={{ font: '700 11px/1 var(--f-num)', color: corDaVariacao(m.var_pct), width: 56, textAlign: 'right' }}
              >
                {sinalPct(m.var_pct)}
              </span>
            </div>
          )
        })}
      </div>

      {/* A série divergente parte do ZERO no meio da caixa, e não de uma base deslocada:
          o sinal É a informação aqui — o mês em que o recorte virou de positivo para
          negativo tem de saltar aos olhos sem ler número nenhum. */}
      {serie.meses.length > 0 && (
        <div style={{ marginTop: 14 }}>
          <div style={{ font: '500 11px/1.2 var(--f-ui)', color: 'var(--tx-label)', marginBottom: 8 }}>
            Mês a mês, cada um contra o seu próprio ano anterior
          </div>
          <div style={{ display: 'flex', gap: 3, alignItems: 'flex-start' }}>
            {serie.meses.map((m, i) => {
              const v = serie.var_pct[i] ?? null
              const n = serie.unidades[i] ?? 0
              const fracao = v === null ? 0 : Math.min(Math.abs(v) / pico, 1)
              return (
                <div
                  key={m}
                  title={`${rotuloMesCompetencia(m)}: ${
                    v === null ? 'sem base comparável' : sinalPct(v)
                  } · ${num(n)} unidades na base daquele mês`}
                  style={{ flex: 1, minWidth: 0 }}
                >
                  <div style={{ height: METADE_SSS, display: 'flex', alignItems: 'flex-end' }}>
                    {v !== null && v > 0 && (
                      <div
                        style={{
                          width: '100%',
                          height: `${fracao * 100}%`,
                          minHeight: 2,
                          background: 'var(--pos)',
                          borderRadius: '2px 2px 0 0',
                        }}
                      />
                    )}
                  </div>
                  <div style={{ height: 1, background: 'var(--line-mid)' }} />
                  <div style={{ height: METADE_SSS }}>
                    {v !== null && v < 0 && (
                      <div
                        style={{
                          width: '100%',
                          height: `${fracao * 100}%`,
                          minHeight: 2,
                          background: 'var(--neg)',
                          borderRadius: '0 0 2px 2px',
                        }}
                      />
                    )}
                  </div>
                  <span
                    className="num"
                    style={{
                      display: 'block',
                      font: '500 8.5px/1 var(--f-num)',
                      color: 'var(--tx-muted)',
                      textAlign: 'center',
                      marginTop: 5,
                    }}
                  >
                    {rotuloMesCurto(m)}
                  </span>
                </div>
              )
            })}
          </div>
        </div>
      )}

      <div style={{ marginTop: 10, font: '400 10.5px/1.5 var(--f-ui)', color: 'var(--tx-muted)' }}>
        A base comparável MUDA de mês para mês — cada ponto recalcula quais unidades do
        recorte operaram o mês inteiro nos dois períodos. Passe o mouse para ver o tamanho
        da base de cada mês.
      </div>
    </Glass>
  )
}

/* Escala de VALOR absoluto do time de campo, e não de risco: os limiares são de R$ por
   mês inteiro (Crítico <150k … Excelente+ >=300k). Por isso ela NÃO usa `COR_SEVERIDADE`
   — pintar "Crítico" com o vermelho do semáforo faria a faixa de faturamento e o
   diagnóstico da unidade parecerem a mesma medida, e uma unidade nova cai em "Crítico"
   sem ter alerta nenhum. */
const COR_FAIXA: Record<string, string> = {
  critico: 'var(--neg)',
  regular: 'var(--warn)',
  bom: 'var(--faixa-neutra)',
  excelente: 'var(--ac)',
  excelente_mais: 'var(--pos)',
  sem_dado: 'var(--tx-off)',
}

export function DistribuicaoFaixas({ faixas }: { faixas: RedeFaixas }) {
  const linhas = faixas.faixas.filter((f) => f.n > 0)
  const total = linhas.reduce((s, f) => s + f.n, 0)

  return (
    <Glass style={{ padding: '15px 17px', minWidth: 0 }}>
      <Rotulo>Onde a massa do recorte está</Rotulo>
      {linhas.length === 0 ? (
        <div style={{ font: '400 11.5px/1.65 var(--f-ui)', color: 'var(--tx-narrative)' }}>
          Sem mês fechado para distribuir este recorte. As faixas são limiares de MÊS
          INTEIRO: aplicá-las a uma competência em curso jogaria a rede toda em "Crítico".
        </div>
      ) : (
        <>
          <BarraSegmentada
            partes={linhas.map((f) => ({
              chave: f.chave,
              valor: f.n,
              cor: COR_FAIXA[f.chave] ?? 'var(--tx-off)',
              rotulo: f.rotulo,
            }))}
          />
          <div style={{ marginTop: 12, display: 'flex', flexDirection: 'column', gap: 7 }}>
            {linhas.map((f) => (
              <div key={f.chave} style={{ display: 'flex', alignItems: 'baseline', gap: 8 }}>
                <span
                  aria-hidden
                  style={{
                    width: 9,
                    height: 9,
                    borderRadius: 2,
                    background: COR_FAIXA[f.chave] ?? 'var(--tx-off)',
                    flexShrink: 0,
                  }}
                />
                <span style={{ flex: 1, minWidth: 0, font: '400 11.5px/1.3 var(--f-ui)', color: 'var(--tx-label)' }}>
                  {f.rotulo}
                </span>
                <span className="num" style={{ font: '600 12px/1 var(--f-num)', color: 'var(--tx-strong)' }}>
                  {num(f.n)}
                </span>
                <span
                  className="num"
                  style={{ font: '500 10px/1 var(--f-num)', color: 'var(--tx-muted)', width: 40, textAlign: 'right' }}
                >
                  {pct(total > 0 ? (100 * f.n) / total : null, 0)}
                </span>
                <span
                  className="num"
                  style={{ font: '500 11px/1 var(--f-num)', color: 'var(--tx-sub)', width: 64, textAlign: 'right' }}
                >
                  {brlCurto(f.faturamento)}
                </span>
              </div>
            ))}
          </div>
        </>
      )}
      <div style={{ marginTop: 11, font: '400 10.5px/1.5 var(--f-ui)', color: 'var(--tx-muted)' }}>
        {faixas.competencia
          ? `Faixas de ${rotuloMesCompetencia(faixas.competencia)} — sempre o último mês FECHADO, mesmo quando a competência escolhida está em curso.`
          : 'As faixas rodam sempre sobre o último mês FECHADO, nunca sobre a competência em curso.'}
      </div>
    </Glass>
  )
}

export function Maturidade({ coortes }: { coortes: RedeCoorteResumo[] }) {
  const total = coortes.reduce((s, c) => s + c.n, 0)
  // Escala pelo MAIOR grupo, não pelo total: a leitura aqui é comparativa entre coortes,
  // e uma barra de 12% do recorte vira um traço ilegível quando o trilho vale 100%. O
  // percentual do recorte vai escrito ao lado, então a composição não se perde.
  const maior = coortes.reduce((m, c) => Math.max(m, c.n), 0)

  return (
    <Glass style={{ padding: '15px 17px', minWidth: 0 }}>
      <Rotulo>Maturidade do recorte</Rotulo>
      {total === 0 ? (
        <div style={{ font: '400 11.5px/1.65 var(--f-ui)', color: 'var(--tx-narrative)' }}>
          Nenhuma unidade neste recorte para classificar por tempo de operação.
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 9 }}>
          {coortes.map((c) => (
            <div key={c.chave}>
              <div style={{ display: 'flex', alignItems: 'baseline', gap: 8, marginBottom: 4 }}>
                <span style={{ flex: 1, minWidth: 0, font: '400 11.5px/1.3 var(--f-ui)', color: 'var(--tx-label)' }}>
                  {c.rotulo}
                </span>
                <span className="num" style={{ font: '600 12px/1 var(--f-num)', color: 'var(--tx-strong)' }}>
                  {num(c.n)}
                </span>
                <span
                  className="num"
                  style={{ font: '500 10px/1 var(--f-num)', color: 'var(--tx-muted)', width: 40, textAlign: 'right' }}
                >
                  {pct((100 * c.n) / total, 0)}
                </span>
              </div>
              <div style={{ height: 8, background: 'var(--surf-raised)', borderRadius: 4 }}>
                <div
                  style={{
                    width: `${maior > 0 ? (100 * c.n) / maior : 0}%`,
                    height: '100%',
                    borderRadius: 4,
                    background: 'var(--ac-a60)',
                  }}
                />
              </div>
            </div>
          ))}
        </div>
      )}
      <div style={{ marginTop: 11, font: '400 10.5px/1.5 var(--f-ui)', color: 'var(--tx-muted)' }}>
        Coorte é tempo de operação. Ela explica boa parte da diferença entre dois recortes
        antes de qualquer julgamento de desempenho.
      </div>
    </Glass>
  )
}

export function Destaques({
  destaques,
  base,
  onBase,
  expandido,
  onExpandir,
  onUnidade,
}: {
  destaques: DestaquesDoRecorte
  base: BaseDoDestaque
  onBase: (b: BaseDoDestaque) => void
  expandido: boolean
  onExpandir: (v: boolean) => void
  onUnidade: (u: RedeUnidade) => void
}) {
  const { puxam, seguram, todas, semBase, competencia } = destaques
  const rotuloBase = competencia ? rotuloMesCompetencia(competencia) : null

  return (
    <Glass style={{ padding: '15px 17px', minWidth: 0 }}>
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 10, flexWrap: 'wrap' }}>
        <Rotulo>Quem puxa e quem segura</Rotulo>
        <div style={{ flex: 1 }} />
        {/* Duas leituras da MESMA lista, e não dois painéis: "ano a ano" abre a conta do
            crescimento comparável do card ao lado — é de lá que vem a pergunta "por causa
            de quem?" — e "mês anterior" responde o que mudou agora. Trocar de base
            reordena a lista inteira, então o rodapé sempre diz contra o que se compara. */}
        {(
          [
            ['sss', 'Ano a ano (SSS)'],
            ['mes', 'Vs mês anterior'],
          ] as [BaseDoDestaque, string][]
        ).map(([chave, rotulo]) => {
          const ativo = base === chave
          return (
            <button
              key={chave}
              type="button"
              aria-pressed={ativo}
              onClick={() => onBase(chave)}
              style={{
                marginBottom: 11,
                padding: '4px 8px',
                borderRadius: 'var(--r-sm)',
                border: `1px solid ${ativo ? 'var(--ac)' : 'var(--line-soft)'}`,
                background: ativo ? 'var(--ac-a12)' : 'transparent',
                color: ativo ? 'var(--ac-text)' : 'var(--tx-soft)',
                font: '600 10px/1 var(--f-ui)',
                cursor: 'pointer',
                whiteSpace: 'nowrap',
              }}
            >
              {rotulo}
            </button>
          )
        })}
      </div>

      {expandido ? (
        <ListaCompleta itens={todas} semBase={semBase} onUnidade={onUnidade} />
      ) : (
        <div style={{ display: 'flex', gap: 18, flexWrap: 'wrap' }}>
          {/* Coluna vazia diz POR QUE está vazia, e a razão é diferente em cada caso: sem
              nenhuma unidade comparável nas duas colunas, o problema é a base; com uma das
              duas cheia, o recorte simplesmente andou todo para o mesmo lado. */}
          <ColunaDestaque
            titulo="Quem puxa"
            itens={puxam}
            onUnidade={onUnidade}
            vazio={
              seguram.length === 0
                ? 'sem base comparável para variação neste recorte'
                : 'nenhuma unidade cresceu nesta comparação'
            }
          />
          <ColunaDestaque
            titulo="Quem segura"
            itens={seguram}
            onUnidade={onUnidade}
            vazio={
              puxam.length === 0
                ? 'sem base comparável para variação neste recorte'
                : 'nenhuma unidade caiu nesta comparação'
            }
          />
        </div>
      )}

      <div style={{ marginTop: 12, display: 'flex', alignItems: 'baseline', gap: 10, flexWrap: 'wrap' }}>
        <button
          type="button"
          onClick={() => onExpandir(!expandido)}
          disabled={todas.length === 0 && semBase.length === 0}
          style={{
            padding: '5px 9px',
            borderRadius: 'var(--r-sm)',
            border: '1px solid var(--line-strong)',
            background: 'transparent',
            color: 'var(--tx-soft)',
            font: '600 10.5px/1 var(--f-ui)',
            cursor: 'pointer',
          }}
        >
          {expandido
            ? 'Mostrar só os extremos'
            : `Ver todas as ${todas.length + semBase.length} unidades`}
        </button>
        <div style={{ flex: 1, minWidth: 200, font: '400 10.5px/1.5 var(--f-ui)', color: 'var(--tx-muted)' }}>
          {base === 'sss' ? (
            <>
              Faturamento de cada unidade contra {rotuloBase ?? 'o mesmo mês do ano anterior'},
              em base comparável: entra quem operou o mês inteiro nos dois períodos. É a
              mesma regra do crescimento comparável do recorte, aberta unidade a unidade.
            </>
          ) : (
            <>
              Faturamento de {rotuloBase ?? 'um mês fechado'} contra o mês anterior. A
              competência em curso não entra: com poucos dias corridos, a variação é ruído
              de janela, não desempenho, e quem inaugurou dentro do período fica fora, como
              no ranking.
            </>
          )}
        </div>
      </div>
    </Glass>
  )
}

/** A lista inteira, ordenada da maior alta para a maior queda.
 *
 *  Existe porque o time pediu para poder abrir a conta: os extremos dizem quem manda no
 *  número, mas a decisão de campo é sobre uma unidade específica, que quase nunca está no
 *  top 5. As sem base comparável vão no fim, VISÍVEIS — sumir com elas faria a lista
 *  parecer completa quando não é. */
function ListaCompleta({
  itens,
  semBase,
  onUnidade,
}: {
  itens: DestaqueDoRecorte[]
  semBase: RedeUnidade[]
  onUnidade: (u: RedeUnidade) => void
}) {
  return (
    <div style={{ maxHeight: 420, overflowY: 'auto', paddingRight: 4 }}>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
        {itens.map((d) => (
          <LinhaDestaque key={d.unidade.id} item={d} onUnidade={onUnidade} />
        ))}
      </div>
      {semBase.length > 0 && (
        <>
          <div
            style={{
              marginTop: 12,
              paddingTop: 9,
              borderTop: '1px solid var(--line-soft)',
              font: '600 10px/1 var(--f-ui)',
              letterSpacing: '.06em',
              textTransform: 'uppercase',
              color: 'var(--tx-label)',
              marginBottom: 8,
            }}
          >
            Sem base comparável ({semBase.length})
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
            {semBase.map((u) => (
              <button
                key={u.id}
                type="button"
                onClick={() => onUnidade(u)}
                title={`Abrir a ficha de ${u.nome}`}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 8,
                  width: '100%',
                  padding: '6px 7px',
                  border: 'none',
                  borderRadius: 'var(--r-sm)',
                  background: 'transparent',
                  textAlign: 'left',
                  cursor: 'pointer',
                }}
              >
                <Semaforo nivel={u.severidade} rotulo={u.severidade_rotulo} tamanho={7} />
                <span
                  style={{
                    flex: 1,
                    minWidth: 0,
                    font: '500 11.5px/1.25 var(--f-ui)',
                    color: 'var(--tx-narrative)',
                    overflow: 'hidden',
                    textOverflow: 'ellipsis',
                    whiteSpace: 'nowrap',
                  }}
                >
                  {u.nome}
                </span>
                <span style={{ font: '400 10px/1 var(--f-ui)', color: 'var(--tx-muted)' }}>
                  {u.comparavel ? 'não operou o período inteiro há um ano' : 'unidade nova'}
                </span>
              </button>
            ))}
          </div>
        </>
      )}
    </div>
  )
}

function ColunaDestaque({
  titulo,
  itens,
  onUnidade,
  vazio,
}: {
  titulo: string
  itens: DestaqueDoRecorte[]
  onUnidade: (u: RedeUnidade) => void
  vazio: string
}) {
  return (
    <div style={{ flex: '1 1 260px', minWidth: 0 }}>
      <div
        style={{
          font: '600 10px/1 var(--f-ui)',
          letterSpacing: '.06em',
          textTransform: 'uppercase',
          color: 'var(--tx-label)',
          marginBottom: 9,
        }}
      >
        {titulo}
      </div>
      {itens.length === 0 ? (
        <div style={{ font: '400 11px/1.5 var(--f-ui)', color: 'var(--tx-muted)' }}>{vazio}</div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
          {itens.map((d) => (
            <LinhaDestaque key={d.unidade.id} item={d} onUnidade={onUnidade} />
          ))}
        </div>
      )}
    </div>
  )
}

/** Uma linha da lista: semáforo, nome, faturamento e a variação.
 *
 *  Mora numa função só porque as duas vistas do painel — os extremos e a lista completa —
 *  precisam ser a MESMA linha. Duplicada, a versão expandida ia divergir na primeira
 *  manutenção e o operador leria dois formatos do mesmo número. */
function LinhaDestaque({
  item,
  onUnidade,
}: {
  item: DestaqueDoRecorte
  onUnidade: (u: RedeUnidade) => void
}) {
  const { unidade: u, variacao_pct, faturamento } = item
  return (
    // Linha inteira num `button`: a ficha é o destino natural de quem lê esta lista, e o
    // alvo de clique passa a ser a linha toda em vez do nome. Vem de graça no teclado e no
    // leitor de tela — e o anel de foco já é global.
    <button
      type="button"
      onClick={() => onUnidade(u)}
      // A maturidade entra no `title` porque explica boa parte das variações extremas
      // desta lista: uma unidade de 6 meses cresce 600% contra o ano passado por estar em
      // rampa, não por desempenho. Ela continua na lista — é ela quem puxa o agregado —,
      // mas quem passa o mouse descobre o porquê antes de cobrar o franqueado.
      title={`Abrir a ficha de ${u.nome} · ${u.uf} · ${u.coorte_rotulo}`}
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: 8,
        width: '100%',
        padding: '6px 7px',
        border: 'none',
        borderRadius: 'var(--r-sm)',
        background: 'transparent',
        textAlign: 'left',
        cursor: 'pointer',
      }}
      onMouseEnter={(e) => {
        e.currentTarget.style.background = 'var(--surf-raised)'
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.background = 'transparent'
      }}
    >
      <Semaforo nivel={u.severidade} rotulo={u.severidade_rotulo} tamanho={7} />
      <span
        style={{
          flex: 1,
          minWidth: 0,
          font: '500 11.5px/1.25 var(--f-ui)',
          color: 'var(--tx-strong)',
          overflow: 'hidden',
          textOverflow: 'ellipsis',
          whiteSpace: 'nowrap',
        }}
      >
        {u.nome}
      </span>
      {/* Faturamento por extenso, com centavo: é o número que o time confere contra o
          extrato. O `title` da linha inteira leva o nome, então aqui cabe o valor cheio. */}
      <span
        className="num"
        style={{ font: '600 11px/1 var(--f-num)', color: 'var(--tx-sub)', whiteSpace: 'nowrap' }}
      >
        {brl(faturamento, false, 2)}
      </span>
      {/* A seta é desenhada aqui, e não pelo `Delta`, porque `Delta` lê o `delta_pct` do
          quarteto (MTD contra MTD) e este painel ordena por outro número. Mostrar um e
          ordenar pelo outro é como a lista sai visivelmente fora de ordem. */}
      <span
        className="num"
        style={{
          width: 62,
          textAlign: 'right',
          font: '700 10.5px/1 var(--f-num)',
          color: corDaVariacao(variacao_pct),
          whiteSpace: 'nowrap',
        }}
      >
        {variacao_pct >= 0 ? '▲' : '▼'} {pct(Math.abs(variacao_pct), 1)}
      </span>
    </button>
  )
}

/** `9` -> `"+9,0%"`; a queda já vem com o sinal do próprio número. O `+` explícito existe
 *  porque, sem ele, "9,0%" ao lado de "2,5%" não diz qual dos dois é crescimento. */
function sinalPct(v: number | null): string {
  if (v === null || !Number.isFinite(v)) return '—'
  return `${v > 0 ? '+' : ''}${pct(v, 1)}`
}

/** Verde sobe, vermelho cai — vale só para métrica em que subir é bom, que é o caso de
 *  tudo o que o SSS soma (faturamento, ativos, recorrentes). */
function corDaVariacao(v: number | null): string {
  if (v === null || !Number.isFinite(v)) return 'var(--tx-muted)'
  return v >= 0 ? 'var(--pos)' : 'var(--neg)'
}

/** Rótulo de seção do painel.
 *
 *  Repete a escala do rótulo da `ExecutiveScreen` de propósito: estes cards ficam LADO A
 *  LADO com os de lá, e meio ponto de diferença no cabeçalho lê como card desalinhado. */
function Rotulo({ children }: { children: ReactNode }) {
  return (
    <div
      style={{
        font: '600 10.5px/1 var(--f-ui)',
        letterSpacing: '.09em',
        textTransform: 'uppercase',
        color: 'var(--tx-muted)',
        marginBottom: 11,
      }}
    >
      {children}
    </div>
  )
}
