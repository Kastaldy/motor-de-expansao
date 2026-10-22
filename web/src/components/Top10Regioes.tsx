import type { CSSProperties, ReactNode } from 'react'

import type { DestinoHex } from '../lib/oportunidades'
import {
  TOKEN_COR_TOP10,
  cabecalhoTop10,
  montarBlocosTop10,
  referenciaTecnicaDaRegua,
  textoDaRegua,
  textoVersaoDaRegua,
  type BlocoTop10,
  type LinhaTop10Regiao,
  type LinhaTop10Vazia,
} from '../lib/top10'
import type { RecomendacaoTop10 } from '../lib/types'

/* ---------------------------------------------------------------------------
   O Top 10 da recomendação única (DEC-077) — o ÚNICO componente que o desenha.

   Três lugares o usam: o passo 5 do município e o passo 5 da UF (no `NarrativePanel`,
   variante `painel`) e o hero de Oportunidades (variante `hero`). Os três recebem o MESMO
   bloco `recomendacao` do servidor, montado por uma função só (`montar_recomendacao`) — é
   isso que faz o Top 10 do mapa e o da lista serem o mesmo.

   Este componente é deliberadamente burro: NÃO reordena, NÃO filtra e NÃO calcula nada
   da régua. As linhas saem de `montarBlocosTop10` (lib/top10.ts, testada), na ordem do
   servidor; a vaga vazia diz o motivo do servidor; o texto da régua é montado com os
   números do payload. Dois blocos fixos — Mata Virgem e Premium — e um segmento nunca
   completa o outro.

   Cor SÓ por token de tema (`--top10-mv`, `--top10-premium`): nada de cor cravada aqui, o
   que `mapa-top10.test.ts` trava. Não confundir com `Recomendacao.tsx`, que é a ficha do
   PONTO ("Serve este imóvel?") e não tem relação com esta regra.
   --------------------------------------------------------------------------- */

export interface Top10RegioesProps {
  bloco: RecomendacaoTop10
  /** `painel` = coluna estreita do mapa; `hero` = largura cheia de Oportunidades. */
  variante: 'painel' | 'hero'
  /** Mostra o texto da régua. No painel a narrativa do passo já a descreve. */
  mostrarRegua?: boolean
  selecionado?: string | null
  /** Clique na linha: seleciona (e o mapa voa até) o hexágono. Ausente = linha não clicável. */
  onSelecionar?: (hexId: string) => void
  /** Põe/tira o hexágono da comparação. Ausente = a lista não oferece comparar. */
  onComparar?: (hexId: string) => void
  comparados?: readonly string[]
  maxComparados?: number
  /** Visão de UF: "Abrir {município}" desce ao município da região. */
  onAbrirMunicipio?: (municipio: string) => void
  /** Oportunidades: "Ver no mapa →" leva UF, município e o pin do hexágono. */
  onVerNoMapa?: (d: DestinoHex) => void
}

