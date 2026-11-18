import { useEffect, useState, type ReactNode } from 'react'

import BotaoInicio from '../components/BotaoInicio'
import MapaDoTerritorio from '../components/masters/MapaDoTerritorio'
import {
  Aviso,
  BarraMeta,
  Botao,
  Chip,
  Eyebrow,
  Glass,
  Kpi,
  Spinner,
} from '../components/primitives'
import { api, ApiError, baixar } from '../lib/api'
import {
  barrasPorAno,
  barrasPorFase,
  barrasPorPrevisao,
  dataBr,
  escalaDaBarra,
  etiquetasDaUnidade,
  metaDoAno,
  pct,
  rotuloDaBarra,
  rotuloUnidade,
  textoAnoDaMeta,
  textoContrato,
  textoPrazo,
  textoDoRelatorio,
  textoProgressoDaMeta,
  topoDoGrafico,
  type MetaDoAno,
  type Barra,
  type FontesMasters,
  type MasterCard,
  type MasterPainel,
  type MastersPayload,
  type TrimestreMeta,
} from '../lib/masters'
import type { Tema } from '../lib/tema'

/* ---------------------------------------------------------------------------
   Tela Masters (DEC-089) — um card por master franqueado e, ao clicar, o painel
   dele: unidades em operação, em inauguração, contratos assinados por fase e a
   meta de aberturas do ano e do contrato.

   RESTRITA (`masters.ver`, growth e lideres): os contratos e as metas vêm da
   planilha de levantamento dos masters, confidencial, ingerida no servidor por
   `scripts/ingerir_masters.py`; a data de inauguração vem da base do Growth, que o
   motor atualiza todo dia. As regras (o que é "em operação", quem conta para a
   meta) são do servidor; aqui só se desenha. Gráfico em SVG à mão, como o resto
   do produto (`ExecCharts`).
   --------------------------------------------------------------------------- */

function rodape(f: FontesMasters | undefined): string {
  if (!f) return ''
  const partes = [
    f.planilha_de ? `Planilha dos masters de ${dataBr(f.planilha_de)}` : null,
    f.growth_ate
      ? `datas de inauguração da base do Growth até ${dataBr(f.growth_ate)}`
      : 'sem a base do Growth: datas de inauguração indisponíveis',
  ]
  return partes.filter(Boolean).join(' · ')
}

function Numero({ rotulo, valor }: { rotulo: string; valor: string }) {
  return (
    <div>
      <div className="num" style={{ font: '700 20px/1 var(--f-num)', color: 'var(--tx-max)' }}>
        {valor}
      </div>
      <div style={{ font: '500 10.5px/1.25 var(--f-ui)', color: 'var(--tx-label)', marginTop: 4 }}>
        {rotulo}
      </div>
    </div>
  )
}

function CardMaster({
  m,
  hoje,
  onAbrir,
}: {
  m: MasterCard
  hoje: string
  onAbrir: () => void
}) {
  const contrato = textoContrato(m.meta)
  return (
    <Glass style={{ padding: '15px 17px', cursor: 'pointer' }} onClick={onAbrir}>
      <div
        role="button"
        tabIndex={0}
        aria-label={`Abrir o painel de ${m.nome}`}
        onKeyDown={(e) => {
          if (e.key === 'Enter' || e.key === ' ') onAbrir()
        }}
        style={{ outline: 'none' }}
      >
        {/* O nome do master com a largura toda (nomes longos, como o de um grupo de sócios,
            quebravam em cinco linhas ao lado da etiqueta); território e tipo de área embaixo. */}
        <div style={{ font: '600 15px/1.25 var(--f-ui)', color: 'var(--tx-max)' }}>{m.nome}</div>
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 8,
            flexWrap: 'wrap',
            marginTop: 6,
            font: '600 11.5px/1.35 var(--f-ui)',
            color: 'var(--tx-label)',
          }}
        >
          {m.territorio && <span>{m.territorio}</span>}
          {m.tipo_area && <Chip tom="gray">{m.tipo_area}</Chip>}
        </div>
        <div style={{ font: '400 11px/1.35 var(--f-ui)', color: 'var(--tx-sub)', marginTop: 2 }}>
          {m.regioes.length ? m.regioes.join(' · ') : 'sem região definida no contrato'}
        </div>
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: '1fr 1fr',
            gap: '12px 16px',
            marginTop: 14,
          }}
        >
          <Numero rotulo="em operação" valor={String(m.resumo.em_operacao)} />
          <Numero rotulo="em inauguração" valor={String(m.resumo.em_inauguracao)} />
          <Numero rotulo="contratos assinados" valor={String(m.resumo.assinados)} />
          <Numero rotulo={`abertas em ${m.resumo.ano}`} valor={textoAnoDaMeta(m.meta)} />
        </div>
        <div
          style={{
            borderTop: '1px solid var(--line)',
            marginTop: 14,
            paddingTop: 10,
            font: '400 11px/1.5 var(--f-ui)',
            color: 'var(--tx-sub)',
          }}
        >
          <div>Prazo do contrato: {textoPrazo(m.meta, hoje)}</div>
          {contrato && <div>Meta do contrato: {contrato}</div>}
        </div>
      </div>
    </Glass>
  )
}

