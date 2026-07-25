import { alunos, brl, num, pctFrac, rotuloMes } from '../lib/format'
import type {
  DreViabilidade,
  MelhoriaPayback,
  PremissasViabilidade,
  SerieMensalLinha,
} from '../lib/types'
import { Glass } from './primitives'

/* ---------------------------------------------------------------------------
   Graficos da Viabilidade. Formas herdadas do template de referencia.
   Todos SVG puro: sem lib de grafico, sem rede, e o texto continua selecionavel.

   FIN-VIAB-01: nenhum destes graficos calcula numero financeiro. Todos leem o
   `viabilidade_payload_v1` — em especial a `serie_mensal`, que e a UNICA serie do
   sistema. Sairam daqui: o IR/CSLL derivado por subtracao (EBITDA - lucro liquido)
   e a rampa SINTETICA (reta de 0 ate a demanda) que nao existia no motor.
   --------------------------------------------------------------------------- */

/** Resultado de caixa DO MES (o motor manda `fcf_mensal`; `fcf` e o alias curto). */
function fcfMes(l: SerieMensalLinha): number | null {
  const v = l.fcf_mensal ?? l.fcf
  return typeof v === 'number' && Number.isFinite(v) ? v : null
}

/** Posicao no eixo: `mes_contrato` e contiguo (1..64); `mes` pula o zero. */
function pontos(
  serie: SerieMensalLinha[],
  valor: (l: SerieMensalLinha) => number | null,
): { t: number; mes: number; v: number }[] {
  const out: { t: number; mes: number; v: number }[] = []
  for (const l of serie) {
    const v = valor(l)
    if (v === null || !Number.isFinite(l.mes_contrato)) continue
    out.push({ t: l.mes_contrato, mes: l.mes, v })
  }
  return out
}

/** Onde no eixo (mes_contrato) cai um mes de calendario do motor. */
function contratoDoMes(serie: SerieMensalLinha[], mes: number | null): number | null {
  if (mes === null) return null
  const l = serie.find((r) => r.mes === mes)
  return l ? l.mes_contrato : null
}

/**
 * Régua demanda × os DOIS pontos de equilíbrio — a leitura mais importante da tela.
 *
 * P0-2: os dois break-evens vêm rotulados e na MESMA unidade da demanda que o
 * operador digita (alunos TOTAIS, com o mix 69/31 escalando). Antes a tela mostrava
 * um número só, calculado em alunos de BALCÃO, comparado contra a demanda total.
 * P2-11: a escala alcança o p90 da faixa (o fator 1,22 parava em 2.811 com p90 3.034).
 */
export function ReguaBreakEven({
  demanda,
  breakEvenEbitda,
  breakEvenCaixa,
  p90,
}: {
  demanda: number
  breakEvenEbitda: number | null
  breakEvenCaixa: number | null
  p90: number | null
}) {
  const beE = breakEvenEbitda != null && Number.isFinite(breakEvenEbitda) ? breakEvenEbitda : null
  const beC = breakEvenCaixa != null && Number.isFinite(breakEvenCaixa) ? breakEvenCaixa : null

  // A régua tem que caber a demanda, os dois equilíbrios E o p90 da faixa.
  const escala = Math.max(demanda, beE ?? 0, beC ?? 0, p90 ?? 0) * 1.1 || 1400
  const posicao = (v: number) => Math.min(96, Math.max(3, (v / escala) * 100))
  const bePctE = beE != null ? posicao(beE) : null
  const bePctC = beC != null ? posicao(beC) : null
  const demPct = Math.min(98, Math.max(2, (demanda / escala) * 100))

  const acimaEbitda = beE != null && demanda >= beE
  const acimaCaixa = beC != null && demanda >= beC

  const rotulo = beE == null
    ? 'sem equilíbrio calculado'
    : acimaCaixa
      ? 'Cobre operação e financiamento'
      : acimaEbitda
        ? 'Cobre a operação, não o financiamento'
        : 'Abaixo do equilíbrio operacional'
  const corRotulo = acimaCaixa
    ? 'var(--pos-text)'
    : acimaEbitda
      ? 'var(--warn-text)'
      : 'var(--neg)'

  // vermelho -> âmbar (a partir do equilíbrio operacional) -> verde (a partir do de caixa)
  const corte1 = bePctE ?? 40
  const corte2 = Math.max(corte1, bePctC ?? corte1)
  const faixa = `linear-gradient(90deg, #c8324a 0%, #d9a441 ${corte1}%, #d9a441 ${corte2}%, #2ec86e ${Math.min(
    100,
    corte2 + 7,
  )}%, #39a063 100%)`

  return (
    <Glass style={{ padding: '17px 19px' }}>
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'baseline',
          gap: 12,
          marginBottom: 30,
        }}
      >
        <span style={{ font: '600 13px/1 var(--f-ui)', color: 'var(--tx-strong)' }}>
          Demanda assumida vs. pontos de equilíbrio
        </span>
        <span style={{ font: '600 12px/1 var(--f-ui)', color: corRotulo }}>{rotulo}</span>
      </div>

      <div style={{ position: 'relative', margin: '0 4px' }}>
        <div style={{ height: 16, borderRadius: 9, background: faixa }} />

        {/* Marcador do break-even OPERACIONAL (EBITDA = 0) */}
        {bePctE != null && (
          <Marcador
            posicao={bePctE}
            topo={24}
            titulo="break-even operacional (EBITDA = 0)"
            valor={alunos(beE)}
          />
        )}

        {/* Marcador do break-even DE CAIXA (cobre a PMT do financiamento) */}
        {bePctC != null && (
          <Marcador
            posicao={bePctC}
            topo={44}
            titulo="break-even de caixa (com financiamento)"
            valor={alunos(beC)}
          />
        )}

        {/* Knob da demanda assumida */}
        <div
          style={{
            position: 'absolute',
            left: `${demPct}%`,
            top: -2,
            transform: 'translateX(-50%)',
            width: 20,
            height: 20,
            borderRadius: '50%',
            background: acimaCaixa
              ? 'var(--pos-text)'
              : acimaEbitda
                ? 'var(--warn-text)'
                : 'var(--neg)',
            border: '3px solid var(--bg-knob)',
            boxShadow: '0 3px 10px rgba(0,0,0,.5)',
          }}
        />
        <div
          className="num"
          style={{
            position: 'absolute',
            left: `${demPct}%`,
            top: -30,
            transform: 'translateX(-50%)',
            font: '600 10.5px/1 var(--f-num)',
            color: 'var(--tx-strong)',
            background: 'rgba(255,255,255,.08)',
            padding: '4px 8px',
            borderRadius: 6,
            whiteSpace: 'nowrap',
          }}
        >
          {alunos(demanda)} · premissa
        </div>
      </div>

      <div
        className="num"
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          marginTop: 66,
          font: '400 10px/1 var(--f-num)',
          color: 'var(--tx-sub)',
        }}
      >
        <span>0</span>
        <span>
          {alunos(escala)} alunos totais
          {p90 != null ? ` · p90 da faixa ${alunos(p90)}` : ''}
        </span>
      </div>
    </Glass>
  )
}

