import { useEffect, useMemo, useState } from 'react'
import { Map, Marker } from 'react-map-gl/maplibre'

import Select from '../components/Select'
import { Aviso, BarraSegmentada, Botao, Eyebrow, Glass, Spinner } from '../components/primitives'
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
 * DESENHO: filtros por DROPDOWN (escalam p/ 27 UFs); leitura variada (medidor radial,
 * barra de COMPOSICAO por tipo, donut, scatter de posicionamento); paleta categorica
 * por TIPO (laranja/azul/aqua, validada no dataviz) alem da rampa de residual; MINI-MAPA
 * ao lado do scatter, com pan/zoom; dossie real do coletor (fallback: Relatorio Pontual).
 */

const BASEMAP = 'https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json'

const FAIXA_LABEL: Record<string, string> = {
  prioridade_maxima: 'Prioridade máxima', alta: 'Alta', media: 'Média', baixa: 'Baixa', minima: 'Mínima',
}
const labelFaixa = (v: string | null): string | null =>
  v == null ? null : (FAIXA_LABEL[v] ?? v.charAt(0).toUpperCase() + v.slice(1))

/** Paleta CATEGORICA por tipo (validada no dataviz, all-pairs, superficie escura). */
const COR_TIPO: Record<string, string> = { galpao: '#d95926', comercial: '#3987e5', loja: '#3987e5', terreno: '#199e70' }
const corTipo = (t: string): string => COR_TIPO[t] ?? '#8b97a5'
const LABEL_TIPO: Record<string, string> = { galpao: 'Galpão', comercial: 'Comercial', loja: 'Loja', terreno: 'Terreno' }
const labelTipo = (t: string): string => LABEL_TIPO[t] ?? (t.charAt(0).toUpperCase() + t.slice(1))
/** Agrupamento para a barra de composicao (loja funde em comercial — so' 108 no total). */
const GRUPOS = [
  { chave: 'galpao', rotulo: 'Galpão', cor: '#d95926', tipos: ['galpao'] },
  { chave: 'comercial', rotulo: 'Comercial/Loja', cor: '#3987e5', tipos: ['comercial', 'loja'] },
  { chave: 'terreno', rotulo: 'Terreno', cor: '#199e70', tipos: ['terreno'] },
]

