import { useState } from 'react'

import BotaoInicio from '../components/BotaoInicio'
import CampoPonto from '../components/CampoPonto'
import { Aviso, Chip, Eyebrow, Glass, Kpi, Spinner } from '../components/primitives'
import { api, ApiError } from '../lib/api'
import { linkGoogleMaps, type EntradaClassificada } from '../lib/entrada-ponto'
import { num } from '../lib/format'
import type { BlocoOpcional, PontoPayload } from '../lib/types'

/**
 * Modo 1 — analise de um PONTO/IMOVEL.
 *
 * LAYOUT DE FICHA, nao o do mapa: sem funil e sem StepperBar. O funil e' um recorte
 * TERRITORIAL (estado -> municipio -> hexes) e nao diz nada sobre um endereco unico.
 *
 * O mapa NAO monta aqui. Enquanto a tela ativa nao for 'mapa' com UF preenchida, deck.gl
 * e MapLibre nem instanciam — o modo custa zero WebGL e zero leitura de particao de UF.
 *
 * ESTADO VAZIO POR BLOCO. Cada bloco pergunta ao SERVIDOR se tem dado (`disponivel`) e
 * mostra o `motivo` que ele devolveu. A cadeia de dados degrada em silencio por desenho
 * (staging ausente -> `(None, None)` sem excecao), entao um bloco que sumisse sozinho
 * seria lido como defeito. Nenhum texto de estado vazio e' inventado aqui.
 */
export default function PontoScreen({ onInicio }: { onInicio: () => void }) {
  const [carregando, setCarregando] = useState(false)
  const [erro, setErro] = useState<string | null>(null)
  const [ficha, setFicha] = useState<PontoPayload | null>(null)

  async function resolver(entrada: EntradaClassificada, texto: string) {
    setCarregando(true)
    setErro(null)
    try {
      // O front resolve coordenada e link longo sozinho; o resto custa uma ida ao
      // servidor (expandir redirect do link curto, ou geocodificar endereço).
      let coord = entrada.coord
      if (!coord) {
        const r = await api.resolverPonto(texto)
        if (!r.found || r.lat == null || r.lng == null) {
          setErro(r.motivo ?? 'Não consegui resolver esse endereço.')
          setFicha(null)
          return
        }
        coord = { lat: r.lat, lng: r.lng }
      }
      setFicha(await api.ponto(coord.lat, coord.lng))
    } catch (e) {
      setErro(e instanceof ApiError ? e.message : 'Falha ao analisar o ponto.')
      setFicha(null)
    } finally {
      setCarregando(false)
    }
  }

  return (
    <div
      style={{
        position: 'absolute',
        inset: 0,
        display: 'flex',
        flexDirection: 'column',
        overflow: 'hidden',
      }}
    >
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
          Análise de ponto
        </h1>
        {ficha && (
          <Chip>
            raio de {num(ficha.raio_km * 1000)} m · {ficha.censo.n_setores ?? '—'} setores
          </Chip>
        )}
      </header>

      <div style={{ flex: 1, overflowY: 'auto', padding: '16px' }}>
        <div style={{ maxWidth: 1100, margin: '0 auto', display: 'grid', gap: 16 }}>
          <Glass style={{ padding: 18 }}>
            <CampoPonto onResolver={resolver} ocupado={carregando} erro={erro} />
          </Glass>

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
              <Spinner /> Lendo os setores censitários do entorno…
            </p>
          )}

          {!ficha && !carregando && !erro && (
            <Aviso
              titulo="Cole um ponto para começar"
              corpo="Funciona com o link do Google Maps (inclusive o curto que o celular compartilha), um endereço escrito ou o par de coordenadas. A leitura sai do Censo 2022 do IBGE, no raio de 1,0 km — a mesma régua do Relatório Pontual."
            />
          )}

          {ficha && <Ficha ficha={ficha} />}
        </div>
      </div>
    </div>
  )
}