/** Traço vertical + rótulo de um dos equilíbrios sobre a régua. */
function Marcador({
  posicao,
  topo,
  titulo,
  valor,
}: {
  posicao: number
  topo: number
  titulo: string
  valor: string
}) {
  return (
    <>
      <div
        style={{
          position: 'absolute',
          left: `${posicao}%`,
          top: -4,
          height: topo + 4,
          width: 2,
          background: 'var(--tx-max)',
          borderRadius: 1,
          opacity: 0.75,
        }}
      />
      <div
        style={{
          position: 'absolute',
          left: `${posicao}%`,
          top: topo,
          transform: 'translateX(-50%)',
          font: '400 9.5px/1.2 var(--f-ui)',
          color: 'var(--tx-sub)',
          whiteSpace: 'nowrap',
          textAlign: 'center',
        }}
      >
        <span className="num" style={{ color: 'var(--tx-soft)', fontWeight: 600 }}>
          {valor}
        </span>{' '}
        · {titulo}
      </div>
    </>
  )
}

/**
 * DRE em cascata do mês steady-state. Barras descem do faturamento até o resultado
 * após IR, agora com as TRÊS naturezas do custo (variável / folha / fixo) e a linha
 * de despesa financeira — tudo pronto no payload. O IR/CSLL vinha derivado por
 * subtração (EBITDA − lucro líquido); agora vem do motor.
 *
 * ANUIDADE (FIN-VIAB-01): o faturamento bruto entra decomposto em duas barras —
 * "Mensalidades" e "Anuidade". Antes a anuidade engordava o faturamento sem nenhuma
 * linha explicando de onde vinha (objeção legítima do gate de QA). O total
 * (`dre.faturamento`) e a parcela (`dre.receita_anuidade`) vêm PRONTOS do payload;
 * a barra de mensalidades é o complemento entre dois números servidos — GEOMETRIA
 * de gráfico, não uma fórmula financeira nova (essas só existem no simulador.py).
 *
 * `premissas` serve só para ROTULAR: o mês de referência do regime pleno
 * (`mes_referencia_steady`, lido do payload — nunca recalculado a partir de
 * `maturacao_meses`) e a regra da anuidade (valor/ano, % elegível, só balcão).
 */