/** Meta do ano por trimestre: barras do acumulado, trimestre atual tracejado, futuros em
 *  cinza e a linha da meta do ano quando ela existe. */
function GraficoMeta({
  trimestres,
  porAno,
  simulada = false,
  hoje,
}: {
  trimestres: TrimestreMeta[]
  porAno: number | null
  simulada?: boolean
  hoje: string
}) {
  const L = 440
  const A = 210
  const base = 168
  const alto = 128
  const topo = topoDoGrafico(trimestres, porAno)
  const slot = L / Math.max(trimestres.length, 1)
  const largura = 58
  const y = (v: number) => base - (v / topo) * alto
  const resumo = trimestres
    .map((t) => `${t.trimestre}º trimestre: ${t.futuro ? 'ainda não começou' : t.acumulado}`)
    .join('; ')
  return (
    <svg
      viewBox={`0 0 ${L} ${A}`}
      role="img"
      aria-label={`Unidades abertas no ano, acumulado por trimestre. ${resumo}`}
      style={{ width: '100%', height: 'auto', display: 'block' }}
    >
      <line x1={0} x2={L} y1={base} y2={base} stroke="var(--line-strong)" strokeWidth={1} />
      {porAno != null && porAno > 0 && (
        <g>
          <line
            x1={0}
            x2={L}
            y1={y(porAno)}
            y2={y(porAno)}
            stroke="var(--gr-rosa)"
            strokeDasharray="5 4"
            strokeWidth={1.4}
          />
          {/* À esquerda: o acumulado só cresce, então as barras do começo do ano são as mais
              baixas e não cobrem o rótulo (à direita ele caía em cima do trimestre atual). */}
          <text
            x={2}
            y={y(porAno) - 5}
            textAnchor="start"
            style={{ font: '600 10.5px var(--f-ui)', fill: 'var(--gr-rosa)' }}
          >
            {simulada ? 'meta simulada' : 'meta do ano'}: {porAno}
          </text>
        </g>
      )}
      {trimestres.map((t, i) => {
        const cx = slot * i + slot / 2
        const h = t.futuro ? 0 : (t.acumulado / topo) * alto
        const cor = t.novas > 0 ? 'var(--ac)' : 'var(--tx-muted)'
        const rotulo = rotuloDaBarra(t)
        return (
          <g key={t.trimestre}>
            {t.atual && (
              <rect
                x={cx - largura / 2}
                y={base - Math.max(h, 26)}
                width={largura}
                height={Math.max(h, 26)}
                fill="none"
                stroke="var(--gr-rosa)"
                strokeDasharray="4 3"
                strokeWidth={1.4}
                rx={3}
              />
            )}
            {h > 0 && (
              <rect
                x={cx - largura / 2 + 3}
                y={base - h + (t.atual ? 3 : 0)}
                width={largura - 6}
                height={Math.max(h - (t.atual ? 3 : 0), 1)}
                fill={cor}
                opacity={t.novas > 0 ? 0.9 : 0.35}
                rx={3}
              />
            )}
            {rotulo && (
              <text
                x={cx}
                y={base - Math.max(h, t.atual ? 26 : 0) - 6}
                textAnchor="middle"
                className="num"
                style={{ font: '700 12px var(--f-num)', fill: 'var(--tx-max)' }}
              >
                {rotulo}
              </text>
            )}
            <text
              x={cx}
              y={base + 17}
              textAnchor="middle"
              style={{
                font: `${t.atual ? 700 : 500} 11.5px var(--f-ui)`,
                fill: t.atual ? 'var(--gr-rosa)' : 'var(--tx-label)',
                opacity: t.futuro ? 0.5 : 1,
              }}
            >
              {t.trimestre}º tri
            </text>
            {t.atual && (
              <text
                x={cx}
                y={base + 31}
                textAnchor="middle"
                style={{ font: '600 9.5px var(--f-ui)', fill: 'var(--gr-rosa)' }}
              >
                em andamento ({dataBr(hoje).slice(0, 5)})
              </text>
            )}
          </g>
        )
      })}
    </svg>
  )
}