/** Rampa de RESIDUAL (score) — canonica do sistema. */
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
      <header style={{ display: 'flex', alignItems: 'flex-end', justifyContent: 'space-between', gap: 20, padding: '16px 26px 12px' }}>
        <div>
          <Eyebrow dot>Camada de oferta &middot; READ-ONLY sobre o M1</Eyebrow>
          <h1 className="story" style={{ margin: '6px 0 0', fontSize: 30, lineHeight: 1.04, color: 'var(--tx-max)' }}>
            Oportunidades Imobiliárias
          </h1>
          <div style={{ marginTop: 3, font: '400 12.5px/1.4 var(--f-ui)', color: 'var(--tx-narrative)' }}>
            {total ? (
              <><b className="num" style={{ color: 'var(--ac-text)' }}>{num(total)}</b> imóveis de locação coletados e cruzados com o território do M1.</>
            ) : ('Imóveis de locação coletados e cruzados com o território do M1.')}
          </div>
        </div>
        <button type="button" onClick={onInicio} style={{ font: '600 12px/1 var(--f-ui)', color: 'var(--tx-muted)', border: '1px solid var(--line-mid)', borderRadius: 'var(--r-md)', padding: '8px 12px', background: 'var(--surf-raised)' }}>← Início</button>
      </header>

      {/* Filtros */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap', padding: '10px 26px', borderTop: '1px solid var(--line-soft)', borderBottom: '1px solid var(--line-soft)' }}>
        <Select label="Estado" value={ufSel} onChange={setUfSel} placeholder="Todos os estados" maxWidth={190}
          options={[{ value: '', label: 'Todos os estados' }, ...ufs.map((u) => ({ value: u, label: u }))]} />
        <Select label="Tipo de imóvel" value={tipoSel} onChange={setTipoSel} placeholder="Todos os tipos" maxWidth={190}
          options={[{ value: '', label: 'Todos os tipos' }, ...tipos.map((t) => ({ value: t, label: labelTipo(t) }))]} />
        <Select label="Ordenar por" value={ordem} onChange={(v) => setOrdem(v as Ordem)} maxWidth={190} buscavel={false} options={ORDENS} />
        <input value={busca} onChange={(e) => setBusca(e.target.value)} placeholder="Buscar bairro, cidade, título…" aria-label="Buscar oportunidade"
          style={{ flex: 1, minWidth: 180, maxWidth: 320, height: 34, padding: '0 12px', background: 'var(--surf-input)', border: '1px solid var(--line-mid)', borderRadius: 'var(--r-md)', color: 'var(--tx-strong)', font: '500 13px/1 var(--f-ui)' }} />
        <span style={{ marginLeft: 'auto', font: '500 12px/1 var(--f-ui)', color: 'var(--tx-muted)' }}>
          <b className="num" style={{ color: 'var(--tx-soft)' }}>{num(filtrados.length)}</b> no recorte
        </span>
      </div>

      {/* Corpo: lista | ficha */}
      <div style={{ flex: 1, display: 'grid', gridTemplateColumns: 'minmax(300px, 32%) 1fr', minHeight: 0 }}>
        <div style={{ borderRight: '1px solid var(--line-soft)', overflowY: 'auto', minHeight: 0 }}>
          {itens == null && !erro && (
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, padding: 24, color: 'var(--tx-muted)' }}><Spinner /> Carregando oportunidades…</div>
          )}
          {erro && <Aviso titulo="Não deu para carregar" corpo={`${erro} — confira o backend na porta 8899 e o data/oportunidades/viaveis.parquet.`} />}
          {itens != null && filtrados.length === 0 && (
            <Aviso titulo="Nada no recorte" corpo="Nenhuma oportunidade bate com os filtros. Amplie o estado, o tipo ou limpe a busca." />
          )}
          {itens != null && filtrados.map((o, i) => (
            <LinhaRanking key={o.id} pos={i + 1} op={o} ativo={o.id === sel} onClick={() => setSel(o.id)} />
          ))}
        </div>

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
    <button type="button" onClick={onClick}
      style={{ width: '100%', textAlign: 'left', display: 'grid', gridTemplateColumns: '26px 1fr auto', gap: 11, alignItems: 'center', padding: '11px 18px', borderBottom: '1px solid var(--line-soft)', borderLeft: `2px solid ${ativo ? 'var(--ac)' : 'transparent'}`, background: ativo ? 'var(--ac-a08)' : 'transparent' }}>
      <span className="num" style={{ font: '600 12px/1 var(--f-num)', color: ativo ? 'var(--ac-text)' : 'var(--tx-rank)', textAlign: 'right' }}>{pos}</span>
      <span style={{ minWidth: 0 }}>
        <span style={{ display: 'block', font: '600 13px/1.25 var(--f-ui)', color: 'var(--tx-strong)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{op.titulo}</span>
        <span style={{ display: 'block', font: '400 11.5px/1.3 var(--f-ui)', color: 'var(--tx-muted)', marginTop: 1 }}>{op.bairro ? `${op.bairro} · ` : ''}{op.municipio}/{op.uf}</span>
        <span style={{ display: 'flex', gap: 8, marginTop: 5, alignItems: 'center' }}>
          <span style={{ display: 'inline-flex', alignItems: 'center', gap: 5, font: '400 11px/1 var(--f-ui)', color: 'var(--tx-sub)' }}>
            <span style={{ width: 7, height: 7, borderRadius: 2, background: corTipo(op.tipo) }} />{labelTipo(op.tipo)}
          </span>
          {op.area != null && <span className="num" style={{ font: '400 11px/1 var(--f-num)', color: 'var(--tx-sub)' }}>{num(op.area)} m²</span>}
          {r != null && <span className="num" style={{ font: '400 11px/1 var(--f-num)', color: 'var(--tx-sub)' }}>R$/m² {num(r, 0)}</span>}
        </span>
      </span>
      <span className="num" title={`Residual ${op.residual != null ? num(op.residual, 0) : '—'}/100`}
        style={{ width: 34, height: 34, borderRadius: 9, display: 'grid', placeItems: 'center', font: '700 13px/1 var(--f-num)', color: '#fff', background: cor, boxShadow: ativo ? '0 0 0 2px var(--ac)' : 'none' }}>
        {op.residual != null ? num(op.residual, 0) : '—'}
      </span>
    </button>
  )
}