export function CascataDre({
  dre,
  premissas,
}: {
  dre: DreViabilidade | null
  premissas: PremissasViabilidade | null
}) {
  const d: DreViabilidade = dre ?? {
    faturamento: null,
    receita_anuidade: null,
    deducoes: null,
    receita_liquida: null,
    impostos: null,
    receita_pos_impostos: null,
    custos_op: null,
    custos_variaveis: null,
    folha: null,
    custos_fixos: null,
    ebitda: null,
    margem: null,
    ir_csll: null,
    despesa_financeira: null,
    resultado_apos_ir: null,
  }

  const anuidade =
    d.receita_anuidade != null && Number.isFinite(d.receita_anuidade) ? d.receita_anuidade : null
  const temAnuidade = anuidade !== null && anuidade > 0
  // Complemento entre dois valores SERVIDOS (total - parcela). Não é um degrau novo
  // do DRE: é a mesma linha de faturamento partida em duas barras para leitura.
  const mensalidades =
    temAnuidade && d.faturamento != null ? d.faturamento - (anuidade as number) : d.faturamento

  /** Mês de operação a que TODA esta DRE se refere (regime pleno). */
  const mesRef = premissas?.mes_referencia_steady ?? null

  const barras = [
    temAnuidade
      ? { rotulo: 'Mensalidades', valor: mensalidades, tipo: 'pos' as const }
      : { rotulo: 'Fat. bruto', valor: d.faturamento, tipo: 'pos' as const },
    ...(temAnuidade ? [{ rotulo: 'Anuidade', valor: anuidade, tipo: 'anu' as const }] : []),
    { rotulo: 'Deduções', valor: d.deducoes, tipo: 'neg' as const },
    { rotulo: 'Impostos', valor: d.impostos, tipo: 'neg' as const },
    { rotulo: 'Custo variável', valor: d.custos_variaveis, tipo: 'neg' as const },
    // "Folha (fixa)": o rotulo tem de dizer a natureza do custo. A folha e
    // dimensionada pelo faturamento MADURO e paga integralmente desde o mes 1 —
    // nao acompanha a rampa (decisao de Felipe, 2026-07-24).
    { rotulo: 'Folha (fixa)', valor: d.folha, tipo: 'neg' as const },
    { rotulo: 'Fixos + aluguel', valor: d.custos_fixos, tipo: 'neg' as const },
    { rotulo: 'EBITDA', valor: d.ebitda, tipo: 'res' as const },
    { rotulo: 'IR/CSLL', valor: d.ir_csll, tipo: 'neg' as const },
    { rotulo: 'Result. após IR', valor: d.resultado_apos_ir, tipo: 'res' as const },
    { rotulo: 'Desp. financeira', valor: d.despesa_financeira, tipo: 'fin' as const },
  ]

  const teto = Math.max(1, d.faturamento ?? 1)
  const piso = Math.min(0, d.ebitda ?? 0, d.resultado_apos_ir ?? 0)
  const amplitude = teto - piso || 1
  // 130 -> 169 (+30%) -> 190 (+21), pedidos de Felipe (2026-07-24): as barras ficavam
  // achatadas. A cascata ganhou linhas neste ciclo (as 3 parcelas do custo + despesa
  // financeira), entao ha mais barras dividindo a MESMA altura — cada uma sobrava
  // ainda mais baixa.
  const H = 190

  return (
    <Glass style={{ padding: '17px 19px', minWidth: 0 }}>
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'baseline',
          marginBottom: 16,
          gap: 10,
        }}
      >
        <span style={{ font: '600 13px/1 var(--f-ui)', color: 'var(--tx-strong)' }}>
          Composição do resultado
        </span>
        <span
          className="num"
          style={{ font: '400 10px/1 var(--f-num)', color: 'var(--tx-muted)' }}
        >
          {mesRef != null ? `DRE do mês ${num(mesRef)} · regime pleno` : 'DRE steady-state'} ·
          margem {pctFrac(d.margem)}
        </span>
      </div>

      {/* Linha de receita explícita: o faturamento bruto e as DUAS fontes que o
          compõem. Sem isto o operador via o faturamento subir sem causa visível. */}
      <div
        style={{
          marginBottom: 14,
          padding: '10px 12px',
          background: 'var(--surf-raised)',
          border: '1px solid var(--line-soft)',
          borderRadius: 'var(--r-md)',
        }}
      >
        <div
          style={{
            display: 'flex',
            flexWrap: 'wrap',
            gap: 18,
            alignItems: 'baseline',
          }}
        >
          <LinhaReceita rotulo="Faturamento bruto" valor={d.faturamento} forte />
          <LinhaReceita rotulo="Mensalidades" valor={mensalidades} />
          <LinhaReceita rotulo="Anuidade" valor={anuidade} destaque={temAnuidade} />
        </div>
        <div
          style={{ font: '400 10px/1.5 var(--f-ui)', color: 'var(--tx-sub)', marginTop: 7 }}
        >
          {temAnuidade && premissas ? (
            <>
              Anuidade: {brl(premissas.anuidade_valor, false, 2)} <strong>uma vez por ano</strong>{' '}
              por aluno {premissas.anuidade_apenas_balcao ? 'de balcão' : ''} que completa{' '}
              {num(premissas.anuidade_mes_inicio)} meses de casa —{' '}
              {pctFrac(premissas.anuidade_elegivel_pct)} chegam lá (a elegibilidade sai do próprio
              churn, não é número avulso). Reconhecida <strong>pro-rata mensal</strong> a partir do
              mês {num(premissas.anuidade_mes_inicio)}, porque os aniversários se espalham pelo
              ano.
              {premissas.anuidade_apenas_balcao
                ? ' Aluno de agregador (Gympass/TotalPass) não paga: o agregador remunera por acesso.'
                : ''}
            </>
          ) : (
            'Anuidade desligada neste cenário: todo o faturamento vem de mensalidades.'
          )}
        </div>
        {mesRef != null && (
          <div
            style={{ font: '400 10px/1.5 var(--f-ui)', color: 'var(--tx-sub)', marginTop: 5 }}
          >
            Todos os números de steady-state desta seção (e os KPIs acima) são do{' '}
            <strong style={{ color: 'var(--tx-soft)' }}>mês {num(mesRef)}</strong> — o primeiro em
            regime pleno
            {premissas
              ? `: alunos maduros (rampa de ${num(premissas.maturacao_meses)} meses) e anuidade já em cobrança`
              : ''}
            .
          </div>
        )}
      </div>

      <div
        style={{
          display: 'flex',
          alignItems: 'flex-end',
          gap: 8,
          height: H,
          marginBottom: 8,
        }}
      >
        {barras.map((b) => {
          const v = b.valor ?? 0
          const altura = Math.max(3, (Math.abs(v) / amplitude) * H)
          const cor =
            b.tipo === 'neg'
              ? 'var(--neg-bar)'
              : b.tipo === 'fin'
                ? 'var(--warn)'
                : b.tipo === 'anu'
                  ? 'var(--ac)' // anuidade: cor própria, é outra fonte de receita
                  : b.tipo === 'res'
                    ? v >= 0
                      ? 'var(--pos)'
                      : 'var(--neg)'
                    : 'var(--pos)'
          return (
            <div
              key={b.rotulo}
              style={{
                flex: 1,
                display: 'flex',
                flexDirection: 'column',
                justifyContent: 'flex-end',
                height: '100%',
              }}
            >
              <div
                style={{
                  height: altura,
                  background: cor,
                  borderRadius: 3,
                  margin: '0 16%',
                  transition: 'height .3s ease',
                }}
                title={`${b.rotulo}: ${brl(b.valor)}`}
              />
            </div>
          )
        })}
      </div>

      <div style={{ display: 'flex', gap: 8 }}>
        {barras.map((b) => (
          <div key={b.rotulo} style={{ flex: 1, textAlign: 'center', minWidth: 0 }}>
            <div
              className="num"
              style={{
                font: '600 10px/1.2 var(--f-num)',
                color:
                  b.tipo === 'res'
                    ? (b.valor ?? 0) >= 0
                      ? 'var(--pos-text)'
                      : 'var(--neg)'
                    : b.tipo === 'fin'
                      ? 'var(--warn-text)'
                      : b.tipo === 'anu'
                        ? 'var(--ac-text)'
                        : b.tipo === 'neg'
                          ? 'var(--tx-narrative)'
                          : 'var(--tx-soft)',
              }}
            >
              {b.valor === null ? 'n/d' : brl(b.valor, true)}
            </div>
            <div
              style={{
                font: '400 9px/1.2 var(--f-ui)',
                color: 'var(--tx-muted)',
                marginTop: 4,
              }}
            >
              {b.rotulo}
            </div>
          </div>
        ))}
      </div>

      <p
        style={{
          font: '400 10px/1.5 var(--f-ui)',
          color: 'var(--tx-sub)',
          margin: '12px 0 0',
        }}
      >
        Receita líquida {brl(d.receita_liquida)} (bruto − deduções) e receita após impostos{' '}
        {brl(d.receita_pos_impostos)} vêm prontas do motor. Custo operacional {brl(d.custos_op)} =
        variável {brl(d.custos_variaveis)} + folha {brl(d.folha)} + fixos com aluguel{' '}
        {brl(d.custos_fixos)}. A <strong>folha é FIXA desde o mês 1</strong>
        {premissas
          ? `: ${brl(premissas.folha_fixa_mes, false, 2)}/mês, dimensionados por ${pctFrac(
              premissas.folha_pct,
            )} do faturamento MADURO (${brl(premissas.folha_base_faturamento_maduro, true)})`
          : ''}{' '}
        — a equipe é contratada antes dos alunos, então ela NÃO acompanha a rampa e só o
        reajuste anual a move. Neste mês de regime pleno o valor coincide com a base; nos
        meses de rampa é ela que segura o EBITDA no negativo. A despesa financeira (juros da
        parcela) aparece à parte: o resultado após IR é DESALAVANCADO, antes da PMT.
      </p>
    </Glass>
  )
}

