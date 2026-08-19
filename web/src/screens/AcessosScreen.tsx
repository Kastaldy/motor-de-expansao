import { useCallback, useEffect, useRef, useState } from 'react'

import BotaoInicio from '../components/BotaoInicio'
import Tabela, { type Coluna } from '../components/Tabela'
import { Rosca } from '../components/exec/ExecCharts'
import {
  Aviso,
  Botao,
  Chip,
  Eyebrow,
  Glass,
  Kpi,
  SparklineSvg,
  Spinner,
} from '../components/primitives'
import { api, ApiError } from '../lib/api'
import { normalizar } from '../lib/exec'
import type {
  AcessosFicha,
  AcessosResumo,
  AcessosUsuarioLinha,
} from '../lib/types'

/* ---------------------------------------------------------------------------
   Aba Acessos — painel de uso do piloto (emenda DEC-027; redesign 2026-08-19).

   RESTRITA: só existe para quem está na allowlist do backend
   (MOTOR_ACESSOS_ADMIN_USUARIOS); para o resto do time a rota devolve 404 e o
   ícone nem aparece no Dock. O corte de privacidade decidido na emenda vale em
   toda a tela: atividade até o nível de FEATURE ("rodou simulador 4x"), nunca o
   conteúdo consultado (endereço, parâmetros) nem IP bruto.

   Visual: grid de 12 colunas ocupando a tela inteira; cada aba do piloto tem uma
   COR DE IDENTIDADE própria (tokens de categoria --gr-azul/--gr-verde/--gr-rosa e
   --ac, os mesmos do resto do produto) na rosca, tabelas e linha do tempo. Gráficos
   em SVG à mão, como o resto do produto (`ExecCharts`); a `Rosca` é a mesma da
   Visão Executiva.
   --------------------------------------------------------------------------- */

const JANELAS = [7, 30, 90] as const

const DIAS_SEMANA = ['Seg', 'Ter', 'Qua', 'Qui', 'Sex', 'Sáb', 'Dom']

/** Identidade de cor por aba (labels acentuados, como o backend entrega). */
const COR_ABA: Record<string, string> = {
  Executiva: 'var(--gr-azul)',
  Mapa: 'var(--ac)',
  Viabilidade: 'var(--gr-verde)',
  Oportunidades: 'var(--gr-rosa)',
}
const corAba = (aba: string | null): string =>
  (aba && COR_ABA[aba]) || 'var(--tx-muted)'

/** Paleta dos avatares — variedade estável por nome, sem estado. */
const CORES_AVATAR = ['var(--gr-azul)', 'var(--gr-verde)', 'var(--gr-rosa)', 'var(--ac)', 'var(--l2)']
function corDoNome(nome: string): string {
  let h = 0
  for (const c of nome) h = (h * 31 + c.charCodeAt(0)) % 997
  return CORES_AVATAR[h % CORES_AVATAR.length]
}

function iniciais(nome: string): string {
  const partes = nome.split(/[._\s-]+/).filter(Boolean)
  return ((partes[0]?.[0] ?? '?') + (partes[1]?.[0] ?? '')).toUpperCase()
}

/** `2026-08-19` -> `19/08`. */
function diaCurto(iso: string | null): string {
  if (!iso) return '—'
  const [, m, d] = iso.split('-')
  return `${d}/${m}`
}

function duracaoDaJanela(ini: string, fim: string): string {
  const [hi, mi] = ini.split(':').map(Number)
  const [hf, mf] = fim.split(':').map(Number)
  const min = hf * 60 + mf - (hi * 60 + mi)
  if (min <= 0) return '—'
  if (min < 60) return `${min} min`
  return `${Math.floor(min / 60)}h${String(min % 60).padStart(2, '0')}`
}

function fmtMs(ms: number | null): string {
  if (ms === null) return '—'
  return ms >= 1000 ? `${(ms / 1000).toFixed(1)} s` : `${ms} ms`
}

