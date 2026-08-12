import type { ReactNode } from 'react'

import { reguaDeConcorrentes, semDistancia } from '../lib/concorrentes'
import { alunos, num } from '../lib/format'
import {
  SCORE_MAX,
  composicaoMercado,
  faixaDaDistribuicao,
  fracaoDoScore,
} from '../lib/medidor'
import type { PontoDistribuicao } from '../lib/types'

/**
 * As peças VISUAIS da ficha: medidor de score, barra do mercado, régua de dispersão.
 *
 * Existem porque uma grade de KPIs responde "quanto é" e não responde "isso é muito?".
 * Cada peça aqui só aparece quando o dado sustenta o desenho — a decisão de aparecer ou
 * não mora em `lib/medidor.ts`, testada. Nenhuma delas colore por limiar de qualidade:
 * o produto não publica corte de "residual bom", e um verde a partir de um número que
 * ninguém aprovou viraria recomendação de abertura.
 */

/**
 * Título das leituras visuais. Mesmo peso do título de um bloco de KPI — a peça visual
 * não é um adorno abaixo dos números, é o conteúdo principal do bloco.
 */
function Titulo({ children }: { children: ReactNode }) {
  return (
    <span style={{ font: '600 12.5px/1.2 var(--f-ui)', color: 'var(--tx-strong)' }}>{children}</span>
  )
}

/**
 * Número de APOIO: rótulo e valor na mesma linha, tipo pequeno.
 *
 * Substitui o card de KPI onde há gráfico. A hierarquia estava invertida (pedido do Juan,
 * 2026-08-12): o número em 24px dominava o bloco e a barra virava rodapé, quando é a
 * barra que responde "isso é muito?". O número continua inteiro e auditável — só deixa
 * de ser a manchete.
 */
export function NumeroApoio({ rotulo, valor }: { rotulo: string; valor: string }) {
  return (
    <span style={{ display: 'inline-flex', alignItems: 'baseline', gap: 6, minWidth: 0 }}>
      <span style={{ font: '400 10.5px/1.3 var(--f-ui)', color: 'var(--tx-sub)' }}>{rotulo}</span>
      <span
        className="num"
        style={{ font: '600 12px/1.3 var(--f-num)', color: 'var(--tx-strong)', whiteSpace: 'nowrap' }}
      >
        {valor}
      </span>
    </span>
  )
}

/** Fila de números de apoio, quebrando em telas estreitas. */
export function FilaApoio({ children }: { children: ReactNode }) {
  return (
    <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px 18px' }}>{children}</div>
  )
}

/** Medidor 0-100 para os scores do produto. Some quando não há score. */
export function MedidorScore({
  rotulo,
  valor,
  nota,
}: {
  rotulo: string
  valor: number | null | undefined
  nota?: string
}) {
  const fr = fracaoDoScore(valor)
  if (fr == null) return null
  return (
    <div style={{ display: 'grid', gap: 7 }}>
      <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', gap: 10 }}>
        <Titulo>{rotulo}</Titulo>
        <span className="num" style={{ font: '700 20px/1 var(--f-num)', color: 'var(--tx-max)' }}>
          {num(valor, 1)}
          <span style={{ font: '400 11px/1 var(--f-num)', color: 'var(--tx-sub)' }}>
            {' '}
            / {SCORE_MAX}
          </span>
        </span>
      </div>
      {/* Barra ALTA: é a peça que se lê primeiro no bloco, não um fio abaixo do número. */}
      <div style={{ height: 12, borderRadius: 6, background: 'var(--surf-pending)', overflow: 'hidden' }}>
        <div
          style={{
            width: `${Math.round(fr * 100)}%`,
            height: '100%',
            borderRadius: 6,
            /* Cor ÚNICA em toda a escala. Um gradiente de vermelho a verde afirmaria que
               40 é ruim e 80 é bom — corte que o produto não publica para estes scores. */
            background: 'var(--ac)',
          }}
        />
      </div>
      {nota && <span style={{ font: '400 10.5px/1.35 var(--f-ui)', color: 'var(--tx-sub)' }}>{nota}</span>}
    </div>
  )
}

/**
 * O mercado repartido: quanto já é atendido e quanto sobra.
 *
 * A barra diz o que dois KPIs lado a lado não dizem sem conta de cabeça — se o residual
 * é a maior parte do mercado ou uma sobra marginal.
 */