/** Barras horizontais de um grupo: rótulo à esquerda (cabe "Buscando Imóvel"), a barra e a
 *  contagem no fim dela. Uma série só, então sem legenda: o título do cartão a nomeia. */
function BarrasDoGrupo({
  barras,
  cor,
  descricao,
}: {
  barras: Barra[]
  cor: string
  descricao: string
}) {
  const L = 340
  const rot = 108
  const linha = 24
  const A = barras.length * linha + 4
  const maior = Math.max(1, ...barras.map((b) => b.n))
  const util = L - rot - 34
  return (
    <svg
      viewBox={`0 0 ${L} ${A}`}
      role="img"
      aria-label={`${descricao}: ${barras.map((b) => `${b.rotulo} ${b.n}`).join('; ')}`}
      style={{ width: '100%', height: 'auto', display: 'block' }}
    >
      {barras.map((b, i) => {
        const y = i * linha + 2
        const w = (b.n / maior) * util
        return (
          <g key={b.rotulo}>
            <text
              x={rot - 8}
              y={y + linha / 2 + 4}
              textAnchor="end"
              style={{
                font: `${b.destaque ? 700 : 500} 11.5px var(--f-ui)`,
                fill: b.destaque ? 'var(--tx-max)' : 'var(--tx-label)',
              }}
            >
              {b.rotulo}
            </text>
            <rect
              x={rot}
              y={y + 5}
              width={Math.max(w, b.n > 0 ? 3 : 0)}
              height={linha - 10}
              rx={3}
              fill={cor}
              opacity={b.destaque || barras.every((x) => !x.destaque) ? 0.9 : 0.45}
            />
            <text
              x={rot + Math.max(w, b.n > 0 ? 3 : 0) + 6}
              y={y + linha / 2 + 4}
              className="num"
              style={{ font: '700 11.5px var(--f-num)', fill: 'var(--tx-max)' }}
            >
              {b.n}
            </text>
          </g>
        )
      })}
    </svg>
  )
}

function CartaoGrafico({
  titulo,
  sub,
  cor,
  barras,
  vazio,
}: {
  titulo: string
  sub?: string
  cor: string
  barras: Barra[]
  vazio: string
}) {
  return (
    <Glass style={{ padding: '14px 16px', minWidth: 0 }}>
      <Eyebrow cor={cor} dot>
        {titulo}
      </Eyebrow>
      {sub && (
        <div style={{ font: '400 11px/1.4 var(--f-ui)', color: 'var(--tx-sub)', marginTop: 4 }}>
          {sub}
        </div>
      )}
      <div style={{ marginTop: 10 }}>
        {barras.length ? (
          <BarrasDoGrupo barras={barras} cor={cor} descricao={titulo} />
        ) : (
          <div style={{ font: '400 12px/1.4 var(--f-ui)', color: 'var(--tx-sub)' }}>{vazio}</div>
        )}
      </div>
    </Glass>
  )
}

/** A barra da meta em unidades: de 0 ao fim da escala (`escalaDaBarra`), a linha ROSA na meta
 *  com o número embaixo, e nada entre os dois. Verde quando bateu a meta, turquesa abaixo. */
function BarraEmUnidades({ md }: { md: MetaDoAno }) {
  const e = escalaDaBarra(md)
  const altura = 12
  const bateu = md.abertas >= md.meta
  const meta = e.posicaoDaMeta * 100
  return (
    <div style={{ marginTop: 9 }}>
      <div
        style={{
          position: 'relative',
          height: altura,
          background: 'var(--surf-raised)',
          borderRadius: altura / 2,
        }}
      >
        <div
          style={{
            width: `${e.posicaoDasAbertas * 100}%`,
            height: '100%',
            borderRadius: altura / 2,
            background: bateu ? 'var(--pos, #37b26b)' : 'var(--ac)',
          }}
        />
        <div
          title={`Meta: ${md.meta}`}
          style={{
            position: 'absolute',
            left: `calc(${meta}% - 1.5px)`,
            top: -4,
            width: 3,
            height: altura + 8,
            borderRadius: 2,
            background: 'var(--gr-rosa)',
          }}
        />
      </div>
      <div style={{ position: 'relative', height: 14, marginTop: 6 }}>
        <span
          className="num"
          style={{ position: 'absolute', left: 0, font: '400 10.5px/1 var(--f-num)', color: 'var(--tx-sub)' }}
        >
          0
        </span>
        <span
          className="num"
          style={{
            position: 'absolute',
            left: `${meta}%`,
            transform: meta >= 99 ? 'translateX(-100%)' : 'translateX(-50%)',
            font: '700 11px/1 var(--f-num)',
            color: 'var(--gr-rosa)',
            whiteSpace: 'nowrap',
          }}
        >
          {md.meta}
        </span>
      </div>
    </div>
  )
}

