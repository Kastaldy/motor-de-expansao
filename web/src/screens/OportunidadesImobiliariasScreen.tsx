import { useEffect, useMemo, useState } from 'react'
import { Map, Marker } from 'react-map-gl/maplibre'

import Select from '../components/Select'
import { Aviso, Botao, Eyebrow, Glass, Spinner } from '../components/primitives'
import { api, ApiError, baixar } from '../lib/api'
import { SCORE_BANDS_HEX } from '../lib/colors'
import { brl, num } from '../lib/format'
import type { Oportunidade } from '../lib/types'

import 'maplibre-gl/dist/maplibre-gl.css'

/**
 * Aba OPORTUNIDADES IMOBILIARIAS — a camada de oferta dentro do piloto.
 *
 * Le o `viaveis.parquet` do coletor (imoveis de locacao ja joinados ao M1) por
 * `/api/oportunidades`. READ-ONLY sobre o M1 e AGREGADA por `hex_id` (contato do
 * corretor so' no dossie, atras do Authelia).
 *
 * DESENHO (rev. 2026-08-20): filtros por DROPDOWN (escalam p/ 27 UFs); leitura variada
 * (medidor radial, donut, scatter de posicionamento) no lugar de barras repetidas;
 * MINI-MAPA no quadrante direito da ficha (padrao da Executiva), centrado no ponto;
 * botoes de acao ligados — "Ver no Mapa Territorial" (deep link) e "Relatorio do ponto".
 */

const BASEMAP = 'https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json'

const FAIXA_LABEL: Record<string, string> = {
  prioridade_maxima: 'Prioridade máxima',
  alta: 'Alta',
  media: 'Média',
  baixa: 'Baixa',
  minima: 'Mínima',
}
const labelFaixa = (v: string | null): string | null =>
  v == null ? null : (FAIXA_LABEL[v] ?? v.charAt(0).toUpperCase() + v.slice(1))

const corResidual = (v: number | null | undefined): string => {
  if (v == null || Number.isNaN(v)) return '#6E7686'
  return SCORE_BANDS_HEX[Math.min(9, Math.max(0, Math.floor(v / 10)))]
}
const rsM2 = (o: Oportunidade): number | null =>
  o.rs_m2 != null ? o.rs_m2 : o.aluguel != null && o.area ? o.aluguel / o.area : null

type Ordem = 'residual' | 'rs_m2' | 'area' | 'aluguel'
const ORDENS: { value: Ordem; label: string }[] = [
  { value: 'residual', label: 'Maior residual (M1)' },
  { value: 'rs_m2', label: 'Menor R$/m²' },
  { value: 'area', label: 'Maior área' },
  { value: 'aluguel', label: 'Menor aluguel' },
]

const MAX_PINS = 140

