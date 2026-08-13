import type { ReactNode } from 'react'

import { leituraDeAglomeracao, reguaDeConcorrentes, semDistancia } from '../lib/concorrentes'
import { alunos, num } from '../lib/format'
import type { FaixaNomeada } from '../lib/faixas'
import {
  SCORE_MAX,
  composicaoMercado,
  faixaDoValor,
  fracaoDoScore,
  leituraDeSaturacao,
} from '../lib/medidor'

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
  faixas,
}: {
  rotulo: string
  valor: number | null | undefined
  nota?: string
  /**
   * Régua NOMEADA para colorir e dar veredito. É a publicada em `lib/faixas.ts` — a mesma
   * que pinta o hexágono no mapa e aparece na legenda. Sem ela o medidor fica na cor
   * neutra: colorir por um limiar escolhido no olho afirmaria bom e ruim por conta
   * própria, e na tela isso vira decisão de abertura.
   */
  faixas?: readonly FaixaNomeada[]
}) {
  const fr = fracaoDoScore(valor)
  if (fr == null) return null
  const faixa = faixas ? faixaDoValor(valor, faixas) : null
  const cor = faixa?.cor ?? 'var(--ac)'
  return (
    <div style={{ display: 'grid', gap: 7 }}>
      <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', gap: 10 }}>
        <Titulo>{rotulo}</Titulo>
        <span style={{ display: 'inline-flex', alignItems: 'baseline', gap: 8 }}>
          {/* O NOME da faixa antes do número: "Excelente" resolve na hora o que "84,2"
              não resolve, e é o mesmo rótulo que o mapa usa. */}
          {faixa && (
            <span
              style={{
                font: '700 10px/1 var(--f-ui)',
                textTransform: 'uppercase',
                letterSpacing: '.06em',
                color: faixa.cor,
                padding: '4px 7px',
                borderRadius: 6,
                background: `${faixa.cor}22`,
              }}
            >
              {faixa.nome}
            </span>
          )}
          <span className="num" style={{ font: '700 20px/1 var(--f-num)', color: 'var(--tx-max)' }}>
            {num(valor, 1)}
            <span style={{ font: '400 11px/1 var(--f-num)', color: 'var(--tx-sub)' }}>
              {' '}
              / {SCORE_MAX}
            </span>
          </span>
        </span>
      </div>
      {/* Barra ALTA: é a peça que se lê primeiro no bloco, não um fio abaixo do número. */}
      <div style={{ height: 12, borderRadius: 6, background: 'var(--surf-pending)', overflow: 'hidden' }}>
        <div style={{ width: `${Math.round(fr * 100)}%`, height: '100%', borderRadius: 6, background: cor }} />
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
  const saturacao = leituraDeSaturacao(sam, residual)
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
      {/* DÁ PARA ENTRAR? (pedido do Juan, 2026-08-13). "Sobra 900 alunos" não responde a
          pergunta seguinte — se esses 900 sustentam uma unidade ou se abrir ali já nasce
          brigando por aluno instalado. A frase vem de `leituraDeSaturacao`, por regra de
          bolso que se declara: o corte é a capacidade de UMA unidade (2.500), constante
          que o produto já publica, e o número aparece escrito na própria frase.
          NÃO é veredito de viabilidade — isso é do simulador, sobre um imóvel concreto. */}
      {saturacao && (
        <p
          style={{
            margin: 0,
            paddingTop: 8,
            borderTop: '1px solid var(--line-soft)',
            font: '400 11.5px/1.5 var(--f-ui)',
            color: saturacao.tom === 'saturado' ? 'var(--tx-soft)' : 'var(--tx-narrative)',
          }}
        >
          {saturacao.frase}
        </p>
      )}
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
  const aglomeracao = leituraDeAglomeracao(pontos, raioKm)
  if (pontos.length === 0 && ocultos === 0) return null

  return (
    <div style={{ display: 'grid', gap: 10 }}>
      <Titulo>Onde eles estão, do imóvel até a borda do raio</Titulo>

      {pontos.length > 0 && (
        <div style={{ display: 'grid', gap: 10 }}>
          {/* UM EIXO SÓ, com um disco por concorrente (relato do Juan, 2026-08-13: a
              versão de uma barra por linha "não trazia o visual necessário"). E não é
              volta ao desenho antigo: o que colidia ali eram os RÓTULOS centrados sob cada
              ponto. Aqui o eixo carrega só posição — nome e distância moram na lista
              abaixo, onde texto não disputa espaço com texto. Assim a pergunta que o bloco
              promete no título ("colados na esquina ou espalhados até a borda?") passa a
              ter resposta de relance, que N barras quase idênticas não davam. */}
          <div aria-hidden style={{ position: 'relative', height: 14 }}>
            <span
              style={{
                position: 'absolute',
                left: 0,
                right: 0,
                top: 6,
                height: 2,
                borderRadius: 1,
                background: 'var(--line-soft)',
              }}
            />
            {pontos.map((p, i) => (
              <span
                key={`${p.rede}-${i}`}
                title={`${p.rede} · ${num(p.dist, 2)} km`}
                style={{
                  position: 'absolute',
                  left: `calc(${p.fracao * 100}% - 5px)`,
                  top: 2,
                  width: 10,
                  height: 10,
                  borderRadius: '50%',
                  background: 'var(--ac)',
                  /* Discos sobrepostos são a INFORMAÇÃO aqui — dois colados no mesmo ponto
                     devem escurecer, e não sumir um sob o outro. A borda separa os
                     vizinhos sem exigir espalhamento artificial. */
                  border: '1.5px solid var(--surf-panel)',
                  boxSizing: 'border-box',
                }}
              />
            ))}
          </div>

          <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: -4 }}>
            {/* --tx-sub e não --tx-off: são os rótulos do eixo, e sem eles o desenho não
                tem escala. 3,17:1 é de-ênfase, não leitura. */}
            <span style={{ font: '400 9.5px/1 var(--f-ui)', color: 'var(--tx-sub)' }}>
              o imóvel
            </span>
            <span className="num" style={{ font: '400 9.5px/1 var(--f-num)', color: 'var(--tx-sub)' }}>
              {num(raioKm * 1000)} m
            </span>
          </div>

          {/* A leitura por extenso, por REGRA (`leituraDeAglomeracao`). O desenho responde
              "onde eles estão" para quem para e compara; a frase responde a pergunta que o
              operador realmente faz — "a disputa é na minha porta ou lá longe?". */}
          {aglomeracao && (
            <p
              style={{
                margin: 0,
                font: '400 11.5px/1.5 var(--f-ui)',
                color: 'var(--tx-narrative)',
              }}
            >
              {aglomeracao.frase}
            </p>
          )}

          {/* A lista: identidade e distância, SEM repetir a barra. Era ela que se
              multiplicava por concorrente sem acrescentar leitura. */}
          <div style={{ display: 'grid', gap: 4 }}>
            {pontos.map((p, i) => (
              <div
                key={`${p.rede}-${i}`}
                style={{
                  display: 'flex',
                  alignItems: 'baseline',
                  justifyContent: 'space-between',
                  gap: 10,
                }}
              >
                <span
                  title={p.rede}
                  style={{
                    font: '500 11px/1.5 var(--f-ui)',
                    color: 'var(--tx-soft)',
                    overflow: 'hidden',
                    textOverflow: 'ellipsis',
                    whiteSpace: 'nowrap',
                  }}
                >
                  {p.rede}
                </span>
                <span
                  className="num"
                  style={{
                    font: '600 11.5px/1.5 var(--f-num)',
                    color: 'var(--tx-strong)',
                    fontVariantNumeric: 'tabular-nums',
                    flexShrink: 0,
                  }}
                >
                  {num(p.dist, 2)} km
                </span>
              </div>
            ))}
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