/** Uma das fontes de receita do faturamento bruto, no cabeçalho da cascata. */
function LinhaReceita({
  rotulo,
  valor,
  forte,
  destaque,
}: {
  rotulo: string
  valor: number | null
  forte?: boolean
  destaque?: boolean
}) {
  return (
    <div style={{ minWidth: 0 }}>
      <div
        style={{
          font: '500 10px/1 var(--f-ui)',
          color: destaque ? 'var(--ac-text)' : 'var(--tx-label)',
          marginBottom: 5,
        }}
      >
        {rotulo}
      </div>
      <div
        className="num"
        style={{
          font: `${forte ? 700 : 600} ${forte ? 14 : 13}px/1 var(--f-num)`,
          color: destaque ? 'var(--ac-text)' : forte ? 'var(--tx-max)' : 'var(--tx-soft)',
        }}
      >
        {valor === null ? 'n/d' : brl(valor, false, 2)}
      </div>
    </div>
  )
}

/**
 * Rampa de alunos — agora a curva REAL do motor (`serie_mensal[].alunos_total`).
 * Antes era uma reta sintética de 0 até a demanda total, desenhada aqui e sem
 * contrapartida no simulador: a operação começa com `alunos_inicial` no mês 1 e
 * o mix balcão/agregadores escala junto até o platô.
 */