export default function OportunidadesImobiliariasScreen({
  onInicio,
  onVerNoMapa,
}: {
  onInicio: () => void
  onVerNoMapa: (uf: string, municipio: string) => void
}) {
  const [itens, setItens] = useState<Oportunidade[] | null>(null)
  const [total, setTotal] = useState(0)
  const [erro, setErro] = useState<string | null>(null)
  const [ufSel, setUfSel] = useState('')
  const [tipoSel, setTipoSel] = useState('')
  const [ordem, setOrdem] = useState<Ordem>('residual')
  const [busca, setBusca] = useState('')
  const [sel, setSel] = useState<string | null>(null)

  useEffect(() => {
    let vivo = true
    api
      .oportunidades()
      .then((r) => {
        if (!vivo) return
        setItens(r.itens)
        setTotal(r.total)
        setSel(r.itens[0]?.id ?? null)
      })
      .catch((e: ApiError) => vivo && setErro(e.message))
    return () => {
      vivo = false
    }
  }, [])

  const ufs = useMemo(() => Array.from(new Set((itens ?? []).map((o) => o.uf))).sort(), [itens])
  const tipos = useMemo(
    () => Array.from(new Set((itens ?? []).map((o) => o.tipo).filter(Boolean))).sort(),
    [itens],
  )

  const filtrados = useMemo(() => {
    let xs = itens ?? []
    if (ufSel) xs = xs.filter((o) => o.uf === ufSel)
    if (tipoSel) xs = xs.filter((o) => o.tipo === tipoSel)
    if (busca.trim()) {
      const q = busca.trim().toLowerCase()
      xs = xs.filter((o) => `${o.titulo} ${o.bairro ?? ''} ${o.municipio}`.toLowerCase().includes(q))
    }
    const ord = [...xs]
    ord.sort((a, b) => {
      if (ordem === 'residual') return (b.residual ?? -1) - (a.residual ?? -1)
      if (ordem === 'area') return (b.area ?? -1) - (a.area ?? -1)
      if (ordem === 'aluguel') return (a.aluguel ?? Infinity) - (b.aluguel ?? Infinity)
      return (rsM2(a) ?? Infinity) - (rsM2(b) ?? Infinity)
    })
    return ord
  }, [itens, ufSel, tipoSel, busca, ordem])

  useEffect(() => {
    if (filtrados.length && !filtrados.some((o) => o.id === sel)) setSel(filtrados[0].id)
  }, [filtrados, sel])

  const atual = filtrados.find((o) => o.id === sel) ?? null

  return (
    <div style={{ height: '100%', display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
      {/* Cabeçalho */}
      <header style={{ display: 'flex', alignItems: 'flex-end', justifyContent: 'space-between', gap: 20, padding: '16px 26px 12px' }}>
        <div>
          <Eyebrow dot>Camada de oferta &middot; READ-ONLY sobre o M1</Eyebrow>
          <h1 className="story" style={{ margin: '6px 0 0', fontSize: 30, lineHeight: 1.04, color: 'var(--tx-max)' }}>
            Oportunidades Imobiliárias
          </h1>
          <div style={{ marginTop: 3, font: '400 12.5px/1.4 var(--f-ui)', color: 'var(--tx-narrative)' }}>
            {total ? (
              <>
                <b className="num" style={{ color: 'var(--ac-text)' }}>{num(total)}</b> imóveis de
                locação coletados e cruzados com o território do M1.
              </>
            ) : (
              'Imóveis de locação coletados e cruzados com o território do M1.'
            )}
          </div>
        </div>
        <button
          type="button"
          onClick={onInicio}
          style={{ font: '600 12px/1 var(--f-ui)', color: 'var(--tx-muted)', border: '1px solid var(--line-mid)', borderRadius: 'var(--r-md)', padding: '8px 12px', background: 'var(--surf-raised)' }}
        >
          ← Início
        </button>
      </header>

      {/* Filtros — DROPDOWNS (escalam para 27 UFs) */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap', padding: '10px 26px', borderTop: '1px solid var(--line-soft)', borderBottom: '1px solid var(--line-soft)' }}>
        <Select
          label="Estado"
          value={ufSel}
          onChange={setUfSel}
          placeholder="Todos os estados"
          maxWidth={190}
          options={[{ value: '', label: 'Todos os estados' }, ...ufs.map((u) => ({ value: u, label: u }))]}
        />
        <Select
          label="Tipo de imóvel"
          value={tipoSel}
          onChange={setTipoSel}
          placeholder="Todos os tipos"
          maxWidth={190}
          options={[{ value: '', label: 'Todos os tipos' }, ...tipos.map((t) => ({ value: t, label: t }))]}
        />
        <Select
          label="Ordenar por"
          value={ordem}
          onChange={(v) => setOrdem(v as Ordem)}
          maxWidth={190}
          buscavel={false}
          options={ORDENS}
        />
        <input
          value={busca}
          onChange={(e) => setBusca(e.target.value)}
          placeholder="Buscar bairro, cidade, título…"
          aria-label="Buscar oportunidade"
          style={{ flex: 1, minWidth: 180, maxWidth: 320, height: 34, padding: '0 12px', background: 'var(--surf-input)', border: '1px solid var(--line-mid)', borderRadius: 'var(--r-md)', color: 'var(--tx-strong)', font: '500 13px/1 var(--f-ui)' }}
        />
        <span style={{ marginLeft: 'auto', font: '500 12px/1 var(--f-ui)', color: 'var(--tx-muted)' }}>
          <b className="num" style={{ color: 'var(--tx-soft)' }}>{num(filtrados.length)}</b> no recorte
        </span>
      </div>

      {/* Corpo: lista | ficha */}
      <div style={{ flex: 1, display: 'grid', gridTemplateColumns: 'minmax(300px, 32%) 1fr', minHeight: 0 }}>
        {/* Lista */}
        <div style={{ borderRight: '1px solid var(--line-soft)', overflowY: 'auto', minHeight: 0 }}>
          {itens == null && !erro && (
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, padding: 24, color: 'var(--tx-muted)' }}>
              <Spinner /> Carregando oportunidades…
            </div>
          )}
          {erro && <Aviso titulo="Não deu para carregar" corpo={`${erro} — confira o backend na porta 8899 e o data/oportunidades/viaveis.parquet.`} />}
          {itens != null && filtrados.length === 0 && (
            <Aviso titulo="Nada no recorte" corpo="Nenhuma oportunidade bate com os filtros. Amplie o estado, o tipo ou limpe a busca." />
          )}
          {itens != null && filtrados.map((o, i) => (
            <LinhaRanking key={o.id} pos={i + 1} op={o} ativo={o.id === sel} onClick={() => setSel(o.id)} />
          ))}
        </div>

        {/* Ficha (com o mini-mapa no quadrante direito) */}
        <div style={{ overflowY: 'auto', minHeight: 0, padding: '18px 22px 26px' }}>
          {atual ? (
            <Ficha op={atual} pares={filtrados} onSel={setSel} onVerNoMapa={onVerNoMapa} />
          ) : (
            <Aviso titulo="Selecione uma oportunidade" corpo="Escolha um ponto no ranking à esquerda para ver o estudo." />
          )}
        </div>
      </div>
    </div>
  )
}

/* ======================= Lista ======================= */
function LinhaRanking({ pos, op, ativo, onClick }: { pos: number; op: Oportunidade; ativo: boolean; onClick: () => void }) {
  const cor = corResidual(op.residual)
  const r = rsM2(op)
  return (
    <button
      type="button"
      onClick={onClick}
      style={{
        width: '100%', textAlign: 'left', display: 'grid', gridTemplateColumns: '26px 1fr auto', gap: 11, alignItems: 'center',
        padding: '11px 18px', borderBottom: '1px solid var(--line-soft)',
        borderLeft: `2px solid ${ativo ? 'var(--ac)' : 'transparent'}`, background: ativo ? 'var(--ac-a08)' : 'transparent',
      }}
    >
      <span className="num" style={{ font: '600 12px/1 var(--f-num)', color: ativo ? 'var(--ac-text)' : 'var(--tx-rank)', textAlign: 'right' }}>{pos}</span>
      <span style={{ minWidth: 0 }}>
        <span style={{ display: 'block', font: '600 13px/1.25 var(--f-ui)', color: 'var(--tx-strong)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{op.titulo}</span>
        <span style={{ display: 'block', font: '400 11.5px/1.3 var(--f-ui)', color: 'var(--tx-muted)', marginTop: 1 }}>
          {op.bairro ? `${op.bairro} · ` : ''}{op.municipio}/{op.uf} · {op.tipo}
        </span>
        {(op.area != null || r != null) && (
          <span style={{ display: 'flex', gap: 10, marginTop: 4, font: '400 11px/1 var(--f-num)', color: 'var(--tx-sub)' }}>
            {op.area != null && <span>{num(op.area)} m²</span>}
            {r != null && <span>R$/m² {num(r, 0)}</span>}
          </span>
        )}
      </span>
      <span
        className="num"
        title={`Residual ${op.residual != null ? num(op.residual, 0) : '—'}/100`}
        style={{ width: 34, height: 34, borderRadius: 9, display: 'grid', placeItems: 'center', font: '700 13px/1 var(--f-num)', color: '#fff', background: cor, boxShadow: ativo ? '0 0 0 2px var(--ac)' : 'none' }}
      >
        {op.residual != null ? num(op.residual, 0) : '—'}
      </span>
    </button>
  )
}

/* ======================= Ficha ======================= */
function Ficha({
  op,
  pares,
  onSel,
  onVerNoMapa,
}: {
  op: Oportunidade
  pares: Oportunidade[]
  onSel: (id: string) => void
  onVerNoMapa: (uf: string, municipio: string) => void
}) {
  const r = rsM2(op)
  const ocupacao = [op.aluguel, op.iptu, op.condominio].reduce<number>((s, v) => s + (v ?? 0), 0)
  const cor = corResidual(op.residual)

  const [baixando, setBaixando] = useState(false)
  const [erroAcao, setErroAcao] = useState<string | null>(null)

  async function baixarDossie() {
    if (op.lat == null || op.lng == null) {
      setErroAcao('Este imóvel não tem coordenada para gerar o relatório.')
      return
    }
    setBaixando(true)
    setErroAcao(null)
    try {
      const { blob, filename } = await api.relatorioPontual({
        lat: op.lat,
        lng: op.lng,
        rotulo: `${op.titulo} — ${op.municipio}/${op.uf}`,
      })
      baixar(blob, filename)
    } catch (e) {
      setErroAcao(e instanceof ApiError ? e.message : 'Falha ao gerar o relatório.')
    } finally {
      setBaixando(false)
    }
  }

  const tese =
    op.residual == null
      ? 'Sem leitura de residual para este hexágono.'
      : op.residual_total != null && op.residual_total > 0
        ? `O mercado ainda comporta cerca de ${num(op.residual_total)} alunos além do já atendido aqui.`
        : 'Hexágono saturado: a oferta instalada já cobre o mercado potencial.'

  return (
    <div style={{ display: 'grid', gap: 15 }}>
      {/* Row 1: hero (esq) + MINI-MAPA (quadrante direito) */}
      <div style={{ display: 'grid', gridTemplateColumns: 'minmax(0,1fr) 320px', gap: 14, alignItems: 'stretch' }}>
        <Glass style={{ padding: 16, display: 'grid', gridTemplateColumns: 'auto 1fr', gap: 16, alignItems: 'center' }}>
          <GaugeArc valor={op.residual} cor={cor} />
          <div style={{ minWidth: 0 }}>
            <Eyebrow dot>Oportunidade selecionada</Eyebrow>
            <div className="story" style={{ marginTop: 6, fontSize: 21, lineHeight: 1.12, color: 'var(--tx-max)' }}>{op.titulo}</div>
            <div style={{ font: '400 12.5px/1.4 var(--f-ui)', color: 'var(--tx-narrative)', marginTop: 3 }}>
              {op.bairro ? `${op.bairro} · ` : ''}{op.municipio}/{op.uf} · {op.tipo} para locação
            </div>
            <div style={{ marginTop: 9, display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
              {op.faixa && <FaixaPill faixa={op.faixa} cor={cor} />}
              <span className="num" style={{ font: '500 11px/1 var(--f-num)', color: 'var(--tx-sub)', padding: '4px 8px', borderRadius: 7, background: 'var(--surf-raised)', border: '1px solid var(--line-soft)' }}>{op.hex_id}</span>
              {op.first_seen && <span style={{ font: '400 11px/1 var(--f-ui)', color: 'var(--tx-sub)' }}>desde {op.first_seen}</span>}
            </div>
            <p style={{ margin: '11px 0 0', font: '400 12.5px/1.5 var(--f-ui)', color: 'var(--tx-soft)', borderTop: '1px solid var(--line-soft)', paddingTop: 10 }}>{tese}</p>
          </div>
        </Glass>
        <MiniMapa op={op} pares={pares} onSel={onSel} />
      </div>

      {/* A OFERTA — stat tiles */}
      <section>
        <TituloBloco titulo="A oferta" nota="dado coletado (OLX)" />
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 10, marginTop: 10 }}>
          <StatTile label="Área" valor={op.area == null ? '—' : num(op.area)} unidade="m²" />
          <StatTile label="Aluguel" valor={op.aluguel == null ? '—' : brl(op.aluguel)} unidade="/mês" />
          <StatTile label="R$/m² mensal" valor={r == null ? '—' : num(r, 0)} destaque />
          <StatTile label="Condomínio" valor={op.condominio == null ? '—' : brl(op.condominio)} />
          <StatTile label="IPTU" valor={op.iptu == null ? '—' : brl(op.iptu)} unidade="/mês" />
          <StatTile label="Custo de ocupação" valor={ocupacao > 0 ? brl(ocupacao) : '—'} unidade="/mês" />
        </div>
      </section>

      {/* MERCADO (donut) + TERRITÓRIO (tiles) */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14 }}>
        <section>
          <TituloBloco titulo="Mercado que sobra" nota="capacidade, não meta" ro />
          <Glass style={{ padding: 14, marginTop: 10 }}>
            <Donut sam={op.sam} residual={op.residual_total} />
          </Glass>
        </section>
        <section>
          <TituloBloco titulo="Quem mora aqui" nota="Censo 2022, no hexágono" ro />
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10, marginTop: 10 }}>
            <StatTile label="População" valor={op.pop == null ? '—' : num(op.pop)} />
            <StatTile label="Renda per capita" valor={op.renda_pc == null ? '—' : brl(op.renda_pc)} />
            <StatTile label="Potencial (censo)" valor={op.censo_score == null ? '—' : num(op.censo_score, 0)} unidade="/100" />
            <StatTile label="Unidades Ultra" valor={op.n_ultra == null ? '—' : num(op.n_ultra)} />
          </div>
        </section>
      </div>

      {/* POSICIONAMENTO — scatter */}
      <section>
        <TituloBloco titulo="Onde este imóvel cai" nota="entre os pontos do recorte" />
        <Glass style={{ padding: 14, marginTop: 10 }}>
          <Scatter pontos={pares} sel={op.id} />
        </Glass>
      </section>

      {/* AÇÕES */}
      <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
        <Botao onClick={() => onVerNoMapa(op.uf, op.municipio)} style={{ flex: 1, minWidth: 200, justifyContent: 'center', display: 'inline-flex' }}>
          Ver no Mapa Territorial
        </Botao>
        <Botao variante="ghost" onClick={baixarDossie} disabled={baixando} style={{ flex: 1, minWidth: 200, justifyContent: 'center', display: 'inline-flex', gap: 8 }} title="Relatório Pontual Censitário do endereço (PDF)">
          {baixando ? <><Spinner /> Gerando…</> : '↓ Relatório do ponto (PDF)'}
        </Botao>
      </div>
      {erroAcao && <div style={{ font: '400 11.5px/1.4 var(--f-ui)', color: 'var(--neg)' }}>{erroAcao}</div>}

      <div style={{ display: 'flex', gap: 9, font: '400 11.5px/1.5 var(--f-ui)', color: 'var(--tx-sub)' }}>
        <span style={{ color: 'var(--ac-text)', flexShrink: 0 }}>ⓘ</span>
        <span>Camada agregada por <span className="num">hex_id</span>, sem dado pessoal. O contato do corretor vive no dossiê do coletor, atrás do Authelia (legítimo interesse B2B).</span>
      </div>
    </div>
  )
}