export function BarraMercado({
  sam,
  residual,
}: {
  sam: number | null | undefined
  residual: number | null | undefined
}) {
  const c = composicaoMercado(sam, residual)
  if (!c) return null
  const pct = Math.round(c.fracaoDisponivel * 100)
  return (
    <div style={{ display: 'grid', gap: 8 }}>
      <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', gap: 10 }}>
        <Titulo>Do mercado potencial, quanto sobra</Titulo>
        <span className="num" style={{ font: '700 20px/1 var(--f-num)', color: 'var(--tx-max)' }}>
          {pct}
          <span style={{ font: '400 11px/1 var(--f-num)', color: 'var(--tx-sub)' }}>%</span>
        </span>
      </div>
      <div style={{ display: 'flex', height: 16, borderRadius: 8, overflow: 'hidden', background: 'var(--surf-pending)' }}>
        <div
          title={`Já atendido: ${alunos(c.atendido)}`}
          style={{ width: `${100 - pct}%`, background: 'var(--tx-rank)' }}
        />
        <div
          title={`Disponível: ${alunos(c.disponivel)}`}
          style={{ width: `${pct}%`, background: 'var(--ac)' }}
        />
      </div>
      <div style={{ display: 'flex', gap: 14, flexWrap: 'wrap' }}>
        <Legenda cor="var(--tx-rank)" rotulo="Já atendido" valor={alunos(c.atendido)} />
        <Legenda cor="var(--ac)" rotulo="Sobra" valor={alunos(c.disponivel)} forte />
      </div>
    </div>
  )
}

function Legenda({
  cor,
  rotulo,
  valor,
  forte,
}: {
  cor: string
  rotulo: string
  valor: string
  forte?: boolean
}) {
  return (
    <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
      <span aria-hidden style={{ width: 9, height: 9, borderRadius: 3, background: cor, flexShrink: 0 }} />
      <span style={{ font: '400 10.5px/1.2 var(--f-ui)', color: 'var(--tx-sub)' }}>{rotulo}</span>
      <span
        className="num"
        style={{
          font: `${forte ? 700 : 500} 11px/1.2 var(--f-num)`,
          color: forte ? 'var(--tx-max)' : 'var(--tx-soft)',
        }}
      >
        {valor}
      </span>
    </span>
  )
}

/**
 * Os concorrentes do raio, cada um no ponto em que cai entre o imóvel e a borda.
 *
 * "4 concorrentes no raio" nao separa dois territorios opostos: quatro academias coladas
 * na esquina, ou quatro na borda de 1 km. O eixo mostra qual dos dois e' o caso.
 *
 * SEM COR POR REDE, de propósito. O mapa colore os pins com os ícones que a API publica
 * (`pins.icones`), e o payload do ponto não traz essa tabela — inventar uma paleta aqui
 * faria a mesma rede aparecer de uma cor no mapa e de outra na ficha, na mesma tela.
 */
