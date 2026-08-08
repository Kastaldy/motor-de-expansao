import { useEffect, useState } from 'react'

import CampoNumero from './CampoNumero'
import { Aviso, Botao, Kpi, Spinner } from './primitives'
import { api, ApiError } from '../lib/api'
import { brl, num, pctFrac } from '../lib/format'
import type { ViabilidadeOut } from '../lib/types'

/**
 * Viabilidade DENTRO do modo de ponto: "fecha a conta?" sem sair da ficha.
 *
 * O QUE ESTA TELA NAO FAZ. Nao deriva numero financeiro nenhum. O motor
 * (`dimensionamento/simulador.py`) devolve tudo pronto e aqui so' se LE — mesma regra
 * que a `ViabilityScreen` ja segue por escrito ("a tela nao re-deriva o veredito").
 * Formula financeira fora do `simulador.py` e' proibida no projeto. Ate o `x100` das
 * taxas e' RENDER (`pctFrac`), nao calculo.
 *
 * O VEREDITO E' UM BOOLEANO, NAO UM SCORE. Nao existe `score_viabilidade` nem nota
 * 0-100: existe `dre.flag_viavel` (margem >= minimo E payback <= maximo). Inventar um
 * score composto "para caber no card" criaria uma quarta definicao de viabilidade.
 *
 * A DEMANDA E' SEMPRE PREMISSA. Por decisao estrategica (DEC-009) o motor e'
 * property-first: a demanda nao e' prevista pela geografia, e' digitada (o payload
 * confirma: `demanda_fonte: "premissa_explicita"`). Por isso ela e' semeada pelo p50
 * dos comparaveis e fica EDITAVEL e VISIVEL — um teto de aluguel calculado sobre
 * demanda assumida so' devolve a premissa de quem digitou.
 *
 * ONDE ESTA A LINHA. Esta ficha responde "fecha a conta, e por que". A grade de
 * sensibilidade, a cascata do DRE e o fluxo de caixa mes a mes sao ANALISE e ficam na
 * tela de Viabilidade — trazer tudo para ca duplicaria 1.650 linhas de tela.
 */
export default function BlocoViabilidadePonto({ lat, lng }: { lat: number; lng: number }) {
  const [m2, setM2] = useState(1500)
  const [aluguel, setAluguel] = useState(20000)
  const [demanda, setDemanda] = useState<number | null>(null)
  const [faixa, setFaixa] = useState<{
    p10: number | null
    p50: number | null
    p90: number | null
    n_comparaveis: number
  } | null>(null)

  const [res, setRes] = useState<ViabilidadeOut | null>(null)
  const [carregando, setCarregando] = useState(false)
  const [erro, setErro] = useState<string | null>(null)

  // Semeia a demanda pelo p50 dos comparaveis da metragem. So' semeia: o operador
  // continua dono do numero.
  useEffect(() => {
    let vivo = true
    api
      .faixaAlunos(m2)
      .then((f) => {
        if (!vivo) return
        setFaixa(f)
        setDemanda((atual) => atual ?? f.p50 ?? null)
      })
      .catch(() => {
        /* sem base de calibracao a faixa some; a secao diz isso abaixo */
      })
    return () => {
      vivo = false
    }
  }, [m2])

  async function calcular() {
    if (!demanda) return
    setCarregando(true)
    setErro(null)
    try {
      setRes(await api.viabilidade({ lat, lng, m2, aluguel, demanda }))
    } catch (e) {
      setErro(e instanceof ApiError ? e.message : 'Falha ao calcular a viabilidade.')
      setRes(null)
    } finally {
      setCarregando(false)
    }
  }

  return (
    <div style={{ display: 'grid', gap: 14 }}>
      <div style={{ display: 'flex', gap: 14, flexWrap: 'wrap', alignItems: 'flex-end' }}>
        <Campo rotulo="Metragem">
          <CampoNumero valor={m2} onValor={setM2} maxDigitos={5} sufixo=" m²" min={200} max={5000} rotulo="Metragem do imóvel" />
        </Campo>
        <Campo rotulo="Aluguel pedido">
          <CampoNumero valor={aluguel} onValor={setAluguel} maxDigitos={7} prefixo="R$ " min={0} rotulo="Aluguel pedido pelo proprietário" />
        </Campo>
        <Campo rotulo="Alunos (premissa)">
          <CampoNumero valor={demanda ?? 0} onValor={setDemanda} maxDigitos={5} min={1} rotulo="Demanda assumida, em alunos" />
        </Campo>
        <Botao onClick={calcular} disabled={carregando || !demanda}>
          {carregando ? (
            <span style={{ display: 'inline-flex', alignItems: 'center', gap: 8 }}>
              <Spinner /> Calculando…
            </span>
          ) : (
            'Calcular'
          )}
        </Botao>
      </div>

      {faixa ? (
        <p style={{ font: '400 11.5px/1.5 var(--f-ui)', color: 'var(--tx-sub)', margin: 0 }}>
          Para {num(m2)} m², unidades comparáveis operam entre {num(faixa.p10)} e{' '}
          {num(faixa.p90)} alunos (mediana {num(faixa.p50)}, {faixa.n_comparaveis}{' '}
          comparáveis). A premissa começa na mediana e é sua para ajustar.
        </p>
      ) : (
        <p style={{ font: '400 11.5px/1.5 var(--f-ui)', color: 'var(--tx-sub)', margin: 0 }}>
          Sem base de comparáveis para sugerir a faixa de alunos desta metragem — a
          premissa fica por sua conta.
        </p>
      )}

      {erro && <Aviso titulo="Não deu para calcular" corpo={erro} />}

      {res && <Resultado res={res} m2={m2} demanda={demanda ?? 0} />}
    </div>
  )
}