/** Bolinha de identidade de aba, com rótulo opcional. */
function PontoAba({ aba, rotulo = true }: { aba: string; rotulo?: boolean }) {
  return (
    <span style={{ display: 'inline-flex', alignItems: 'center', gap: 5, whiteSpace: 'nowrap' }}>
      <span
        style={{
          width: 7,
          height: 7,
          borderRadius: '50%',
          background: corAba(aba),
          flexShrink: 0,
        }}
      />
      {rotulo && (
        <span style={{ font: '400 11px/1 var(--f-ui)', color: 'var(--tx-soft)' }}>{aba}</span>
      )}
    </span>
  )
}

function Avatar({ nome, tamanho = 28 }: { nome: string; tamanho?: number }) {
  const cor = corDoNome(nome)
  return (
    <span
      aria-hidden
      style={{
        width: tamanho,
        height: tamanho,
        borderRadius: '50%',
        flexShrink: 0,
        display: 'inline-grid',
        placeItems: 'center',
        background: `color-mix(in srgb, ${cor} 20%, transparent)`,
        color: cor,
        font: `700 ${Math.round(tamanho * 0.38)}px/1 var(--f-ui)`,
        letterSpacing: '.02em',
      }}
    >
      {iniciais(nome)}
    </span>
  )
}

/** Card padrão do grid. `span` em colunas (de 12). */
function Card({
  span,
  titulo,
  acao,
  children,
}: {
  span: number
  titulo?: string
  acao?: React.ReactNode
  children: React.ReactNode
}) {
  return (
    <Glass
      style={{
        gridColumn: `span ${span}`,
        minWidth: 0,
        padding: '15px 17px',
        display: 'flex',
        flexDirection: 'column',
        gap: 12,
      }}
    >
      {(titulo || acao) && (
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8 }}>
          {titulo && <Eyebrow>{titulo}</Eyebrow>}
          {acao}
        </div>
      )}
      {children}
    </Glass>
  )
}

/**
 * Largura real do card (mesmo racional do `useLargura` de ExecCharts, replicado
 * aqui porque ele não é exportado): SVG com viewBox fixo centralizaria o desenho
 * num card largo em vez de preenchê-lo.
 */
function useLarguraLocal(): [(no: HTMLElement | null) => void, number] {
  const [largura, setLargura] = useState(0)
  const observador = useRef<ResizeObserver | null>(null)
  const medir = useCallback((no: HTMLElement | null) => {
    observador.current?.disconnect()
    if (!no) return
    setLargura(no.getBoundingClientRect().width)
    if (typeof ResizeObserver === 'undefined') return
    const obs = new ResizeObserver(([entrada]) => setLargura(entrada.contentRect.width))
    obs.observe(no)
    observador.current = obs
  }, [])
  useEffect(() => () => observador.current?.disconnect(), [])
  return [medir, largura]
}

/** Teto de dias desenhados: acima disso as barras virariam fio e o eixo, ruído. */
const MAX_DIAS_SERIE = 180

/**
 * Série diária: barras de AÇÕES + linha de USUÁRIOS únicos, no mesmo eixo de
 * dias. SVG medido (não centraliza), eixo com gridlines e rótulos de data
 * esparsos; a base da escala é ZERO, como manda ExecCharts.
 */