export function RampaAlunos({
  serie,
  maturacaoMeses,
}: {
  serie: SerieMensalLinha[]
  maturacaoMeses: number | null
}) {
  const pts = pontos(
    serie.filter((l) => l.fase === 'operacao'),
    (l) => (Number.isFinite(l.alunos_total) ? l.alunos_total : null),
  )

  if (pts.length < 2) {
    return (
      <Glass
        style={{
          padding: '17px 19px',
          flex: 1,
          display: 'flex',
          flexDirection: 'column',
          minWidth: 0,
        }}
      >
        <Cabecalho titulo="Rampa de alunos" sub="série do motor" valor="n/d" cor="var(--tx-muted)" />
        <p style={{ font: '400 12px/1.5 var(--f-ui)', color: 'var(--tx-muted)', marginTop: 10 }}>
          Sem série mensal para este cenário.
        </p>
      </Glass>
    )
  }

  // Horizonte curto: a rampa se lê nos primeiros meses; o platô já aparece plano.
  const mat = maturacaoMeses != null && maturacaoMeses > 0 ? Math.round(maturacaoMeses) : null
  const limite = Math.min(pts[pts.length - 1].mes, Math.max((mat ?? 8) + 6, 18))
  const visiveis = pts.filter((p) => p.mes <= limite)
  const plateau = Math.max(...visiveis.map((p) => p.v))

  const W = 300
  const H = 120
  const y = (v: number) => H - (v / Math.max(1, plateau)) * (H * 0.88) - 8
  const x = (mes: number) => (mes / limite) * W

  // A curva parte do mês 0 (unidade fechada) e sobe até o platô do motor.
  const linha = [`0,${y(0).toFixed(1)}`]
    .concat(visiveis.map((p) => `${x(p.mes).toFixed(1)},${y(p.v).toFixed(1)}`))
    .join(' ')
  const area = `0,${H} ${linha} ${W},${H}`
  const xMat = mat != null && mat <= limite ? x(mat) : null

  return (
    <Glass
      style={{
        padding: '17px 19px',
        flex: 1,
        display: 'flex',
        flexDirection: 'column',
        minWidth: 0,
      }}
    >
      <Cabecalho
        titulo="Rampa de alunos"
        sub={mat != null ? `alunos totais · platô no mês ${mat}` : 'alunos totais (motor)'}
        valor={alunos(plateau)}
        cor="var(--ac-text)"
      />
      <div style={{ flex: 1, minHeight: 120, marginTop: 12 }}>
        <svg
          viewBox={`0 0 ${W} ${H}`}
          preserveAspectRatio="none"
          style={{ width: '100%', height: '100%', display: 'block' }}
          aria-hidden
        >
          <defs>
            <linearGradient id="rampaGrad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="var(--ac)" stopOpacity="0.3" />
              <stop offset="100%" stopColor="var(--ac)" stopOpacity="0.02" />
            </linearGradient>
          </defs>
          <polygon points={area} fill="url(#rampaGrad)" />
          {xMat != null && (
            <line
              x1={xMat}
              y1="0"
              x2={xMat}
              y2={H}
              stroke="var(--ac)"
              strokeWidth="1"
              strokeDasharray="3 3"
              opacity="0.5"
              vectorEffect="non-scaling-stroke"
            />
          )}
          <polyline
            points={linha}
            fill="none"
            stroke="var(--ac)"
            strokeWidth="2.5"
            strokeLinejoin="round"
            strokeLinecap="round"
            vectorEffect="non-scaling-stroke"
          />
        </svg>
      </div>
      <div
        className="num"
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          marginTop: 4,
          font: '400 9px/1 var(--f-num)',
          color: 'var(--tx-sub)',
        }}
      >
        <span>mês 0</span>
        <span>mês {limite}</span>
      </div>
    </Glass>
  )
}

/**
 * Fluxo de caixa ACUMULADO (`serie_mensal[].fcf_acumulado`) — mergulha com o CAPEX
 * na pré-abertura e cruza o zero no payback. Como a série é a mesma do KPI, o mês
 * marcado aqui e o payback do card são por construção o mesmo número (eram 33 e 35).
 */