function Campo({ rotulo, children }: { rotulo: string; children: React.ReactNode }) {
  return (
    <label style={{ display: 'grid', gap: 6 }}>
      <span style={{ font: '600 11px/1 var(--f-ui)', color: 'var(--tx-muted)' }}>{rotulo}</span>
      {children}
    </label>
  )
}

function Resultado({ res, m2, demanda }: { res: ViabilidadeOut; m2: number; demanda: number }) {
  const dre = res.dre
  const teto = res.aluguel_teto
  const ret = res.retorno
  const inv = res.investimento
  const pre = res.premissas
  const viavel = dre?.flag_viavel === true
  const payback = ret?.payback ?? null

  /**
   * ÓTICA DO NEGÓCIO, declarada — nunca os aliases do topo.
   *
   * `retorno.tir_anual` e `retorno.vpl` existem, mas os tipos os marcam
   * `@deprecated` e avisam que são "o par do SÓCIO, não do negócio". Lê-los aqui
   * daria o número da ótica errada em silêncio no momento em que houvesse
   * financiamento — as duas coincidem só enquanto a dívida é zero.
   *
   * A ficha mostra o NEGÓCIO porque a pergunta é sobre o imóvel (o ativo), não sobre
   * a alavancagem de quem investe. A `ViabilityScreen` mostra as duas lado a lado,
   * que é onde essa comparação cabe.
   */
  const otica = ret?.negocio ?? ret?.socio ?? null
  const tir = otica?.tir_anual ?? null
  const vpl = otica?.vpl ?? null
  const retornoAnual = otica?.retorno_anual ?? null
  const taxaMin = otica?.taxa_minima_aa ?? pre?.taxa_minima_negocio_aa ?? null

  /**
   * POR QUE reprovou — lido dos MESMOS limiares que o motor usou, nunca recalculado.
   *
   * Sem isto o selo diz "não fecha a conta" e o operador fica sem saber onde apertar.
   * Medido na Av. Paulista: a margem é 40,8%, ótima, e quem reprova é o payback de 38
   * meses contra o máximo de 36 — junto com a TIR de 23,4% abaixo da mínima de 25%.
   * Sem a explicação, o operador tentaria cortar custo, que não é o problema.
   */
  const motivos: string[] = []
  if (pre?.margem_viavel_min != null && dre?.margem != null && dre.margem < pre.margem_viavel_min) {
    motivos.push(`margem de ${pctFrac(dre.margem)} abaixo do mínimo de ${pctFrac(pre.margem_viavel_min)}`)
  }
  if (pre?.payback_viavel_max != null && (payback == null || payback > pre.payback_viavel_max)) {
    motivos.push(
      payback == null
        ? 'payback que não acontece no horizonte do modelo'
        : `payback de ${num(payback)} meses acima do máximo de ${num(pre.payback_viavel_max)}`,
    )
  }
  if (tir != null && taxaMin != null && tir < taxaMin) {
    motivos.push(`TIR de ${pctFrac(tir)} abaixo da taxa mínima de ${pctFrac(taxaMin)}`)
  }

  return (
    <div style={{ display: 'grid', gap: 16, marginTop: 4 }}>
      <div style={{ display: 'grid', gap: 8 }}>
        <div
          style={{
            display: 'inline-flex', alignItems: 'center', gap: 9, alignSelf: 'start',
            padding: '9px 14px', borderRadius: 999,
            background: viavel ? 'var(--pos-pill)' : 'var(--surf-raised)',
            border: `1px solid ${viavel ? 'var(--pos)' : 'var(--line-strong)'}`,
            font: '700 12.5px/1 var(--f-ui)',
            color: viavel ? 'var(--pos-text)' : 'var(--tx-soft)',
          }}
        >
          <span
            aria-hidden
            style={{
              width: 7, height: 7, borderRadius: '50%',
              background: viavel ? 'var(--pos)' : 'var(--tx-muted)',
            }}
          />
          {viavel ? 'Fecha a conta' : 'Não fecha a conta'}
        </div>
        {!viavel && motivos.length > 0 && (
          <p style={{ font: '400 11.5px/1.5 var(--f-ui)', color: 'var(--tx-narrative)', margin: 0 }}>
            Reprova por {motivos.join('; ')}.
          </p>
        )}
      </div>

      <Grupo titulo="Operação madura" nota="em regime, depois da maturação">
        <Kpi label="Faturamento/mês" valor={brl(dre?.faturamento)} />
        <Kpi label="EBITDA/mês" valor={brl(dre?.ebitda)} />
        <Kpi label="Margem líquida" valor={pctFrac(dre?.margem)} />
        <Kpi label="Resultado após IR" valor={brl(dre?.resultado_apos_ir)} />
      </Grupo>

      <Grupo titulo="Retorno" nota="ótica do negócio (o ativo, sem financiamento)">
        <Kpi
          label="TIR anual"
          valor={pctFrac(tir)}
          sub={taxaMin != null ? `mínima ${pctFrac(taxaMin)}` : undefined}
        />
        {/* VPL negativo e' INFORMACAO, nao erro: significa que o projeto nao paga a
            taxa minima exigida. Por isso vai com sinal, e nao em modulo. */}
        <Kpi label="VPL" valor={brl(vpl)} />
        <Kpi label="Retorno anual" valor={pctFrac(retornoAnual)} />
        <Kpi
          label="Payback"
          valor={payback != null ? `${num(payback)} meses` : 'não atinge'}
          sub={pre?.payback_viavel_max != null ? `máximo ${num(pre.payback_viavel_max)}` : undefined}
        />
      </Grupo>

      <Grupo titulo="Investimento">
        <Kpi
          label="Cheque total"
          valor={brl(inv?.cheque_total)}
          sub={inv?.mes_cheque_total != null ? `pico no mês ${num(inv.mes_cheque_total)}` : undefined}
        />
        <Kpi label="Obra (CAPEX)" valor={brl(inv?.obra)} />
        <Kpi label="Taxa de franquia" valor={brl(inv?.taxa_franquia)} />
        <Kpi label="Aporte inicial" valor={brl(inv?.aporte_inicial)} />
      </Grupo>

      <Grupo titulo="Encher a unidade" nota="quanto precisa, e de onde vem o aluno">
        <Kpi
          label="Break-even"
          valor={res.break_even?.ebitda != null ? `${num(res.break_even.ebitda)} alunos` : num(null)}
        />
        <Kpi
          label="Caixa positivo"
          valor={
            res.mes_caixa_operacional_positivo != null
              ? `mês ${num(res.mes_caixa_operacional_positivo)}`
              : 'não atinge'
          }
        />
        <Kpi label="Alunos no balcão" valor={num(res.split?.balcao)} />
        <Kpi label="Alunos por agregador" valor={num(res.split?.agregadores)} />
      </Grupo>

      {/* ---- Aluguel teto ---- */}
      {teto && (
        <div
          style={{
            padding: 15, borderRadius: 'var(--r-md)',
            background: 'var(--surf-raised)', border: '1px solid var(--line-soft)',
            display: 'grid', gap: 10,
          }}
        >
          <div style={{ font: '600 12.5px/1 var(--f-ui)', color: 'var(--tx-soft)' }}>
            Até quanto cabe de aluguel
          </div>

          <div style={{ display: 'flex', gap: 22, flexWrap: 'wrap', alignItems: 'baseline' }}>
            <div>
              <div className="num" style={{ font: '700 26px/1 var(--f-num)', color: 'var(--tx-max)' }}>
                {brl(teto.teto)}
              </div>
              <div style={{ font: '500 10.5px/1 var(--f-num)', color: 'var(--tx-muted)', marginTop: 6 }}>
                TETO (20% do faturamento)
              </div>
            </div>
            <Secundario rotulo="Ideal (15%)" valor={teto.ideal} />
            <Secundario rotulo="Exceção (30%)" valor={teto.excecao} />
            {/* O unico teto que NAO e' circular: sai do cenario p10 dos comparaveis,
                nao da demanda que o operador digitou. */}
            <Secundario rotulo="Conservador (p10)" valor={teto.teto_p10 ?? null} />
          </div>

          {/* A PREMISSA ANDA COLADA NO NUMERO. Sem ela, o teto lê como atributo do
              imóvel — e não é: é consequência dos alunos e da metragem digitados acima. */}
          <p style={{ font: '400 11.5px/1.5 var(--f-ui)', color: 'var(--tx-narrative)', margin: 0 }}>
            Teto para <strong style={{ color: 'var(--tx-soft)' }}>{num(demanda)} alunos</strong> e{' '}
            <strong style={{ color: 'var(--tx-soft)' }}>{num(m2)} m²</strong>
            {pre?.ticket_blended != null && <>, com ticket médio de {brl(pre.ticket_blended, false, 2)}</>}.
            Muda a premissa, muda o teto — este número não é preço de mercado da região, e o
            projeto não tem base de aluguel por m² para dizer isso.
          </p>
        </div>
      )}

      {res.flag_fora_envelope && (
        <Aviso
          titulo="Metragem fora do envelope calibrado"
          corpo="A base de comparáveis cobre um intervalo de metragem; fora dele a faixa de alunos é extrapolação, não leitura."
        />
      )}
      {res.flag_zona_morta && (
        <Aviso
          titulo="Zona morta"
          corpo={res.motivo_zona_morta ?? 'O cenário cai numa faixa em que o motor não sustenta recomendação.'}
        />
      )}

      <p style={{ font: '400 11px/1.5 var(--f-ui)', color: 'var(--tx-sub)', margin: 0 }}>
        Grade de sensibilidade, cascata do DRE e fluxo de caixa mês a mês ficam na tela de
        Viabilidade — aqui a ficha responde se fecha a conta, e por quê.
      </p>
    </div>
  )
}

/** Um grupo de KPIs com título: a ficha ficou grande demais para uma grade só. */
function Grupo({
  titulo,
  nota,
  children,
}: {
  titulo: string
  nota?: string
  children: React.ReactNode
}) {
  return (
    <div style={{ display: 'grid', gap: 10 }}>
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 8, flexWrap: 'wrap' }}>
        <span style={{ font: '600 12px/1 var(--f-ui)', color: 'var(--tx-soft)' }}>{titulo}</span>
        {nota && <span style={{ font: '400 11px/1 var(--f-ui)', color: 'var(--tx-sub)' }}>{nota}</span>}
      </div>
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(148px, 1fr))',
          gap: 12,
        }}
      >
        {children}
      </div>
    </div>
  )
}

function Secundario({ rotulo, valor }: { rotulo: string; valor: number | null }) {
  return (
    <div>
      <div className="num" style={{ font: '600 15px/1 var(--f-num)', color: 'var(--tx-soft)' }}>
        {brl(valor)}
      </div>
      <div style={{ font: '500 10px/1 var(--f-num)', color: 'var(--tx-sub)', marginTop: 5 }}>
        {rotulo}
      </div>
    </div>
  )
}