/* ======================= Ficha ======================= */
function Ficha({ op, pares, onSel, onVerNoMapa }: { op: Oportunidade; pares: Oportunidade[]; onSel: (id: string) => void; onVerNoMapa: (uf: string, municipio: string) => void }) {
  const r = rsM2(op)
  const ocupacao = [op.aluguel, op.iptu, op.condominio].reduce<number>((s, v) => s + (v ?? 0), 0)
  const cor = corResidual(op.residual)
  const [baixando, setBaixando] = useState(false)
  const [erroAcao, setErroAcao] = useState<string | null>(null)

  async function baixarDossie() {
    setBaixando(true)
    setErroAcao(null)
    try {
      // Prefere o dossiê real do coletor; se não houver, cai no Relatório Pontual do ponto.
      if (op.tem_dossie) {
        const { blob, filename } = await api.dossie(op.id)
        baixar(blob, filename)
      } else if (op.lat != null && op.lng != null) {
        const { blob, filename } = await api.relatorioPontual({ lat: op.lat, lng: op.lng, rotulo: `${op.titulo} — ${op.municipio}/${op.uf}` })
        baixar(blob, filename)
      } else {
        setErroAcao('Sem dossiê e sem coordenada para gerar o relatório do ponto.')
      }
    } catch (e) {
      setErroAcao(e instanceof ApiError ? e.message : 'Falha ao gerar o documento.')
    } finally {
      setBaixando(false)
    }
  }

  const tese =
    op.residual == null ? 'Sem leitura de residual para este hexágono.'
      : op.residual_total != null && op.residual_total > 0
        ? `O mercado ainda comporta cerca de ${num(op.residual_total)} alunos além do já atendido aqui.`
        : 'Hexágono saturado: a oferta instalada já cobre o mercado potencial.'

  return (
    <div style={{ display: 'grid', gap: 15 }}>
      {/* Row 1: hero + composição do recorte */}
      <div style={{ display: 'grid', gridTemplateColumns: 'minmax(0,1.35fr) minmax(0,1fr)', gap: 14, alignItems: 'stretch' }}>
        <Glass style={{ padding: 16, display: 'grid', gridTemplateColumns: 'auto 1fr', gap: 16, alignItems: 'center' }}>
          <GaugeArc valor={op.residual} cor={cor} />
          <div style={{ minWidth: 0 }}>
            <Eyebrow dot>Oportunidade selecionada</Eyebrow>
            <div className="story" style={{ marginTop: 6, fontSize: 21, lineHeight: 1.12, color: 'var(--tx-max)' }}>{op.titulo}</div>
            <div style={{ font: '400 12.5px/1.4 var(--f-ui)', color: 'var(--tx-narrative)', marginTop: 3 }}>{op.bairro ? `${op.bairro} · ` : ''}{op.municipio}/{op.uf} · {labelTipo(op.tipo)} para locação</div>
            <div style={{ marginTop: 9, display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
              {op.faixa && <FaixaPill faixa={op.faixa} cor={cor} />}
              <span className="num" style={{ font: '500 11px/1 var(--f-num)', color: 'var(--tx-sub)', padding: '4px 8px', borderRadius: 7, background: 'var(--surf-raised)', border: '1px solid var(--line-soft)' }}>{op.hex_id}</span>
              {op.first_seen && <span style={{ font: '400 11px/1 var(--f-ui)', color: 'var(--tx-sub)' }}>desde {op.first_seen}</span>}
            </div>
            <p style={{ margin: '11px 0 0', font: '400 12.5px/1.5 var(--f-ui)', color: 'var(--tx-soft)', borderTop: '1px solid var(--line-soft)', paddingTop: 10 }}>{tese}</p>
          </div>
        </Glass>
        <Composicao pontos={pares} />
      </div>

      {/* A oferta */}
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

      {/* Mercado (donut) + território (tiles) */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14 }}>
        <section>
          <TituloBloco titulo="Mercado que sobra" nota="capacidade, não meta" ro />
          <Glass style={{ padding: 14, marginTop: 10 }}><Donut sam={op.sam} residual={op.residual_total} /></Glass>
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

      {/* Scatter + Mini-mapa lado a lado */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14 }}>
        <section>
          <TituloBloco titulo="Onde este imóvel cai" nota="preço × residual, por tipo" />
          <Glass style={{ padding: 14, marginTop: 10 }}><Scatter pontos={pares} sel={op.id} /></Glass>
        </section>
        <section>
          <TituloBloco titulo="Localização" nota="arraste e dê zoom" />
          <div style={{ marginTop: 10 }}><MiniMapa op={op} pares={pares} onSel={onSel} /></div>
        </section>
      </div>

      {/* Ações */}
      <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
        <Botao onClick={() => onVerNoMapa(op.uf, op.municipio)} style={{ flex: 1, minWidth: 200, justifyContent: 'center', display: 'inline-flex' }}>Ver no Mapa Territorial</Botao>
        <Botao variante="ghost" onClick={baixarDossie} disabled={baixando} style={{ flex: 1, minWidth: 200, justifyContent: 'center', display: 'inline-flex', gap: 8 }}
          title={op.tem_dossie ? 'Dossiê PDF do coletor (oferta + território)' : 'Sem dossiê pronto — gera o Relatório Pontual do endereço'}>
          {baixando ? <><Spinner /> Gerando…</> : op.tem_dossie ? '↓ Baixar dossiê (PDF)' : '↓ Relatório do ponto (PDF)'}
        </Botao>
      </div>
      {erroAcao && <div style={{ font: '400 11.5px/1.4 var(--f-ui)', color: 'var(--neg)' }}>{erroAcao}</div>}

      <div style={{ display: 'flex', gap: 9, font: '400 11.5px/1.5 var(--f-ui)', color: 'var(--tx-sub)' }}>
        <span style={{ color: 'var(--ac-text)', flexShrink: 0 }}>ⓘ</span>
        <span>Camada agregada por <span className="num">hex_id</span>, sem dado pessoal na tela. O contato do corretor vive no dossiê do coletor, servido sob acesso restrito.</span>
      </div>
    </div>
  )
}

