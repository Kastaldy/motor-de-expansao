import { useMemo } from 'react'

import BotaoInicio from '../components/BotaoInicio'
import Select from '../components/Select'
import { Aviso, Chip, Eyebrow, Glass, Spinner } from '../components/primitives'
import { camadaCor } from '../lib/colors'
import {
  TOP_POR_CAMADA,
  consolidar,
  fraseConsolidada,
  topPorCamada,
  type CidadeConsolidada,
} from '../lib/consolidado'
import { alunos, num } from '../lib/format'
import {
  lerCrescimento,
  temCoberturaSatelite,
  type CrescimentoMunicipio,
} from '../lib/oportunidades'
import type { MunicipioPayload, Passo, RankItem } from '../lib/types'

/**
 * Modo 3 — as melhores oportunidades, POR CAMADA e depois consolidadas.
 *
 * POR QUE NAO E' UMA LISTA SO'. A fila do passo 5 e' a recomendacao do motor, mas
 * sozinha ela esconde ONDE cada cidade se destaca: uma pode estar ali por residual
 * bruto e outra por crescimento, e as duas aparecem iguais. Separando por camada, o
 * operador ve o top 5 de cada leitura — potencial, demanda, concorrencia, crescimento
 * e a fila — e entende o que cada cidade tem de melhor.
 *
 * O CONSOLIDADO NO FIM NAO E' UM SCORE. Somar ou ponderar as cinco camadas criaria uma
 * sexta definicao de prioridade sobre o M1 — criticidade Alta pela regua do
 * CLAUDE.md §2, e o piloto e' "sem recalculo de score em runtime". O que ele faz e'
 * CONTAR em quantas camadas a cidade aparece no topo, desempatando pela fila oficial.
 * Contagem o operador confere a olho, somando os cartoes acima.
 */
