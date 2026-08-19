import { useEffect, useState } from 'react'

import BotaoInicio from '../components/BotaoInicio'
import Tabela, { type Coluna } from '../components/Tabela'
import { Aviso, Botao, Chip, Eyebrow, Glass, Kpi, Spinner } from '../components/primitives'
import { api, ApiError } from '../lib/api'
import type { AcessosFicha, AcessosResumo, AcessosUsuarioLinha } from '../lib/types'

/* ---------------------------------------------------------------------------
   Aba Acessos — painel de uso do piloto (emenda DEC-027, 2026-08-19).

   RESTRITA: só existe para quem está na allowlist do backend (env
   `MOTOR_ACESSOS_ADMIN_USUARIOS`); para o resto do time a rota devolve 404 e o
   ícone nem aparece no Dock. O que ela mostra — e o corte deliberado do que
   esconde — está decidido na emenda: agregados + atividade por usuário até o
   nível de FEATURE ("rodou simulador 4x"), nunca o conteúdo consultado
   (endereço pesquisado, parâmetros de simulação). O próprio painel fica fora
   das métricas (senão o admin inflaria os números só de olhar).

   Autônoma como a Executiva: busca sozinha, não herda estado do mapa. Gráficos
   em SVG/CSS à mão — o projeto não tem biblioteca de gráficos (primitives.tsx).
   --------------------------------------------------------------------------- */

const JANELAS = [7, 30, 90] as const

const DIAS_SEMANA = ['Seg', 'Ter', 'Qua', 'Qui', 'Sex', 'Sáb', 'Dom']

/** `2026-08-19` -> `19/08` (rótulo curto de eixo/célula). */
function diaCurto(iso: string | null): string {
  if (!iso) return '—'
  const [, m, d] = iso.split('-')
  return `${d}/${m}`
}

function Secao({ titulo, children }: { titulo: string; children: React.ReactNode }) {
  return (
    <Glass style={{ padding: '14px 16px', display: 'flex', flexDirection: 'column', gap: 10 }}>
      <Eyebrow>{titulo}</Eyebrow>
      {children}
    </Glass>
  )
}

/** Teto de barras renderizadas: acima disso (minWidth 2px + gap) o gráfico
 *  estouraria o card — a série do rollup cresce para sempre. */
const MAX_BARRAS_SERIE = 180

/** Barras diárias (ações/dia) com título por barra — divs, mesma técnica dos ExecCharts. */
function BarrasSerie({ serie: serieCompleta }: { serie: AcessosResumo['serie'] }) {
  const serie = serieCompleta.slice(-MAX_BARRAS_SERIE)
  const max = Math.max(1, ...serie.map((d) => d.acoes))
  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'flex-end', gap: 2, height: 110 }}>
        {serie.map((d) => (
          <div
            key={d.dia}
            title={`${diaCurto(d.dia)} — ${d.acoes} ações · ${d.usuarios} usuários`}
            style={{
              flex: 1,
              minWidth: 2,
              height: `${Math.max(2, (100 * d.acoes) / max)}%`,
              background: d.acoes ? 'var(--ac)' : 'var(--surf-raised)',
              opacity: d.acoes ? 0.85 : 1,
              borderRadius: 2,
            }}
          />
        ))}
      </div>
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          marginTop: 6,
          font: '400 10px/1 var(--f-num)',
          color: 'var(--tx-muted)',
        }}
      >
        <span>
          {serieCompleta.length > MAX_BARRAS_SERIE
            ? `últimos ${MAX_BARRAS_SERIE} dias (série desde ${diaCurto(serieCompleta[0]?.dia ?? null)})`
            : diaCurto(serie[0]?.dia ?? null)}
        </span>
        <span>{diaCurto(serie[serie.length - 1]?.dia ?? null)}</span>
      </div>
    </div>
  )
}

/** Hora × dia da semana (BRT). Opacidade proporcional ao volume da célula. */
function Heatmap({ heatmap }: { heatmap: number[][] }) {
  const max = Math.max(1, ...heatmap.flat())
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
      {heatmap.map((linha, d) => (
        <div key={DIAS_SEMANA[d]} style={{ display: 'flex', alignItems: 'center', gap: 3 }}>
          <span
            style={{
              width: 28,
              flexShrink: 0,
              font: '500 9.5px/1 var(--f-ui)',
              color: 'var(--tx-muted)',
            }}
          >
            {DIAS_SEMANA[d]}
          </span>
          {linha.map((v, h) => (
            <div
              key={h}
              title={`${DIAS_SEMANA[d]} ${String(h).padStart(2, '0')}h — ${v} ações`}
              style={{
                flex: 1,
                minWidth: 4,
                height: 14,
                borderRadius: 2,
                background: v ? 'var(--ac)' : 'var(--surf-raised)',
                opacity: v ? 0.25 + 0.75 * (v / max) : 1,
              }}
            />
          ))}
        </div>
      ))}
      <div style={{ display: 'flex', gap: 3, marginLeft: 31 }}>
        {Array.from({ length: 24 }, (_, h) => (
          <span
            key={h}
            style={{
              flex: 1,
              minWidth: 4,
              font: '400 8.5px/1 var(--f-num)',
              color: 'var(--tx-muted)',
              textAlign: 'center',
            }}
          >
            {h % 6 === 0 ? h : ''}
          </span>
        ))}
      </div>
    </div>
  )
}

