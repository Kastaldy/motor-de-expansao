import { useEffect, useState } from 'react'

import CampoNumero from './CampoNumero'
import { Aviso, Botao, Kpi, Spinner } from './primitives'
import { api, ApiError } from '../lib/api'
import { num } from '../lib/format'
import type { ViabilidadeOut } from '../lib/types'

/**
 * Viabilidade DENTRO do modo de ponto: "fecha a conta?" sem sair da ficha.
 *
 * O QUE ESTA TELA NAO FAZ. Nao deriva numero financeiro nenhum. O motor
 * (`dimensionamento/simulador.py`) devolve tudo pronto e aqui so' se LE — mesma regra
 * que a `ViabilityScreen` ja segue por escrito ("a tela nao re-deriva o veredito").
 * Formula financeira fora do `simulador.py` e' proibida no projeto.
 *
 * O VEREDITO E' UM BOOLEANO, NAO UM SCORE. Nao existe `score_viabilidade` nem nota
 * 0-100: existe `dre.flag_viavel` (margem >= 30% E payback <= 36 meses de operacao).
 * Inventar um score composto "para caber no card" criaria uma quarta definicao de
 * viabilidade no sistema.
 *
 * A DEMANDA E' SEMPRE PREMISSA. Por decisao estrategica (DEC-009) o motor e'
 * property-first: a demanda nao e' prevista pela geografia, e' digitada. O payload
 * confirma (`demanda_fonte: "premissa_explicita"`). Por isso ela e' semeada pelo p50
 * dos comparaveis e fica EDITAVEL e VISIVEL — um teto de aluguel calculado sobre
 * demanda assumida so' devolve a premissa de quem digitou, e apresentar isso como "o
 * aluguel maximo do imovel" seria circular.
 */
export default function BlocoViabilidadePonto({ lat, lng }: { lat: number; lng: number }) {
  const [m2, setM2] = useState(1500)
  const [aluguel, setAluguel] = useState(20000)
  const [demanda, setDemanda] = useState<number | null>(null)
  const [faixa, setFaixa] = useState<{ p10: number | null; p50: number | null; p90: number | null; n_comparaveis: number } | null>(null)

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
  const viavel = dre?.flag_viavel === true
  const payback = res.retorno?.payback ?? null

  return (
    <div style={{ display: 'grid', gap: 14, marginTop: 4 }}>
      {/* Veredito: o BOOLEANO do motor, exibido como selo. */}
      <div
        style={{
          display: 'inline-flex',
          alignItems: 'center',
          gap: 9,
          alignSelf: 'start',
          padding: '9px 14px',
          borderRadius: 999,
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

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))', gap: 12 }}>
        <Kpi label="Margem líquida" valor={dre?.margem != null ? `${num(dre.margem * 100, 1)}%` : num(null)} />
        {/* `null` aqui NAO e' "sem dado": e' "o payback nao acontece no horizonte". */}
        <Kpi label="Payback" valor={payback != null ? `${num(payback)} meses` : 'não atinge'} />
        <Kpi label="Break-even" valor={res.break_even?.ebitda != null ? `${num(res.break_even.ebitda)} alunos` : num(null)} />
        <Kpi label="Cheque total" valor={res.investimento?.cheque_total != null ? `R$ ${num(res.investimento.cheque_total)}` : num(null)} />
      </div>

      {/* ---- Aluguel teto ---- */}
      {teto && (
        <div
          style={{
            padding: 15,
            borderRadius: 'var(--r-md)',
            background: 'var(--surf-raised)',
            border: '1px solid var(--line-soft)',
            display: 'grid',
            gap: 10,
          }}
        >
          <div style={{ font: '600 12.5px/1 var(--f-ui)', color: 'var(--tx-soft)' }}>
            Até quanto cabe de aluguel
          </div>

          <div style={{ display: 'flex', gap: 22, flexWrap: 'wrap', alignItems: 'baseline' }}>
            <div>
              <div className="num" style={{ font: '700 26px/1 var(--f-num)', color: 'var(--tx-max)' }}>
                R$ {num(teto.teto)}
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

          {/* A PREMISSA ANDA COLADA NO NUMERO. Sem ela, "R$ 52.597" lê como um atributo
              do imóvel — e não é: é consequência direta dos alunos e da metragem que
              foram digitados logo acima. */}
          <p style={{ font: '400 11.5px/1.5 var(--f-ui)', color: 'var(--tx-narrative)', margin: 0 }}>
            Teto para <strong style={{ color: 'var(--tx-soft)' }}>{num(demanda)} alunos</strong> e{' '}
            <strong style={{ color: 'var(--tx-soft)' }}>{num(m2)} m²</strong>. Muda a premissa, muda
            o teto — este número não é preço de mercado da região, e o projeto não tem base de
            aluguel por m² para dizer isso.
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
        <Aviso titulo="Zona morta" corpo={res.motivo_zona_morta ?? 'O cenário cai numa faixa em que o motor não sustenta recomendação.'} />
      )}
    </div>
  )
}

function Secundario({ rotulo, valor }: { rotulo: string; valor: number | null }) {
  return (
    <div>
      <div className="num" style={{ font: '600 15px/1 var(--f-num)', color: 'var(--tx-soft)' }}>
        {valor != null ? `R$ ${num(valor)}` : num(null)}
      </div>
      <div style={{ font: '500 10px/1 var(--f-num)', color: 'var(--tx-sub)', marginTop: 5 }}>
        {rotulo}
      </div>
    </div>
  )
}