/** O botão ÚNICO do relatório (BLK-MASTERS-04; 18/11/2026, Juan: "maior, do lado direito, e
 *  apenas um botão só"). Com duas ou mais áreas, o servidor manda um PDF por área num .zip. */
function BotaoDoRelatorio({ p }: { p: MasterPainel }) {
  const [gerando, setGerando] = useState(false)
  const [erro, setErro] = useState<string | null>(null)

  async function gerar() {
    setGerando(true)
    setErro(null)
    try {
      const { blob, filename } = await api.relatorioMaster(p.id)
      baixar(blob, filename)
    } catch (e) {
      setErro(e instanceof ApiError ? e.message : 'Falha ao gerar o relatório do master.')
    } finally {
      setGerando(false)
    }
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: 6 }}>
      <Botao
        onClick={gerar}
        disabled={gerando}
        title="Relatório do master: o estudo de área e as metas, com os padrões das unidades quando a região tem dado"
        style={{ padding: '13px 24px', font: '700 14.5px/1 var(--f-ui)' }}
      >
        {gerando ? 'Gerando o relatório…' : 'Gerar relatório'}
      </Botao>
      <div
        style={{
          font: '400 11px/1.4 var(--f-ui)',
          color: 'var(--tx-sub)',
          textAlign: 'right',
          maxWidth: 280,
          display: 'flex',
          alignItems: 'center',
          gap: 6,
        }}
      >
        {gerando && <Spinner tamanho={12} />}
        {gerando ? 'Gerando no servidor; pode levar até um minuto por área.' : textoDoRelatorio(p.regioes)}
      </div>
      {erro && (
        <div
          style={{
            font: '400 12px/1.4 var(--f-ui)',
            color: 'var(--warn-text)',
            textAlign: 'right',
            maxWidth: 320,
          }}
        >
          {erro}
        </div>
      )}
    </div>
  )
}

/** Simulação da meta do ano só na prévia local (18/11/2026, Juan: "simulação só na prévia"):
 *  `import.meta.env.DEV` é verdadeiro no `npm run dev` e falso no build que vai para produção. */
const SIMULAR_META_SEM_DADO = import.meta.env.DEV

/** A barra da meta do ano, até 100%: quanto já foi e quanto falta. Com a meta SIMULADA (só na
 *  prévia), a etiqueta e a nota dizem isso; sem meta (produção), "não informada". */
function BarraDaMetaDoAno({ md, ano }: { md: MetaDoAno | null; ano: number }) {
  if (!md) {
    return (
      <div>
        <div style={{ font: '600 12.5px/1.3 var(--f-ui)', color: 'var(--tx-max)' }}>
          Meta de {ano}: não informada
        </div>
        <div style={{ marginTop: 9, opacity: 0.5 }}>
          <BarraMeta valor={null} meta={100} altura={12} />
        </div>
        <div style={{ font: '400 11.5px/1.45 var(--f-ui)', color: 'var(--tx-sub)', marginTop: 8 }}>
          A meta do ano deste master não está na planilha. Quando ela entrar na config, a barra
          mostra quanto já foi e quanto falta.
        </div>
      </div>
    )
  }
  return (
    <div>
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 8,
          flexWrap: 'wrap',
          font: '600 12.5px/1.3 var(--f-ui)',
          color: 'var(--tx-max)',
        }}
      >
        Meta de {ano}: {md.abertas} de {md.meta} {md.meta === 1 ? 'unidade' : 'unidades'}
        {md.simulada && <Chip tom="amber">simulada</Chip>}
      </div>
      {/* A escala em UNIDADES (18/11/2026, Juan): só o 0 e a meta, marcada por uma linha rosa com
          o número; quem passou da meta tem a barra além da linha. */}
      <BarraEmUnidades md={md} />
      <div
        className="num"
        style={{ font: '700 13px/1.3 var(--f-ui)', color: 'var(--tx-max)', marginTop: 6 }}
      >
        {textoProgressoDaMeta(md)}
      </div>
      {md.simulada && (
        <div
          style={{
            font: 'italic 400 11px/1.45 var(--f-ui)',
            color: 'var(--warn-text)',
            marginTop: 6,
          }}
        >
          Simulação: a meta do ano não está na planilha. Usei as aberturas do ano ± 2; quando a
          meta real entrar na config, a barra passa a usar ela.
        </div>
      )}
    </div>
  )
}