/** Barras horizontais de proporção (uso por aba, features da ficha). */
function BarrasHorizontais({
  itens,
}: {
  itens: { rotulo: string; valor: number; sub?: string }[]
}) {
  const max = Math.max(1, ...itens.map((i) => i.valor))
  if (!itens.length) {
    return (
      <span style={{ font: '400 12px/1.4 var(--f-ui)', color: 'var(--tx-muted)' }}>
        Nada registrado na janela.
      </span>
    )
  }
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 7 }}>
      {itens.map((i) => (
        <div key={i.rotulo} style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span
            style={{
              width: 190,
              flexShrink: 0,
              font: '500 11.5px/1.2 var(--f-ui)',
              color: 'var(--tx-soft)',
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              whiteSpace: 'nowrap',
            }}
            title={i.rotulo}
          >
            {i.rotulo}
          </span>
          <div style={{ flex: 1, height: 10, background: 'var(--surf-raised)', borderRadius: 5 }}>
            <div
              style={{
                width: `${(100 * i.valor) / max}%`,
                height: '100%',
                borderRadius: 5,
                background: 'var(--ac)',
                opacity: 0.8,
              }}
            />
          </div>
          <span
            className="num"
            style={{
              width: 66,
              flexShrink: 0,
              textAlign: 'right',
              font: '600 11.5px/1 var(--f-num)',
              color: 'var(--tx-max)',
            }}
          >
            {i.valor}
            {i.sub ? ` ${i.sub}` : ''}
          </span>
        </div>
      ))}
    </div>
  )
}

/** Nível 2 — a ficha de um usuário (mesmo padrão de troca de corpo da Executiva). */
function FichaUsuarioAcessos({
  nome,
  dias,
  onVoltar,
}: {
  nome: string
  dias: number
  onVoltar: () => void
}) {
  const [ficha, setFicha] = useState<AcessosFicha | null>(null)
  const [carregando, setCarregando] = useState(false)
  const [erro, setErro] = useState<string | null>(null)

  useEffect(() => {
    let vivo = true
    setCarregando(true)
    setErro(null)
    api
      .acessosUsuario(nome, dias)
      .then((f) => {
        if (vivo) setFicha(f)
      })
      .catch((e: ApiError) => {
        if (vivo) {
          setErro(e.message)
          setFicha(null)
        }
      })
      .finally(() => vivo && setCarregando(false))
    return () => {
      vivo = false
    }
  }, [nome, dias])

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
        <Botao variante="ghost" onClick={onVoltar} style={{ padding: '8px 12px' }}>
          ← Todos os usuários
        </Botao>
        <span style={{ font: '600 15px/1 var(--f-ui)', color: 'var(--tx-max)' }}>{nome}</span>
      </div>

      {carregando ? (
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 8,
            color: 'var(--tx-muted)',
            font: '400 12px/1 var(--f-ui)',
            padding: 20,
          }}
        >
          <Spinner /> Lendo a trilha…
        </div>
      ) : erro ? (
        <Aviso titulo="Não deu para abrir a ficha" corpo={erro} />
      ) : ficha ? (
        <>
          <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
            <Kpi label="Ações na janela" valor={String(ficha.acoes)} />
            <Kpi label="Dias ativos" valor={String(ficha.dias_ativos)} />
            <Kpi
              label="Último acesso"
              valor={diaCurto(ficha.ultimo_dia)}
              sub={ficha.ultimo_hora ? `às ${ficha.ultimo_hora} (BRT)` : undefined}
            />
            <Kpi
              label="IPs distintos"
              valor={String(ficha.ips)}
              sub="contagem — o IP em si fica só na trilha"
            />
          </div>

          <Secao titulo="O que fez (por feature — sem o conteúdo consultado)">
            <BarrasHorizontais
              itens={ficha.features.map((f) => ({ rotulo: f.feature, valor: f.n }))}
            />
          </Secao>

          <Secao titulo="Janelas de atividade por dia">
            <Tabela
              colunas={
                [
                  { chave: 'dia', rotulo: 'Dia', render: (d) => diaCurto(d.dia), largura: 90 },
                  {
                    chave: 'janela',
                    rotulo: 'Janela (BRT)',
                    render: (d) => (
                      <span className="num">
                        {d.ini}–{d.fim}
                      </span>
                    ),
                  },
                  {
                    chave: 'acoes',
                    rotulo: 'Ações',
                    alinhamento: 'right',
                    largura: 80,
                    render: (d) => <span className="num">{d.acoes}</span>,
                  },
                ] as Coluna<AcessosFicha['dias'][number]>[]
              }
              dados={ficha.dias}
              chaveDe={(d) => d.dia}
            />
          </Secao>
        </>
      ) : null}
    </div>
  )
}