function GraficoSerie({ serie: serieCompleta }: { serie: AcessosResumo['serie'] }) {
  const [medir, medida] = useLarguraLocal()
  const serie = serieCompleta.slice(-MAX_DIAS_SERIE)
  const largura = medida > 0 ? medida : 640
  const altura = 168
  const topo = 6
  const baseEixo = altura - 16 // faixa inferior para os rótulos de data
  const maxAcoes = Math.max(1, ...serie.map((d) => d.acoes))
  const n = Math.max(serie.length, 1)
  const fatia = largura / n
  const larguraBarra = Math.max(1.5, Math.min(14, fatia * 0.62))

  // Linha de usuários com BASE ZERO e teto próprio — `caminhoSparkline` normaliza
  // por min-max e, sobre um gráfico COM eixo numérico, uma série constante sairia
  // cravada no meio da caixa (defeito da revisão adversarial de 2026-08-19).
  const maxUsuarios = Math.max(1, ...serie.map((d) => d.usuarios))
  const yUsuario = (v: number) => topo + (baseEixo - topo) * (1 - v / maxUsuarios)
  const xCentro = (i: number) => i * fatia + fatia / 2
  const caminhoUsuarios = serie
    .map((d, i) => `${i === 0 ? 'M' : 'L'}${xCentro(i).toFixed(1)} ${yUsuario(d.usuarios).toFixed(1)}`)
    .join(' ')

  // ~6 datas no eixo, sempre com a primeira e a última.
  const passo = Math.max(1, Math.ceil(n / 6))
  const comRotulo = (i: number) => i === 0 || i === n - 1 || (i % passo === 0 && i < n - passo / 2)

  // Dedup: com pico de 1 ação/dia, 0.5 e 1 arredondam para o MESMO tick (chave
  // React duplicada + gridline dobrada).
  const gridY = [...new Set([Math.max(1, Math.round(maxAcoes * 0.5)), maxAcoes])]

  return (
    <figure ref={medir} style={{ margin: 0 }}>
      <svg viewBox={`0 0 ${largura} ${altura}`} width="100%" height={altura} role="img" aria-label="Ações e usuários por dia">
        {gridY.map((v) => {
          const y = topo + (baseEixo - topo) * (1 - v / maxAcoes)
          return (
            <g key={v}>
              <line x1={0} y1={y} x2={largura} y2={y} stroke="var(--line-soft)" strokeWidth={1} />
              <text x={0} y={y - 3} style={{ font: '500 8.5px/1 var(--f-num)', fill: 'var(--tx-muted)' }}>
                {v}
              </text>
            </g>
          )
        })}
        <line x1={0} y1={baseEixo} x2={largura} y2={baseEixo} stroke="var(--line-mid)" strokeWidth={1} />
        {serie.map((d, i) => {
          const h = ((baseEixo - topo) * d.acoes) / maxAcoes
          const x = i * fatia + (fatia - larguraBarra) / 2
          const ultima = i === n - 1
          return (
            <g key={d.dia}>
              <rect
                x={x}
                y={baseEixo - Math.max(h, d.acoes ? 1.5 : 0)}
                width={larguraBarra}
                height={Math.max(h, d.acoes ? 1.5 : 0)}
                rx={Math.min(2.5, larguraBarra / 2)}
                fill={ultima ? 'var(--ac)' : 'color-mix(in srgb, var(--ac) 45%, transparent)'}
              >
                <title>{`${diaCurto(d.dia)} — ${d.acoes} ações · ${d.usuarios} usuários`}</title>
              </rect>
              {comRotulo(i) && (
                // Nas pontas o rótulo ancora para dentro, senão a borda do SVG o corta.
                <text
                  x={i === 0 ? 2 : i === n - 1 ? largura - 2 : xCentro(i)}
                  y={altura - 4}
                  textAnchor={i === 0 ? 'start' : i === n - 1 ? 'end' : 'middle'}
                  style={{ font: '500 8.5px/1 var(--f-num)', fill: 'var(--tx-muted)' }}
                >
                  {diaCurto(d.dia)}
                </text>
              )}
            </g>
          )
        })}
        {serie.length > 0 && (
          <g pointerEvents="none">
            <path
              d={caminhoUsuarios}
              fill="none"
              stroke="var(--gr-azul)"
              strokeWidth={1.6}
              strokeLinejoin="round"
            />
            <circle
              cx={xCentro(n - 1)}
              cy={yUsuario(serie[n - 1].usuarios)}
              r={2.6}
              fill="var(--gr-azul)"
            />
          </g>
        )}
      </svg>
      <figcaption
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 14,
          marginTop: 8,
          font: '400 10.5px/1 var(--f-ui)',
          color: 'var(--tx-muted)',
        }}
      >
        <span style={{ display: 'inline-flex', alignItems: 'center', gap: 5 }}>
          <span style={{ width: 9, height: 9, borderRadius: 2, background: 'var(--ac)' }} /> ações
        </span>
        <span style={{ display: 'inline-flex', alignItems: 'center', gap: 5 }}>
          <span style={{ width: 12, height: 2, background: 'var(--gr-azul)' }} /> usuários únicos
          (escala própria, máx. {maxUsuarios})
        </span>
        {serieCompleta.length > MAX_DIAS_SERIE && (
          <span>· exibindo os últimos {MAX_DIAS_SERIE} dias (série desde {diaCurto(serieCompleta[0]?.dia ?? null)})</span>
        )}
      </figcaption>
    </figure>
  )
}

