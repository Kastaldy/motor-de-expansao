import { useCallback, useMemo, useState } from 'react'

import BlocosComparacao from './BlocosComparacao'
import CampoPonto from './CampoPonto'
import { Botao, Glass } from './primitives'
import type { AlvoCaptura } from '../lib/captura-mapa'
import type { EntradaClassificada } from '../lib/entrada-ponto'
import { type BlocoParametro, blocosPorParametro } from '../lib/comparacao'
import {
  DIMENSOES_PONTO,
  MAX_PONTOS,
  compararPontos,
  corDoPonto,
  passaNoEstudo,
  resumoDoEstudo,
  rotulosDosPontos,
} from '../lib/comparacao-pontos'
import { ranquear } from '../lib/ranking-comparacao'
import { alunos, num } from '../lib/format'
import type { PontoPayload } from '../lib/types'

/**
 * Os pontos colados: as abas para trocar entre eles, e a comparacao A x B.
 *
 * A COMPARACAO NAO INCLUI VIABILIDADE, de proposito. Por DEC-009 a demanda e' premissa
 * digitada pelo operador, entao dois imoveis com a mesma metragem e o mesmo aluguel
 * produzem DRE, payback e break-even IDENTICOS — duas colunas com os mesmos numeros,
 * que se le como defeito. O que muda entre pontos e' o contexto (quem mora em volta,
 * quanto sobra de mercado, quem ja disputa), e e' isso que a tabela compara. A
 * viabilidade continua embaixo, por ponto.
 */