export default function OportunidadesScreen({
  ufs,
  uf,
  onUf,
  dados,
  carregando,
  erro,
  onInicio,
  onVerNoMapa,
}: {
  ufs: string[]
  uf: string
  onUf: (uf: string) => void
  dados: MunicipioPayload | null
  carregando: boolean
  erro: string | null
  onInicio: () => void
  onVerNoMapa: (municipio: string) => void
}) {
  const passos = dados?.passos ?? []
  const cres = dados?.cres_mun ?? null

  const camadas = useMemo(() => topPorCamada(passos), [passos])
  const consolidado = useMemo(() => consolidar(passos), [passos])

  return (
    <div style={{ position: 'absolute', inset: 0, display: 'flex', flexDirection: 'column' }}>
      <header
        style={{
          flexShrink: 0,
          margin: '16px 16px 0',
          padding: '9px 12px',
          display: 'flex',
          alignItems: 'center',
          gap: 12,
          flexWrap: 'wrap',
          background: 'var(--surf-chrome)',
          border: '1px solid var(--line-soft)',
          borderRadius: 'var(--r-xl)',
          backdropFilter: 'blur(14px)',
        }}
      >
        <BotaoInicio onInicio={onInicio} />
        <h1
          style={{
            font: '600 14px/1 var(--f-ui)',
            letterSpacing: '-.01em',
            color: 'var(--tx-max)',
            margin: 0,
          }}
        >
          Melhores oportunidades
        </h1>
        <Select
          label="Estado"
          value={uf}
          onChange={onUf}
          maxWidth={130}
          buscavel
          placeholder="Estado…"
          options={ufs.map((u) => ({ value: u, label: u }))}
        />
        {passos.length > 0 && <Chip>top {TOP_POR_CAMADA} por camada</Chip>}
      </header>

      <div style={{ flex: 1, overflowY: 'auto', padding: 16 }}>
        <div style={{ maxWidth: 1000, margin: '0 auto', display: 'grid', gap: 18 }}>
          {!uf && (
            <Aviso
              titulo="Escolha um estado"
              corpo="As camadas são lidas por estado: o motor percorre a partição inteira da UF e devolve o topo de cada leitura — potencial, demanda, concorrência, crescimento e a fila de recomendação."
            />
          )}

          {carregando && (
            <p
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 8,
                font: '400 13px/1 var(--f-ui)',
                color: 'var(--tx-muted)',
              }}
            >
              <Spinner /> Lendo a partição do estado…
            </p>
          )}

          {erro && <Aviso titulo="Não deu para carregar" corpo={erro} />}

          {passos.length > 0 && !carregando && (
            <>
              {camadas.map(({ passo, itens }) => (
                <BlocoCamada
                  key={passo.n}
                  passo={passo}
                  itens={itens}
                  cres={cres}
                  onVerNoMapa={onVerNoMapa}
                />
              ))}

              {/* ---- Consolidado ---- */}
              <Glass style={{ padding: 18, display: 'grid', gap: 14 }}>
                <div style={{ display: 'grid', gap: 6 }}>
                  <Eyebrow dot>Para onde ir</Eyebrow>
                  <span
                    style={{
                      font: '400 21px/1.25 var(--f-story)',
                      color: 'var(--tx-max)',
                    }}
                  >
                    Quem aparece no topo de mais camadas
                  </span>
                  <p
                    style={{
                      font: '400 11.5px/1.5 var(--f-ui)',
                      color: 'var(--tx-sub)',
                      margin: 0,
                    }}
                  >
                    Isto é uma <strong style={{ color: 'var(--tx-soft)' }}>contagem</strong>, não
                    um score: quantas das {passos.length} camadas trazem a cidade no top{' '}
                    {TOP_POR_CAMADA}. Somar ou ponderar as camadas criaria uma definição nova de
                    prioridade em cima do M1 — e elas medem coisas diferentes. Empate é desfeito
                    pela posição na fila de recomendação.
                  </p>
                </div>

                {consolidado.length === 0 ? (
                  <Aviso
                    titulo="Nenhuma cidade se repete entre as camadas"
                    corpo="Cada camada destaca cidades diferentes neste estado. Sem repetição não há leitura consolidada — vale ler camada a camada acima."
                  />
                ) : (
                  <div style={{ display: 'grid', gap: 10 }}>
                    {consolidado.map((c, i) => (
                      <LinhaConsolidada
                        key={c.nome}
                        posicao={i + 1}
                        cidade={c}
                        totalCamadas={passos.length}
                        onVerNoMapa={onVerNoMapa}
                      />
                    ))}
                  </div>
                )}
              </Glass>

              {!temCoberturaSatelite(dados?.uf) && (
                <p style={{ font: '400 11px/1.5 var(--f-ui)', color: 'var(--tx-sub)', margin: 0 }}>
                  Neste estado a camada de área construída (satélite) não tem cobertura — ela
                  colore o mapa em 12 UFs. O crescimento acima vem de outra fonte (CAGED) e segue
                  valendo, sempre lido contra a mediana deste estado.
                </p>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  )
}

/** Uma camada: o topo dela, com a identidade de cor que o funil já usa. */
function BlocoCamada({
  passo,
  itens,
  cres,
  onVerNoMapa,
}: {
  passo: Passo
  itens: RankItem[]
  cres: Record<string, CrescimentoMunicipio> | null
  onVerNoMapa: (municipio: string) => void
}) {
  const cor = camadaCor(passo.n)

  return (
    <Glass style={{ padding: 18, display: 'grid', gap: 12 }}>
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 10, flexWrap: 'wrap' }}>
        <span
          className="num"
          style={{
            font: '700 10.5px/1 var(--f-num)',
            color: cor.fg,
            background: cor.bg,
            border: `1px solid ${cor.borda}`,
            borderRadius: 6,
            padding: '4px 7px',
          }}
        >
          CAMADA {passo.n}
        </span>
        <span style={{ font: '600 15px/1.2 var(--f-ui)', color: 'var(--tx-max)' }}>
          {passo.titulo}
        </span>
        <span style={{ font: '400 11px/1 var(--f-ui)', color: 'var(--tx-sub)' }}>
          top {itens.length} · ordenado por {passo.metrica}
        </span>
      </div>

      {itens.length === 0 ? (
        <p style={{ font: '400 12px/1.5 var(--f-ui)', color: 'var(--tx-muted)', margin: 0 }}>
          Nenhuma cidade passou nesta camada.
        </p>
      ) : (
        <div style={{ display: 'grid', gap: 4 }}>
          {itens.map((it, i) => {
            const municipio = it.municipio ?? it.titulo ?? ''
            const leitura = lerCrescimento(cres?.[municipio])
            return (
              <button
                key={`${passo.n}-${it.rank}-${municipio}`}
                type="button"
                onClick={() => onVerNoMapa(municipio)}
                title={`Ver ${municipio} no mapa`}
                style={{
                  display: 'flex',
                  alignItems: 'baseline',
                  gap: 10,
                  padding: '7px 8px',
                  borderRadius: 8,
                  border: '1px solid transparent',
                  background: 'transparent',
                  textAlign: 'left',
                }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.background = 'var(--surf-raised)'
                  e.currentTarget.style.borderColor = 'var(--line-soft)'
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.background = 'transparent'
                  e.currentTarget.style.borderColor = 'transparent'
                }}
              >
                <span
                  className="num"
                  style={{ font: '600 11px/1 var(--f-num)', color: cor.fg, width: 18 }}
                >
                  {i + 1}º
                </span>
                <span
                  style={{
                    flex: 1,
                    minWidth: 0,
                    font: '500 13px/1.3 var(--f-ui)',
                    color: 'var(--tx-strong)',
                    overflow: 'hidden',
                    textOverflow: 'ellipsis',
                    whiteSpace: 'nowrap',
                  }}
                >
                  {it.titulo}
                </span>
                {/* So' na camada de crescimento: nas outras a etiqueta seria ruido,
                    porque o que ordena ali nao e o crescimento. */}
                {passo.n === 4 && leitura.classe !== 'sem-dado' && (
                  <span
                    style={{
                      font: '500 10px/1 var(--f-ui)',
                      color:
                        leitura.classe === 'acima'
                          ? 'var(--pos-text)'
                          : leitura.classe === 'abaixo'
                            ? 'var(--neg)'
                            : 'var(--tx-sub)',
                    }}
                  >
                    {leitura.rotulo}
                  </span>
                )}
                <span
                  className="num"
                  style={{
                    font: '600 13px/1 var(--f-num)',
                    color: 'var(--tx-max)',
                    fontVariantNumeric: 'tabular-nums',
                  }}
                >
                  {it.label === 'residual' ? alunos(it.valor) : num(it.valor)}
                </span>
                <span
                  style={{
                    font: '400 9.5px/1 var(--f-ui)',
                    color: 'var(--tx-sub)',
                    minWidth: 54,
                  }}
                >
                  {it.label}
                </span>
              </button>
            )
          })}
        </div>
      )}
    </Glass>
  )
}