/** Hora × dia da semana (BRT), rampa da cor de acento sobre a superfície. */
function Heatmap({ heatmap, altura = 15 }: { heatmap: number[][]; altura?: number }) {
  const max = Math.max(1, ...heatmap.flat())
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
      {heatmap.map((linha, d) => (
        <div key={DIAS_SEMANA[d]} style={{ display: 'flex', alignItems: 'center', gap: 3 }}>
          <span
            style={{
              width: 30,
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
                minWidth: 5,
                height: altura,
                borderRadius: 3,
                background: v
                  ? `color-mix(in srgb, var(--ac) ${Math.round(18 + 82 * (v / max))}%, var(--surf-raised))`
                  : 'var(--surf-raised)',
              }}
            />
          ))}
        </div>
      ))}
      <div style={{ display: 'flex', gap: 3, marginLeft: 33 }}>
        {Array.from({ length: 24 }, (_, h) => (
          <span
            key={h}
            className="num"
            style={{
              flex: 1,
              minWidth: 5,
              font: '400 8.5px/1 var(--f-num)',
              color: 'var(--tx-muted)',
              textAlign: 'center',
            }}
          >
            {h % 3 === 0 ? h : ''}
          </span>
        ))}
      </div>
    </div>
  )
}

/** Barras horizontais de proporção (features, rotas lentas). */
function BarrasHorizontais({
  itens,
  mono = false,
}: {
  itens: { rotulo: string; valor: number; texto?: string; cor?: string }[]
  /** rótulo em fonte mono (rotas, códigos) */
  mono?: boolean
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
    <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
      {itens.map((i) => (
        <div key={i.rotulo} style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <span
            className={mono ? 'num' : undefined}
            style={{
              width: 190,
              flexShrink: 0,
              font: mono ? '500 10.5px/1.2 var(--f-num)' : '500 11.5px/1.2 var(--f-ui)',
              color: 'var(--tx-soft)',
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              whiteSpace: 'nowrap',
            }}
            title={i.rotulo}
          >
            {i.rotulo}
          </span>
          <div style={{ flex: 1, height: 9, background: 'var(--surf-raised)', borderRadius: 5 }}>
            <div
              style={{
                width: `${(100 * i.valor) / max}%`,
                height: '100%',
                borderRadius: 5,
                background: i.cor ?? 'var(--ac)',
                opacity: 0.85,
              }}
            />
          </div>
          <span
            className="num"
            style={{
              width: 62,
              flexShrink: 0,
              textAlign: 'right',
              font: '600 11.5px/1 var(--f-num)',
              color: 'var(--tx-max)',
            }}
          >
            {i.texto ?? i.valor}
          </span>
        </div>
      ))}
    </div>
  )
}