export default function PainelPontos({
  fichas,
  aberto,
  onAbrir,
  onRemover,
  onResolver,
  onLimpar,
  carregando,
  erro,
  onCapturarMapas,
}: {
  fichas: PontoPayload[]
  aberto: number
  onAbrir: (i: number) => void
  onRemover: (i: number) => void
  /** Resolve e acrescenta um ponto — o mesmo caminho da caixa de colar da tela. */
  onResolver: (entrada: EntradaClassificada, texto: string) => Promise<void>
  /** Tira os pontos, a janela e a marca do mapa. */
  onLimpar: () => void
  carregando: boolean
  erro: string | null
  /**
   * Captura do mapa, publicada pelo App. O modo de ponto usa o MESMO mapa do Explorar, e
   * cada ficha traz o `hex_id` do hexágono em que o endereço caiu — é por ele que o mapa
   * enquadra. A COORDENADA vai junto: o hexágono tem ~5 km² e comporta mais de um imóvel,
   * então sem ela a foto não diz qual endereço é o assunto daquela coluna.
   * Ausente = o PDF sai sem mapas, declarando a ausência.
   */
  onCapturarMapas?: (alvos: AlvoCaptura[]) => Promise<string[]>
}) {
  /** O campo de colar aberto aqui dentro, ao lado do botão que o pediu. */
  const [adicionando, setAdicionando] = useState(false)
  const [gerandoRelatorio, setGerandoRelatorio] = useState(false)
  const [erroRelatorio, setErroRelatorio] = useState<string | null>(null)

  /* Rotulos da LISTA, nao de cada ponto isolado: dois enderecos da mesma cidade sem
     bairro resolvido tinham o mesmo nome, e as abas, os seletores e as duas colunas da
     tabela ficavam indistinguiveis. */
  const rotulos = useMemo(() => rotulosDosPontos(fichas), [fichas])

  const blocos = useMemo(
    () => blocosPorParametro(DIMENSOES_PONTO, fichas),
    [fichas],
  ) as BlocoParametro<unknown>[]

  /* O deck em PDF dos pontos. HÁ captura de mapa, sim — um enquadramento por endereço,
     no hexágono em que ele caiu e com o imóvel marcado. (Esta nota dizia o contrário: ela
     é anterior ao commit que trouxe o mapa para o deck de pontos e ficou para trás.)

     Cada item leva os CRITÉRIOS avaliados junto: liderar parâmetros e passar no estudo são
     perguntas diferentes, e um ponto pode ganhar a comparação e ainda assim reprovar num
     piso do produto. Viabilidade fica de fora de propósito — é entrada do operador sobre um
     imóvel concreto (DEC-009), e a comparação não a tem. */
  const gerarRelatorio = useCallback(async () => {
    if (fichas.length < 2 || gerandoRelatorio) return
    setGerandoRelatorio(true)
    setErroRelatorio(null)
    try {
      const ranking = ranquear(DIMENSOES_PONTO, fichas, rotulos, { aprovado: passaNoEstudo })
      const itens = ranking.itens.map((it) => ({
        ...it,
        criterios: (fichas[it.indice]?.criterios ?? []).map((c) => ({
          rotulo: c.rotulo,
          passa: c.passa,
        })),
      }))
      /* Um enquadramento por ENDEREÇO, pelo hexágono em que ele caiu. O mapa se mexe
         sozinho durante isso — o botão avisa. Falha na captura não impede o PDF: o slide
         declara a ausência em vez de sumir. */
      const imagens = onCapturarMapas
        ? await onCapturarMapas(
            fichas.map((f) => ({ hexId: String(f.hex_id ?? ''), lat: f.lat, lng: f.lng })),
          )
        : []
      const cidade = fichas[0]?.local?.municipio ? `${fichas[0].local.municipio} - ` : ''
      const resposta = await fetch('/api/relatorio/comparacao', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          ...ranking,
          itens,
          titulo: 'Comparação de pontos',
          subtitulo: `${cidade}${fichas.length} pontos`,
          dePontos: true,
          imagens,
        }),
      })
      if (!resposta.ok) throw new Error(`HTTP ${resposta.status}`)
      const blob = await resposta.blob()
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = 'comparacao-pontos.pdf'
      a.click()
      URL.revokeObjectURL(url)
    } catch (erro) {
      setErroRelatorio('Não foi possível gerar o PDF. Tente de novo.')
      console.error('[deck] falhou ao gerar o PDF da comparação de pontos', erro)
    } finally {
      setGerandoRelatorio(false)
    }
  }, [fichas, rotulos, gerandoRelatorio, onCapturarMapas])

  // A prosa comparativa só com DOIS pontos — ver a nota no JSX.
  const comparacao = useMemo(
    () => (fichas.length === 2 ? compararPontos(fichas[0], fichas[1], rotulos[0], rotulos[1]) : null),
    [fichas, rotulos],
  )

  return (
    <div style={{ display: 'grid', gap: 16 }}>
      {/* ---- Abas dos pontos ---- */}
      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
        {fichas.map((f, i) => {
          const ativo = i === aberto
          return (
            <span
              key={`${f.hex_id}-${i}`}
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: 6,
                padding: '7px 8px 7px 11px',
                borderRadius: 999,
                /* A COR DO PONTO identifica a aba e volta na coluna da comparação: é
                   como o operador liga "esta aba" a "esta coluna" sem ler o rótulo. */
                background: ativo ? `${corDoPonto(i)}1F` : 'var(--surf-raised)',
                border: `1px solid ${ativo ? corDoPonto(i) : 'var(--line-soft)'}`,
              }}
            >
              <button
                type="button"
                onClick={() => onAbrir(i)}
                style={{
                  background: 'transparent',
                  border: 0,
                  padding: 0,
                  font: `${ativo ? 700 : 500} 12px/1 var(--f-ui)`,
                  color: ativo ? corDoPonto(i) : 'var(--tx-soft)',
                }}
              >
                {rotulos[i]}
              </button>
              <span className="num" style={{ font: '500 10px/1 var(--f-num)', color: 'var(--tx-sub)' }}>
                {alunos(f.mercado?.residual)}
              </span>
              {fichas.length > 1 && (
                <button
                  type="button"
                  onClick={() => onRemover(i)}
                  title={`Remover ${rotulos[i]}`}
                  aria-label={`Remover ${rotulos[i]}`}
                  style={{
                    background: 'transparent',
                    border: 0,
                    padding: '0 2px',
                    color: 'var(--tx-rank)',
                    font: '700 12px/1 var(--f-ui)',
                  }}
                >
                  ×
                </button>
              )}
            </span>
          )
        })}

        {fichas.length < MAX_PONTOS ? (
          <Botao variante="ghost" onClick={() => setAdicionando((v) => !v)} aria-expanded={adicionando}>
            {adicionando ? '− Fechar' : '+ Adicionar mais um ponto'}
          </Botao>
        ) : (
          <span style={{ font: '400 11px/1.4 var(--f-ui)', color: 'var(--tx-sub)' }}>
            {/* Teto declarado: sem isto o botao sumiria sem explicacao. */}
            Máximo de {MAX_PONTOS} pontos — remova um para colar outro.
          </span>
        )}

        {/* Limpeza. Só com ponto na tela — um "Limpar" sobre lista vazia é botão morto. */}
        {fichas.length > 0 && (
          <Botao variante="ghost" onClick={onLimpar} title="Tira os pontos, a janela e a marca do mapa">
            Limpar tudo
          </Botao>
        )}
      </div>

      {/* ---- Campo de colar, AQUI e não no cabeçalho ----
          A versão anterior mandava o cursor para a lupa do topo, e o operador tinha de
          procurar onde o foco caiu — longe do botão que ele acabou de clicar e longe da
          lista que está montando. O campo aparece colado na ação que o pediu, e some
          quando o ponto entra. Não é a caixa fixa que duplicava a lupa: existe só
          enquanto está aberto, a pedido. */}
      {adicionando && (
        <div
          style={{
            padding: 12,
            borderRadius: 'var(--r-lg)',
            border: '1px solid var(--ac-a25)',
            background: 'var(--surf-raised)',
            display: 'grid',
            gap: 8,
          }}
        >
          <CampoPonto
            onResolver={async (entrada, texto) => {
              await onResolver(entrada, texto)
              setAdicionando(false)
            }}
            ocupado={carregando}
            erro={erro}
          />
        </div>
      )}

      {/* ---- Comparação ---- */}
      {fichas.length >= 2 && (
        <Glass style={{ padding: 18, display: 'grid', gap: 12 }}>
          <div style={{ display: 'flex', alignItems: 'baseline', gap: 10, flexWrap: 'wrap' }}>
            <span style={{ font: '600 15px/1.2 var(--f-ui)', color: 'var(--tx-max)' }}>
              Comparando os pontos
            </span>
            <span style={{ font: '400 11px/1 var(--f-ui)', color: 'var(--tx-sub)' }}>
              contexto do entorno — a viabilidade fica por ponto, abaixo
            </span>
          </div>

          {/* A LEITURA ABSOLUTA, ao lado da relativa. Os blocos abaixo dizem quem ganha de
              quem em cada parâmetro; esta linha diz quantos pisos do produto cada ponto
              cumpre — número que não muda quando se troca o concorrente da comparação.
              As duas juntas evitam a leitura de que "o melhor da lista" já serve (pedido
              do Juan, 2026-08-19). */}
          <div style={{ display: 'flex', gap: 14, flexWrap: 'wrap', alignItems: 'center' }}>
            {fichas.map((f, i) => {
              const r = resumoDoEstudo(f)
              if (!r) return null
              const completo = r.cumpridos === r.avaliados
              return (
                <span
                  key={`estudo-${i}`}
                  style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}
                >
                  <span
                    aria-hidden
                    style={{
                      width: 8,
                      height: 8,
                      borderRadius: 2,
                      background: corDoPonto(i),
                    }}
                  />
                  <span style={{ font: '400 11px/1.3 var(--f-ui)', color: 'var(--tx-sub)' }}>
                    {rotulos[i]}
                  </span>
                  <span
                    className="num"
                    style={{
                      font: '700 11px/1.3 var(--f-num)',
                      color: completo ? 'var(--ac-text)' : 'var(--neg)',
                    }}
                  >
                    {r.cumpridos}/{r.avaliados}
                  </span>
                  <span style={{ font: '400 10.5px/1.3 var(--f-ui)', color: 'var(--tx-muted)' }}>
                    critérios
                  </span>
                </span>
              )
            })}
          </div>

          {/* BLOCO POR PARÂMETRO, com TODOS os pontos dentro (pedido do Juan,
              2026-08-13). Substitui o par A x B como leitura principal: com 5 pontos são
              10 pares, e "qual tem mais residual?" virava varredura. Aqui cada parâmetro
              responde sozinho, e o seletor de par deixa de ser necessário — foi ele que
              segurava o teto em 4 pontos. */}
          <BlocosComparacao
            blocos={blocos}
            rotulos={rotulos}
            cor={corDoPonto}
            onRelatorio={gerarRelatorio}
            rotuloRelatorio={
              gerandoRelatorio
                ? 'Gerando o PDF - o mapa está sendo capturado...'
                : 'Gerar relatório em PDF'
            }
          />

          {/* SÓ A FRASE, e não a tabela A x B inteira. Ela ficou aqui por uma versão e o
              resultado foi a janela repetir os MESMOS seis parâmetros duas vezes, uma nos
              blocos e outra na tabela ("ainda está péssima para visualização", Juan,
              2026-08-13). O que a tabela acrescentava era o veredito em prosa; os números
              já estão nos blocos, com barra e destaque.

              E o veredito só existe com DOIS pontos: com três ou mais, "X é o melhor"
              precisaria de um critério que some parâmetros — score novo, que exige DEC.
              Some em vez de mentir. */}
          {fichas.length === 2 && comparacao && (
            <p
              style={{
                margin: 0,
                paddingTop: 10,
                borderTop: '1px solid var(--line-soft)',
                font: '400 11.5px/1.55 var(--f-ui)',
                color: 'var(--tx-narrative)',
              }}
            >
              {comparacao.frase}
            </p>
          )}

          {erroRelatorio && (
            /* A falha é DITA, não engolida: um botão que não responde faz o operador
               clicar de novo e achar que a tela travou. */
            <p
              style={{
                margin: 0,
                padding: '9px 11px',
                borderRadius: 'var(--r-md)',
                border: '1px solid var(--neg)',
                font: '400 11.5px/1.5 var(--f-ui)',
                color: 'var(--tx-soft)',
              }}
            >
              {erroRelatorio}
            </p>
          )}

          <p style={{ font: '400 11px/1.5 var(--f-ui)', color: 'var(--tx-sub)', margin: 0 }}>
            Cada leitura sai do raio de {num((fichas[0]?.raio_km ?? 1) * 1000)} m em torno do
            ponto — a mesma régua do Relatório Pontual.
          </p>
        </Glass>
      )}
    </div>
  )
}