function LinhaConsolidada({
  posicao,
  cidade,
  totalCamadas,
  onVerNoMapa,
}: {
  posicao: number
  cidade: CidadeConsolidada
  totalCamadas: number
  onVerNoMapa: (municipio: string) => void
}) {
  return (
    <div
      style={{
        display: 'grid',
        gap: 8,
        padding: '12px 14px',
        borderRadius: 'var(--r-md)',
        background: 'var(--surf-raised)',
        border: '1px solid var(--line-soft)',
      }}
    >
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 10, flexWrap: 'wrap' }}>
        <span
          className="num"
          style={{ font: '700 14px/1 var(--f-num)', color: 'var(--ac-text)', width: 26 }}
        >
          {posicao}º
        </span>
        <span style={{ flex: 1, minWidth: 0, font: '600 16px/1.2 var(--f-ui)', color: 'var(--tx-max)' }}>
          {cidade.nome}
        </span>
        {/* As bolinhas dizem QUAIS camadas, na cor de cada uma: a evidencia da contagem
            fica visivel sem o operador ter de rolar para cima e conferir. */}
        <span style={{ display: 'inline-flex', gap: 4 }} aria-hidden>
          {Array.from({ length: totalCamadas }, (_, i) => i + 1).map((n) => {
            const presente = cidade.presencas.some((p) => p.n === n)
            return (
              <span
                key={n}
                title={`camada ${n}`}
                style={{
                  width: 9,
                  height: 9,
                  borderRadius: '50%',
                  background: presente ? camadaCor(n).fg : 'transparent',
                  border: `1px solid ${presente ? camadaCor(n).fg : 'var(--line-strong)'}`,
                }}
              />
            )
          })}
        </span>
        <span className="num" style={{ font: '700 14px/1 var(--f-num)', color: 'var(--tx-max)' }}>
          {cidade.presencas.length}/{totalCamadas}
        </span>
        <button
          type="button"
          onClick={() => onVerNoMapa(cidade.nome)}
          style={{
            padding: '6px 10px',
            borderRadius: 8,
            border: '1px solid var(--ac-a25)',
            background: 'var(--ac-a12)',
            color: 'var(--ac-chip)',
            font: '600 11px/1 var(--f-ui)',
          }}
        >
          Ver no mapa →
        </button>
      </div>
      <p style={{ font: '400 11.5px/1.5 var(--f-ui)', color: 'var(--tx-narrative)', margin: 0 }}>
        {fraseConsolidada(cidade, totalCamadas)}
      </p>
    </div>
  )
}