function Ficha({ ficha }: { ficha: PontoPayload }) {
  const { local, censo, concorrencia, mercado } = ficha

  return (
    <div style={{ display: 'grid', gap: 16 }}>
      {/* ---------------- Identificação ---------------- */}
      <Glass style={{ padding: 18, display: 'grid', gap: 10 }}>
        <Eyebrow dot>Ponto analisado</Eyebrow>
        <div
          style={{
            font: '600 20px/1.2 var(--f-ui)',
            color: 'var(--tx-max)',
            letterSpacing: '-.01em',
          }}
        >
          {local.bairro ?? 'Local sem bairro identificado'}
        </div>
        <div style={{ font: '400 13px/1.4 var(--f-ui)', color: 'var(--tx-narrative)' }}>
          {[local.municipio, local.uf].filter(Boolean).join(' · ')}
        </div>
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
          <Chip>hex {ficha.hex_id}</Chip>
          <Chip>
            {ficha.lat.toFixed(5)}, {ficha.lng.toFixed(5)}
          </Chip>
          {/* Link de SAÍDA: o operador confere no próprio Maps onde o pino caiu — é a
              única forma de ele ver que a coordenada resolvida é mesmo o imóvel dele. */}
          <a
            href={linkGoogleMaps(ficha.lat, ficha.lng)}
            target="_blank"
            rel="noreferrer"
            style={{
              font: '600 11.5px/1 var(--f-ui)',
              color: 'var(--ac-text)',
              textDecoration: 'underline',
            }}
          >
            Abrir no Google Maps ↗
          </a>
        </div>
      </Glass>

      {/* ---------------- Socioeconomia (sempre disponível) ---------------- */}
      <Secao titulo="Quem mora em volta" nota={`Censo 2022 (IBGE) · raio de ${num(ficha.raio_km * 1000)} m`}>
        <GradeKpi>
          <Kpi label="População" valor={num(censo.populacao)} />
          <Kpi label="Domicílios" valor={num(censo.domicilios)} />
          <Kpi label="Renda per capita" valor={comPrefixo('R$ ', censo.renda_per_capita)} />
          <Kpi label="Renda domiciliar" valor={comPrefixo('R$ ', censo.renda_media_domiciliar)} />
          <Kpi label="Densidade" valor={comSufixo(censo.densidade_hab_km2, ' hab/km²')} />
          <Kpi label="Score socioeconômico" valor={num(censo.score_socioeconomico, 1)} />
        </GradeKpi>
        <Rodape>
          A densidade desconta água e vazio: divide pela área de setor censitário
          realmente intersectada, não pela área do círculo.
        </Rodape>
      </Secao>

      {/* ---------------- Concorrência ---------------- */}
      <Secao titulo="Quem já disputa o aluno aqui" bloco={concorrencia}>
        <GradeKpi>
          <Kpi label="Concorrentes no raio" valor={num(concorrencia.n_concorrentes)} />
          <Kpi label="Unidades Ultra no raio" valor={num(concorrencia.n_ultra)} />
        </GradeKpi>
      </Secao>

      {/* ---------------- Mercado / residual ---------------- */}
      <Secao titulo="Quanto de mercado sobra" bloco={mercado}>
        <GradeKpi>
          <Kpi label="Mercado potencial (SAM)" valor={comSufixo(mercado.sam, ' alunos')} />
          <Kpi label="Residual disponível" valor={comSufixo(mercado.residual, ' alunos')} />
          <Kpi label="Score de residual" valor={num(mercado.score_residual, 1)} />
        </GradeKpi>
      </Secao>

      {/* ---------------- Viabilidade: ainda não ---------------- */}
      <Secao titulo="Fecha a conta?">
        <Aviso
          titulo="Viabilidade ainda não entra por aqui"
          corpo="O break-even, o payback e o teto de aluguel dependem de metragem e aluguel pedido, que este modo ainda não coleta. Por enquanto eles ficam na tela de Viabilidade, com o ponto escolhido pelo mapa."
        />
      </Secao>
    </div>
  )
}

/** Seção com estado vazio DECLARADO pelo servidor, nunca inventado aqui. */
function Secao({
  titulo,
  nota,
  bloco,
  children,
}: {
  titulo: string
  nota?: string
  bloco?: BlocoOpcional
  children: React.ReactNode
}) {
  const vazio = bloco && !bloco.disponivel
  return (
    <Glass style={{ padding: 18, display: 'grid', gap: 14 }}>
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 10, flexWrap: 'wrap' }}>
        <span style={{ font: '600 15px/1.2 var(--f-ui)', color: 'var(--tx-max)' }}>
          {titulo}
        </span>
        {nota && (
          <span style={{ font: '400 11.5px/1 var(--f-ui)', color: 'var(--tx-sub)' }}>
            {nota}
          </span>
        )}
      </div>
      {vazio ? (
        <Aviso titulo="Sem dado para este bloco" corpo={bloco.motivo ?? 'Origem não informada.'} />
      ) : (
        children
      )}
    </Glass>
  )
}

/* Prefixo/sufixo só entram quando HÁ número: "R$ —" e "— hab/km²" leem como se o
   dado existisse e valesse zero. Sem dado, fica só o travessão de `num`. */
function comPrefixo(prefixo: string, v: number | null): string {
  return v == null ? num(v) : `${prefixo}${num(v)}`
}

function comSufixo(v: number | null, sufixo: string): string {
  return v == null ? num(v) : `${num(v)}${sufixo}`
}

function GradeKpi({ children }: { children: React.ReactNode }) {
  return (
    <div
      style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))',
        gap: 12,
      }}
    >
      {children}
    </div>
  )
}

function Rodape({ children }: { children: React.ReactNode }) {
  return (
    <p style={{ font: '400 11.5px/1.5 var(--f-ui)', color: 'var(--tx-sub)', margin: 0 }}>
      {children}
    </p>
  )
}