/* ======================= Mini-mapa (quadrante direito) ======================= */
function MiniMapa({ op, pares, onSel }: { op: Oportunidade; pares: Oportunidade[]; onSel: (id: string) => void }) {
  const [vs, setVs] = useState(() => ({ longitude: op.lng ?? -49, latitude: op.lat ?? -16, zoom: op.lat != null ? 12.5 : 3.5 }))

  // Recentra no ponto quando a seleção muda (mapa controlado, sem remontar).
  useEffect(() => {
    if (op.lat != null && op.lng != null) {
      setVs((v) => ({ ...v, longitude: op.lng as number, latitude: op.lat as number, zoom: Math.max(v.zoom, 12.5) }))
    }
  }, [op.id, op.lat, op.lng])

  const vizinhos = useMemo(
    () => pares.filter((p) => p.id !== op.id && p.lat != null && p.lng != null).slice(0, MAX_PINS),
    [pares, op.id],
  )
  const semCoord = op.lat == null || op.lng == null

  return (
    <div style={{ position: 'relative', borderRadius: 'var(--r-lg)', overflow: 'hidden', border: '1px solid var(--line)', background: 'var(--bg-lift)', minHeight: 210 }}>
      <div style={{ position: 'absolute', top: 8, left: 8, zIndex: 2, font: '600 9.5px/1 var(--f-ui)', textTransform: 'uppercase', letterSpacing: '.08em', color: 'var(--tx-label)', background: 'var(--surf-panel)', border: '1px solid var(--line-soft)', borderRadius: 7, padding: '5px 8px', backdropFilter: 'blur(10px)' }}>
        Localização
      </div>
      {semCoord ? (
        <div style={{ position: 'absolute', inset: 0, display: 'grid', placeItems: 'center', font: '400 12px/1.5 var(--f-ui)', color: 'var(--tx-muted)', textAlign: 'center', padding: 16 }}>
          Sem coordenada para este imóvel.
        </div>
      ) : (
        <Map
          longitude={vs.longitude}
          latitude={vs.latitude}
          zoom={vs.zoom}
          onMove={(e) => setVs(e.viewState)}
          mapStyle={BASEMAP}
          scrollZoom={false}
          dragRotate={false}
          attributionControl={{ compact: true }}
          reuseMaps
          style={{ position: 'absolute', inset: 0, width: '100%', height: '100%' }}
        >
          {vizinhos.map((p) => (
            <Marker key={p.id} longitude={p.lng as number} latitude={p.lat as number} anchor="center" onClick={() => onSel(p.id)}>
              <div title={p.titulo} style={{ width: 8, height: 8, borderRadius: '50%', background: corResidual(p.residual), border: '1px solid rgba(8,11,16,.7)', opacity: 0.75, cursor: 'pointer' }} />
            </Marker>
          ))}
          <Marker longitude={op.lng as number} latitude={op.lat as number} anchor="center">
            <div style={{ width: 16, height: 16, borderRadius: '50%', background: 'var(--ac)', border: '2px solid #fff', boxShadow: '0 0 0 4px var(--ac-a24), var(--sh-pop)' }} />
          </Marker>
        </Map>
      )}
    </div>
  )
}