export default function AcessosScreen({ onInicio }: { onInicio: () => void }) {
  const [dias, setDias] = useState<number>(30)
  const [resumo, setResumo] = useState<AcessosResumo | null>(null)
  const [carregando, setCarregando] = useState(false)
  const [erro, setErro] = useState<string | null>(null)
  const [aberta, setAberta] = useState<string | null>(null)

  useEffect(() => {
    let vivo = true
    setCarregando(true)
    setErro(null)
    api
      .acessosResumo(dias)
      .then((r) => {
        if (vivo) setResumo(r)
      })
      .catch((e: ApiError) => {
        if (vivo) {
          setErro(
            e.status === 404
              ? 'O painel de acessos não está habilitado para este usuário.'
              : e.message,
          )
          setResumo(null)
        }
      })
      .finally(() => vivo && setCarregando(false))
    return () => {
      vivo = false
    }
  }, [dias])

  const colunas: Coluna<AcessosUsuarioLinha>[] = [
    {
      chave: 'nome',
      rotulo: 'Usuário',
      render: (u) => (
        <span style={{ font: '600 12px/1.2 var(--f-ui)', color: 'var(--tx-max)' }}>{u.nome}</span>
      ),
    },
    {
      chave: 'ultimo',
      rotulo: 'Último acesso',
      largura: 120,
      render: (u) => (
        <span className="num">
          {diaCurto(u.ultimo_dia)}
          {u.ultimo_hora ? ` ${u.ultimo_hora}` : ''}
        </span>
      ),
    },
    {
      chave: 'dias_ativos',
      rotulo: 'Dias ativos',
      alinhamento: 'right',
      largura: 90,
      render: (u) => <span className="num">{u.dias_ativos}</span>,
    },
    {
      chave: 'acoes',
      rotulo: 'Ações',
      alinhamento: 'right',
      largura: 76,
      render: (u) => <span className="num">{u.acoes}</span>,
    },
    {
      chave: 'abas',
      rotulo: 'Abas',
      render: (u) => u.abas.join(', ') || '—',
    },
    {
      chave: 'ips',
      rotulo: 'IPs',
      alinhamento: 'right',
      largura: 60,
      ajuda: 'Nº de IPs distintos na janela — o IP em si não é exibido',
      render: (u) => <span className="num">{u.ips}</span>,
    },
  ]

  return (
    <div
      style={{
        position: 'absolute',
        inset: 0,
        display: 'flex',
        flexDirection: 'column',
        background: 'var(--bg-base)',
      }}
    >
      <header
        style={{
          flexShrink: 0,
          display: 'flex',
          alignItems: 'center',
          gap: 12,
          padding: '12px 18px',
          borderBottom: '1px solid var(--line-soft)',
          background: 'var(--surf-chrome)',
          backdropFilter: 'blur(14px)',
        }}
      >
        <BotaoInicio onInicio={onInicio} />
        <h1 style={{ font: '600 14px/1 var(--f-ui)', color: 'var(--tx-max)', margin: 0 }}>
          Acessos e uso do piloto
        </h1>
        <Chip tom="amber">restrito</Chip>
        <div style={{ flex: 1 }} />
        <div style={{ display: 'flex', gap: 6 }}>
          {JANELAS.map((j) => (
            <button
              key={j}
              type="button"
              onClick={() => setDias(j)}
              aria-pressed={dias === j}
              style={{
                padding: '7px 11px',
                borderRadius: 'var(--r-md)',
                border: '1px solid',
                borderColor: dias === j ? 'var(--ac)' : 'var(--line-strong)',
                background: dias === j ? 'var(--ac-a16)' : 'transparent',
                color: dias === j ? 'var(--ac-text)' : 'var(--tx-soft)',
                font: '600 11.5px/1 var(--f-ui)',
                cursor: 'pointer',
              }}
            >
              {j} dias
            </button>
          ))}
        </div>
        {resumo && (
          <span style={{ font: '400 10.5px/1 var(--f-num)', color: 'var(--tx-muted)' }}>
            atualizado {resumo.gerado_em}
          </span>
        )}
      </header>

      <div style={{ flex: 1, overflowY: 'auto', padding: 16 }}>
        {carregando && !resumo ? (
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 8,
              color: 'var(--tx-muted)',
              font: '400 12px/1 var(--f-ui)',
              padding: 30,
            }}
          >
            <Spinner /> Lendo a trilha de acesso…
          </div>
        ) : erro ? (
          <Aviso
            titulo="Painel indisponível"
            corpo={erro}
            acao={
              <Botao variante="ghost" onClick={onInicio}>
                Voltar ao início
              </Botao>
            }
          />
        ) : resumo ? (
          aberta ? (
            <FichaUsuarioAcessos nome={aberta} dias={dias} onVoltar={() => setAberta(null)} />
          ) : (
            // Refetch (troca de janela) com dado antigo na tela: esmaece e trava o
            // clique em vez de piscar um spinner — feedback sem perder o contexto.
            <div
              style={{
                display: 'flex',
                flexDirection: 'column',
                gap: 12,
                maxWidth: 1180,
                opacity: carregando ? 0.55 : 1,
                pointerEvents: carregando ? 'none' : 'auto',
                transition: 'opacity .15s ease',
              }}
            >
              <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
                <Kpi label="Usuários hoje" valor={String(resumo.hoje.usuarios)} />
                <Kpi label="Ações hoje" valor={String(resumo.hoje.acoes)} />
                <Kpi label="Aba mais usada hoje" valor={resumo.hoje.aba_top ?? '—'} />
                <Kpi
                  label="Último acesso"
                  valor={resumo.hoje.ultimo?.usuario ?? '—'}
                  sub={resumo.hoje.ultimo?.hora ? `às ${resumo.hoje.ultimo.hora} (BRT)` : undefined}
                />
              </div>

              <Secao titulo="Ações por dia — série completa (rollup sem dado pessoal)">
                <BarrasSerie serie={resumo.serie} />
              </Secao>

              <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
                <Glass
                  style={{
                    flex: '1 1 380px',
                    minWidth: 0,
                    padding: '14px 16px',
                    display: 'flex',
                    flexDirection: 'column',
                    gap: 10,
                  }}
                >
                  <Eyebrow>{`Uso por aba — ${resumo.janela_dias} dias`}</Eyebrow>
                  <BarrasHorizontais
                    itens={resumo.por_aba.map((a) => ({
                      rotulo: a.aba,
                      valor: a.acoes,
                      sub: `· ${a.usuarios}u`,
                    }))}
                  />
                </Glass>
                <Glass
                  style={{
                    flex: '2 1 520px',
                    minWidth: 0,
                    padding: '14px 16px',
                    display: 'flex',
                    flexDirection: 'column',
                    gap: 10,
                  }}
                >
                  <Eyebrow>Quando o time usa — hora × dia da semana (BRT)</Eyebrow>
                  <Heatmap heatmap={resumo.heatmap} />
                </Glass>
              </div>

              <Secao titulo={`Usuários — ${resumo.janela_dias} dias (clique para a ficha)`}>
                <Tabela
                  colunas={colunas}
                  dados={resumo.usuarios}
                  chaveDe={(u) => u.nome}
                  onLinha={(u) => setAberta(u.nome)}
                  vazio="Nenhum acesso registrado na janela."
                />
              </Secao>

              <Secao titulo="Saúde do piloto (da própria trilha)">
                <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
                  <Kpi
                    label="Taxa de erro"
                    valor={`${resumo.saude.taxa_erro_pct}%`}
                    sub={`${resumo.saude.erros_4xx} × 4xx · ${resumo.saude.erros_5xx} × 5xx em ${resumo.saude.total} requisições`}
                    tone={resumo.saude.erros_5xx > 0 ? 'var(--neg)' : undefined}
                  />
                  <div style={{ flex: '3 1 420px', minWidth: 0 }}>
                    <BarrasHorizontais
                      itens={resumo.saude.lentas.map((l) => ({
                        rotulo: l.rota,
                        valor: l.p95_ms ?? 0,
                        sub: 'ms',
                      }))}
                    />
                    <div
                      style={{
                        marginTop: 6,
                        font: '400 10px/1.4 var(--f-ui)',
                        color: 'var(--tx-muted)',
                      }}
                    >
                      p95 de latência das rotas mais pedidas (mín. 5 chamadas na janela).
                    </div>
                  </div>
                </div>
              </Secao>

              <div style={{ font: '400 10.5px/1.5 var(--f-ui)', color: 'var(--tx-muted)' }}>
                As métricas excluem este painel e as chamadas de diagnóstico. O conteúdo
                consultado (endereços pesquisados, parâmetros de simulação) não é exibido aqui —
                fica apenas na trilha bruta do servidor, com retenção de 90 dias (DEC-027). A
                série diária vem do rollup sem dado pessoal e por isso segue além dos 90 dias.
              </div>
            </div>
          )
        ) : null}
      </div>
    </div>
  )
}