function Lista({
  titulo,
  n,
  vazio,
  children,
}: {
  titulo: string
  n: number
  vazio: string
  children: ReactNode
}) {
  return (
    <Glass style={{ padding: '14px 16px', minWidth: 0 }}>
      <Eyebrow dot>
        {titulo} ({n})
      </Eyebrow>
      {/* Altura limitada, com rolagem por dentro: a lista do DF/GO tem 33 unidades e empurrava
          os gráficos do fim do painel para longe. */}
      <div
        style={{
          marginTop: 10,
          display: 'flex',
          flexDirection: 'column',
          gap: 8,
          maxHeight: 420,
          overflowY: 'auto',
          paddingRight: 4,
        }}
      >
        {n === 0 ? (
          <div style={{ font: '400 12px/1.4 var(--f-ui)', color: 'var(--tx-sub)' }}>{vazio}</div>
        ) : (
          children
        )}
      </div>
    </Glass>
  )
}

function Linha({
  nome,
  direita,
  etiquetas = [],
}: {
  nome: string
  direita?: string
  etiquetas?: string[]
}) {
  return (
    <div style={{ borderBottom: '1px solid var(--line)', paddingBottom: 7 }}>
      <div style={{ display: 'flex', gap: 8, alignItems: 'baseline' }}>
        <div style={{ font: '500 12.5px/1.3 var(--f-ui)', color: 'var(--tx-max)', flex: 1 }}>
          {nome}
        </div>
        {direita && (
          <div
            className="num"
            style={{ font: '400 11.5px/1 var(--f-num)', color: 'var(--tx-sub)', whiteSpace: 'nowrap' }}
          >
            {direita}
          </div>
        )}
      </div>
      {etiquetas.length > 0 && (
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 5, marginTop: 5 }}>
          {etiquetas.map((e) => (
            <Chip key={e} tom={e.startsWith('sem data') ? 'amber' : 'gray'}>
              {e}
            </Chip>
          ))}
        </div>
      )}
    </div>
  )
}

type VisaoDoMaster = 'expansao' | 'unidades'

const VISOES: { chave: VisaoDoMaster; rotulo: string; sub: string }[] = [
  { chave: 'expansao', rotulo: 'Expansão', sub: 'meta, território, inaugurações e contratos' },
  { chave: 'unidades', rotulo: 'Unidades', sub: 'as unidades em operação' },
]

/** Os dois seletores do painel (18/11/2026, Juan: "dentro da aba do master, dois seletores que
 *  mudem o que mostra na página, um para expansão e outro para unidades"). */
function SeletorDaVisao({
  valor,
  onTrocar,
}: {
  valor: VisaoDoMaster
  onTrocar: (v: VisaoDoMaster) => void
}) {
  return (
    <div role="group" aria-label="O que mostrar do master" style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
      {VISOES.map((v) => {
        const ativo = v.chave === valor
        return (
          <button
            key={v.chave}
            type="button"
            aria-pressed={ativo}
            onClick={() => onTrocar(v.chave)}
            style={{
              minWidth: 200,
              padding: '10px 16px',
              textAlign: 'left',
              borderRadius: 'var(--r-md)',
              border: `1.5px solid ${ativo ? 'var(--ac)' : 'var(--line-soft)'}`,
              background: ativo ? 'var(--ac-a16)' : 'var(--surf-card)',
              color: ativo ? 'var(--ac-text)' : 'var(--tx-soft)',
              cursor: 'pointer',
            }}
          >
            <div style={{ font: '700 14px/1.2 var(--f-ui)' }}>{v.rotulo}</div>
            <div style={{ font: '400 11px/1.3 var(--f-ui)', color: 'var(--tx-sub)', marginTop: 3 }}>
              {v.sub}
            </div>
          </button>
        )
      })}
    </div>
  )
}