export function FluxoCaixa({
  serie,
  payback,
  carencia,
}: {
  serie: SerieMensalLinha[]
  payback: number | null
  carencia: number
}) {
  const pts = pontos(serie, (l) =>
    Number.isFinite(l.fcf_acumulado) ? l.fcf_acumulado : null,
  )

  if (pts.length < 2) {
    return (
      <Glass style={{ padding: '17px 19px' }}>
        <Cabecalho
          titulo="Fluxo de caixa acumulado"
          sub="M-4 a M+60"
          valor="n/d"
          cor="var(--tx-muted)"
        />
        <p style={{ font: '400 12px/1.5 var(--f-ui)', color: 'var(--tx-muted)', marginTop: 10 }}>
          Sem série de fluxo para este cenário.
        </p>
      </Glass>
    )
  }

  const W = 620
  const H = 150
  const padL = 8
  const padR = 8
  const tMin = pts[0].t
  const tMax = pts[pts.length - 1].t
  const span = tMax - tMin || 1
  const vals = pts.map((p) => p.v)
  const min = Math.min(...vals, 0)
  const max = Math.max(...vals, 0)
  const range = max - min || 1

  const x = (t: number) => padL + ((t - tMin) / span) * (W - padL - padR)
  const y = (v: number) => H - ((v - min) / range) * H
  const zeroY = y(0)

  const linha = pts.map((p) => `${x(p.t).toFixed(1)},${y(p.v).toFixed(1)}`).join(' ')
  const area = `${x(tMin).toFixed(1)},${zeroY.toFixed(1)} ${linha} ${x(tMax).toFixed(
    1,
  )},${zeroY.toFixed(1)}`

  const fim = pts[pts.length - 1]
  const zeroFrac = Math.max(0, Math.min(1, zeroY / H))
  const tPayback = contratoDoMes(serie, payback)

  return (
    <Glass
      style={{
        padding: '17px 19px',
        flex: 1,
        minWidth: 0,
        display: 'flex',
        flexDirection: 'column',
      }}
    >
      <div
        style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', gap: 10 }}
      >
        <span>
          <span
            style={{ display: 'block', font: '600 13px/1 var(--f-ui)', color: 'var(--tx-strong)' }}
          >
            Fluxo de caixa acumulado
          </span>
          <span
            style={{
              display: 'block',
              font: '400 10px/1 var(--f-ui)',
              color: 'var(--tx-muted)',
              marginTop: 5,
            }}
          >
            M-4 a M+60 · começa no CAPEX
            {carencia > 0 ? ` · carência de ${carencia}m de aluguel` : ' · sem carência'}
          </span>
        </span>
        <span style={{ textAlign: 'right' }}>
          <span
            className="num"
            style={{
              display: 'block',
              font: '700 13px/1 var(--f-num)',
              color: fim.v >= 0 ? 'var(--pos-text)' : 'var(--neg)',
            }}
          >
            {brl(fim.v, true)}
          </span>
          <span
            style={{
              display: 'block',
              font: '400 9.5px/1 var(--f-ui)',
              color: 'var(--tx-sub)',
              marginTop: 4,
            }}
          >
            no {rotuloMes(fim.mes)}
          </span>
        </span>
      </div>

      <svg
        viewBox={`0 0 ${W} ${H}`}
        preserveAspectRatio="none"
        style={{ width: '100%', height: 150, marginTop: 12, display: 'block' }}
        aria-hidden
      >
        <defs>
          <linearGradient id="fcfGrad" gradientUnits="userSpaceOnUse" x1="0" y1="0" x2="0" y2={H}>
            <stop offset={zeroFrac} stopColor="var(--pos)" stopOpacity="0.28" />
            <stop offset={zeroFrac} stopColor="var(--neg)" stopOpacity="0.24" />
          </linearGradient>
        </defs>

        {/* área entre a curva e a linha do zero: verde acima, vermelho abaixo */}
        <polygon points={area} fill="url(#fcfGrad)" />

        {/* linha do zero (retorno do capital investido) */}
        <line
          x1={padL}
          y1={zeroY}
          x2={W - padR}
          y2={zeroY}
          stroke="rgba(255,255,255,.28)"
          strokeWidth="1"
          strokeDasharray="4 4"
        />

        {/* marcador do payback (cruzamento do zero) */}
        {tPayback != null && (
          <line
            x1={x(tPayback)}
            y1="0"
            x2={x(tPayback)}
            y2={H}
            stroke="var(--ac)"
            strokeWidth="1.5"
            strokeDasharray="3 3"
          />
        )}

        {/* a curva */}
        <polyline
          points={linha}
          fill="none"
          stroke="var(--tx-max)"
          strokeWidth="2.5"
          strokeLinejoin="round"
          strokeLinecap="round"
        />
      </svg>

      {/* eixo de meses + rótulo do payback */}
      <div style={{ position: 'relative', height: 16, marginTop: 2 }}>
        <span
          className="num"
          style={{
            position: 'absolute',
            left: 0,
            font: '400 9.5px/1 var(--f-num)',
            color: 'var(--tx-sub)',
          }}
        >
          {rotuloMes(pts[0].mes)}
        </span>
        <span
          className="num"
          style={{
            position: 'absolute',
            right: 0,
            font: '400 9.5px/1 var(--f-num)',
            color: 'var(--tx-sub)',
          }}
        >
          {rotuloMes(fim.mes)}
        </span>
        {tPayback != null && payback != null && (
          <span
            className="num"
            style={{
              position: 'absolute',
              left: `${((tPayback - tMin) / span) * 100}%`,
              transform: 'translateX(-50%)',
              font: '600 9.5px/1 var(--f-num)',
              color: 'var(--ac-text)',
              whiteSpace: 'nowrap',
            }}
          >
            payback {num(payback)}m
          </span>
        )}
      </div>
    </Glass>
  )
}

/**
 * Resultado de caixa MÊS A MÊS (`serie_mensal[].fcf_mensal`, não acumulado): o que a
 * operação gera em cada mês, já líquido de IR/CSLL, PMT e investimento do mês.
 *
 * P2-15: isto NÃO é payback. O indicador daqui é o "1º mês com caixa operacional
 * positivo"; payback é só o retorno do capital (gráfico acima).
 */
