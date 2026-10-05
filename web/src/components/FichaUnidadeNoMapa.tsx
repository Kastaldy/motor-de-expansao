import { useEffect, useState, type ReactNode } from 'react'

import {
  api,
  baixar,
  EXPORTS_REDE_ATIVOS,
  MOTIVO_EXPORTS_DESLIGADOS,
  type ApiError,
} from '../lib/api'
import { rotuloDaRede } from '../lib/concorrentes'
import {
  ROTULO_FONTE,
  comodidadesDeclaradas,
  estadoDasComodidades,
  imagemDoConcorrente,
  modalidadesDoCanal,
  nomeDoConcorrente,
  planosDoConcorrente,
} from '../lib/ficha-unidade'
import { alunos, brl, distanciaCurta, num, renda } from '../lib/format'
import type {
  PontoPayload,
  RedeComodidadesCanal,
  RedeFicha,
  RedeMapaConcorrente,
  RedePlanosEntorno,
  RedeUnidadeInteligencia,
} from '../lib/types'
import IconeComodidade from './IconeComodidade'
import { CardPainel, LinhaTabela, Pill, TituloSecao } from './PecasPainel'
import { Botao } from './primitives'

/**
 * A ficha de uma UNIDADE da Ultra dentro da janela flutuante do Mapa Territorial —
 * aberta pelo seletor UNIDADES do cabeçalho ou pelo clique no pin da unidade (pedido do Juan,
 * 2026-10-01).
 *
 * É uma leitura CURTA, para ser lida ao lado do mapa: quantos alunos a unidade tem, como
 * é o entorno dela e, com mais peso, quem concorre ali — em que agregador cada academia
 * está, por quanto, e o que ela oferece. A ficha completa (série, funil, diagnóstico)
 * continua sendo a página da Visão Executiva; esta não a substitui.
 *
 * NÃO HÁ ROTA NOVA. Tudo sai de três leituras que já existiam: a ficha da rede
 * (`/api/rede/unidade/{id}`), a inteligência dela (`.../inteligencia`) e o censo do ponto
 * (`/api/ponto`). Cada bloco carrega e falha SOZINHO: a rede fora do ar não apaga o
 * entorno, e vice-versa.
 *
 * DOIS RAIOS na mesma janela, e cada número diz o seu: o entorno (renda, densidade) é o
 * raio de 1 km do Relatório Pontual; a concorrência é o de 2 km da ficha da rede.
 */
