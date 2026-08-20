import { useEffect, useMemo, useState } from 'react'

import { FilaApoio, MedidorScore, NumeroApoio, BarraMercado } from '../components/LeiturasVisuais'
import { Aviso, Chip, Eyebrow, Glass, Kpi, Spinner } from '../components/primitives'
import { api, ApiError } from '../lib/api'
import { FAIXAS_DEMANDA, FAIXAS_POTENCIAL } from '../lib/faixas'
import { alunos, brl, num } from '../lib/format'
import { faixaDoValor } from '../lib/medidor'
import type { Oportunidade } from '../lib/types'

/** Label de EXIBIÇÃO da faixa M1 (o valor bruto vem sem acento — regra do CLAUDE.md:
 *  nunca acentuar o identificador; acentuar só na camada de label). */
const FAIXA_LABEL: Record<string, string> = {
  prioridade_maxima: 'Prioridade máxima',
  alta: 'Alta',
  media: 'Média',
  baixa: 'Baixa',
  minima: 'Mínima',
}
const labelFaixa = (v: string | null): string | null =>
  v == null ? null : (FAIXA_LABEL[v] ?? v.charAt(0).toUpperCase() + v.slice(1))

/**
 * Aba OPORTUNIDADES IMOBILIARIAS — a camada de oferta dentro do piloto.
 *
 * Le o `viaveis.parquet` do coletor (imoveis de locacao ja joinados ao M1) via
 * `/api/oportunidades`. É READ-ONLY sobre o M1 e AGREGADA por `hex_id`: nenhum dado
 * pessoal de corretor sai do backend (o dossie PDF com contato fica atras do Authelia).
 *
 * Reusa a MESMA linguagem visual das outras fichas do piloto — `MedidorScore`,
 * `BarraMercado`, `FilaApoio`, `Eyebrow`, `Chip`, `Kpi` — para casar com o sistema:
 * a leitura de uma oportunidade tem de ler igual à leitura de um hexagono.
 */