/* ======================= Peças visuais ======================= */

/** Medidor RADIAL (semicírculo) do residual. */
function GaugeArc({ valor, cor }: { valor: number | null; cor: string }) {
  const R = 46, cx = 56, cy = 56
  const frac = valor == null ? 0 : Math.min(1, Math.max(0, valor / 100))
  const ponto = (t: number): [number, number] => {
    const ang = Math.PI * (1 - t)
    return [cx + R * Math.cos(ang), cy - R * Math.sin(ang)]
  }
  const arco = (t0: number, t1: number) => {
    const [x0, y0] = ponto(t0)
    const [x1, y1] = ponto(t1)
    return `M ${x0.toFixed(1)} ${y0.toFixed(1)} A ${R} ${R} 0 0 1 ${x1.toFixed(1)} ${y1.toFixed(1)}`
  }
  return (
    <svg width="112" height="72" viewBox="0 0 112 72" aria-label={`Residual ${valor ?? 'sem dado'} de 100`}>
      <path d={arco(0, 1)} fill="none" stroke="var(--surf-pending)" strokeWidth="10" strokeLinecap="round" />
      {valor != null && frac > 0 && <path d={arco(0, frac)} fill="none" stroke={cor} strokeWidth="10" strokeLinecap="round" />}
      <text x={cx} y={cy - 8} textAnchor="middle" style={{ font: '700 22px var(--f-num)', fill: 'var(--tx-max)' }}>{valor != null ? num(valor, 0) : '—'}</text>
      <text x={cx} y={cy + 8} textAnchor="middle" style={{ font: '400 9px var(--f-ui)', fill: 'var(--tx-sub)', letterSpacing: '.08em' }}>RESIDUAL</text>
    </svg>
  )
}