/* ======================= Composição do recorte (barra por tipo) ======================= */
function Composicao({ pontos }: { pontos: Oportunidade[] }) {
  const partes = GRUPOS.map((g) => ({
    chave: g.chave, cor: g.cor, rotulo: g.rotulo,
    valor: pontos.filter((o) => g.tipos.includes(o.tipo)).length,
  })).filter((p) => p.valor > 0)
  const totalN = partes.reduce((s, p) => s + p.valor, 0) || 1
  return (
    <Glass style={{ padding: 16, display: 'flex', flexDirection: 'column', gap: 12, justifyContent: 'center' }}>
      <div style={{ font: '600 12px/1 var(--f-ui)', textTransform: 'uppercase', letterSpacing: '.08em', color: 'var(--tx-label)' }}>Composição do recorte</div>
      <BarraSegmentada altura={14} partes={partes} />
      <div style={{ display: 'grid', gap: 7 }}>
        {partes.map((p) => (
          <div key={p.chave} style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <span style={{ width: 10, height: 10, borderRadius: 3, background: p.cor, flexShrink: 0 }} />
            <span style={{ font: '400 12px/1.2 var(--f-ui)', color: 'var(--tx-soft)' }}>{p.rotulo}</span>
            <span className="num" style={{ marginLeft: 'auto', font: '600 12px/1.2 var(--f-num)', color: 'var(--tx-strong)' }}>{num(p.valor)}</span>
            <span className="num" style={{ font: '400 11px/1.2 var(--f-num)', color: 'var(--tx-sub)', width: 42, textAlign: 'right' }}>{Math.round((p.valor / totalN) * 100)}%</span>
          </div>
        ))}
      </div>
    </Glass>
  )
}