/* ---------------------------------------------------------------------------
   Nível 2 — a ficha de um usuário (padrão de troca de corpo da Executiva).
   --------------------------------------------------------------------------- */

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

  if (carregando) {
    return (
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 8,
          color: 'var(--tx-muted)',
          font: '400 12px/1 var(--f-ui)',
          padding: 24,
        }}
      >
        <Spinner /> Lendo a trilha…
      </div>
    )
  }
  if (erro) {
    return (
      <Aviso
        titulo="Não deu para abrir a ficha"
        corpo={erro}
        acao={
          <Botao variante="ghost" onClick={onVoltar}>
            ← Todos os usuários
          </Botao>
        }
      />
    )
  }
  if (!ficha) return null

  // Guardas contra payload de backend ANTIGO (cache/deploy no meio): os campos do
  // redesign podem faltar e a ficha degrada em vez de quebrar a tela inteira.
  const sessoes = ficha.sessoes ?? []
  const linhaDoTempo = ficha.linha_do_tempo ?? []
  const porAba = ficha.por_aba ?? []
  const nErros = ficha.erros ?? 0
  const temHeatmap = Array.isArray(ficha.heatmap)
  const diasAsc = [...(ficha.dias ?? [])].reverse()

  const colunasSessoes: Coluna<AcessosFicha['sessoes'][number]>[] = [
    {
      chave: 'dia',
      rotulo: 'Dia',
      largura: 76,
      render: (s) => <span className="num">{diaCurto(s.dia)}</span>,
    },
    {
      chave: 'janela',
      rotulo: 'Sessão (BRT)',
      largura: 130,
      render: (s) => (
        <span className="num">
          {s.ini}–{s.fim}
        </span>
      ),
    },
    {
      chave: 'duracao',
      rotulo: 'Duração',
      largura: 84,
      render: (s) => <span className="num">{duracaoDaJanela(s.ini, s.fim)}</span>,
    },
    {
      chave: 'acoes',
      rotulo: 'Ações',
      alinhamento: 'right',
      largura: 66,
      render: (s) => <span className="num">{s.acoes}</span>,
    },
    {
      chave: 'abas',
      rotulo: 'Onde',
      render: (s) => (
        <span style={{ display: 'inline-flex', gap: 10 }}>
          {s.abas.map((a) => (
            <PontoAba key={a} aba={a} />
          ))}
        </span>
      ),
    },
  ]

  // Linha do tempo agrupada por dia, preservando a ordem (mais recente primeiro).
  const grupos: { dia: string; eventos: AcessosFicha['linha_do_tempo'] }[] = []
  for (const ev of linhaDoTempo) {
    const grupo = grupos[grupos.length - 1]
    if (grupo && grupo.dia === ev.dia) grupo.eventos.push(ev)
    else grupos.push({ dia: ev.dia, eventos: [ev] })
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, flexWrap: 'wrap' }}>
        <Botao variante="ghost" onClick={onVoltar} style={{ padding: '8px 12px' }}>
          ← Todos os usuários
        </Botao>
        <Avatar nome={ficha.nome} tamanho={38} />
        <div style={{ minWidth: 0 }}>
          <div style={{ font: '700 16px/1.2 var(--f-ui)', color: 'var(--tx-max)' }}>{ficha.nome}</div>
          <div style={{ font: '400 11px/1.4 var(--f-ui)', color: 'var(--tx-muted)', marginTop: 2 }}>
            visto por último em {diaCurto(ficha.ultimo_dia)}
            {ficha.ultimo_hora ? ` às ${ficha.ultimo_hora} (BRT)` : ''} · janela de {ficha.janela_dias} dias
          </div>
        </div>
        <div style={{ display: 'inline-flex', gap: 12, marginLeft: 4 }}>
          {(ficha.abas ?? []).map((a) => (
            <PontoAba key={a} aba={a} />
          ))}
        </div>
      </div>

      <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
        <Kpi label="Ações na janela" valor={String(ficha.acoes)} />
        <Kpi label="Sessões" valor={String(sessoes.length)} sub="pausa > 30 min abre outra" />
        <Kpi label="Dias ativos" valor={String(ficha.dias_ativos)} />
        <Kpi
          label="IPs distintos"
          valor={String(ficha.ips)}
          sub="contagem — o IP em si fica só na trilha"
        />
        <Kpi
          label="Respostas de erro"
          valor={String(nErros)}
          tone={nErros > 0 ? 'var(--warn-text)' : undefined}
          sub="4xx/5xx recebidas por este usuário"
        />
      </div>

      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(12, minmax(0, 1fr))',
          gap: 12,
        }}
      >
        <Card span={7} titulo="Atividade por dia">
          <div style={{ maxHeight: 300, overflowY: 'auto' }}>
            <BarrasHorizontais
              itens={diasAsc.map((d) => ({
                rotulo: `${diaCurto(d.dia)} · ${d.ini}–${d.fim}`,
                valor: d.acoes,
                texto: `${d.acoes}`,
              }))}
              mono
            />
          </div>
        </Card>
        <Card span={5} titulo="O que fez (por feature)">
          <BarrasHorizontais itens={(ficha.features ?? []).map((f) => ({ rotulo: f.feature, valor: f.n }))} />
          {porAba.length > 0 && (
            <div style={{ display: 'flex', gap: 14, flexWrap: 'wrap', marginTop: 2 }}>
              {porAba.map((a) => (
                <span key={a.aba} style={{ display: 'inline-flex', alignItems: 'center', gap: 5 }}>
                  <PontoAba aba={a.aba} />
                  <span className="num" style={{ font: '600 11px/1 var(--f-num)', color: 'var(--tx-max)' }}>
                    {a.acoes}
                  </span>
                </span>
              ))}
            </div>
          )}
        </Card>

        <Card span={7} titulo="Sessões (mais recentes primeiro)">
          <div style={{ maxHeight: 320, overflowY: 'auto' }}>
            <Tabela colunas={colunasSessoes} dados={sessoes} chaveDe={(s) => `${s.dia}-${s.ini}`} />
          </div>
        </Card>
        <Card span={5} titulo="Horários de uso (hora × dia, BRT)">
          {temHeatmap ? (
            <Heatmap heatmap={ficha.heatmap} altura={13} />
          ) : (
            <span style={{ font: '400 12px/1.4 var(--f-ui)', color: 'var(--tx-muted)' }}>
              Indisponível neste payload.
            </span>
          )}
        </Card>

        <Card span={12} titulo={`Linha do tempo — últimas ${linhaDoTempo.length} ações (sem o conteúdo consultado)`}>
          <div style={{ maxHeight: 420, overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: 4 }}>
            {grupos.map((g) => (
              <div key={g.dia}>
                <div
                  style={{
                    font: '600 10.5px/1 var(--f-num)',
                    color: 'var(--tx-label)',
                    textTransform: 'uppercase',
                    letterSpacing: '.06em',
                    padding: '8px 0 6px',
                    borderBottom: '1px solid var(--line-soft)',
                  }}
                >
                  {diaCurto(g.dia)}
                </div>
                {g.eventos.map((ev, i) => (
                  <div
                    key={`${ev.hora}-${i}`}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: 10,
                      padding: '6px 0',
                      borderBottom: '1px solid var(--line-soft)',
                    }}
                  >
                    <span className="num" style={{ width: 44, flexShrink: 0, font: '500 11px/1 var(--f-num)', color: 'var(--tx-muted)' }}>
                      {ev.hora}
                    </span>
                    <span
                      style={{
                        width: 7,
                        height: 7,
                        borderRadius: '50%',
                        background: corAba(ev.aba),
                        flexShrink: 0,
                      }}
                      title={ev.aba ?? 'fora das abas'}
                    />
                    <span style={{ font: '400 12px/1.3 var(--f-ui)', color: 'var(--tx-soft)', flex: 1, minWidth: 0 }}>
                      {ev.feature}
                    </span>
                    {ev.erro && <Chip tom="red">erro</Chip>}
                  </div>
                ))}
              </div>
            ))}
          </div>
        </Card>
      </div>
    </div>
  )
}