/** DONUT: já atendido × sobra. */
function Donut({ sam, residual }: { sam: number | null; residual: number | null }) {
  if (sam == null || residual == null || sam <= 0) {
    return <div style={{ font: '400 12px/1.5 var(--f-ui)', color: 'var(--tx-muted)', textAlign: 'center', padding: '18px 0' }}>Sem leitura de mercado para o hexágono.</div>
  }
  const sobra = Math.max(0, Math.min(residual, sam))
  const atendido = Math.max(0, sam - sobra)
  const pct = Math.round((sobra / sam) * 100)
  const R = 34, C = 2 * Math.PI * R
  const lenSobra = (sobra / sam) * C
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
      <svg width="92" height="92" viewBox="0 0 92 92" style={{ flexShrink: 0 }}>
        <g transform="rotate(-90 46 46)">
          <circle cx="46" cy="46" r={R} fill="none" stroke="var(--tx-rank)" strokeWidth="13" />
          <circle cx="46" cy="46" r={R} fill="none" stroke="var(--ac)" strokeWidth="13" strokeDasharray={`${lenSobra} ${C - lenSobra}`} strokeLinecap="round" />
        </g>
        <text x="46" y="43" textAnchor="middle" style={{ font: '700 20px var(--f-num)', fill: 'var(--tx-max)' }}>{pct}<tspan style={{ fontSize: 11, fill: 'var(--tx-sub)' }}>%</tspan></text>
        <text x="46" y="58" textAnchor="middle" style={{ font: '400 8.5px var(--f-ui)', fill: 'var(--tx-sub)' }}>sobra</text>
      </svg>
      <div style={{ display: 'grid', gap: 8, minWidth: 0 }}>
        <LegDonut cor="var(--ac)" rotulo="Sobra (residual)" valor={`${num(sobra)}`} forte />
        <LegDonut cor="var(--tx-rank)" rotulo="Já atendido" valor={`${num(atendido)}`} />
        <div style={{ font: '400 10.5px/1.4 var(--f-ui)', color: 'var(--tx-sub)' }}>de {num(sam)} alunos do mercado potencial (SAM)</div>
      </div>
    </div>
  )
}
function LegDonut({ cor, rotulo, valor, forte }: { cor: string; rotulo: string; valor: string; forte?: boolean }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 7 }}>
      <span style={{ width: 9, height: 9, borderRadius: 3, background: cor, flexShrink: 0 }} />
      <span style={{ font: '400 11px/1.2 var(--f-ui)', color: 'var(--tx-sub)' }}>{rotulo}</span>
      <span className="num" style={{ marginLeft: 'auto', font: `${forte ? 700 : 500} 12px/1.2 var(--f-num)`, color: forte ? 'var(--tx-max)' : 'var(--tx-soft)' }}>{valor}</span>
    </div>
  )
}