/* ======================= Peças visuais ======================= */
function GaugeArc({ valor, cor }: { valor: number | null; cor: string }) {
  const R = 46, cx = 56, cy = 56
  const frac = valor == null ? 0 : Math.min(1, Math.max(0, valor / 100))
  const ponto = (t: number): [number, number] => { const a = Math.PI * (1 - t); return [cx + R * Math.cos(a), cy - R * Math.sin(a)] }
  const arco = (t0: number, t1: number) => { const [x0, y0] = ponto(t0); const [x1, y1] = ponto(t1); return `M ${x0.toFixed(1)} ${y0.toFixed(1)} A ${R} ${R} 0 0 1 ${x1.toFixed(1)} ${y1.toFixed(1)}` }
  return (
    <svg width="112" height="72" viewBox="0 0 112 72" aria-label={`Residual ${valor ?? 'sem dado'} de 100`}>
      <path d={arco(0, 1)} fill="none" stroke="var(--surf-pending)" strokeWidth="10" strokeLinecap="round" />
      {valor != null && frac > 0 && <path d={arco(0, frac)} fill="none" stroke={cor} strokeWidth="10" strokeLinecap="round" />}
      <text x={cx} y={cy - 8} textAnchor="middle" style={{ font: '700 22px var(--f-num)', fill: 'var(--tx-max)' }}>{valor != null ? num(valor, 0) : '—'}</text>
      <text x={cx} y={cy + 8} textAnchor="middle" style={{ font: '400 9px var(--f-ui)', fill: 'var(--tx-sub)', letterSpacing: '.08em' }}>RESIDUAL</text>
    </svg>
  )
}

function Donut({ sam, residual }: { sam: number | null; residual: number | null }) {
  if (sam == null || residual == null || sam <= 0) {
    return <div style={{ font: '400 12px/1.5 var(--f-ui)', color: 'var(--tx-muted)', textAlign: 'center', padding: '18px 0' }}>Sem leitura de mercado para o hexágono.</div>
  }
  const sobra = Math.max(0, Math.min(residual, sam)), atendido = Math.max(0, sam - sobra)
  const pct = Math.round((sobra / sam) * 100), R = 34, C = 2 * Math.PI * R
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
        <LegLinha cor="var(--ac)" rotulo="Sobra (residual)" valor={num(sobra)} forte />
        <LegLinha cor="var(--tx-rank)" rotulo="Já atendido" valor={num(atendido)} />
        <div style={{ font: '400 10.5px/1.4 var(--f-ui)', color: 'var(--tx-sub)' }}>de {num(sam)} alunos do mercado potencial (SAM)</div>
      </div>
    </div>
  )
}
function LegLinha({ cor, rotulo, valor, forte }: { cor: string; rotulo: string; valor: string; forte?: boolean }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 7 }}>
      <span style={{ width: 9, height: 9, borderRadius: 3, background: cor, flexShrink: 0 }} />
      <span style={{ font: '400 11px/1.2 var(--f-ui)', color: 'var(--tx-sub)' }}>{rotulo}</span>
      <span className="num" style={{ marginLeft: 'auto', font: `${forte ? 700 : 500} 12px/1.2 var(--f-num)`, color: forte ? 'var(--tx-max)' : 'var(--tx-soft)' }}>{valor}</span>
    </div>
  )
}