export default function Top10Regioes({
  bloco,
  variante,
  mostrarRegua = true,
  selecionado = null,
  onSelecionar,
  onComparar,
  comparados,
  maxComparados,
  onAbrirMunicipio,
  onVerNoMapa,
}: Top10RegioesProps) {
  const blocos = montarBlocosTop10(bloco)
  const cabecalho = cabecalhoTop10(bloco)
  const hero = variante === 'hero'

  return (
    <div style={{ display: 'grid', gap: hero ? 14 : 10 }}>
      <div style={{ display: 'grid', gap: 4 }}>
        <span className="num" style={{ font: '700 12.5px/1.2 var(--f-num)', color: 'var(--tx-strong)' }}>
          {cabecalho.vagas}
        </span>
        {cabecalho.candidatos && (
          <span style={{ font: '400 11px/1.4 var(--f-ui)', color: 'var(--tx-muted)' }}>
            {cabecalho.candidatos}
          </span>
        )}
      </div>

      {mostrarRegua && (
        <div style={{ display: 'grid', gap: 4 }}>
          <p style={{ margin: 0, font: '400 11.5px/1.55 var(--f-ui)', color: 'var(--tx-narrative)' }}>
            {textoDaRegua(bloco.regra, bloco.rotulos)}
          </p>
          {/* O carimbo da régua: quem lê a lista sabe DE QUANDO é a versão que a decidiu. A
              versão crua e a decisão ficam só na dica, como detalhe técnico. */}
          <span
            className="num"
            title={referenciaTecnicaDaRegua(bloco.regra)}
            style={{ font: '400 9.5px/1.2 var(--f-num)', color: 'var(--tx-muted)' }}
          >
            {textoVersaoDaRegua(bloco.regra)}
          </span>
        </div>
      )}

      <div
        style={{
          display: 'grid',
          gap: hero ? 16 : 12,
          gridTemplateColumns: hero ? 'repeat(auto-fit, minmax(340px, 1fr))' : '1fr',
          alignItems: 'start',
        }}
      >
        {blocos.map((b) => (
          <BlocoSegmento
            key={b.segmento}
            bloco={b}
            selecionado={selecionado}
            onSelecionar={onSelecionar}
            onComparar={onComparar}
            comparados={comparados}
            maxComparados={maxComparados}
            onAbrirMunicipio={onAbrirMunicipio}
            onVerNoMapa={onVerNoMapa}
          />
        ))}
      </div>
    </div>
  )
}

type AcoesDaLinha = Pick<
  Top10RegioesProps,
  'onSelecionar' | 'onComparar' | 'comparados' | 'maxComparados' | 'onAbrirMunicipio' | 'onVerNoMapa'
>

function BlocoSegmento({
  bloco,
  selecionado,
  ...acoes
}: { bloco: BlocoTop10; selecionado: string | null } & AcoesDaLinha) {
  const cor = TOKEN_COR_TOP10[bloco.segmento]
  /* Segmento indisponível não tem contagem de candidatos (nada foi calculado): o rótulo
     acessível e o cabeçalho dizem o status, e não "0 candidatos". */
  const resumo = bloco.textoCandidatos ?? bloco.indisponivel?.titulo ?? ''
  return (
    <section aria-label={`${bloco.titulo}: ${resumo}`} style={{ display: 'grid', gap: 6 }}>
      <header style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        <span aria-hidden style={{ width: 9, height: 9, borderRadius: 2, background: cor, flexShrink: 0 }} />
        <span style={{ font: '600 13px/1.2 var(--f-ui)', color: 'var(--tx-max)' }}>{bloco.titulo}</span>
        {bloco.textoCandidatos && (
          <span
            style={{ marginLeft: 'auto', font: '400 10.5px/1 var(--f-ui)', color: 'var(--tx-muted)' }}
          >
            {bloco.textoCandidatos}
          </span>
        )}
      </header>

      {bloco.semCandidato ? (
        /* Segmento calculado SEM nenhum candidato: uma frase só, e não cinco linhas "vaga
           vazia" iguais — o caso mais comum fora das cidades grandes. */
        <div
          role="status"
          style={{
            padding: '11px 12px',
            borderRadius: 'var(--r-lg)',
            border: '1px dashed var(--line-strong)',
            font: '400 11.5px/1.45 var(--f-ui)',
            color: 'var(--tx-muted)',
          }}
        >
          {bloco.semCandidato}
        </div>
      ) : bloco.indisponivel ? (
        /* UMA mensagem por bloco, e não cinco linhas "vazia" repetindo o mesmo motivo: sem
           o carimbo k da malha o segmento inteiro não foi calculado. */
        <div
          role="status"
          style={{
            display: 'grid',
            gap: 4,
            padding: '11px 12px',
            borderRadius: 'var(--r-lg)',
            border: '1px dashed var(--line-strong)',
          }}
        >
          <span style={{ font: '600 12px/1.2 var(--f-ui)', color: 'var(--warn-text)' }}>
            {bloco.indisponivel.titulo}
          </span>
          <span style={{ font: '400 11.5px/1.45 var(--f-ui)', color: 'var(--tx-muted)' }}>
            {bloco.indisponivel.motivo}
          </span>
        </div>
      ) : (
        bloco.linhas.map((linha) =>
          linha.tipo === 'regiao' ? (
            <LinhaRegiao
              key={linha.chave}
              linha={linha}
              cor={cor}
              rotuloSegmento={bloco.titulo}
              ativo={linha.chave === selecionado}
              {...acoes}
            />
          ) : (
            <LinhaVazia key={linha.chave} linha={linha} />
          ),
        )
      )}
    </section>
  )
}