/* ---------------------------------------------------------------------------
   Nível 1 — o painel.
   --------------------------------------------------------------------------- */

export default function AcessosScreen({ onInicio }: { onInicio: () => void }) {
  const [dias, setDias] = useState<number>(30)
  const [resumo, setResumo] = useState<AcessosResumo | null>(null)
  const [carregando, setCarregando] = useState(false)
  const [erro, setErro] = useState<string | null>(null)
  const [aberta, setAberta] = useState<string | null>(null)
  const [filtroUsuario, setFiltroUsuario] = useState('')

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
        <span style={{ display: 'inline-flex', alignItems: 'center', gap: 9, minWidth: 0 }}>
          <Avatar nome={u.nome} tamanho={26} />
          <span style={{ font: '600 12px/1.2 var(--f-ui)', color: 'var(--tx-max)', overflow: 'hidden', textOverflow: 'ellipsis' }}>
            {u.nome}
          </span>
        </span>
      ),
    },
    {
      chave: 'serie14',
      rotulo: 'Ritmo diário',
      largura: 100,
      ordenavel: false,
      ajuda: 'Ações por dia (série da janela, até 14 dias)',
      render: (u) => <SparklineSvg valores={u.serie14 ?? []} largura={84} altura={20} />,
    },
    {
      chave: 'ultimo',
      rotulo: 'Último acesso',
      largura: 116,
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
      largura: 86,
      render: (u) => <span className="num">{u.dias_ativos}</span>,
    },
    {
      chave: 'acoes',
      rotulo: 'Ações',
      alinhamento: 'right',
      largura: 70,
      render: (u) => (
        <span className="num" style={{ color: 'var(--tx-max)', fontWeight: 600 }}>{u.acoes}</span>
      ),
    },
    {
      chave: 'abas',
      rotulo: 'Abas',
      render: (u) => (
        <span style={{ display: 'inline-flex', gap: 10 }}>
          {u.abas.map((a) => (
            <PontoAba key={a} aba={a} />
          ))}
        </span>
      ),
    },
    {
      chave: 'ips',
      rotulo: 'IPs',
      alinhamento: 'right',
      largura: 56,
      ajuda: 'Nº de IPs distintos na janela — o IP em si não é exibido',
      render: (u) => <span className="num">{u.ips}</span>,
    },
  ]

  // Filtro local da tabela: o payload inteiro já está no cliente (mesma razão do
  // `filtrarUnidades` da Executiva) — digitar não pode custar um round-trip.
  const alvoFiltro = normalizar(filtroUsuario)
  const usuariosFiltrados = resumo
    ? resumo.usuarios.filter((u) => !alvoFiltro || normalizar(u.nome).includes(alvoFiltro))
    : []

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
          padding: '12px 20px',
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

      <div style={{ flex: 1, overflowY: 'auto', padding: '16px 22px' }}>
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
                display: 'grid',
                gridTemplateColumns: 'repeat(12, minmax(0, 1fr))',
                gap: 14,
                opacity: carregando ? 0.55 : 1,
                pointerEvents: carregando ? 'none' : 'auto',
                transition: 'opacity .15s ease',
              }}
            >
              <div style={{ gridColumn: 'span 12', display: 'flex', gap: 12, flexWrap: 'wrap' }}>
                <Kpi label="Usuários hoje" valor={String(resumo.hoje.usuarios)} />
                <Kpi label="Ações hoje" valor={String(resumo.hoje.acoes)} />
                <Kpi
                  label="Aba mais usada hoje"
                  valor={resumo.hoje.aba_top ?? '—'}
                  tone={resumo.hoje.aba_top ? corAba(resumo.hoje.aba_top) : undefined}
                />
                <Kpi
                  label="Último acesso"
                  valor={resumo.hoje.ultimo?.usuario ?? '—'}
                  sub={resumo.hoje.ultimo?.hora ? `às ${resumo.hoje.ultimo.hora} (BRT)` : undefined}
                />
                <Kpi
                  label="Taxa de erro"
                  valor={`${resumo.saude.taxa_erro_pct}%`}
                  tone={resumo.saude.erros_5xx > 0 ? 'var(--neg)' : undefined}
                  sub={`na janela de ${resumo.janela_dias} dias`}
                />
              </div>

              <Card span={8} titulo="Ritmo de uso — ações e usuários por dia">
                <GraficoSerie serie={resumo.serie} />
              </Card>

              <Card span={4} titulo={`Uso por aba — ${resumo.janela_dias} dias`}>
                {resumo.por_aba.length ? (
                  <Rosca
                    partes={resumo.por_aba.map((a) => ({
                      rotulo: a.aba,
                      valor: a.acoes,
                      cor: corAba(a.aba),
                    }))}
                    tamanho={148}
                    espessura={22}
                    centroValor={String(resumo.por_aba.reduce((s, a) => s + a.acoes, 0))}
                    centroRotulo="ações"
                  />
                ) : (
                  <span style={{ font: '400 12px/1.4 var(--f-ui)', color: 'var(--tx-muted)' }}>
                    Nada registrado na janela.
                  </span>
                )}
              </Card>

              <Card span={7} titulo="Quando o time usa — hora × dia da semana (BRT)">
                <Heatmap heatmap={resumo.heatmap} />
              </Card>

              <Card span={5} titulo="Saúde do piloto">
                <div style={{ display: 'flex', gap: 16, alignItems: 'baseline' }}>
                  <span
                    className="num"
                    style={{
                      font: '700 26px/1 var(--f-num)',
                      color: resumo.saude.erros_5xx > 0 ? 'var(--neg)' : 'var(--pos-text)',
                    }}
                  >
                    {resumo.saude.taxa_erro_pct}%
                  </span>
                  <span style={{ font: '400 11px/1.4 var(--f-ui)', color: 'var(--tx-sub)' }}>
                    de erro · {resumo.saude.erros_4xx} × 4xx · {resumo.saude.erros_5xx} × 5xx
                    <br />
                    em {resumo.saude.total} requisições
                  </span>
                </div>
                <BarrasHorizontais
                  mono
                  itens={resumo.saude.lentas.map((l) => ({
                    rotulo: l.rota,
                    valor: l.p95_ms ?? 0,
                    texto: fmtMs(l.p95_ms),
                    cor: (l.p95_ms ?? 0) >= 5000 ? 'var(--warn)' : 'var(--ac)',
                  }))}
                />
                <div style={{ font: '400 10px/1.4 var(--f-ui)', color: 'var(--tx-muted)' }}>
                  p95 de latência das rotas mais pedidas (mín. 5 chamadas na janela).
                </div>
              </Card>

              <Card
                span={12}
                titulo={`Usuários — ${resumo.janela_dias} dias`}
                acao={
                  <span style={{ display: 'inline-flex', alignItems: 'center', gap: 12 }}>
                    <span style={{ font: '400 10.5px/1 var(--f-ui)', color: 'var(--tx-muted)' }}>
                      clique numa linha para abrir a ficha
                    </span>
                    <input
                      value={filtroUsuario}
                      onChange={(e) => setFiltroUsuario(e.target.value)}
                      placeholder="Filtrar usuário…"
                      aria-label="Filtrar usuário"
                      style={{ width: 168 }}
                    />
                  </span>
                }
              >
                <Tabela
                  colunas={colunas}
                  dados={usuariosFiltrados}
                  chaveDe={(u) => u.nome}
                  onLinha={(u) => setAberta(u.nome)}
                  vazio={
                    filtroUsuario.trim()
                      ? `Nenhum usuário corresponde a "${filtroUsuario.trim()}".`
                      : 'Nenhum acesso registrado na janela.'
                  }
                />
              </Card>

              <div
                style={{
                  gridColumn: 'span 12',
                  font: '400 10.5px/1.5 var(--f-ui)',
                  color: 'var(--tx-muted)',
                }}
              >
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