/** SCATTER: R$/m² (x) × residual (y). Dots coloridos por TIPO. Aspecto fixo. */
function Scatter({ pontos, sel }: { pontos: Oportunidade[]; sel: string }) {
  const W = 360, H = 190, padL = 34, padR = 12, padT = 12, padB = 30
  const dados = pontos
    .map((o) => ({ id: o.id, x: rsM2(o), y: o.residual, tipo: o.tipo }))
    .filter((d): d is { id: string; x: number; y: number; tipo: string } => d.x != null && d.y != null)
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
  const gruposPresentes = GRUPOS.filter((g) => dados.some((d) => g.tipos.includes(d.tipo)))
  return (
    <div>
      <svg viewBox={`0 0 ${W} ${H}`} width="100%" style={{ display: 'block', height: 'auto', maxHeight: 210 }} preserveAspectRatio="xMidYMid meet">
        <rect x={px(0)} y={py(100)} width={px(xMed) - px(0)} height={py(50) - py(100)} fill="var(--ac-a08)" />
        <line x1={padL} y1={padT} x2={padL} y2={H - padB} stroke="var(--line-mid)" strokeWidth="1" />
        <line x1={padL} y1={H - padB} x2={W - padR} y2={H - padB} stroke="var(--line-mid)" strokeWidth="1" />
        <line x1={px(xMed)} y1={padT} x2={px(xMed)} y2={H - padB} stroke="var(--line-soft)" strokeWidth="1" strokeDasharray="3 3" />
        <line x1={padL} y1={py(50)} x2={W - padR} y2={py(50)} stroke="var(--line-soft)" strokeWidth="1" strokeDasharray="3 3" />
        {eixoY.map((v) => <text key={`y${v}`} x={padL - 6} y={py(v) + 3} textAnchor="end" style={{ font: '400 9px var(--f-num)', fill: 'var(--tx-sub)' }}>{v}</text>)}
        {eixoX.map((v, i) => <text key={`x${v}-${i}`} x={px(v)} y={H - padB + 13} textAnchor={i === 0 ? 'start' : i === eixoX.length - 1 ? 'end' : 'middle'} style={{ font: '400 9px var(--f-num)', fill: 'var(--tx-sub)' }}>{v}</text>)}
        {dados.map((d) => (d.id === sel ? null : <circle key={d.id} cx={px(d.x)} cy={py(d.y)} r={3} fill={corTipo(d.tipo)} opacity={0.5} />))}
        {selD && (<>
          <circle cx={px(selD.x)} cy={py(selD.y)} r={8} fill="none" stroke="var(--ac)" strokeWidth="2" />
          <circle cx={px(selD.x)} cy={py(selD.y)} r={4.5} fill={corTipo(selD.tipo)} stroke="var(--bg-base)" strokeWidth="1.2" />
        </>)}
        <text x={(padL + W - padR) / 2} y={H - 4} textAnchor="middle" style={{ font: '400 9.5px var(--f-ui)', fill: 'var(--tx-sub)' }}>aluguel R$/m² →</text>
        <text x={12} y={(padT + H - padB) / 2} textAnchor="middle" transform={`rotate(-90 12 ${(padT + H - padB) / 2})`} style={{ font: '400 9.5px var(--f-ui)', fill: 'var(--tx-sub)' }}>residual →</text>
      </svg>
      <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap', marginTop: 6 }}>
        {gruposPresentes.map((g) => (
          <span key={g.chave} style={{ display: 'inline-flex', alignItems: 'center', gap: 5, font: '400 10.5px/1 var(--f-ui)', color: 'var(--tx-sub)' }}>
            <span style={{ width: 8, height: 8, borderRadius: '50%', background: g.cor }} />{g.rotulo}
          </span>
        ))}
      </div>
      <p style={{ margin: '7px 0 0', font: '400 10.5px/1.5 var(--f-ui)', color: 'var(--tx-narrative)' }}>
        Alvo: quadrante <b style={{ color: 'var(--ac-text)' }}>superior esquerdo</b> (barato por m², residual alto). O anel turquesa marca este imóvel.
      </p>
    </div>
  )
}