function PainelMaster({
  p,
  tema,
  visao,
  onVisao,
  onVoltar,
}: {
  p: MasterPainel
  tema: Tema
  visao: VisaoDoMaster
  onVisao: (v: VisaoDoMaster) => void
  onVoltar: () => void
}) {
  const m = p.meta
  const contrato = textoContrato(m)
  const nAssinados = p.assinados.reduce((s, f) => s + f.unidades.length, 0)
  const porAno = barrasPorAno(p.em_operacao, m.ano)
  const md = metaDoAno(p.id, m.ano, m.n_ano, m.por_ano, SIMULAR_META_SEM_DADO)
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
      <div>
        <Botao variante="ghost" onClick={onVoltar} style={{ padding: '7px 11px' }}>
          ← Todos os masters
        </Botao>
      </div>
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'flex-start',
          gap: 20,
          flexWrap: 'wrap',
        }}
      >
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
            <h2 style={{ font: '600 22px/1.1 var(--f-ui)', color: 'var(--tx-max)', margin: 0 }}>
              {p.nome}
            </h2>
            {p.tipo_area && <Chip tom="blue">{p.tipo_area}</Chip>}
          </div>
          {p.territorio && (
            <div style={{ font: '600 13px/1.4 var(--f-ui)', color: 'var(--tx-label)', marginTop: 6 }}>
              Território {p.territorio}
            </div>
          )}
          <div style={{ font: '400 12px/1.5 var(--f-ui)', color: 'var(--tx-sub)', marginTop: 2 }}>
            {p.regioes.length
              ? p.regioes.map((r) => `${r.nome} (${r.tipo.toLowerCase()})`).join(' · ')
              : 'Sem região definida no contrato.'}
          </div>
          {p.nota && (
            <div
              style={{
                font: 'italic 400 12px/1.5 var(--f-ui)',
                color: 'var(--tx-label)',
                marginTop: 4,
              }}
            >
              {p.nota}
            </div>
          )}
        </div>
        <BotaoDoRelatorio p={p} />
      </div>

      <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
        <Kpi label="Em operação" valor={String(p.resumo.em_operacao)} />
        <Kpi label="Em inauguração" valor={String(p.resumo.em_inauguracao)} />
        <Kpi label="Contratos assinados" valor={String(nAssinados)} />
        <Kpi
          label={`Abertas em ${m.ano}`}
          valor={textoAnoDaMeta(m)}
          sub={
            md
              ? `${pct(md.pct)} da meta do ano${md.simulada ? ' (simulada)' : ''}`
              : 'meta do ano não informada'
          }
        />
      </div>

      {/* Dois seletores que trocam o que a página mostra (18/11/2026, Juan): a expansão do
          master (meta, território, inaugurações e contratos) ou as unidades dele em operação. */}
      <SeletorDaVisao valor={visao} onTrocar={onVisao} />

      {visao === 'unidades' ? (
        // Unidades: as em operação, com as aberturas por ano ao lado.
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))',
            gap: 12,
            alignItems: 'start',
          }}
        >
          <Lista titulo="Em operação" n={p.em_operacao.length} vazio="Nenhuma unidade em operação.">
            {p.em_operacao.map((u) => (
              <Linha
                key={`${u.unidade}-${u.uf}`}
                nome={rotuloUnidade(u.unidade, u.uf)}
                direita={u.inauguracao ? `desde ${dataBr(u.inauguracao)}` : undefined}
                etiquetas={etiquetasDaUnidade(u)}
              />
            ))}
          </Lista>
          <CartaoGrafico
            titulo="Em operação: aberturas por ano"
            sub={
              porAno.semData
                ? `${porAno.semData} sem data no Growth, fora do gráfico`
                : `${m.ano} em destaque`
            }
            cor="var(--ac)"
            barras={porAno.barras}
            vazio="Sem data de inauguração no Growth para estas unidades."
          />
        </div>
      ) : (
        // Expansão: a meta, o território, as inaugurações e os contratos assinados.
        <>
        {/* A meta em destaque, com o mesmo rosado do slide de metas do relatório; a barra até
            100% fica embaixo do gráfico por trimestre (18/11/2026, Juan). */}
        <Glass
          style={{
            padding: '16px 18px',
            border: '1.5px solid var(--gr-rosa)',
            background: 'color-mix(in srgb, var(--gr-rosa) 7%, var(--surf-card))',
          }}
        >
          <div style={{ display: 'flex', gap: 24, flexWrap: 'wrap', alignItems: 'flex-start' }}>
            <div style={{ flex: '0 1 320px', minWidth: 220 }}>
              <Eyebrow cor="var(--gr-rosa)">Meta de aberturas de {m.ano}</Eyebrow>
              <div
                className="num"
                style={{ font: '700 44px/1 var(--f-num)', color: 'var(--gr-rosa)', marginTop: 10 }}
              >
                {m.por_ano ? pct(m.pct_ano) : m.n_ano}
              </div>
              <div
                style={{
                  font: '400 12.5px/1.6 var(--f-ui)',
                  color: 'var(--tx-sub)',
                  marginTop: 8,
                }}
              >
                <div>
                  {m.por_ano
                    ? `${m.n_ano} de ${m.por_ano} unidades abertas em ${m.ano}`
                    : `unidades abertas em ${m.ano} que contam para a meta`}
                </div>
                <div>desde o início: {m.n_contam} contam para a meta</div>
                {contrato && <div>meta do contrato: {contrato}</div>}
                <div>prazo do contrato: {textoPrazo(m, p.hoje)}</div>
                {m.sem_data.length > 0 && (
                  <div>
                    {m.sem_data.length === 1
                      ? '1 sem data no Growth, fora da conta do ano'
                      : `${m.sem_data.length} sem data no Growth, fora da conta do ano`}
                  </div>
                )}
              </div>
            </div>
            {/* A "Meta de <ano>" com a barra em cima e o gráfico por trimestre embaixo, na mesma
                largura (18/11/2026, Juan: "deixe a meta aparecendo acima do gráfico"). */}
            <div style={{ flex: '2 1 360px', minWidth: 300, maxWidth: 600 }}>
              <BarraDaMetaDoAno md={md} ano={m.ano} />
              <div
                style={{ font: '600 12.5px/1.3 var(--f-ui)', color: 'var(--tx-max)', marginTop: 22 }}
              >
                Unidades abertas em {m.ano} que contam para a meta, até o fim de cada trimestre
              </div>
              <div
                style={{ font: '400 11px/1.4 var(--f-ui)', color: 'var(--tx-sub)', margin: '3px 0 8px' }}
              >
                em destaque, os trimestres com abertura (entre parênteses, quantas); zera a cada ano
              </div>
              <GraficoMeta
                trimestres={m.trimestres}
                porAno={md?.meta ?? null}
                simulada={md?.simulada ?? false}
                hoje={p.hoje}
              />
            </div>
          </div>
        </Glass>

        {/* Uma parte do relatório na tela (18/11/2026, Juan): o território no mapa, como na
            carteira, com renda e densidade para ligar. Sem região no contrato, não há o que mostrar. */}
        {p.regioes.length > 0 && (
          <Glass style={{ padding: '14px 16px', minWidth: 0 }}>
            <Eyebrow>Território no mapa</Eyebrow>
            <div
              style={{ font: '400 11px/1.4 var(--f-ui)', color: 'var(--tx-sub)', margin: '3px 0 10px' }}
            >
              as regiões do contrato e as unidades Ultra nelas; ligue a renda ou a densidade para ver o
              território por dentro (as mesmas do Mapa do motor)
            </div>
            <MapaDoTerritorio masterId={p.id} tema={tema} />
          </Glass>
        )}

        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))',
            gap: 12,
            alignItems: 'start',
          }}
        >
          <Lista
            titulo="Em inauguração"
            n={p.em_inauguracao.length}
            vazio="Nenhuma unidade com inauguração marcada nem em pré-venda."
          >
            {p.em_inauguracao.map((u) => (
              <Linha
                key={`${u.unidade}-${u.uf}`}
                nome={rotuloUnidade(u.unidade, u.uf)}
                direita={u.previsao ? `abre ${dataBr(u.previsao)}` : (u.fase ?? undefined)}
              />
            ))}
          </Lista>
          <Lista titulo="Contratos assinados" n={nAssinados} vazio="Nenhum contrato assinado.">
            {p.assinados.map((f) => (
              <div key={f.fase} style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                <div style={{ font: '600 11.5px/1 var(--f-ui)', color: 'var(--tx-label)' }}>
                  {f.fase} ({f.unidades.length})
                </div>
                {f.unidades.map((u) => (
                  <Linha
                    key={`${f.fase}-${u.unidade}`}
                    nome={u.unidade}
                    direita={[u.cidade, u.uf].filter(Boolean).join(' / ') || undefined}
                    etiquetas={u.dentro_territorio === false ? ['fora do território'] : []}
                  />
                ))}
              </div>
            ))}
          </Lista>
        </div>

        {/* Um gráfico para cada grupo, no fim do painel (18/11/2026, Juan). */}
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))',
            gap: 12,
            alignItems: 'start',
          }}
        >
          <CartaoGrafico
            titulo="Em inauguração: por mês previsto"
            sub="data de inauguração no Growth; pré-venda sem data por último"
            cor="var(--gr-azul)"
            barras={barrasPorPrevisao(p.em_inauguracao)}
            vazio="Nenhuma unidade em inauguração."
          />
          <CartaoGrafico
            titulo="Contratos assinados: por fase"
            sub="da fase mais perto de abrir à mais longe"
            cor="var(--gr-verde)"
            barras={barrasPorFase(p.assinados)}
            vazio="Nenhum contrato assinado."
          />
        </div>
        </>
      )}
    </div>
  )
}