export default function FichaUnidadeNoMapa({ unidadeId }: { unidadeId: string }) {
  const [ficha, setFicha] = useState<RedeFicha | null>(null)
  const [intel, setIntel] = useState<RedeUnidadeInteligencia | null>(null)
  const [ponto, setPonto] = useState<PontoPayload | null>(null)
  const [erroFicha, setErroFicha] = useState<string | null>(null)
  const [erroIntel, setErroIntel] = useState<string | null>(null)
  const [erroPonto, setErroPonto] = useState(false)
  const [baixando, setBaixando] = useState(false)
  const [erroPdf, setErroPdf] = useState<string | null>(null)

  const gerarRelatorio = async () => {
    setBaixando(true)
    setErroPdf(null)
    try {
      const { blob, filename } = await api.redeUnidadeConcorrenciaPdf(unidadeId)
      baixar(blob, filename)
    } catch (e) {
      setErroPdf((e as ApiError).message)
    } finally {
      setBaixando(false)
    }
  }

  useEffect(() => {
    let vivo = true
    setFicha(null)
    setIntel(null)
    setPonto(null)
    setErroFicha(null)
    setErroIntel(null)
    setErroPonto(false)
    setErroPdf(null)

    api
      .redeUnidade(unidadeId)
      .then((f) => {
        if (!vivo) return
        setFicha(f)
        const { lat, lng } = f.unidade
        if (lat == null || lng == null) return
        // O censo do ponto só pode ser pedido depois da coordenada, que vem na ficha.
        api
          .ponto(lat, lng)
          .then((p) => vivo && setPonto(p))
          .catch(() => vivo && setErroPonto(true))
      })
      .catch((e: Error) => vivo && setErroFicha(e.message))
    api
      .redeUnidadeInteligencia(unidadeId)
      .then((i) => vivo && setIntel(i))
      .catch((e: Error) => vivo && setErroIntel(e.message))

    return () => {
      vivo = false
    }
  }, [unidadeId])

  const semPonto = ficha != null && (ficha.unidade.lat == null || ficha.unidade.lng == null)
  const concorrentes = intel?.mapa?.concorrentes ?? []

  return (
    <div style={{ display: 'grid', gap: 18 }}>
      {/* ---- Ação: o relatório da unidade ----
          Baixa em PDF o que esta janela mostra (alunos, região e cada concorrente com o
          que oferece). Só acende com a ficha carregada: sem ela não há o que imprimir.
          Obedece à MESMA chave dos exports da Visão Executiva (`EXPORTS_REDE_ATIVOS`,
          desligada pelo Felipe em 15/09): é dado da rede saindo em arquivo, e uma porta
          nova ao lado da que foi fechada furaria a decisão. Religa junto com as outras. */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12 }}>
        <span style={{ font: '400 12px/1.4 var(--f-ui)', color: 'var(--tx-sub)' }}>
          {ficha
            ? [ficha.unidade.cidade, ficha.unidade.uf].filter(Boolean).join(' · ')
            : 'Carregando a unidade…'}
        </span>
        <Botao
          disabled={!EXPORTS_REDE_ATIVOS || !ficha || baixando}
          title={EXPORTS_REDE_ATIVOS ? undefined : MOTIVO_EXPORTS_DESLIGADOS}
          onClick={gerarRelatorio}
        >
          {baixando ? 'Gerando…' : 'Gerar relatório'}
        </Botao>
      </div>
      {erroPdf && <Nota>{erroPdf}</Nota>}

      {semPonto && (
        <Nota>
          Esta unidade não tem coordenada cadastrada: o mapa abriu no estado dela, e as
          leituras de entorno e de concorrência dependem do ponto.
        </Nota>
      )}

      {/* ---------------- Alunos ---------------- */}
      <section>
        <TituloSecao titulo="Alunos" nota={ficha ? `ref. ${ficha.referencia}` : undefined} />
        {erroFicha ? (
          <Nota>Não foi possível carregar os alunos da unidade. {erroFicha}</Nota>
        ) : (
          <>
            <div style={GRADE_3}>
              <Numero rotulo="Ativos" valor={ficha ? alunos(ficha.metricas.ativos?.atual) : '…'} />
              <Numero rotulo="Pagantes" valor={ficha ? alunos(ficha.metricas.pagantes?.atual) : '…'} />
              <Numero
                rotulo="Agregadores"
                valor={ficha ? alunos(ficha.metricas.agregadores?.atual) : '…'}
              />
            </div>
            <CardPainel style={{ padding: 0, marginTop: 10 }}>
              <LinhaTabela rotulo="Alunos via Wellhub" valor={alunos(intel?.agregadores?.wellhub)} />
              <LinhaTabela rotulo="Alunos via TotalPass" valor={alunos(intel?.agregadores?.totalpass)} />
              <LinhaTabela rotulo="Plano da unidade no Wellhub" valor={planoDaUltra(intel?.planos_wellhub)} />
              <LinhaTabela rotulo="Plano da unidade no TotalPass" valor={planoDaUltra(intel?.planos)} />
            </CardPainel>
          </>
        )}
      </section>

      {/* ---------------- Entorno (1 km) ---------------- */}
      <section>
        <TituloSecao titulo="Região" nota={`raio de ${num(ponto?.raio_km ?? 1, 1)} km`} />
        {semPonto ? (
          <Nota>Sem coordenada, não há entorno para ler.</Nota>
        ) : erroPonto ? (
          <Nota>Não foi possível ler o censo do entorno.</Nota>
        ) : ponto && !ponto.censo.disponivel ? (
          <Nota>{ponto.censo.motivo ?? 'Censo do entorno indisponível nesta base.'}</Nota>
        ) : (
          <div style={GRADE_2}>
            <Numero
              rotulo="Renda média domiciliar"
              valor={ponto ? renda(ponto.censo.renda_media_domiciliar) : '…'}
            />
            <Numero
              rotulo="Renda per capita"
              valor={ponto ? renda(ponto.censo.renda_per_capita) : '…'}
            />
            <Numero
              rotulo="Densidade"
              valor={ponto ? num(ponto.censo.densidade_hab_km2) : '…'}
              unidade="hab/km²"
            />
            <Numero rotulo="População" valor={ponto ? num(ponto.censo.populacao) : '…'} unidade="hab" />
          </div>
        )}
      </section>

      {/* ---------------- Concorrentes (2 km) ---------------- */}
      <section>
        <TituloSecao
          titulo="Concorrentes"
          nota={intel?.mapa ? `${concorrentes.length} a ${distanciaCurta(intel.mapa.raio_m)}` : undefined}
        />
        {erroIntel ? (
          <Nota>Não foi possível carregar a concorrência. {erroIntel}</Nota>
        ) : !intel ? (
          <Nota>Carregando as academias do entorno…</Nota>
        ) : !intel.mapa ? (
          <Nota>Sem coordenada, não há concorrência para ler.</Nota>
        ) : concorrentes.length === 0 ? (
          <Nota>Nenhuma academia mapeada a {distanciaCurta(intel.mapa.raio_m)} desta unidade.</Nota>
        ) : (
          <>
            {concorrentes.every((c) => estadoDasComodidades(c) === 'indisponivel') && (
              <Nota>
                Comodidades indisponíveis: a base do que cada academia oferece não foi carregada
                neste ambiente.
              </Nota>
            )}
            <div style={{ display: 'grid', gap: 10, marginTop: 10 }}>
              {concorrentes.map((c, i) => (
                <CardConcorrente
                  key={`${c.lat}-${c.lng}-${i}`}
                  c={c}
                  imagem={imagemDoConcorrente(c, intel.mapa?.logos)}
                />
              ))}
            </div>
          </>
        )}
      </section>
    </div>
  )
}