export function FluxoCaixaOperacional({
  serie,
  mesPositivo,
}: {
  serie: SerieMensalLinha[]
  mesPositivo: number | null
}) {
  const pts = pontos(serie, fcfMes)

  if (pts.length < 2) {
    return (
      <Glass style={{ padding: '17px 19px' }}>
        <Cabecalho
          titulo="Caixa operacional mês a mês"
          sub="por mês"
          valor="n/d"
          cor="var(--tx-muted)"
        />
        <p style={{ font: '400 12px/1.5 var(--f-ui)', color: 'var(--tx-muted)', marginTop: 10 }}>
          Sem série de fluxo para este cenário.
        </p>
      </Glass>
    )
  }

  const W = 620
  // 230 -> 300 (+30%) por pedido de Felipe (2026-07-24): a 230 o grafico ficava
  // espremido num retangulo 2,7:1 e a travessia do zero mal se distinguia. O card
  // (Glass) cresce junto porque o SVG esta no fluxo normal.
  const H = 300
  const padL = 8
  const padR = 8
  const tMin = pts[0].t
  const tMax = pts[pts.length - 1].t
  const span = tMax - tMin || 1
  const vals = pts.map((p) => p.v)
  const min = Math.min(...vals, 0)
  const max = Math.max(...vals, 0)
  const range = max - min || 1

  const x = (t: number) => padL + ((t - tMin) / span) * (W - padL - padR)
  const y = (v: number) => H - ((v - min) / range) * H
  const zeroY = y(0)

  const linha = pts.map((p) => `${x(p.t).toFixed(1)},${y(p.v).toFixed(1)}`).join(' ')
  const area = `${x(tMin).toFixed(1)},${zeroY.toFixed(1)} ${linha} ${x(tMax).toFixed(
    1,
  )},${zeroY.toFixed(1)}`

  const estavel = pts[pts.length - 1].v // resultado do último mês (platô steady)
  const zeroFrac = Math.max(0, Math.min(1, zeroY / H))
  const tPos = contratoDoMes(serie, mesPositivo)

  return (
    <Glass style={{ padding: '17px 19px' }}>
      <div
        style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', gap: 10 }}
      >
        <span>
          <span
            style={{ display: 'block', font: '600 13px/1 var(--f-ui)', color: 'var(--tx-strong)' }}
          >
            Caixa operacional mês a mês
          </span>
          <span
            style={{
              display: 'block',
              font: '400 10px/1 var(--f-ui)',
              color: 'var(--tx-muted)',
              marginTop: 5,
            }}
          >
            {mesPositivo != null
              ? `1º mês com caixa operacional positivo: mês ${mesPositivo} · daí em diante fica positivo`
              : 'A operação não fecha nenhum mês no positivo de forma permanente neste cenário'}
          </span>
        </span>
        <span style={{ textAlign: 'right' }}>
          <span
            className="num"
            style={{
              display: 'block',
              font: '700 13px/1 var(--f-num)',
              color: estavel >= 0 ? 'var(--pos-text)' : 'var(--neg)',
            }}
          >
            {brl(estavel, true)}
          </span>
          <span
            style={{
              display: 'block',
              font: '400 9.5px/1 var(--f-ui)',
              color: 'var(--tx-sub)',
              marginTop: 4,
            }}
          >
            por mês (estável)
          </span>
        </span>
      </div>

      <div style={{ position: 'relative', marginTop: 12 }}>
        <svg
          viewBox={`0 0 ${W} ${H}`}
          preserveAspectRatio="none"
          style={{ width: '100%', height: H, display: 'block' }}
          aria-hidden
        >
          <defs>
            <linearGradient id="fcoGrad" gradientUnits="userSpaceOnUse" x1="0" y1="0" x2="0" y2={H}>
              <stop offset={zeroFrac} stopColor="var(--pos)" stopOpacity="0.28" />
              <stop offset={zeroFrac} stopColor="var(--neg)" stopOpacity="0.24" />
            </linearGradient>
          </defs>

          <polygon points={area} fill="url(#fcoGrad)" />

          {/* linha do zero: acima = mês no azul, abaixo = mês no vermelho */}
          <line
            x1={padL}
            y1={zeroY}
            x2={W - padR}
            y2={zeroY}
            stroke="rgba(255,255,255,.28)"
            strokeWidth="1"
            strokeDasharray="4 4"
          />

          {/* marcador do 1º mês com caixa operacional positivo */}
          {tPos != null && (
            <line
              x1={x(tPos)}
              y1="0"
              x2={x(tPos)}
              y2={H}
              stroke="var(--ac)"
              strokeWidth="1.5"
              strokeDasharray="3 3"
            />
          )}

          {/* a curva do resultado mensal */}
          <polyline
            points={linha}
            fill="none"
            stroke="var(--tx-max)"
            strokeWidth="2.5"
            strokeLinejoin="round"
            strokeLinecap="round"
          />

          {tPos != null && <circle cx={x(tPos)} cy={zeroY} r="3.2" fill="var(--ac)" />}
        </svg>
        {/* Rótulos do eixo Y: a MAGNITUDE (R$/mês) muda por cenário mesmo quando a
            forma (rampa até o platô) parece igual — antes o gráfico normalizado dava a
            impressão de ser sempre o mesmo. */}
        <span
          className="num"
          style={{
            position: 'absolute',
            top: 1,
            left: 3,
            font: '400 9px/1 var(--f-num)',
            color: 'var(--tx-sub)',
            pointerEvents: 'none',
          }}
        >
          {brl(max, true)}
        </span>
        <span
          className="num"
          style={{
            position: 'absolute',
            top: `${zeroFrac * 100}%`,
            left: 3,
            transform: 'translateY(-50%)',
            font: '400 9px/1 var(--f-num)',
            color: 'var(--tx-off)',
            pointerEvents: 'none',
          }}
        >
          R$ 0
        </span>
        {min < 0 && (
          <span
            className="num"
            style={{
              position: 'absolute',
              bottom: 1,
              left: 3,
              font: '400 9px/1 var(--f-num)',
              color: 'var(--neg)',
              pointerEvents: 'none',
            }}
          >
            {brl(min, true)}
          </span>
        )}
      </div>

      {/* eixo de meses + rótulo do 1º mês positivo */}
      <div style={{ position: 'relative', height: 16, marginTop: 2 }}>
        <span
          className="num"
          style={{
            position: 'absolute',
            left: 0,
            font: '400 9.5px/1 var(--f-num)',
            color: 'var(--tx-sub)',
          }}
        >
          {rotuloMes(pts[0].mes)}
        </span>
        <span
          className="num"
          style={{
            position: 'absolute',
            right: 0,
            font: '400 9.5px/1 var(--f-num)',
            color: 'var(--tx-sub)',
          }}
        >
          {rotuloMes(pts[pts.length - 1].mes)}
        </span>
        {tPos != null && mesPositivo != null && (
          <span
            className="num"
            style={{
              position: 'absolute',
              left: `${((tPos - tMin) / span) * 100}%`,
              transform: 'translateX(-50%)',
              font: '600 9.5px/1 var(--f-num)',
              color: 'var(--ac-text)',
              whiteSpace: 'nowrap',
            }}
          >
            caixa positivo · mês {mesPositivo}
          </span>
        )}
      </div>
    </Glass>
  )
}

