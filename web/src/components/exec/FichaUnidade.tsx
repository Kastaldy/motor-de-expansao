import { useEffect, useState } from 'react'

import { api, ApiError, baixar } from '../../lib/api'
import {
  METRICAS_EM_PONTOS,
  formatarMetrica,
  lerDelta,
  rotuloRanking,
  rotuloVsMedia,
} from '../../lib/exec'
import { brl, num, pct } from '../../lib/format'
import type { RedeFicha } from '../../lib/types'
import { Aviso, BarraMeta, Botao, Delta, Glass, Semaforo, Spinner } from '../primitives'
import {
  BannerRecomendacao,
  BarrasPeriodo,
  ComparativoCoorte,
  FunilComercial,
  LinhaPeriodo,
  Rosca,
} from './ExecCharts'

/* ---------------------------------------------------------------------------
   Nível 2 — a ficha da unidade.

   SUBSTITUI o corpo da aba em vez de abrir num modal. Modal de 768 px de altura
   pediria focus trap e um segundo scroller aninhado dentro do único scroller da
   tela; e o Voltar do browser, que é o gesto natural de quem abriu uma ficha,
   não funcionaria. Aqui `history.pushState` cuida do Voltar e do Esc, e os
   filtros vivem ACIMA do switch — abrir e fechar a ficha não refaz request
   nenhum da carteira.
   --------------------------------------------------------------------------- */

/** Métricas da ficha, na ordem em que o consultor lê. */
const METRICAS_FICHA: { chave: string; rotulo: string; formato: 'brl' | 'int' | 'pct' | 'nota'; bomSubindo: boolean }[] = [
  { chave: 'faturamento', rotulo: 'Faturamento', formato: 'brl', bomSubindo: true },
  { chave: 'faturamento_sem_agregador', rotulo: 'Receita de recorrentes', formato: 'brl', bomSubindo: true },
  { chave: 'faturamento_agregador', rotulo: 'Receita de agregadores', formato: 'brl', bomSubindo: true },
  { chave: 'receita_por_recorrente', rotulo: 'Receita por recorrente', formato: 'brl', bomSubindo: true },
  { chave: 'ativos', rotulo: 'Alunos ativos', formato: 'int', bomSubindo: true },
  { chave: 'pagantes', rotulo: 'Recorrentes', formato: 'int', bomSubindo: true },
  { chave: 'agregadores', rotulo: 'Agregadores', formato: 'int', bomSubindo: true },
  { chave: 'churn_pct', rotulo: 'Churn', formato: 'pct', bomSubindo: false },
  { chave: 'saldo_operacional', rotulo: 'Saldo operacional', formato: 'int', bomSubindo: true },
  { chave: 'vendas', rotulo: 'Vendas', formato: 'int', bomSubindo: true },
  { chave: 'cancelados', rotulo: 'Cancelados', formato: 'int', bomSubindo: false },
  { chave: 'conversao_pct', rotulo: 'Conversão de visitas', formato: 'pct', bomSubindo: true },
  { chave: 'nps', rotulo: 'NPS', formato: 'nota', bomSubindo: true },
  { chave: 'em_cobranca_pct', rotulo: 'Em cobrança', formato: 'pct', bomSubindo: false },
  { chave: 'pct_agregador_alunos', rotulo: 'Dependência de agregador', formato: 'pct', bomSubindo: false },
]

/** Exibidas com aviso e SEM régua: o denominador ainda não foi confirmado com a Growth. */
const METRICAS_A_VALIDAR: { chave: string; rotulo: string }[] = [
  { chave: 'inadimplente', rotulo: 'Inadimplentes' },
  { chave: 'treino_ativo', rotulo: 'Treino ativo' },
]

/** Rótulos do comparativo de coorte.
 *
 *  Onde MENOS é melhor, a direção vai escrita: "Churn — percentil 92" lê como elogio e é
 *  o oposto (92% dos pares têm churn menor). Inverter o percentil em silêncio seria pior
 *  que não mostrá-lo. */
const ROTULOS_COORTE_GRAFICO: Record<string, string> = {
  faturamento: 'Faturamento',
  receita_por_recorrente: 'Receita por recorrente',
  ativos: 'Alunos ativos',
  churn_pct: 'Churn (menor é melhor)',
  conversao_pct: 'Conversão',
  nps: 'NPS',
}
const FORMATO_COORTE: Record<string, 'brl' | 'int' | 'pct' | 'nota'> = {
  faturamento: 'brl',
  receita_por_recorrente: 'brl',
  ativos: 'int',
  churn_pct: 'pct',
  conversao_pct: 'pct',
  nps: 'nota',
}