/* ---------------------------------------------------------------------------
   Peças
   --------------------------------------------------------------------------- */

const GRADE_3: React.CSSProperties = { display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 10 }
const GRADE_2: React.CSSProperties = { display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 10 }

/** "TP 2 · R$ 199,90", ou o motivo de não haver plano — nunca um traço mudo. */
function planoDaUltra(planos: RedePlanosEntorno | undefined): string {
  if (!planos) return '…'
  if (!planos.disponivel) return 'Indisponível'
  if (!planos.ultra) return 'Não identificado'
  return `${planos.ultra.plano} · ${brl(planos.ultra.preco, false, 2)}`
}

function Numero({ rotulo, valor, unidade }: { rotulo: string; valor: string; unidade?: string }) {
  return (
    <CardPainel style={{ padding: '12px 14px' }}>
      <div style={{ font: '400 11px/1.3 var(--f-ui)', color: 'var(--tx-label)' }}>{rotulo}</div>
      <div
        className="num"
        style={{ font: '600 20px/1.2 var(--f-num)', color: 'var(--tx-max)', marginTop: 4 }}
      >
        {valor}
        {unidade && (
          <span style={{ font: '400 10.5px/1 var(--f-num)', color: 'var(--tx-sub)', marginLeft: 5 }}>
            {unidade}
          </span>
        )}
      </div>
    </CardPainel>
  )
}

function Nota({ children }: { children: ReactNode }) {
  return (
    <p style={{ margin: 0, font: '400 12px/1.5 var(--f-ui)', color: 'var(--tx-narrative)' }}>
      {children}
    </p>
  )
}

function Etiqueta({ children, forte = false }: { children: ReactNode; forte?: boolean }) {
  return (
    <span
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: 5,
        padding: '4px 8px',
        borderRadius: 999,
        border: `1px solid ${forte ? 'var(--ops)' : 'var(--line-soft)'}`,
        font: '500 11px/1 var(--f-ui)',
        color: forte ? 'var(--ops-text)' : 'var(--tx-soft)',
        whiteSpace: 'nowrap',
      }}
    >
      {children}
    </span>
  )
}