/** SCATTER de posicionamento: R$/m² (x) × residual (y). Aspecto fixo, sem distorcer. */
function Scatter({ pontos, sel }: { pontos: Oportunidade[]; sel: string }) {
  const W = 360, H = 190, padL = 34, padR = 12, padT = 12, padB = 30
  const dados = pontos
    .map((o) => ({ id: o.id, x: rsM2(o), y: o.residual }))
    .filter((d): d is { id: string; x: number; y: number } => d.x != null && d.y != null)
  if (dados.length < 3) {
    return <div style={{ font: '400 12px/1.5 var(--f-ui)', color: 'var(--tx-muted)', textAlign: 'center', padding: '14px 0' }}>Poucos pontos com preço e residual para comparar neste recorte.</div>
  }
  const xsOrd = dados.map((d) => d.x).sort((a, b) => a - b)
  const xMax = xsOrd[Math.floor(xsOrd.length * 0.95)] ?? xsOrd[xsOrd.length - 1] ?? 1
  const xMed = xsOrd[Math.floor(xsOrd.length / 2)] ?? 0
  const px = (x: number) => padL + (Math.min(x, xMax) / xMax) * (W - padL - padR)
  const py = (y: number) => padT + (1 - y / 100) * (H - padT - padB)
  const selD = dados.find((d) => d.id === sel)
  const eixoX = [0, Math.round(xMax / 2), Math.round(xMax)]
  const eixoY = [0, 50, 100]
  return (
    <div>
      <svg viewBox={`0 0 ${W} ${H}`} width="100%" style={{ display: 'block', height: 'auto', maxHeight: 220 }} preserveAspectRatio="xMidYMid meet">
        {/* quadrante-alvo: caro barato (x baixo) + residual alto (y alto) */}
        <rect x={px(0)} y={py(100)} width={px(xMed) - px(0)} height={py(50) - py(100)} fill="var(--ac-a08)" />
        {/* eixos */}
        <line x1={padL} y1={padT} x2={padL} y2={H - padB} stroke="var(--line-mid)" strokeWidth="1" />
        <line x1={padL} y1={H - padB} x2={W - padR} y2={H - padB} stroke="var(--line-mid)" strokeWidth="1" />
        {/* guias de mediana/meio */}
        <line x1={px(xMed)} y1={padT} x2={px(xMed)} y2={H - padB} stroke="var(--line-soft)" strokeWidth="1" strokeDasharray="3 3" />
        <line x1={padL} y1={py(50)} x2={W - padR} y2={py(50)} stroke="var(--line-soft)" strokeWidth="1" strokeDasharray="3 3" />
        {/* ticks Y */}
        {eixoY.map((v) => (
          <text key={`y${v}`} x={padL - 6} y={py(v) + 3} textAnchor="end" style={{ font: '400 9px var(--f-num)', fill: 'var(--tx-sub)' }}>{v}</text>
        ))}
        {/* ticks X */}
        {eixoX.map((v, i) => (
          <text key={`x${v}-${i}`} x={px(v)} y={H - padB + 13} textAnchor={i === 0 ? 'start' : i === eixoX.length - 1 ? 'end' : 'middle'} style={{ font: '400 9px var(--f-num)', fill: 'var(--tx-sub)' }}>{v}</text>
        ))}
        {/* pontos */}
        {dados.map((d) => (d.id === sel ? null : <circle key={d.id} cx={px(d.x)} cy={py(d.y)} r={3} fill={corResidual(d.y)} opacity={0.45} />))}
        {selD && (
          <>
            <circle cx={px(selD.x)} cy={py(selD.y)} r={8} fill="none" stroke="var(--ac)" strokeWidth="2" />
            <circle cx={px(selD.x)} cy={py(selD.y)} r={4.5} fill={corResidual(selD.y)} stroke="var(--bg-base)" strokeWidth="1.2" />
          </>
        )}
        {/* rótulos de eixo */}
        <text x={(padL + W - padR) / 2} y={H - 4} textAnchor="middle" style={{ font: '400 9.5px var(--f-ui)', fill: 'var(--tx-sub)' }}>aluguel R$/m² →</text>
        <text x={12} y={(padT + H - padB) / 2} textAnchor="middle" transform={`rotate(-90 12 ${(padT + H - padB) / 2})`} style={{ font: '400 9.5px var(--f-ui)', fill: 'var(--tx-sub)' }}>residual →</text>
      </svg>
      <p style={{ margin: '8px 0 0', font: '400 11px/1.5 var(--f-ui)', color: 'var(--tx-narrative)' }}>
        O alvo é o quadrante <b style={{ color: 'var(--ac-text)' }}>superior esquerdo</b> (turquesa): aluguel barato por m² e residual alto. O anel turquesa marca este imóvel.
      </p>
    </div>
  )
}