/** MV1 / P1 — a mesma marca que o mapa desenha sobre o hexágono. */
function Selo({ rotulo, cor }: { rotulo: string; cor: string }) {
  return (
    <span
      className="num"
      aria-hidden
      style={{
        flexShrink: 0,
        minWidth: 32,
        padding: '4px 5px',
        borderRadius: 6,
        border: `1px solid ${cor}`,
        color: cor,
        font: '700 11px/1 var(--f-num)',
        textAlign: 'center',
      }}
    >
      {rotulo}
    </span>
  )
}

const BOTAO_VER_NO_MAPA: CSSProperties = {
  padding: '6px 10px',
  borderRadius: 8,
  border: '1px solid var(--ac-a25)',
  background: 'var(--ac-a12)',
  color: 'var(--ac-chip)',
  font: '600 11px/1 var(--f-ui)',
}

const BOTAO_ABRIR: CSSProperties = {
  padding: '6px 10px',
  borderRadius: 8,
  border: '1px solid var(--line-soft)',
  background: 'transparent',
  color: 'var(--tx-soft)',
  font: '600 11px/1 var(--f-ui)',
}

function LinhaRegiao({
  linha,
  cor,
  rotuloSegmento,
  ativo,
  onSelecionar,
  onComparar,
  comparados,
  maxComparados,
  onAbrirMunicipio,
  onVerNoMapa,
}: {
  linha: LinhaTop10Regiao
  cor: string
  rotuloSegmento: string
  ativo: boolean
} & AcoesDaLinha) {
  const clicavel = Boolean(onSelecionar)
  const acionar = () => onSelecionar?.(linha.chave)
  const naComparacao = (comparados ?? []).includes(linha.chave)
  const cheio =
    maxComparados != null && (comparados ?? []).length >= maxComparados && !naComparacao
  const municipio = linha.vaga.nome_municipio
  const acoes: ReactNode[] = []
  if (onAbrirMunicipio && municipio) {
    acoes.push(
      <button
        key="abrir"
        type="button"
        onClick={() => onAbrirMunicipio(municipio)}
        title={`Descer a ${municipio}, com as camadas do município`}
        style={BOTAO_ABRIR}
      >
        Abrir {municipio}
      </button>,
    )
  }
  if (onVerNoMapa) {
    const destino = linha.destino
    acoes.push(
      <button
        key="mapa"
        type="button"
        onClick={() => destino && onVerNoMapa(destino)}
        disabled={!destino}
        title={destino ? 'Levar ao hexágono no mapa' : 'Esta região não traz coordenada para o mapa'}
        style={{ ...BOTAO_VER_NO_MAPA, opacity: destino ? 1 : 0.4 }}
      >
        Ver no mapa →
      </button>,
    )
  }

  return (
    <div
      style={{
        // SELEÇÃO = branco, a mesma cor do contorno do hexágono selecionado no mapa
        // (mesma linguagem do NarrativePanel).
        border: `1px solid ${ativo ? 'var(--tx-max)' : 'var(--line-soft)'}`,
        borderRadius: 'var(--r-lg)',
        background: ativo ? 'var(--surf-pending)' : 'var(--surf-raised)',
        transition: 'background .15s ease, border-color .15s ease',
      }}
    >
      <div
        role={clicavel ? 'button' : undefined}
        tabIndex={clicavel ? 0 : undefined}
        onClick={clicavel ? acionar : undefined}
        onKeyDown={
          clicavel
            ? (e) => {
                if (e.key === 'Enter' || e.key === ' ') {
                  e.preventDefault()
                  acionar()
                }
              }
            : undefined
        }
        style={{
          padding: '10px 12px',
          display: 'grid',
          gap: 6,
          cursor: clicavel ? 'pointer' : 'default',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <Selo rotulo={linha.rotulo} cor={cor} />
          <span style={{ flex: 1, minWidth: 0 }}>
            <span style={{ display: 'flex', alignItems: 'center', gap: 7, flexWrap: 'wrap' }}>
              <span style={{ font: '600 13.5px/1.2 var(--f-ui)', color: 'var(--tx-strong)' }}>
                {linha.nome}
              </span>
              <span
                style={{
                  font: '700 9.5px/1 var(--f-ui)',
                  textTransform: 'uppercase',
                  letterSpacing: '.05em',
                  padding: '3px 7px',
                  borderRadius: 'var(--r-sm)',
                  color: cor,
                  background: `color-mix(in srgb, ${cor} 14%, transparent)`,
                  whiteSpace: 'nowrap',
                }}
              >
                {rotuloSegmento}
              </span>
            </span>
            <span
              className="num"
              style={{
                display: 'block',
                marginTop: 3,
                font: '400 10.5px/1.3 var(--f-num)',
                color: 'var(--tx-label)',
              }}
            >
              {linha.municipioUf ? `${linha.municipioUf} · ${linha.hexCurto}` : linha.hexCurto}
            </span>
          </span>

          <span style={{ textAlign: 'right', flexShrink: 0 }}>
            <span
              className="num"
              style={{ display: 'block', font: '700 15px/1 var(--f-num)', color: 'var(--tx-max)' }}
            >
              {linha.principal.valor}
            </span>
            <span
              style={{
                display: 'block',
                marginTop: 4,
                font: '400 9.5px/1.2 var(--f-ui)',
                color: 'var(--tx-sub)',
              }}
            >
              {linha.principal.unidade}
            </span>
          </span>

          {/* Comparar: dentro da linha no LAYOUT, fora dela no EVENTO (`stopPropagation`),
              para pôr na comparação não mover a câmera junto. */}
          {onComparar && (
            <button
              type="button"
              onClick={(e) => {
                e.stopPropagation()
                onComparar(linha.chave)
              }}
              disabled={cheio}
              title={
                cheio
                  ? `A comparação já tem ${maxComparados} hexágonos. Tire um para pôr outro.`
                  : naComparacao
                    ? 'Tirar da comparação'
                    : 'Pôr na comparação'
              }
              aria-pressed={naComparacao}
              style={{
                flexShrink: 0,
                width: 26,
                height: 26,
                display: 'grid',
                placeItems: 'center',
                borderRadius: 7,
                border: `1px solid ${naComparacao ? 'var(--ac)' : 'var(--line-soft)'}`,
                background: naComparacao ? 'var(--ac)' : 'var(--surf-raised)',
                color: naComparacao ? 'var(--ac-on)' : 'var(--tx-soft)',
                font: '700 13px/1 var(--f-ui)',
                cursor: cheio ? 'not-allowed' : 'pointer',
                opacity: cheio ? 0.4 : 1,
              }}
            >
              {naComparacao ? '✓' : '+'}
            </button>
          )}
        </div>

        <span style={{ font: '400 11px/1.45 var(--f-ui)', color: 'var(--tx-label)' }}>
          {linha.secundaria}
        </span>
      </div>

      {/* As ações ficam FORA da área clicável: botão dentro de botão confunde leitor de
          tela e teclado, e o clique numa ação não deve também selecionar a linha. */}
      {acoes.length > 0 && (
        <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', padding: '0 12px 10px' }}>{acoes}</div>
      )}
    </div>
  )
}

function LinhaVazia({ linha }: { linha: LinhaTop10Vazia }) {
  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: 10,
        padding: '9px 12px',
        borderRadius: 'var(--r-lg)',
        border: '1px dashed var(--line-strong)',
      }}
    >
      <Selo rotulo={linha.rotulo} cor="var(--tx-muted)" />
      <span style={{ font: '400 11.5px/1.45 var(--f-ui)', color: 'var(--tx-muted)' }}>{linha.texto}</span>
    </div>
  )
}
