import { useEffect, useRef, useState } from 'react'

import { api } from '../lib/api'
import type { CamadaMetodologia, MetodologiaPayload, MetricaMetodologia } from '../lib/types'
import { Chip, Eyebrow, Spinner } from './primitives'

/* ---------------------------------------------------------------------------
   Metodologia dos scores — o "manual" do funil do Mapa.

   Irma do `NotasMetodologicas` da Viabilidade, e pelo mesmo motivo: o rotulo de
   uma camada nao cabe a explicacao. "Residual" e' uma subtracao de tres termos,
   "concorrentes" e' uma DIVISAO e nao uma contagem de enderecos, e as reguas de
   corte mudam entre a visao de UF e a de municipio. Sem isto, quem le a tela tem
   de saber de cor ou perguntar.

   Gaveta, nao modal: o mapa continua visivel atras, entao da' para conferir a
   regra e o hexagono ao mesmo tempo.

   NENHUM numero e' escrito aqui. Tudo vem de /api/metodologia, que por sua vez le
   as constantes que o proprio funil usa — ajustar um parametro no backend corrige
   o corte E este texto de uma vez.
   --------------------------------------------------------------------------- */

/** Faixas visiveis no escopo atual: as marcadas com o escopo + as universais. */
function faixasDoEscopo(camada: CamadaMetodologia, escopo: 'municipio' | 'uf') {
  return camada.faixas.filter((f) => !f.escopo || f.escopo === escopo)
}

function Metrica({ nome, coluna, fonte, resumo, regra, ressalva }: MetricaMetodologia) {
  const [aberta, setAberta] = useState(false)
  return (
    <div style={{ paddingTop: 13 }}>
      <div style={{ font: '600 12.5px/1.35 var(--f-ui)', color: 'var(--tx-max)' }}>{nome}</div>

      {/* A FONTE vem antes do texto: a primeira duvida de quem le' um numero de
          mercado e' "de onde voces tiraram isso?". Responder depois e' tarde. */}
      <div
        className="num"
        style={{
          marginTop: 5,
          font: '500 9.5px/1.3 var(--f-num)',
          textTransform: 'uppercase',
          letterSpacing: '.05em',
          color: 'var(--tx-muted)',
        }}
      >
        {`fonte · ${fonte}`}
      </div>

      <p
        style={{
          margin: '6px 0 0',
          font: '400 12px/1.55 var(--f-ui)',
          color: 'var(--tx-soft)',
        }}
      >
        {resumo}
      </p>

      {/* Ressalva fica SEMPRE visivel, nunca atras do toggle: e' o limite do numero. */}
      {ressalva && (
        <p
          style={{
            margin: '7px 0 0',
            paddingLeft: 9,
            borderLeft: '2px solid rgba(217,164,65,.45)',
            font: '400 11px/1.5 var(--f-ui)',
            color: 'var(--tx-muted)',
          }}
        >
          {ressalva}
        </p>
      )}
      <button
        type="button"
        onClick={() => setAberta((v) => !v)}
        aria-expanded={aberta}
        style={{
          marginTop: 6,
          padding: 0,
          background: 'none',
          border: 'none',
          cursor: 'pointer',
          font: '600 10.5px/1 var(--f-num)',
          textTransform: 'uppercase',
          letterSpacing: '.06em',
          color: 'var(--ac)',
        }}
      >
        {aberta ? '− ocultar' : '+ como é calculado'}
      </button>
      {aberta && (
        <div
          style={{
            marginTop: 8,
            padding: '9px 11px',
            borderRadius: 'var(--r-md)',
            background: 'var(--surf-raised)',
            border: '1px solid var(--line-soft)',
          }}
        >
          <p
            style={{
              margin: 0,
              font: '400 11.5px/1.6 var(--f-ui)',
              color: 'var(--tx-sub)',
            }}
          >
            {regra}
          </p>
          <div
            className="num"
            style={{
              marginTop: 7,
              font: '500 10.5px/1 var(--f-num)',
              color: 'var(--tx-muted)',
              wordBreak: 'break-all',
            }}
          >
            {coluna}
          </div>
        </div>
      )}
    </div>
  )
}