/** Uma academia do entorno: quem é, a que distância, em que agregador e o que oferece. */
function CardConcorrente({ c, imagem }: { c: RedeMapaConcorrente; imagem: string | null }) {
  const planos = planosDoConcorrente(c)
  const estado = estadoDasComodidades(c)
  return (
    <CardPainel style={{ padding: '12px 14px', display: 'grid', gap: 9 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
        {/* A imagem da academia: logo da rede ou arte do app que a lista. Decorativa (o nome
            está ao lado), por isso `alt` vazio; sem imagem, o quadro fica neutro. */}
        {imagem ? (
          <img
            src={imagem}
            alt=""
            width={40}
            height={40}
            style={{ display: 'block', flexShrink: 0, borderRadius: 8, objectFit: 'cover' }}
          />
        ) : (
          <span style={{ width: 40, height: 40, borderRadius: 8, background: 'var(--ac-a12)', flexShrink: 0 }} />
        )}
        <span style={{ flex: 1, font: '600 13px/1.3 var(--f-ui)', color: 'var(--tx-max)', minWidth: 0 }}>
          {nomeDoConcorrente(c)}
        </span>
        <span className="num" style={{ font: '500 11.5px/1 var(--f-num)', color: 'var(--tx-sub)', flexShrink: 0 }}>
          {distanciaCurta(c.distancia_m)}
        </span>
      </div>

      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, alignItems: 'center' }}>
        <Pill
          texto={c.classe === 'cadeia' ? `Rede · ${rotuloDaRede(c.rede)}` : 'Independente'}
          cor="var(--tx-soft)"
        />
        {c.estudio && <Pill texto="Estúdio" cor="var(--tx-sub)" />}
      </div>

      {/* Agregadores: plano exigido e preço da ASSINATURA do app — não é mensalidade de balcão. */}
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
        {planos.length === 0 ? (
          <span style={{ font: '400 11.5px/1.4 var(--f-ui)', color: 'var(--tx-sub)' }}>
            Sem plano de Wellhub ou TotalPass identificado.
          </span>
        ) : (
          planos.map((p) => (
            <Etiqueta key={p.agregador} forte>
              {p.rotulo} · {p.plano}
              {p.preco != null ? ` · ${brl(p.preco, false, 2)}` : ''}
            </Etiqueta>
          ))
        )}
      </div>

      {estado === 'nao_coletada' && (
        <span style={{ font: '400 11.5px/1.4 var(--f-ui)', color: 'var(--tx-sub)' }}>
          Comodidades não coletadas para esta academia.
        </span>
      )}
      {estado === 'coletada' && (
        <div style={{ display: 'grid', gap: 7 }}>
          <Canal titulo="No site da rede" canal={c.comodidades?.recorrente ?? null} />
          <Canal titulo="No agregador" canal={c.comodidades?.agregador ?? null} />
        </div>
      )}
    </CardPainel>
  )
}

/**
 * O que UM canal declara. O site da rede e o agregador ficam em linhas separadas de
 * propósito: são leituras diferentes da mesma academia, e fundi-las apagaria a diferença.
 * Item ausente é "não declarado" — a fonte nunca afirma o que a academia não tem.
 */
function Canal({ titulo, canal }: { titulo: string; canal: RedeComodidadesCanal | null }) {
  if (!canal) return null
  const itens = comodidadesDeclaradas(canal)
  const modalidades = modalidadesDoCanal(canal)
  const fonte = ROTULO_FONTE[canal.fonte] ?? canal.fonte
  return (
    <div style={{ display: 'grid', gap: 5 }}>
      <span
        className="num"
        style={{
          font: '400 9.5px/1 var(--f-num)',
          letterSpacing: '.1em',
          textTransform: 'uppercase',
          color: 'var(--tx-sub)',
        }}
      >
        {titulo}
        {canal.fonte !== 'site' ? ` · ${fonte}` : ''}
      </span>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
        {itens.length === 0 ? (
          <span style={{ font: '400 11.5px/1.4 var(--f-ui)', color: 'var(--tx-sub)' }}>
            Nenhum dos itens acompanhados foi declarado.
          </span>
        ) : (
          itens.map(({ item, rotulo }) => (
            <Etiqueta key={item}>
              <IconeComodidade item={item} tamanho={13} />
              {rotulo}
            </Etiqueta>
          ))
        )}
      </div>
      {canal.lista.length > 0 && (
        <details>
          <summary style={{ font: '400 11px/1.4 var(--f-ui)', color: 'var(--tx-label)', cursor: 'pointer' }}>
            Tudo que a fonte declara ({canal.lista.length})
          </summary>
          <p style={{ margin: '5px 0 0', font: '400 11.5px/1.5 var(--f-ui)', color: 'var(--tx-narrative)' }}>
            {canal.lista.join(' · ')}
          </p>
        </details>
      )}
      {/* Modalidades: só o agregador as publica. Canal sem nenhuma não ganha linha — dizer
          "sem modalidades" afirmaria uma ausência que a fonte não declara. */}
      {modalidades.length > 0 && (
        <details>
          <summary style={{ font: '400 11px/1.4 var(--f-ui)', color: 'var(--tx-label)', cursor: 'pointer' }}>
            Modalidades ({modalidades.length})
          </summary>
          <p style={{ margin: '5px 0 0', font: '400 11.5px/1.5 var(--f-ui)', color: 'var(--tx-narrative)' }}>
            {modalidades.join(' · ')}
          </p>
        </details>
      )}
    </div>
  )
}