export interface FichaUnidadeProps {
  unidadeId: string
  mes: string
  onVoltar: () => void
}

export default function FichaUnidade({ unidadeId, mes, onVoltar }: FichaUnidadeProps) {
  const [ficha, setFicha] = useState<RedeFicha | null>(null)
  const [carregando, setCarregando] = useState(true)
  const [erro, setErro] = useState<string | null>(null)
  const [baixando, setBaixando] = useState(false)
  // Erro do DOWNLOAD, separado do erro de CARGA: falhar ao gerar o PDF não pode apagar a
  // ficha inteira da tela — inclusive o que a pessoa já tinha digitado no formulário de
  // atribuição.
  const [erroPdf, setErroPdf] = useState<string | null>(null)

  useEffect(() => {
    let vivo = true
    setCarregando(true)
    setErro(null)
    api
      .redeUnidade(unidadeId, mes)
      .then((d) => vivo && setFicha(d))
      .catch((e: ApiError) => vivo && setErro(e.message))
      .finally(() => vivo && setCarregando(false))
    return () => {
      vivo = false
    }
  }, [unidadeId, mes])

  if (carregando && !ficha) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, padding: 40, color: 'var(--tx-sub)' }}>
        <Spinner /> Lendo a ficha da unidade…
      </div>
    )
  }
  if (erro || !ficha) {
    return (
      <Aviso
        titulo="Ficha indisponível"
        corpo={erro ?? 'Não foi possível ler esta unidade.'}
        acao={<Botao variante="ghost" onClick={onVoltar}>Voltar para a carteira</Botao>}
      />
    )
  }

  const u = ficha.unidade
  const d = ficha.diagnostico

  async function baixarPdf() {
    setBaixando(true)
    setErroPdf(null)
    try {
      const { blob, filename } = await api.redeUnidadePdf(unidadeId, mes)
      baixar(blob, filename)
    } catch (e) {
      setErroPdf((e as ApiError).message)
    } finally {
      setBaixando(false)
    }
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
      <div style={{ display: 'flex', alignItems: 'flex-start', gap: 14, flexWrap: 'wrap' }}>
        <Botao variante="ghost" onClick={onVoltar}>
          ← Carteira
        </Botao>
        <div style={{ flex: 1, minWidth: 240 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 9 }}>
            <Semaforo nivel={d.severidade} rotulo={d.severidade_rotulo} tamanho={11} />
            <h2 className="story" style={{ font: '400 27px/1.1 var(--f-story)', color: 'var(--tx-max)', margin: 0 }}>
              {u.nome}
            </h2>
          </div>
          <div style={{ font: '400 11.5px/1.5 var(--f-ui)', color: 'var(--tx-sub)', marginTop: 6 }}>
            {[
              u.cidade,
              u.uf,
              u.coorte_rotulo,
              u.inauguracao ? `inaugurada em ${u.inauguracao}` : null,
              u.consultor ? `consultor ${u.consultor}` : 'sem consultor atribuído',
              u.master_franquia ? `master ${u.master_franquia}` : null,
            ]
              .filter(Boolean)
              .join(' · ')}
          </div>
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: 6 }}>
          <Botao variante="ghost" onClick={baixarPdf} disabled={baixando}>
            {baixando ? <Spinner /> : '↓'} Ficha em PDF
          </Botao>
          {erroPdf && (
            <span style={{ font: '400 10.5px/1.4 var(--f-ui)', color: 'var(--neg, #ff5a6e)', maxWidth: 240, textAlign: 'right' }}>
              {erroPdf}
            </span>
          )}
        </div>
      </div>

      <BannerRecomendacao
        severidade={d.severidade}
        titulo={d.severidade_rotulo}
        resumo={d.resumo}
        recomendacoes={d.recomendacoes}
        competencia={d.competencia}
      />

      <div style={{ display: 'flex', gap: 14, flexWrap: 'wrap', alignItems: 'flex-start' }}>
        <Glass style={{ flex: '1 1 520px', padding: '16px 18px', minWidth: 0 }}>
          <Titulo>O quarteto de contexto</Titulo>
          <table style={{ width: '100%', borderCollapse: 'collapse', font: '400 12px/1.2 var(--f-ui)' }}>
            <thead>
              <tr>
                {['Métrica', 'Mês', 'vs M-1', 'Ranking', '% vs média da rede'].map((c, i) => (
                  <th
                    key={c}
                    scope="col"
                    style={{
                      textAlign: i === 0 ? 'left' : 'right',
                      padding: '0 6px 8px',
                      font: '600 9.5px/1 var(--f-ui)',
                      letterSpacing: '.06em',
                      textTransform: 'uppercase',
                      color: 'var(--tx-muted)',
                      borderBottom: '1px solid var(--line-mid)',
                    }}
                  >
                    {c}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {METRICAS_FICHA.map((m) => {
                const metrica = ficha.metricas[m.chave]
                if (!metrica || metrica.atual === null) return null
                const leitura = lerDelta(metrica, m.bomSubindo, METRICAS_EM_PONTOS.has(m.chave))
                return (
                  <tr key={m.chave} style={{ height: 30 }}>
                    <td style={{ padding: '0 6px', borderBottom: '1px solid var(--line-soft)', color: 'var(--tx-label)' }}>
                      {m.rotulo}
                    </td>
                    <td className="num" style={celulaNum}>
                      {formatarMetrica(metrica.atual, m.formato)}
                    </td>
                    <td style={{ ...celulaNum, color: 'var(--tx-muted)' }}>
                      <Delta leitura={leitura} tamanho={10.5} />
                    </td>
                    <td className="num" style={{ ...celulaNum, color: 'var(--tx-sub)' }}>
                      {metrica.rank ? `${metrica.rank}/${metrica.rank_total}` : '—'}
                    </td>
                    <td
                      className="num"
                      style={{
                        ...celulaNum,
                        // A cor segue a DIREÇÃO da métrica, não o sinal. Churn 40% acima
                        // da média da rede pintado de verde faz o consultor tratar como
                        // ponto forte exatamente o número que está disparando o alerta.
                        color: corDoDesvio(metrica.vs_media_pct, m.bomSubindo),
                      }}
                      title={`${rotuloRanking(metrica)} · ${rotuloVsMedia(metrica)}`}
                    >
                      {metrica.vs_media_pct === null
                        ? '—'
                        : `${metrica.vs_media_pct > 0 ? '+' : ''}${pct(metrica.vs_media_pct, 1)}`}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>

          <div style={{ marginTop: 14, display: 'flex', gap: 18, flexWrap: 'wrap' }}>
            {METRICAS_A_VALIDAR.map((m) => {
              const metrica = ficha.metricas[m.chave]
              if (!metrica || metrica.atual === null) return null
              return (
                <span
                  key={m.chave}
                  title="Denominador ainda não confirmado com a Growth: exibido sem régua e fora de qualquer alerta."
                  style={{ font: '400 11px/1 var(--f-ui)', color: 'var(--tx-muted)' }}
                >
                  {m.rotulo}: <span className="num">{num(metrica.atual)}</span> *
                </span>
              )
            })}
          </div>
        </Glass>

        <Glass style={{ flex: '1 1 330px', padding: '16px 18px', minWidth: 0 }}>
          <Titulo>Contra os pares de mesma maturidade</Titulo>
          <ComparativoCoorte
            comparacao={ficha.coorte}
            metricas={Object.keys(ROTULOS_COORTE_GRAFICO)}
            rotulos={ROTULOS_COORTE_GRAFICO}
            formato={FORMATO_COORTE}
          />
        </Glass>
      </div>

      <div style={{ display: 'flex', gap: 14, flexWrap: 'wrap' }}>
        <Glass style={{ flex: '1 1 420px', padding: '16px 18px', minWidth: 0 }}>
          <Titulo>Faturamento nos 12 meses fechados</Titulo>
          <BarrasPeriodo meses={ficha.serie.meses} valores={ficha.serie.faturamento} formato="brl" />
        </Glass>
        <Glass style={{ flex: '1 1 300px', padding: '16px 18px', minWidth: 0 }}>
          <Titulo>Base de alunos</Titulo>
          <LinhaPeriodo
            meses={ficha.serie.meses}
            valores={ficha.serie.ativos}
            titulo="Alunos ativos"
            formato="int"
          />
          <div style={{ marginTop: 12 }}>
            <LinhaPeriodo
              meses={ficha.serie.meses}
              valores={ficha.serie.churn_pct}
              titulo="Churn (%)"
              cor="var(--gr-coral)"
              formato="pct"
            />
          </div>
        </Glass>

        <Glass style={{ flex: '1 1 300px', padding: '16px 18px', minWidth: 0 }}>
          <Titulo>Composição da base</Titulo>
          <Rosca
            partes={[
              {
                rotulo: 'Recorrentes',
                valor: ficha.metricas.pagantes?.atual ?? 0,
                cor: 'var(--ac)',
              },
              {
                rotulo: 'Agregadores',
                valor: ficha.metricas.agregadores?.atual ?? 0,
                cor: 'var(--gr-rosa)',
              },
            ]}
            centroValor={pct(ficha.metricas.pct_agregador_alunos?.atual ?? null, 0)}
            centroRotulo="agregadores"
          />
          <div style={{ marginTop: 12, font: '400 10.5px/1.55 var(--f-ui)', color: 'var(--tx-muted)' }}>
            Aluno de agregador paga menos e pode sair em bloco por decisão do parceiro. A
            régua de alerta está em {ficha.reguas.agregador?.limiar ?? 70}% da base.
          </div>
        </Glass>
      </div>

      <div style={{ display: 'flex', gap: 14, flexWrap: 'wrap' }}>
        <Glass style={{ flex: '1 1 360px', padding: '16px 18px', minWidth: 0 }}>
          <Titulo>Funil comercial do período</Titulo>
          <FunilComercial
            visitas={ficha.funil.visitas}
            convertidos={ficha.funil.convertidos}
            vendas={ficha.funil.vendas}
            novosAlunos={ficha.funil.novos_alunos}
            conversao={ficha.funil.conversao_pct}
            aviso={ficha.funil.aviso}
          />
        </Glass>
        <Glass style={{ flex: '1 1 300px', padding: '16px 18px', minWidth: 0 }}>
          <Titulo>NPS e a meta da rede</Titulo>
          <div className="num" style={{ font: '700 30px/1 var(--f-num)', color: 'var(--tx-max)' }}>
            {num(ficha.metricas.nps?.atual, 1)}
          </div>
          <div style={{ margin: '12px 0 6px' }}>
            <BarraMeta valor={ficha.metricas.nps?.atual ?? null} meta={ficha.meta_nps} minimo={-100} />
          </div>
          <div style={{ font: '400 11px/1.5 var(--f-ui)', color: 'var(--tx-sub)' }}>
            Meta oficial da rede: {ficha.meta_nps}. O alerta só dispara em{' '}
            {ficha.reguas.nps?.limiar ?? 40} — meta não é alerta.
          </div>
          <div style={{ marginTop: 12 }}>
            <LinhaPeriodo meses={ficha.serie.meses} valores={ficha.serie.nps} titulo="NPS por mês" cor="var(--gr-azul)" />
          </div>
        </Glass>
        <Glass style={{ flex: '1 1 280px', padding: '16px 18px', minWidth: 0 }}>
          <Titulo>Novos alunos, dia a dia</Titulo>
          <BarrasPeriodo
            meses={ficha.serie_diaria.datas}
            valores={ficha.serie_diaria.novos_alunos}
            altura={104}
            formato="int"
            cor="var(--gr-verde)"
          />
          <div style={{ marginTop: 8, font: '400 10.5px/1.5 var(--f-ui)', color: 'var(--tx-muted)' }}>
            Derivado da série cumulativa da API — é o bloco que hoje é colado à mão na planilha.
          </div>
        </Glass>
      </div>

      <CadastroDaUnidade ficha={ficha} onAtualizar={setFicha} />

      <Glass style={{ padding: '14px 18px' }}>
        <Titulo>Notas de método</Titulo>
        <ul style={{ margin: 0, paddingLeft: 18, font: '400 11.5px/1.7 var(--f-ui)', color: 'var(--tx-narrative)' }}>
          {ficha.notas.map((n) => (
            <li key={n}>{n}</li>
          ))}
          <li>
            Ficha comparada com {ficha.coorte.n} unidades — {ficha.coorte.base_rotulo}.
          </li>
          {u.gold != null && (
            <li>
              Plano Gold da unidade: {brl(u.gold, false, 0)}
              {u.ltv != null ? ` · LTV estimado ${brl(u.ltv, false, 0)}` : ''}
              {u.life_time != null ? ` · life time ${num(u.life_time, 1)} meses` : ''} (cadastro do time).
            </li>
          )}
        </ul>
      </Glass>
    </div>
  )
}

/**
 * Atribuição de consultor / master franqueado — a única escrita do piloto.
 *
 * A `versao` implementa a concorrência otimista: se outra pessoa gravou nesse meio-tempo,
 * o servidor devolve 409 e a tela diz para recarregar em vez de sobrescrever em silêncio.
 */
function CadastroDaUnidade({
  ficha,
  onAtualizar,
}: {
  ficha: RedeFicha
  onAtualizar: (f: RedeFicha) => void
}) {
  const [valores, setValores] = useState<Record<string, string>>(ficha.cadastro.valores)
  const [salvando, setSalvando] = useState(false)
  const [mensagem, setMensagem] = useState<string | null>(null)

  useEffect(() => setValores(ficha.cadastro.valores), [ficha.cadastro.valores])

  const rotulos: Record<string, string> = {
    consultor: 'Consultor da franqueadora',
    consultor_2: 'Consultor do master',
    master_franquia: 'Master franquia',
  }
  const mudou = ficha.cadastro.campos_editaveis.some(
    (c) => (valores[c] ?? '') !== (ficha.cadastro.valores[c] ?? ''),
  )

  async function salvar() {
    setSalvando(true)
    setMensagem(null)
    try {
      const r = await api.redeCadastroAtribuir(ficha.unidade.id, ficha.cadastro.versao, valores)
      onAtualizar({
        ...ficha,
        unidade: { ...ficha.unidade, consultor: r.valores.consultor || null },
        cadastro: { ...ficha.cadastro, versao: r.versao, valores: r.valores },
      })
      setMensagem('Atribuição salva.')
    } catch (e) {
      setMensagem((e as ApiError).message)
    } finally {
      setSalvando(false)
    }
  }

  if (!ficha.cadastro.disponivel) {
    return (
      <Glass style={{ padding: '14px 18px' }}>
        <Titulo>Responsáveis</Titulo>
        <div style={{ font: '400 11.5px/1.6 var(--f-ui)', color: 'var(--tx-sub)' }}>
          O cadastro operacional não está montado neste ambiente — os responsáveis aparecem
          apenas quando o volume de cadastro está disponível.
        </div>
      </Glass>
    )
  }

  return (
    <Glass style={{ padding: '14px 18px' }}>
      <Titulo>Responsáveis</Titulo>
      <div style={{ display: 'flex', gap: 14, flexWrap: 'wrap', alignItems: 'flex-end' }}>
        {ficha.cadastro.campos_editaveis.map((campo) => (
          <label key={campo} style={{ display: 'flex', flexDirection: 'column', gap: 5, minWidth: 200 }}>
            <span style={{ font: '500 10.5px/1 var(--f-ui)', color: 'var(--tx-label)' }}>
              {rotulos[campo] ?? campo}
            </span>
            <input
              value={valores[campo] ?? ''}
              placeholder="a atribuir"
              onChange={(e) => setValores({ ...valores, [campo]: e.target.value })}
              style={{ minWidth: 200 }}
            />
          </label>
        ))}
        <Botao onClick={salvar} disabled={!mudou || salvando}>
          {salvando ? <Spinner /> : null} Salvar atribuição
        </Botao>
        {mensagem && (
          <span style={{ font: '400 11.5px/1.5 var(--f-ui)', color: 'var(--tx-sub)', maxWidth: 340 }}>
            {mensagem}
          </span>
        )}
      </div>
      <div style={{ marginTop: 10, font: '400 10.5px/1.5 var(--f-ui)', color: 'var(--tx-muted)' }}>
        Fica registrado quem alterou o quê e quando. Os demais campos do cadastro (cidade,
        franqueado, modalidades) vêm da planilha do time e ainda não são editáveis aqui.
      </div>
    </Glass>
  )
}

/** Verde quando o desvio da média é BOM para esta métrica; vermelho quando é ruim. */
function corDoDesvio(desvio: number | null, bomSubindo: boolean): string {
  if (desvio === null || Math.abs(desvio) < 0.05) return 'var(--tx-muted)'
  return desvio > 0 === bomSubindo ? 'var(--pos, #37b26b)' : 'var(--neg, #ff5a6e)'
}

const celulaNum = {
  padding: '0 6px',
  textAlign: 'right' as const,
  borderBottom: '1px solid var(--line-soft)',
  font: '600 12px/1 var(--f-num)',
  color: 'var(--tx-strong)',
}

function Titulo({ children }: { children: React.ReactNode }) {
  return (
    <div
      style={{
        font: '600 10.5px/1 var(--f-ui)',
        letterSpacing: '.09em',
        textTransform: 'uppercase',
        color: 'var(--tx-muted)',
        marginBottom: 12,
      }}
    >
      {children}
    </div>
  )
}