function Camada({
  camada,
  escopo,
  ativa,
}: {
  camada: CamadaMetodologia
  escopo: 'municipio' | 'uf'
  ativa: boolean
}) {
  const faixas = faixasDoEscopo(camada, escopo)
  return (
    <section
      style={{
        padding: '15px 0',
        borderTop: '1px solid var(--line-soft)',
        // A camada em que o usuario esta' ganha um trilho de destaque: liga o que
        // ele ve' no mapa ao que le' aqui, sem precisar contar os passos.
        boxShadow: ativa ? 'inset 3px 0 0 var(--ac)' : 'none',
        paddingLeft: ativa ? 11 : 0,
        transition: 'padding-left .15s ease',
      }}
    >
      <Eyebrow cor={ativa ? 'var(--ac)' : 'var(--tx-muted)'} dot={ativa}>
        {`Camada ${camada.n}`}
      </Eyebrow>
      <h3
        style={{
          margin: '7px 0 0',
          font: '600 14px/1.25 var(--f-ui)',
          color: 'var(--tx-max)',
        }}
      >
        {camada.titulo}
      </h3>
      <p
        style={{
          margin: '4px 0 0',
          font: '400 12px/1.5 var(--f-ui)',
          color: 'var(--tx-muted)',
          fontStyle: 'italic',
        }}
      >
        {camada.pergunta}
      </p>

      <div
        style={{
          marginTop: 9,
          padding: '7px 10px',
          borderRadius: 'var(--r-md)',
          background: 'var(--surf-raised)',
          border: '1px solid var(--line-soft)',
        }}
      >
        <span
          className="num"
          style={{
            font: '600 9.5px/1 var(--f-num)',
            textTransform: 'uppercase',
            letterSpacing: '.07em',
            color: 'var(--tx-muted)',
          }}
        >
          passa no corte
        </span>
        <div
          className="num"
          style={{ marginTop: 5, font: '600 12px/1.35 var(--f-num)', color: 'var(--tx-max)' }}
        >
          {camada.corte}
        </div>
      </div>

      {camada.metricas.map((m) => (
        <Metrica key={m.coluna + m.nome} {...m} />
      ))}

      {faixas.length > 0 && (
        <div style={{ marginTop: 13 }}>
          <span
            className="num"
            style={{
              font: '600 9.5px/1 var(--f-num)',
              textTransform: 'uppercase',
              letterSpacing: '.07em',
              color: 'var(--tx-muted)',
            }}
          >
            etiquetas do ranking
          </span>
          <div style={{ marginTop: 7, display: 'flex', flexDirection: 'column', gap: 6 }}>
            {faixas.map((f) => (
              <div
                key={f.etiqueta + f.condicao}
                style={{ display: 'flex', alignItems: 'center', gap: 8 }}
              >
                <Chip tom={f.tom} cor={f.cor}>
                  {f.etiqueta}
                </Chip>
                <span
                  className="num"
                  style={{ font: '400 11px/1.3 var(--f-num)', color: 'var(--tx-sub)' }}
                >
                  {f.condicao}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {camada.legenda_mapa && camada.legenda_mapa.length > 0 && (
        <div style={{ marginTop: 13 }}>
          <span
            className="num"
            style={{
              font: '600 9.5px/1 var(--f-num)',
              textTransform: 'uppercase',
              letterSpacing: '.07em',
              color: 'var(--tx-muted)',
            }}
          >
            cores do mapa
          </span>
          <div style={{ marginTop: 7, display: 'flex', flexDirection: 'column', gap: 6 }}>
            {camada.legenda_mapa.map((f) => (
              <div
                key={f.etiqueta + f.condicao}
                style={{ display: 'flex', alignItems: 'center', gap: 8 }}
              >
                <Chip tom={f.tom} cor={f.cor}>
                  {f.etiqueta}
                </Chip>
                <span
                  className="num"
                  style={{ font: '400 11px/1.3 var(--f-num)', color: 'var(--tx-sub)' }}
                >
                  {f.condicao}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {camada.nota && (
        <div
          style={{
            marginTop: 12,
            padding: '9px 11px',
            borderRadius: 'var(--r-md)',
            background: 'rgba(217,164,65,.10)',
            border: '1px solid rgba(217,164,65,.28)',
          }}
        >
          <p
            style={{ margin: 0, font: '400 11.5px/1.55 var(--f-ui)', color: 'var(--warn, #e0b25a)' }}
          >
            {camada.nota}
          </p>
        </div>
      )}
    </section>
  )
}

export default function MethodologyPanel({
  aberto,
  onFechar,
  passoAtivo,
  escopo,
}: {
  aberto: boolean
  onFechar: () => void
  /** Passo em que o usuário está no funil, para destacar a camada correspondente. */
  passoAtivo: number
  /** 'uf' quando nenhum município está selecionado — muda as faixas exibidas. */
  escopo: 'municipio' | 'uf'
}) {
  const [dados, setDados] = useState<MetodologiaPayload | null>(null)
  const [erro, setErro] = useState<string | null>(null)
  const fecharRef = useRef<HTMLButtonElement>(null)

  // Busca uma vez, na primeira abertura: o payload e' estatico (so' constantes do
  // backend), entao refazer a chamada a cada abertura seria trafego sem ganho.
  useEffect(() => {
    if (!aberto || dados) return
    let vivo = true
    api
      .metodologia()
      .then((r) => {
        if (vivo) setDados(r)
      })
      .catch((e: unknown) => {
        if (vivo) {
          setErro(e instanceof Error ? e.message : 'Não foi possível carregar a metodologia.')
        }
      })
    return () => {
      vivo = false
    }
  }, [aberto, dados])

  // Esc fecha, e o foco vai para o botao de fechar ao abrir (a gaveta cobre parte
  // da tela; sem isto o teclado continua navegando no mapa atras).
  useEffect(() => {
    if (!aberto) return
    fecharRef.current?.focus()
    const onTecla = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onFechar()
    }
    window.addEventListener('keydown', onTecla)
    return () => window.removeEventListener('keydown', onTecla)
  }, [aberto, onFechar])

  if (!aberto) return null

  return (
    <aside
      role="dialog"
      aria-modal="false"
      aria-label="Metodologia dos scores"
      style={{
        position: 'absolute',
        top: 0,
        right: 0,
        bottom: 0,
        width: 'min(430px, 100vw)',
        zIndex: 30,
        display: 'flex',
        flexDirection: 'column',
        background: 'var(--surf-chrome)',
        borderLeft: '1px solid var(--line)',
        backdropFilter: 'blur(18px)',
        boxShadow: '-18px 0 46px rgba(0,0,0,.34)',
      }}
    >
      <header
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 10,
          padding: '15px 16px 13px',
          borderBottom: '1px solid var(--line-soft)',
          flexShrink: 0,
        }}
      >
        <div style={{ flex: 1, minWidth: 0 }}>
          <Eyebrow>metodologia</Eyebrow>
          <h2
            style={{
              margin: '7px 0 0',
              font: '600 15px/1.2 var(--f-ui)',
              color: 'var(--tx-max)',
            }}
          >
            Como cada camada decide
          </h2>
        </div>
        <button
          ref={fecharRef}
          type="button"
          onClick={onFechar}
          aria-label="Fechar metodologia"
          style={{
            flexShrink: 0,
            width: 30,
            height: 30,
            borderRadius: 'var(--r-md)',
            border: '1px solid var(--line-strong)',
            background: 'transparent',
            color: 'var(--tx-soft)',
            font: '400 15px/1 var(--f-ui)',
            cursor: 'pointer',
          }}
        >
          ✕
        </button>
      </header>

      <div style={{ flex: 1, overflowY: 'auto', padding: '0 16px 18px' }}>
        {erro && (
          <p
            role="alert"
            style={{ margin: '16px 0 0', font: '500 12px/1.5 var(--f-ui)', color: 'var(--neg)' }}
          >
            {erro}
          </p>
        )}

        {!dados && !erro && (
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 8,
              padding: '20px 0',
              color: 'var(--tx-muted)',
              font: '500 12px/1 var(--f-ui)',
            }}
          >
            <Spinner /> carregando…
          </div>
        )}

        {dados && (
          <>
            <p
              style={{
                margin: '14px 0 0',
                font: '400 12.5px/1.65 var(--f-ui)',
                color: 'var(--tx-soft)',
              }}
            >
              {dados.intro}
            </p>
            <p
              style={{
                margin: '8px 0 0',
                font: '400 11.5px/1.55 var(--f-ui)',
                color: 'var(--tx-muted)',
              }}
            >
              Os cortes abaixo estão
              {escopo === 'uf' ? ' na visão do estado' : ' na visão do município'} — as
              réguas mudam entre as duas.
            </p>

            {/* De onde vem o dado, ANTES das camadas: sem isto o leitor passa o painel
                inteiro sem saber se olha para censo, para concorrente ou para chute. */}
            <section style={{ marginTop: 15 }}>
              <Eyebrow cor="var(--tx-muted)">de onde vêm os dados</Eyebrow>
              <div style={{ marginTop: 9, display: 'flex', flexDirection: 'column', gap: 9 }}>
                {dados.fontes.map((f) => (
                  <div
                    key={f.nome}
                    style={{
                      padding: '9px 11px',
                      borderRadius: 'var(--r-md)',
                      background: 'var(--surf-raised)',
                      border: '1px solid var(--line-soft)',
                    }}
                  >
                    <div
                      style={{ font: '600 11.5px/1.3 var(--f-ui)', color: 'var(--tx-max)' }}
                    >
                      {f.nome}
                    </div>
                    <p
                      style={{
                        margin: '4px 0 0',
                        font: '400 11px/1.55 var(--f-ui)',
                        color: 'var(--tx-sub)',
                      }}
                    >
                      {f.detalhe}
                    </p>
                  </div>
                ))}
              </div>
            </section>

            {dados.camadas.map((c) => (
              <Camada key={c.n} camada={c} escopo={escopo} ativa={c.n === passoAtivo} />
            ))}

            <section style={{ padding: '15px 0 0', borderTop: '1px solid var(--line-soft)' }}>
              <Eyebrow cor="var(--tx-muted)">parâmetros do modelo</Eyebrow>
              <div style={{ marginTop: 9, display: 'flex', flexDirection: 'column', gap: 5 }}>
                {dados.parametros.map((p) => (
                  <div
                    key={p.nome}
                    style={{
                      display: 'flex',
                      alignItems: 'baseline',
                      justifyContent: 'space-between',
                      gap: 10,
                      font: '400 11.5px/1.4 var(--f-ui)',
                      color: 'var(--tx-sub)',
                    }}
                  >
                    <span>{p.nome}</span>
                    <span
                      className="num"
                      style={{
                        font: '600 11.5px/1.4 var(--f-num)',
                        color: 'var(--tx-max)',
                        whiteSpace: 'nowrap',
                      }}
                    >
                      {p.valor}
                    </span>
                  </div>
                ))}
              </div>
              <p
                style={{
                  margin: '11px 0 0',
                  font: '400 10.5px/1.5 var(--f-ui)',
                  color: 'var(--tx-muted)',
                }}
              >
                Estes valores vêm do servidor, não estão escritos nesta tela: mudar a régua
                no backend muda o funil e este texto junto.
              </p>
            </section>
          </>
        )}
      </div>
    </aside>
  )
}