export default function OportunidadesImobiliariasScreen({ onInicio }: { onInicio: () => void }) {
  const [itens, setItens] = useState<Oportunidade[] | null>(null)
  const [total, setTotal] = useState(0)
  const [erro, setErro] = useState<string | null>(null)
  const [ufSel, setUfSel] = useState<string>('')
  const [tipoSel, setTipoSel] = useState<string>('')
  const [sel, setSel] = useState<string | null>(null)

  useEffect(() => {
    let vivo = true
    setItens(null)
    setErro(null)
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

  const ufs = useMemo(
    () => Array.from(new Set((itens ?? []).map((o) => o.uf))).sort(),
    [itens],
  )
  const tipos = useMemo(
    () => Array.from(new Set((itens ?? []).map((o) => o.tipo).filter(Boolean))).sort(),
    [itens],
  )

  const filtrados = useMemo(() => {
    let xs = itens ?? []
    if (ufSel) xs = xs.filter((o) => o.uf === ufSel)
    if (tipoSel) xs = xs.filter((o) => o.tipo === tipoSel)
    return xs
  }, [itens, ufSel, tipoSel])

  // Mantém a seleção válida quando o filtro muda.
  useEffect(() => {
    if (filtrados.length && !filtrados.some((o) => o.id === sel)) setSel(filtrados[0].id)
  }, [filtrados, sel])

  const atual = filtrados.find((o) => o.id === sel) ?? null

  // KPIs sobre o recorte visível.
  const comResidual = filtrados.filter((o) => (o.residual ?? 0) > 0).length
  const pracas = new Set(filtrados.map((o) => o.municipio)).size
  const alugueis = filtrados.map((o) => o.aluguel).filter((v): v is number => v != null).sort((a, b) => a - b)
  const aluguelMediana = alugueis.length ? alugueis[Math.floor(alugueis.length / 2)] : null

  return (
    <div style={{ height: '100%', display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
      {/* ---- Cabeçalho ---- */}
      <header
        style={{
          display: 'flex',
          alignItems: 'flex-end',
          justifyContent: 'space-between',
          gap: 20,
          padding: '18px 26px 14px',
          borderBottom: '1px solid var(--line-soft)',
        }}
      >
        <div>
          <Eyebrow dot>Camada de oferta &middot; READ-ONLY sobre o M1</Eyebrow>
          <h1
            className="story"
            style={{ margin: '6px 0 0', fontSize: 30, lineHeight: 1.04, color: 'var(--tx-max)' }}
          >
            Oportunidades Imobiliárias
          </h1>
          <div style={{ marginTop: 4, font: '400 12.5px/1.4 var(--f-ui)', color: 'var(--tx-narrative)', maxWidth: '64ch' }}>
            Imóveis de <b style={{ color: 'var(--ac-text)', fontWeight: 600 }}>locação</b> coletados,
            ancorados na malha H3 e cruzados com o território do M1 — demanda, residual e censo.
          </div>
        </div>
        <button
          type="button"
          onClick={onInicio}
          style={{
            font: '600 12px/1 var(--f-ui)',
            color: 'var(--tx-muted)',
            border: '1px solid var(--line-mid)',
            borderRadius: 'var(--r-md)',
            padding: '8px 12px',
            background: 'var(--surf-raised)',
          }}
        >
          ← Início
        </button>
      </header>

      {/* ---- Filtros ---- */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 8,
          flexWrap: 'wrap',
          padding: '11px 26px',
          borderBottom: '1px solid var(--line-soft)',
        }}
      >
        <span style={{ font: '600 10px/1 var(--f-ui)', textTransform: 'uppercase', letterSpacing: '.08em', color: 'var(--tx-label)' }}>
          Estado
        </span>
        <ChipFiltro ativo={ufSel === ''} onClick={() => setUfSel('')}>Todos</ChipFiltro>
        {ufs.map((u) => (
          <ChipFiltro key={u} ativo={ufSel === u} onClick={() => setUfSel(u)}>{u}</ChipFiltro>
        ))}
        <span style={{ font: '600 10px/1 var(--f-ui)', textTransform: 'uppercase', letterSpacing: '.08em', color: 'var(--tx-label)', marginLeft: 8 }}>
          Tipo
        </span>
        <ChipFiltro ativo={tipoSel === ''} onClick={() => setTipoSel('')}>Todos</ChipFiltro>
        {tipos.map((t) => (
          <ChipFiltro key={t} ativo={tipoSel === t} onClick={() => setTipoSel(t)}>{t}</ChipFiltro>
        ))}
      </div>

      {/* ---- KPIs ---- */}
      <div style={{ display: 'flex', gap: 12, padding: '14px 26px', flexWrap: 'wrap' }}>
        <Kpi label="Oportunidades" valor={num(total)} sub="viáveis no índice (GO/SP/RJ)" />
        <Kpi label="No recorte" valor={num(filtrados.length)} sub={`${num(comResidual)} com residual > 0`} />
        <Kpi label="Praças" valor={num(pracas)} sub="municípios distintos" />
        <Kpi label="Aluguel mediano" valor={aluguelMediana == null ? '—' : brl(aluguelMediana)} sub="no recorte visível" />
      </div>

      {/* ---- Split lista / ficha ---- */}
      <div style={{ flex: 1, display: 'grid', gridTemplateColumns: 'minmax(360px, 40%) 1fr', minHeight: 0, borderTop: '1px solid var(--line-soft)' }}>
        {/* Lista */}
        <div style={{ borderRight: '1px solid var(--line-soft)', display: 'flex', flexDirection: 'column', minHeight: 0 }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '11px 20px 10px', borderBottom: '1px solid var(--line-soft)' }}>
            <span style={{ font: '600 10.5px/1 var(--f-ui)', textTransform: 'uppercase', letterSpacing: '.07em', color: 'var(--tx-label)' }}>
              Ranking · <b style={{ color: 'var(--tx-soft)', fontFamily: 'var(--f-num)' }}>{filtrados.length}</b> pontos
            </span>
            <span style={{ font: '400 12px/1 var(--f-ui)', color: 'var(--ac-text)' }}>Residual (M1) ▾</span>
          </div>
          <div style={{ overflowY: 'auto', minHeight: 0 }}>
            {itens == null && !erro && (
              <div style={{ display: 'flex', alignItems: 'center', gap: 10, padding: 24, color: 'var(--tx-muted)' }}>
                <Spinner /> Carregando oportunidades…
              </div>
            )}
            {erro && (
              <Aviso
                titulo="Não deu para carregar"
                corpo={`${erro} — confira se o backend está no ar na porta 8899 e se o data/oportunidades/viaveis.parquet existe.`}
              />
            )}
            {itens != null && filtrados.map((o) => (
              <LinhaRanking key={o.id} op={o} ativo={o.id === sel} onClick={() => setSel(o.id)} />
            ))}
          </div>
        </div>

        {/* Ficha */}
        <div style={{ overflowY: 'auto', minHeight: 0, padding: '20px 24px 34px' }}>
          {atual ? <Ficha op={atual} /> : (
            <Aviso titulo="Selecione uma oportunidade" corpo="Escolha um ponto no ranking à esquerda para ver o estudo." />
          )}
        </div>
      </div>
    </div>
  )
}

/* ---- Chip de filtro (clicável) ---- */
function ChipFiltro({ ativo, onClick, children }: { ativo: boolean; onClick: () => void; children: React.ReactNode }) {
  return (
    <button
      type="button"
      onClick={onClick}
      style={{
        padding: '5px 12px',
        borderRadius: 'var(--r-full, 999px)',
        font: '500 12.5px/1 var(--f-ui)',
        background: ativo ? 'var(--ac-a16)' : 'var(--surf-raised)',
        border: `1px solid ${ativo ? 'var(--ac-a30)' : 'var(--line-mid)'}`,
        color: ativo ? 'var(--ac-chip)' : 'var(--tx-soft)',
      }}
    >
      {children}
    </button>
  )
}

/* ---- Uma linha do ranking ---- */
function LinhaRanking({ op, ativo, onClick }: { op: Oportunidade; ativo: boolean; onClick: () => void }) {
  const f = op.residual != null ? faixaDoValor(op.residual, FAIXAS_DEMANDA) : null
  const cor = f?.cor ?? 'var(--tx-off)'
  const rsM2 = op.rs_m2 != null ? Math.round(op.rs_m2) : op.aluguel != null && op.area ? Math.round(op.aluguel / op.area) : null
  return (
    <button
      type="button"
      onClick={onClick}
      style={{
        width: '100%',
        textAlign: 'left',
        display: 'grid',
        gridTemplateColumns: '1fr auto',
        gap: 12,
        alignItems: 'center',
        padding: '12px 20px',
        borderBottom: '1px solid var(--line-soft)',
        borderLeft: `2px solid ${ativo ? 'var(--ac)' : 'transparent'}`,
        background: ativo ? 'var(--ac-a08)' : 'transparent',
      }}
    >
      <div style={{ minWidth: 0 }}>
        <div style={{ font: '600 13.5px/1.25 var(--f-ui)', color: 'var(--tx-strong)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
          {op.titulo}
        </div>
        <div style={{ font: '400 12px/1.3 var(--f-ui)', color: 'var(--tx-muted)', marginTop: 1 }}>
          {op.bairro ? `${op.bairro} · ` : ''}{op.municipio}/{op.uf}
        </div>
        <div style={{ display: 'flex', gap: 6, marginTop: 7, flexWrap: 'wrap' }}>
          <Tag>{op.tipo}</Tag>
          {op.area != null && <Tag><span className="num">{num(op.area)}</span> m²</Tag>}
          {rsM2 != null && <Tag>R$/m² <span className="num">{rsM2}</span></Tag>}
        </div>
      </div>
      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: 6 }}>
        <span className="num" style={{ display: 'inline-flex', alignItems: 'center', gap: 6, font: '600 12.5px/1 var(--f-num)', color: 'var(--tx-soft)' }}>
          <span style={{ width: 9, height: 9, borderRadius: 2, background: cor }} />
          {op.residual != null ? Math.round(op.residual) : '—'}
        </span>
        {op.faixa && <Chip cor={cor}>{labelFaixa(op.faixa)}</Chip>}
      </div>
    </button>
  )
}

function Tag({ children }: { children: React.ReactNode }) {
  return (
    <span style={{ font: '400 11px/1.3 var(--f-ui)', padding: '1px 7px', borderRadius: 5, background: 'var(--surf-input)', color: 'var(--tx-narrative)', border: '1px solid var(--line)' }}>
      {children}
    </span>
  )
}

/* ---- A ficha de uma oportunidade ---- */
function Ficha({ op }: { op: Oportunidade }) {
  const rsM2 = op.rs_m2 != null ? Math.round(op.rs_m2) : op.aluguel != null && op.area ? Math.round(op.aluguel / op.area) : null
  const ocupacao = [op.aluguel, op.iptu, op.condominio].reduce<number>((s, v) => s + (v ?? 0), 0)
  return (
    <div style={{ display: 'grid', gap: 16 }}>
      {/* cabeçalho da ficha */}
      <div>
        <Eyebrow dot>Oportunidade selecionada</Eyebrow>
        <div className="story" style={{ marginTop: 8, fontSize: 24, lineHeight: 1.1, color: 'var(--tx-max)' }}>
          {op.titulo}
        </div>
        <div style={{ font: '400 13px/1.4 var(--f-ui)', color: 'var(--tx-narrative)', marginTop: 3 }}>
          {op.bairro ? `${op.bairro} · ` : ''}{op.municipio}/{op.uf} · {op.tipo} para locação
        </div>
        <div style={{ marginTop: 9, display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
          <span className="num" style={{ font: '500 11px/1 var(--f-num)', color: 'var(--tx-sub)', padding: '5px 8px', borderRadius: 7, background: 'var(--surf-raised)', border: '1px solid var(--line-soft)' }}>
            {op.hex_id}
          </span>
          {op.first_seen && <Chip tom="gray">Acompanhado desde {op.first_seen}</Chip>}
          {op.lat != null && op.lng != null && (
            <a
              href={`https://www.google.com/maps/search/?api=1&query=${op.lat},${op.lng}`}
              target="_blank"
              rel="noreferrer"
              style={{ font: '600 11px/1 var(--f-ui)', color: 'var(--ac-text)', textDecoration: 'underline', textUnderlineOffset: 2 }}
            >
              Abrir no Google Maps ↗
            </a>
          )}
        </div>
      </div>

      {/* Quem mora aqui (censo) */}
      <Bloco titulo="Quem mora aqui" nota="Censo 2022 (IBGE), no hexágono" ro>
        <MedidorScore rotulo="Potencial socioeconômico" valor={op.censo_score} faixas={FAIXAS_POTENCIAL} />
        <FilaApoio>
          <NumeroApoio rotulo="População" valor={op.pop == null ? '—' : num(op.pop)} />
          <NumeroApoio rotulo="Renda per capita" valor={op.renda_pc == null ? '—' : brl(op.renda_pc)} />
        </FilaApoio>
      </Bloco>

      {/* Quanto de mercado sobra */}
      <Bloco titulo="Quanto de mercado sobra" nota="capacidade, não meta de abertura" ro>
        <BarraMercado sam={op.sam} residual={op.residual_total} />
        <MedidorScore
          rotulo="Score de residual"
          valor={op.residual}
          faixas={FAIXAS_DEMANDA}
          nota="satura em 100 acima de 2.500 alunos — uma unidade cheia"
        />
        <FilaApoio>
          <NumeroApoio rotulo="Mercado potencial (SAM)" valor={op.sam == null ? '—' : alunos(op.sam)} />
          <NumeroApoio rotulo="Residual disponível" valor={op.residual_total == null ? '—' : alunos(op.residual_total)} />
          <NumeroApoio rotulo="Unidades Ultra no hexágono" valor={op.n_ultra == null ? '—' : num(op.n_ultra)} />
        </FilaApoio>
      </Bloco>

      {/* A oferta */}
      <Bloco titulo="A oferta" nota="dado coletado (OLX)">
        <FilaApoio>
          <NumeroApoio rotulo="Área" valor={op.area == null ? '—' : `${num(op.area)} m²`} />
          <NumeroApoio rotulo="Aluguel" valor={op.aluguel == null ? '—' : `${brl(op.aluguel)}/mês`} />
          <NumeroApoio rotulo="R$/m² mensal" valor={rsM2 == null ? '—' : String(rsM2)} />
        </FilaApoio>
        <FilaApoio>
          <NumeroApoio rotulo="Condomínio" valor={op.condominio == null ? '—' : brl(op.condominio)} />
          <NumeroApoio rotulo="IPTU" valor={op.iptu == null ? '—' : `${brl(op.iptu)}/mês`} />
          <NumeroApoio rotulo="Custo de ocupação" valor={ocupacao > 0 ? `${brl(ocupacao)}/mês` : '—'} />
        </FilaApoio>
      </Bloco>

      {/* Nota de confidencialidade */}
      <Glass style={{ padding: '12px 14px' }}>
        <div style={{ display: 'flex', gap: 9, font: '400 11.5px/1.5 var(--f-ui)', color: 'var(--tx-sub)' }}>
          <span style={{ color: 'var(--ac-text)', flexShrink: 0 }}>ⓘ</span>
          <span>
            Camada agregada por <span className="num">hex_id</span>, sem dado pessoal. O contato do
            corretor vive no dossiê PDF, atrás do Authelia (legítimo interesse B2B).
          </span>
        </div>
      </Glass>
    </div>
  )
}

/** Seção da ficha — mesmo desenho do `Bloco` do `FichaHex`. */
function Bloco({ titulo, nota, ro, children }: { titulo: string; nota?: string; ro?: boolean; children: React.ReactNode }) {
  return (
    <section>
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 8, flexWrap: 'wrap' }}>
        <h3 style={{ margin: 0, font: '600 13px/1.2 var(--f-ui)', color: 'var(--tx-max)' }}>{titulo}</h3>
        {nota && <span style={{ font: '400 11px/1.3 var(--f-ui)', color: 'var(--tx-sub)' }}>{nota}</span>}
        {ro && (
          <span style={{ marginLeft: 'auto', font: '400 10px/1 var(--f-ui)', color: 'var(--ac-text)', background: 'var(--ac-a10)', border: '1px solid var(--ac-a24)', padding: '3px 8px', borderRadius: 'var(--r-full, 999px)' }}>
            M1 · read-only
          </span>
        )}
      </div>
      <div style={{ marginTop: 10, display: 'grid', gap: 12 }}>{children}</div>
    </section>
  )
}