/* ======================= Mini-mapa (ao lado do scatter, com pan/zoom) ======================= */
function MiniMapa({ op, pares, onSel }: { op: Oportunidade; pares: Oportunidade[]; onSel: (id: string) => void }) {
  const [vs, setVs] = useState(() => ({ longitude: op.lng ?? -49, latitude: op.lat ?? -16, zoom: op.lat != null ? 13 : 3.5 }))
  const [zoomArmado, setZoomArmado] = useState(false)

  useEffect(() => {
    if (op.lat != null && op.lng != null) setVs((v) => ({ ...v, longitude: op.lng as number, latitude: op.lat as number, zoom: Math.max(v.zoom, 13) }))
  }, [op.id, op.lat, op.lng])

  const vizinhos = useMemo(() => pares.filter((p) => p.id !== op.id && p.lat != null && p.lng != null).slice(0, MAX_PINS), [pares, op.id])
  const semCoord = op.lat == null || op.lng == null
  const ajustarZoom = (d: number) => setVs((v) => ({ ...v, zoom: Math.min(18, Math.max(3, v.zoom + d)) }))

  return (
    <div onPointerDown={() => setZoomArmado(true)} onMouseLeave={() => setZoomArmado(false)}
      style={{ position: 'relative', borderRadius: 'var(--r-lg)', overflow: 'hidden', border: '1px solid var(--line)', background: 'var(--bg-lift)', height: 236 }}>
      {semCoord ? (
        <div style={{ position: 'absolute', inset: 0, display: 'grid', placeItems: 'center', font: '400 12px/1.5 var(--f-ui)', color: 'var(--tx-muted)', textAlign: 'center', padding: 16 }}>Sem coordenada para este imóvel.</div>
      ) : (
        <>
          <Map longitude={vs.longitude} latitude={vs.latitude} zoom={vs.zoom} onMove={(e) => setVs(e.viewState)}
            mapStyle={BASEMAP} scrollZoom={zoomArmado} dragRotate={false} attributionControl={{ compact: true }} reuseMaps
            style={{ position: 'absolute', inset: 0, width: '100%', height: '100%' }}>
            {vizinhos.map((p) => (
              <Marker key={p.id} longitude={p.lng as number} latitude={p.lat as number} anchor="center" onClick={() => onSel(p.id)}>
                <div title={`${p.titulo} · ${labelTipo(p.tipo)}`} style={{ width: 9, height: 9, borderRadius: '50%', background: corTipo(p.tipo), border: '1px solid rgba(8,11,16,.7)', opacity: 0.85, cursor: 'pointer' }} />
              </Marker>
            ))}
            <Marker longitude={op.lng as number} latitude={op.lat as number} anchor="center">
              <div style={{ width: 16, height: 16, borderRadius: '50%', background: 'var(--ac)', border: '2px solid #fff', boxShadow: '0 0 0 4px var(--ac-a24), var(--sh-pop)' }} />
            </Marker>
          </Map>
          {/* controles de zoom */}
          <div style={{ position: 'absolute', right: 8, top: 8, display: 'flex', flexDirection: 'column', gap: 4, zIndex: 3 }}>
            <BotaoZoom rotulo="Aproximar" onClick={() => ajustarZoom(1)}>+</BotaoZoom>
            <BotaoZoom rotulo="Afastar" onClick={() => ajustarZoom(-1)}>−</BotaoZoom>
          </div>
          {!zoomArmado && (
            <div style={{ position: 'absolute', left: 8, top: 8, zIndex: 3, font: '500 9.5px/1 var(--f-ui)', color: 'var(--tx-muted)', background: 'var(--surf-panel)', border: '1px solid var(--line-soft)', borderRadius: 6, padding: '4px 7px', backdropFilter: 'blur(8px)', pointerEvents: 'none' }}>
              clique para a roda dar zoom · arraste para mover
            </div>
          )}
        </>
      )}
    </div>
  )
}
function BotaoZoom({ children, rotulo, onClick }: { children: React.ReactNode; rotulo: string; onClick: () => void }) {
  return (
    <button type="button" title={rotulo} aria-label={rotulo} onClick={onClick}
      style={{ width: 26, height: 26, display: 'grid', placeItems: 'center', borderRadius: 'var(--r-sm)', border: '1px solid var(--line-soft)', background: 'var(--surf-panel)', backdropFilter: 'blur(10px)', color: 'var(--tx-soft)', font: '600 15px/1 var(--f-ui)', cursor: 'pointer' }}>{children}</button>
  )
}

/* ======================= Auxiliares ======================= */
function StatTile({ label, valor, unidade, destaque }: { label: string; valor: string; unidade?: string; destaque?: boolean }) {
  return (
    <div style={{ background: 'var(--surf-raised)', border: '1px solid var(--line-soft)', borderRadius: 'var(--r-md)', padding: '9px 11px' }}>
      <div style={{ font: '500 10.5px/1.2 var(--f-ui)', color: 'var(--tx-label)' }}>{label}</div>
      <div className="num" style={{ font: '700 16px/1.1 var(--f-num)', color: destaque ? 'var(--ac-text)' : 'var(--tx-strong)', marginTop: 4 }}>
        {valor}{unidade && <span style={{ font: '400 10px var(--f-num)', color: 'var(--tx-sub)' }}> {unidade}</span>}
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
    <span style={{ font: '700 10px/1 var(--f-ui)', textTransform: 'uppercase', letterSpacing: '.05em', padding: '4px 9px', borderRadius: 999, color: cor, background: `${cor}22`, border: `1px solid ${cor}55` }}>{labelFaixa(faixa)}</span>
  )
}