export function ReguaConcorrentes({
  lista,
  raioKm,
}: {
  lista: { rede: string | null; dist_km: number | null }[] | null | undefined
  raioKm: number
}) {
  const pontos = reguaDeConcorrentes(lista, raioKm)
  const ocultos = semDistancia(lista)
  if (pontos.length === 0 && ocultos === 0) return null

  return (
    <div style={{ display: 'grid', gap: 9 }}>
      <Titulo>Onde eles estão, do imóvel até a borda do raio</Titulo>

      {pontos.length > 0 && (
        <div style={{ display: 'grid', gap: 7 }}>
          {/* UMA LINHA POR CONCORRENTE. O nome tem coluna própria à esquerda e a distância
              à direita — texto nunca disputa espaço com texto, que era o defeito do eixo
              único com rótulos empilhados. */}
          {pontos.map((p, i) => (
            <div
              key={`${p.rede}-${i}`}
              style={{
                display: 'grid',
                gridTemplateColumns: 'minmax(64px, 84px) 1fr auto',
                alignItems: 'center',
                gap: 10,
              }}
            >
              <span
                title={p.rede}
                style={{
                  font: '600 11px/1.2 var(--f-ui)',
                  color: 'var(--tx-soft)',
                  overflow: 'hidden',
                  textOverflow: 'ellipsis',
                  whiteSpace: 'nowrap',
                }}
              >
                {p.rede}
              </span>
              <span
                aria-hidden
                style={{ position: 'relative', height: 10, display: 'block' }}
              >
                <span
                  style={{
                    position: 'absolute',
                    left: 0,
                    right: 0,
                    top: 4,
                    height: 2,
                    borderRadius: 1,
                    background: 'var(--line-soft)',
                  }}
                />
                {/* O traço cheio vai do imóvel até o concorrente: o comprimento É a
                    distância, e é ele que se lê de relance, não a posição do disco. */}
                <span
                  style={{
                    position: 'absolute',
                    left: 0,
                    top: 4,
                    width: `${p.fracao * 100}%`,
                    height: 2,
                    borderRadius: 1,
                    background: 'var(--ac-a30)',
                  }}
                />
                <span
                  style={{
                    position: 'absolute',
                    left: `calc(${p.fracao * 100}% - 5px)`,
                    top: 0,
                    width: 10,
                    height: 10,
                    borderRadius: '50%',
                    background: 'var(--ac)',
                  }}
                />
              </span>
              <span
                className="num"
                style={{
                  font: '600 11.5px/1.2 var(--f-num)',
                  color: 'var(--tx-strong)',
                  fontVariantNumeric: 'tabular-nums',
                }}
              >
                {num(p.dist, 2)} km
              </span>
            </div>
          ))}

          {/* A régua do eixo, uma vez só, embaixo de todas as linhas. */}
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'minmax(64px, 84px) 1fr auto',
              gap: 10,
              marginTop: 1,
            }}
          >
            <span />
            <span style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span style={{ font: '400 9.5px/1 var(--f-ui)', color: 'var(--tx-off)' }}>
                o imóvel
              </span>
              <span className="num" style={{ font: '400 9.5px/1 var(--f-num)', color: 'var(--tx-off)' }}>
                {num(raioKm * 1000)} m
              </span>
            </span>
            <span />
          </div>
        </div>
      )}

      {/* A diferença entre o KPI e o desenho é DECLARADA: contagem 4 com 3 pontos na
          régua, em silêncio, lê-se como defeito. */}
      {ocultos > 0 && (
        <span style={{ font: '400 10.5px/1.4 var(--f-ui)', color: 'var(--tx-sub)' }}>
          {ocultos === 1
            ? '1 concorrente sem distância medida não aparece na régua — segue contado acima.'
            : `${ocultos} concorrentes sem distância medida não aparecem na régua — seguem contados acima.`}
        </span>
      )}
    </div>
  )
}

/**
 * A régua setor a setor, com a mediana marcada.
 *
 * A ficha mostra a MÉDIA do raio, e média esconde território dividido: dois pontos com a
 * mesma média podem ser lugares completamente diferentes. Os extremos e a mediana já vêm
 * no payload — faltava mostrá-los.
 */
export function ReguaDispersao({
  rotulo,
  dist,
  formatar = (v: number) => num(v),
}: {
  rotulo: string
  dist: PontoDistribuicao | null | undefined
  formatar?: (v: number) => string
}) {
  const f = faixaDaDistribuicao(dist)
  if (!f) return null
  return (
    <div style={{ display: 'grid', gap: 5 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', gap: 10 }}>
        <span style={{ font: '500 10.5px/1.2 var(--f-ui)', color: 'var(--tx-label)' }}>{rotulo}</span>
        <span className="num" style={{ font: '500 10.5px/1.2 var(--f-num)', color: 'var(--tx-sub)' }}>
          mediana {formatar(f.p50)}
        </span>
      </div>
      <div style={{ position: 'relative', height: 6, borderRadius: 3, background: 'var(--surf-pending)' }}>
        <div style={{ position: 'absolute', inset: 0, borderRadius: 3, background: 'var(--line-mid)' }} />
        {/* A marca da mediana, e não uma barra que preenche: o que se lê aqui é ONDE o
            meio cai entre os extremos, não "quanto" de alguma coisa. */}
        <div
          aria-hidden
          style={{
            position: 'absolute',
            left: `calc(${Math.round(f.posicaoMediana * 100)}% - 1px)`,
            top: -3,
            width: 2,
            height: 12,
            borderRadius: 1,
            background: 'var(--tx-max)',
          }}
        />
      </div>
      <div style={{ display: 'flex', justifyContent: 'space-between' }}>
        <span className="num" style={{ font: '400 9.5px/1 var(--f-num)', color: 'var(--tx-off)' }}>
          {formatar(f.min)}
        </span>
        <span className="num" style={{ font: '400 9.5px/1 var(--f-num)', color: 'var(--tx-off)' }}>
          {formatar(f.max)}
        </span>
      </div>
    </div>
  )
}