function Cabecalho({
  titulo,
  sub,
  valor,
  cor,
}: {
  titulo: string
  sub: string
  valor: string
  cor: string
}) {
  return (
    <div
      style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', gap: 10 }}
    >
      <span>
        <span
          style={{
            display: 'block',
            font: '600 13px/1 var(--f-ui)',
            color: 'var(--tx-strong)',
          }}
        >
          {titulo}
        </span>
        <span
          style={{
            display: 'block',
            font: '400 10px/1 var(--f-ui)',
            color: 'var(--tx-muted)',
            marginTop: 5,
          }}
        >
          {sub}
        </span>
      </span>
      <span className="num" style={{ font: '700 13px/1 var(--f-num)', color: cor }}>
        {valor}
      </span>
    </div>
  )
}

/** Monta a frase de melhoria do payback (quanto cortar de CAPEX ou aluguel). */
function textoMelhoria(m: MelhoriaPayback): string {
  const partes: string[] = []
  if (m.reduzir_capex != null) partes.push(`reduza o CAPEX em ~${brl(m.reduzir_capex, true)}`)
  if (m.reduzir_aluguel != null) {
    partes.push(`reduza o aluguel em ~${brl(m.reduzir_aluguel, true)}/mês`)
  }
  if (!partes.length) {
    return 'cortes só de CAPEX ou de aluguel não bastam — reveja a demanda assumida ou a metragem'
  }
  return partes.join(' ou ')
}

/** Banner de veredito — a frase que o operador leva para o comitê. */
export function Veredito({
  aprovado,
  margem,
  demanda,
  breakEvenEbitda,
  breakEvenCaixa,
  payback,
  melhoria,
}: {
  aprovado: boolean
  /** margem EBITDA em FRACAO (o payload nunca manda percentual). */
  margem: number | null
  demanda: number
  breakEvenEbitda: number | null
  breakEvenCaixa: number | null
  payback?: number | null
  /** Sugestao vinda PRONTA do backend (leitura da serie), nunca calculada aqui. */
  melhoria?: MelhoriaPayback | null
}) {
  const cor = aprovado ? 'var(--pos)' : 'var(--warn)'
  const cobreCaixa = breakEvenCaixa != null && demanda >= breakEvenCaixa
  return (
    <div
      style={{
        display: 'flex',
        gap: 14,
        alignItems: 'stretch',
        padding: '15px 18px',
        background: 'var(--surf-verdict)',
        border: '1px solid var(--line)',
        borderRadius: 'var(--r-lg)',
        backdropFilter: 'blur(14px)',
      }}
    >
      <span style={{ width: 4, borderRadius: 3, background: cor, flexShrink: 0 }} />
      <div style={{ flex: 1, minWidth: 0 }}>
        <div
          className="story"
          style={{ font: '400 19px/1.2 var(--f-story)', color: 'var(--tx-max)' }}
        >
          {aprovado ? 'Viável no cenário assumido' : 'Abaixo do ponto de equilíbrio'}
        </div>
        <div
          style={{
            font: '400 12.5px/1.45 var(--f-ui)',
            color: 'var(--tx-narrative)',
            marginTop: 5,
          }}
        >
          Com {alunos(demanda)} alunos totais assumidos
          {breakEvenEbitda != null
            ? ` contra ${alunos(breakEvenEbitda)} de equilíbrio operacional`
            : ''}
          {breakEvenCaixa != null ? ` e ${alunos(breakEvenCaixa)} de equilíbrio de caixa` : ''}, a
          margem EBITDA fica em {pctFrac(margem)}.{' '}
          {aprovado
            ? cobreCaixa
              ? 'O imóvel fecha a conta e ainda cobre o financiamento nas premissas atuais.'
              : 'A operação se paga, mas a demanda ainda não cobre a parcela do financiamento.'
            : 'Reveja aluguel, metragem ou a demanda assumida antes de levar adiante.'}
          {payback != null && (
            <>
              {' '}
              Payback (retorno do capital) em {num(payback)} meses.
            </>
          )}
          {melhoria && (
            <>
              {' '}
              <strong style={{ color: 'var(--warn-text)' }}>
                O payback{payback != null ? ` (~${num(payback)} meses)` : ''} passa de 40 meses.
              </strong>{' '}
              Para trazê-lo a ~{melhoria.alvo_meses} meses, {textoMelhoria(melhoria)}.
            </>
          )}
        </div>
      </div>
      <span
        style={{
          alignSelf: 'flex-start',
          font: '600 11px/1 var(--f-ui)',
          padding: '7px 11px',
          borderRadius: 8,
          whiteSpace: 'nowrap',
          background: aprovado ? 'rgba(46,200,110,.16)' : 'rgba(217,164,65,.16)',
          border: `1px solid ${aprovado ? 'rgba(46,200,110,.35)' : 'rgba(217,164,65,.4)'}`,
          color: aprovado ? 'var(--pos-pill)' : 'var(--warn-text)',
        }}
      >
        {aprovado ? 'Aprovado para comitê' : 'Requer revisão de premissas'}
      </span>
    </div>
  )
}