export default function MastersScreen({ onInicio, tema }: { onInicio: () => void; tema: Tema }) {
  const [lista, setLista] = useState<MastersPayload | null>(null)
  const [erro, setErro] = useState<string | null>(null)
  const [carregando, setCarregando] = useState(true)
  const [aberto, setAberto] = useState<string | null>(null)
  const [painel, setPainel] = useState<MasterPainel | null>(null)
  const [erroPainel, setErroPainel] = useState<string | null>(null)
  const [visao, setVisao] = useState<VisaoDoMaster>('expansao')

  useEffect(() => {
    let vivo = true
    api
      .masters()
      .then((r) => vivo && setLista(r))
      .catch((e: ApiError) => vivo && setErro(e.message))
      .finally(() => vivo && setCarregando(false))
    return () => {
      vivo = false
    }
  }, [])

  useEffect(() => {
    if (!aberto) return
    let vivo = true
    setPainel(null)
    setErroPainel(null)
    api
      .master(aberto)
      .then((r) => vivo && setPainel(r))
      .catch((e: ApiError) => vivo && setErroPainel(e.message))
    return () => {
      vivo = false
    }
  }, [aberto])

  const fontes = painel?.fontes ?? lista?.fontes
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
        className="barra-ultra"
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
          Masters
        </h1>
        <Chip tom="amber">restrito</Chip>
        <div style={{ flex: 1 }} />
        <span style={{ font: '400 10.5px/1.3 var(--f-ui)', color: 'var(--tx-muted)' }}>
          {rodape(fontes)}
        </span>
      </header>

      <div style={{ flex: 1, overflowY: 'auto', padding: '16px 22px' }}>
        {carregando ? (
          <div style={{ display: 'flex', justifyContent: 'center', padding: 40 }}>
            <Spinner tamanho={18} />
          </div>
        ) : erro ? (
          <Aviso titulo="Dados dos masters indisponíveis" corpo={erro} />
        ) : aberto ? (
          erroPainel ? (
            <Aviso
              titulo="Não foi possível abrir o painel"
              corpo={erroPainel}
              acao={
                <Botao variante="ghost" onClick={() => setAberto(null)}>
                  ← Todos os masters
                </Botao>
              }
            />
          ) : painel ? (
            <PainelMaster
              p={painel}
              tema={tema}
              visao={visao}
              onVisao={setVisao}
              onVoltar={() => setAberto(null)}
            />
          ) : (
            <div style={{ display: 'flex', justifyContent: 'center', padding: 40 }}>
              <Spinner tamanho={18} />
            </div>
          )
        ) : lista && lista.masters.length > 0 ? (
          <>
            <div style={{ font: '400 12.5px/1.5 var(--f-ui)', color: 'var(--tx-sub)', marginBottom: 12 }}>
              Contratos, unidades e meta de aberturas de cada master. Clique num master para ver o
              painel dele.
            </div>
            <div
              style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fill, minmax(290px, 1fr))',
                gap: 12,
              }}
            >
              {lista.masters.map((m) => (
                <CardMaster key={m.id} m={m} hoje={lista.hoje} onAbrir={() => setAberto(m.id)} />
              ))}
            </div>
          </>
        ) : (
          <Aviso titulo="Nenhum master" corpo="A planilha ingerida não tem nenhum master." />
        )}
      </div>
    </div>
  )
}