/* ======================= Auxiliares ======================= */
function StatTile({ label, valor, unidade, destaque }: { label: string; valor: string; unidade?: string; destaque?: boolean }) {
  return (
    <div style={{ background: 'var(--surf-raised)', border: '1px solid var(--line-soft)', borderRadius: 'var(--r-md)', padding: '9px 11px' }}>
      <div style={{ font: '500 10.5px/1.2 var(--f-ui)', color: 'var(--tx-label)' }}>{label}</div>
      <div className="num" style={{ font: '700 16px/1.1 var(--f-num)', color: destaque ? 'var(--ac-text)' : 'var(--tx-strong)', marginTop: 4 }}>
        {valor}
        {unidade && <span style={{ font: '400 10px var(--f-num)', color: 'var(--tx-sub)' }}> {unidade}</span>}
      </div>
    </div>
  )
}
function TituloBloco({ titulo, nota, ro }: { titulo: string; nota?: string; ro?: boolean }) {
  return (
    <div style={{ display: 'flex', alignItems: 'baseline', gap: 8, flexWrap: 'wrap' }}>
      <h3 style={{ margin: 0, font: '600 13px/1.2 var(--f-ui)', color: 'var(--tx-max)' }}>{titulo}</h3>
      {nota && <span style={{ font: '400 11px/1.3 var(--f-ui)', color: 'var(--tx-sub)' }}>{nota}</span>}
      {ro && <span style={{ marginLeft: 'auto', font: '400 10px/1 var(--f-ui)', color: 'var(--ac-text)', background: 'var(--ac-a10)', border: '1px solid var(--ac-a24)', padding: '3px 8px', borderRadius: 999 }}>M1 · read-only</span>}
    </div>
  )
}
function FaixaPill({ faixa, cor }: { faixa: string; cor: string }) {
  return (
    <span style={{ font: '700 10px/1 var(--f-ui)', textTransform: 'uppercase', letterSpacing: '.05em', padding: '4px 9px', borderRadius: 999, color: cor, background: `${cor}22`, border: `1px solid ${cor}55` }}>
      {labelFaixa(faixa)}
    </span>
  )
}
