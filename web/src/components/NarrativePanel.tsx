import { useState } from 'react'

import { camadaCor } from '../lib/colors'
import { type Linha, type Serie, parseDims, parseSeries } from '../lib/crescimento'
import { alunos, num } from '../lib/format'
import {
  filtrarPorCrescimento,
  lerCrescimento,
  ordenarComDesempate,
  temCoberturaSatelite,
  type CrescimentoMunicipio,
} from '../lib/oportunidades'
import type { Hex, Passo } from '../lib/types'
import { Chip, Eyebrow } from './primitives'

/* ---------------------------------------------------------------------------
   Painel narrativo — o elemento-assinatura do piloto.

   Conta a historia do funil em vez de despejar metricas: cada camada declara de
   onde veio e o que sobrou (999 hexagonos -> 314 quentes -> 38 com residual ->
   23 white spaces -> 4 aberturas). A narrativa usa serif; o numero, mono. Essa
   separacao tipografica e o que faz a tela ler como um briefing, nao um painel.

   COR (ver --l1..--l4 em tokens.css): o eyebrow e o bloco do funil vestem a cor da
   camada — antes os 4 passos eram identicos em turquesa, a mesma cor do KPI do
   header, e o usuario lia o contador da camada e o total do territorio como o
   mesmo numero. A SELECAO saiu do turquesa e virou branca (--tx-max), casando com
   o contorno branco que o mapa ja usa no hex selecionado: painel e mapa passam a
   dizer "este esta selecionado" com a mesma cor. O turquesa fica so' na ACAO
   (botao "Testar viabilidade") e no cenario multi-hex.
   --------------------------------------------------------------------------- */

export interface NarrativePanelProps {
  passo: Passo
  selecionado: string | null
  onSelecionarHex: (hexId: string) => void
  onAnalisar: (hexId: string) => void
  /** Visão de UF: clicar num item (município) filtra para ele (drill-down). */
  onDrillMunicipio?: (municipio: string) => void
  hexes: Hex[]
  /** Total de passos do funil. Deriva do payload — não é literal, para o 6º passo
   *  não repetir a caçada por "de 4" que este bloco já teve de fazer. */
  totalPassos: number
  /** Crescimento por município (`MapaResposta.cres_mun`). Só o passo 5 usa. */
  cresMun?: Record<string, CrescimentoMunicipio> | null
  /** UF em tela, para avisar da cobertura de satélite no passo 4. */
  uf?: string | null
}

/* ---------------------------------------------------------------------------
   Passo 4 — bloco "Detalhes", recolhido por padrao.

   O veredito de uma frase resolve a leitura rapida; quem quiser o porque abre e
   ve as cinco dimensoes e o grafico. Cada dimensao e um botao: clicar troca a
   serie do grafico, entao o mesmo espaco serve as cinco.
   --------------------------------------------------------------------------- */

/** Grafico da serie selecionada. Generico: escala sai dos proprios dados.
 *  O cabecalho carrega a leitura INTEIRA — nome, periodo, variacao e os valores
 *  das pontas — para nao ser preciso olhar a linha da dimensao acima nem rolar. */
function Grafico({ serie, resumo }: { serie: Serie; resumo?: Linha }) {
  const v = serie.valores
  const W = 346
  const H = 40
  // A escala sai dos PROPRIOS dados. Ancorada no zero, a curva de Populacao virava
  // uma reta em 91,6% dos municipios (amplitude mediana de 1,3 px num SVG de 40)
  // enquanto o cabecalho ao lado anunciava a variacao.
  const mn = Math.min(...v)
  const mx = Math.max(...v)
  const rg = mx - mn || 1
  const X = (i: number) => (i * W) / (v.length - 1)
  const Y = (n: number) => H - ((n - mn) / rg) * H
  const linha = v.map((n, i) => `${i ? 'L' : 'M'}${X(i).toFixed(1)} ${Y(n).toFixed(1)}`).join(' ')
  const ult = v[v.length - 1]
  const pri = v[0]
  const cor = ult >= pri ? 'var(--ac)' : 'var(--warn-text, #E0684B)'
  const destaque = resumo
    ? `${resumo.unidade === '%' && resumo.valor >= 0 ? '+' : ''}${num(
        resumo.valor,
        Math.abs(resumo.valor) < 10 ? 1 : 0,
      )}${resumo.unidade}`
    : num(ult)
  return (
    <div
      style={{
        marginTop: 12,
        padding: '11px 12px 9px',
        borderRadius: 'var(--r-lg)',
        background: 'var(--surf-raised)',
        border: '1px solid var(--line-soft)',
      }}
    >
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'baseline',
          gap: 10,
          marginBottom: 8,
        }}
      >
        <span style={{ font: '600 13px/1.2 var(--f-ui)', color: 'var(--tx-strong)' }}>
          {serie.nome}
          <span
            className="num"
            style={{
              display: 'block',
              font: '400 9.5px/1 var(--f-num)',
              color: 'var(--tx-off)',
              marginTop: 3,
            }}
          >
            {resumo?.periodo || `${serie.ini} – ${serie.fim}`}
          </span>
        </span>
        <span
          className="num"
          style={{ font: '700 17px/1 var(--f-num)', color: cor, whiteSpace: 'nowrap' }}
        >
          {destaque}
        </span>
      </div>
      <svg
        viewBox={`0 0 ${W} ${H}`}
        style={{ display: 'block', width: '100%', height: 'auto', overflow: 'visible' }}
        role="img"
        aria-label={`${serie.nome}, de ${num(pri)} em ${serie.ini} a ${num(ult)} em ${serie.fim}`}
      >
        {mn < 0 && (
          <line x1="0" x2={W} y1={Y(0)} y2={Y(0)} stroke="var(--line-mid)" strokeWidth="1" />
        )}
        <path d={`${linha} L${W} ${Y(mn)} L0 ${Y(mn)} Z`} fill={cor} opacity={0.13} />
        <path d={linha} fill="none" stroke={cor} strokeWidth="1.8" strokeLinejoin="round" />
        <circle cx={X(v.length - 1)} cy={Y(ult)} r="3" fill={cor} />
      </svg>
      {/* As pontas trazem ano E valor: quem olha so o grafico ja sabe de onde
          para onde foi, sem consultar a linha da dimensao. */}
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          font: '400 9.5px/1 var(--f-num)',
          color: 'var(--tx-sub)',
          marginTop: 5,
        }}
      >
        <span>
          {serie.ini} · {num(pri)} {serie.unidade}
        </span>
        <span>
          {serie.fim} · {num(ult)} {serie.unidade}
        </span>
      </div>
    </div>
  )
}

/* As cinco dimensoes do crescimento municipal, cada uma com o NUMERO REAL e a
   posicao no pais. O numero responde "quanto"; a barra responde "isso e muito?".
   Sozinho, nenhum dos dois decide — juntos, sim. */
function Dimensoes({
  dims,
  ativo,
  onEscolher,
  temSerie,
}: {
  dims: string
  ativo: string | null
  onEscolher: (nome: string) => void
  temSerie: (nome: string) => boolean
}) {
  const linhas = parseDims(dims)
  if (!linhas.length) return null
  return (
    <div style={{ marginTop: 10, display: 'flex', flexDirection: 'column', gap: 3 }}>
      {linhas.map((l) => {
        const clicavel = temSerie(l.nome)
        const on = ativo === l.nome
        return (
        <button
          key={l.nome}
          type="button"
          onClick={clicavel ? () => onEscolher(l.nome) : undefined}
          disabled={!clicavel}
          aria-pressed={on}
          title={clicavel ? `Ver o gráfico de ${l.nome.toLowerCase()}` : 'Sem série para esta dimensão'}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 9,
            width: '100%',
            padding: '4px 6px',
            margin: '0 -6px',
            borderRadius: 7,
            background: on ? 'var(--ac-a10)' : 'transparent',
            border: `1px solid ${on ? 'var(--ac-a30)' : 'transparent'}`,
            cursor: clicavel ? 'pointer' : 'default',
            textAlign: 'left',
          }}
        >
          <span
            style={{
              font: `${on ? '600' : '400'} 11px/1 var(--f-ui)`,
              color: on ? 'var(--ac-text)' : 'var(--tx-label)',
              width: 74,
              flexShrink: 0,
            }}
          >
            {l.nome}
          </span>
          {/* Uma linha so. O periodo saiu daqui e foi para o cabecalho do grafico,
              que mostra o indicador escolhido inteiro — assim as cinco linhas cabem
              na tela junto com a curva, sem rolar. */}
          <span
            className="num"
            title={l.periodo ? `Variação no período ${l.periodo}` : undefined}
            style={{
              font: '600 11.5px/1 var(--f-num)',
              color: l.valor < 0 ? 'var(--warn-text, #E0684B)' : 'var(--tx-strong)',
              width: 66,
              textAlign: 'right',
              flexShrink: 0,
            }}
          >
            {l.unidade === '%' && l.valor >= 0 ? '+' : ''}
            {num(l.valor, Math.abs(l.valor) < 10 ? 1 : 0)}
            {l.unidade}
          </span>
          <span
            aria-hidden
            style={{
              flex: 1,
              height: 5,
              borderRadius: 3,
              background: 'var(--line-mid)',
              overflow: 'hidden',
              minWidth: 40,
            }}
          >
            <span
              style={{
                display: 'block',
                width: `${Math.max(2, Math.min(100, l.pos))}%`,
                height: '100%',
                background: 'var(--ac)',
                borderRadius: 3,
              }}
            />
          </span>
          <span
            className="num"
            style={{
              font: '400 9.5px/1 var(--f-num)',
              color: 'var(--tx-off)',
              width: 52,
              flexShrink: 0,
            }}
          >
            {l.pos > 50 ? `top ${Math.max(1, 100 - l.pos)}%` : `${l.pos}º pct`}
          </span>
        </button>
        )
      })}
    </div>
  )
}

/** Bloco recolhivel do passo 4: dimensoes clicaveis + grafico da escolhida. */
function Detalhes({
  dims,
  series,
  de,
}: {
  dims: string | null
  series: string | null
  /** Nome do municipio, para o nome acessivel do botao. Na visao de UF sao dez
   *  botoes "Detalhes" na mesma tela; sem isso o leitor de tela ouve dez vezes
   *  o mesmo rotulo sem saber de qual cidade. */
  de?: string
}) {
  const [aberto, setAberto] = useState(false)
  const lista = series ? parseSeries(series) : []
  const porNome = new Map(lista.map((s) => [s.nome, s]))
  const [sel, setSel] = useState<string | null>(null)
  if (!dims && !lista.length) return null
  const atual = (sel && porNome.get(sel)) || lista[0] || null
  return (
    <div style={{ marginTop: 14 }}>
      <button
        type="button"
        onClick={() => setAberto((a) => !a)}
        aria-expanded={aberto}
        aria-label={de ? `Detalhes de ${de}` : 'Detalhes'}
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 7,
          width: '100%',
          padding: '8px 11px',
          borderRadius: 'var(--r-lg)',
          background: 'var(--surf-raised)',
          border: '1px solid var(--line-soft)',
          font: '600 11.5px/1 var(--f-ui)',
          color: 'var(--tx-soft)',
          cursor: 'pointer',
        }}
      >
        <span aria-hidden style={{ font: '400 10px/1 var(--f-num)', color: 'var(--tx-muted)' }}>
          {aberto ? '▾' : '▸'}
        </span>
        Detalhes
        <span
          style={{
            marginLeft: 'auto',
            font: '400 10px/1 var(--f-ui)',
            color: 'var(--tx-muted)',
          }}
        >
          {aberto ? 'ocultar' : 'renda, população, empresas, prédios, emprego'}
        </span>
      </button>

      {aberto && (
        <>
          {/* O grafico vem ANTES das linhas: assim o indicador escolhido e a curva
              ficam na mesma altura da tela, sem precisar rolar ate o fim da lista. */}
          {atual && (
            <Grafico
              serie={atual}
              resumo={dims ? parseDims(dims).find((l) => l.nome === atual.nome) : undefined}
            />
          )}
          {dims && (
            <Dimensoes
              dims={dims}
              ativo={atual?.nome ?? null}
              onEscolher={setSel}
              temSerie={(n) => porNome.has(n)}
            />
          )}
        </>
      )}
    </div>
  )
}

export default function NarrativePanel({
  passo,
  selecionado,
  onSelecionarHex,
  onAnalisar,
  onDrillMunicipio,
  totalPassos,
  cresMun,
  uf,
}: NarrativePanelProps) {
  /** Filtro OPCIONAL do passo 5. Começa desligado: a fila que o motor entregou é a
   *  resposta padrão, e esconder itens por default seria decidir pelo operador. */
  const [soCrescendo, setSoCrescendo] = useState(false)
  // Vem UMA vez no passo, nao repetido em cada hexagono (o payload de uma UF
  // triplicava). Na visao de UF cada item do ranking traz o seu.
  /* Só o passo 5 passa por aqui. Nos outros a lista é a do servidor, intocada.
     `ordenarComDesempate` NÃO reordena por crescimento: a chave primária continua
     sendo o residual, e o crescimento só decide entre empates. */
  const itens =
    passo.n === 5
      ? filtrarPorCrescimento(ordenarComDesempate(passo.itens, cresMun), cresMun, soCrescendo)
      : passo.itens
  const escondidos = passo.n === 5 ? passo.itens.length - itens.length : 0

  const series = passo.series ?? null
  const dims = passo.dims ?? null
  const cor = camadaCor(passo.n)
  return (
    <aside
      aria-label={`Camada ${passo.n} de ${totalPassos}: ${passo.titulo}`}
      style={{
        width: 394,
        flexShrink: 0,
        display: 'flex',
        flexDirection: 'column',
        background: 'var(--surf-panel)',
        border: '1px solid var(--line-soft)',
        borderRadius: 'var(--r-2xl)',
        backdropFilter: 'blur(18px)',
        overflow: 'hidden',
      }}
    >
      <header style={{ padding: '18px 20px 16px' }}>
        {/* O NUMERAL fica: a cor nunca e' o unico portador da identidade da
            camada (daltonismo). O total vem do payload — o funil ja' passou de 4
            para 5 camadas, entao numero cravado aqui mentiria. */}
        <Eyebrow dot cor={cor.fg}>
          Camada {passo.n} de {totalPassos} · {passo.mode}
        </Eyebrow>

        <h2
          className="story"
          style={{
            font: '400 25px/1.15 var(--f-story)',
            color: 'var(--tx-max)',
            margin: '11px 0 0',
            letterSpacing: '.005em',
          }}
        >
          {passo.titulo}
        </h2>

        <p
          style={{
            font: '400 13px/1.6 var(--f-ui)',
            color: 'var(--tx-narrative)',
            margin: '9px 0 0',
          }}
        >
          {passo.narrativa}
        </p>

        <div
          style={{
            marginTop: 15,
            padding: '13px 15px',
            background: cor.bg,
            border: `1px solid ${cor.borda}`,
            borderRadius: 'var(--r-lg)',
            display: 'flex',
            alignItems: 'baseline',
            gap: 9,
            flexWrap: 'wrap',
          }}
        >
          <span
            className="num"
            style={{ font: '700 30px/1 var(--f-num)', color: cor.fg }}
          >
            {num(passo.funil_big)}
          </span>
          <span
            style={{ font: '600 12.5px/1 var(--f-ui)', color: 'var(--tx-soft)' }}
          >
            {passo.funil_unit}
          </span>
          <span
            style={{
              font: '400 10.5px/1.3 var(--f-ui)',
              color: 'var(--tx-muted)',
              width: '100%',
            }}
          >
            filtrados de {passo.funil_from}
          </span>
        </div>

      </header>

      <div
        style={{
          flex: 1,
          overflowY: 'auto',
          padding: '4px 14px 12px',
          display: 'flex',
          flexDirection: 'column',
          gap: 8,
        }}
      >
        {/* O Detalhes fica DENTRO da area rolavel. No cabecalho ele era cortado:
            ao abrir o grafico da renda nao dava para ver o numero e a curva juntos,
            porque o header nao rola. Na visao de UF cada item traz o seu, entao
            aqui so aparece quando a lista nao tem detalhe proprio. */}
        {passo.n === 4 && !passo.itens.some((it) => it.dims || it.series) && (
          <Detalhes dims={dims} series={series} />
        )}

        {passo.n === 5 && passo.itens.length > 0 && (
          <div style={{ display: 'grid', gap: 8, margin: '0 0 12px' }}>
            <label
              style={{
                display: 'flex', alignItems: 'center', gap: 8,
                font: '500 11.5px/1.3 var(--f-ui)', color: 'var(--tx-soft)',
              }}
            >
              <input
                type="checkbox"
                checked={soCrescendo}
                onChange={(e) => setSoCrescendo(e.target.checked)}
              />
              Só cidades crescendo acima da mediana do estado
            </label>
            {soCrescendo && escondidos > 0 && (
              /* Dizer QUANTOS sumiram: filtro que encolhe a lista em silêncio faz o
                 operador achar que a fila é menor do que é. */
              <span style={{ font: '400 11px/1.4 var(--f-ui)', color: 'var(--tx-sub)' }}>
                {escondidos} {escondidos === 1 ? 'item escondido' : 'itens escondidos'} pelo
                filtro — a ordem da fila não muda, só a visibilidade.
              </span>
            )}
          </div>
        )}

        {passo.n === 4 && !temCoberturaSatelite(uf) && (
          /* A cor do hexágono no passo 4 vem de satélite, que cobre 12 UFs. Fora
             delas o mapa acende cinza — não é defeito, é ausência de dado, e sem
             aviso vira chamado. O número do painel (CAGED) segue nacional. */
          <p
            style={{
              margin: '0 0 12px',
              padding: '9px 11px',
              borderRadius: 'var(--r-sm)',
              background: 'var(--surf-raised)',
              border: '1px dashed var(--line-strong)',
              font: '400 11.5px/1.5 var(--f-ui)',
              color: 'var(--tx-muted)',
            }}
          >
            Os hexágonos aparecem cinza neste estado: a camada de área construída
            (satélite) cobre 12 UFs, e {uf ?? 'esta'} não está entre elas. Os números de
            emprego abaixo continuam valendo — eles vêm do CAGED, com cobertura nacional.
          </p>
        )}

        {itens.length === 0 ? (
          <p
            style={{
              font: '400 12.5px/1.6 var(--f-ui)',
              color: 'var(--tx-muted)',
              padding: '18px 6px',
              margin: 0,
            }}
          >
            {/* O botão "← Camada anterior" só existe a partir do passo 2 (StepperBar
                o esconde quando `atual === 1`); na camada 1 mandar o usuário clicar
                nele apontaria para um controle que não está na tela. */}
            {passo.n > 1
              ? 'Nenhuma região passou neste filtro. Use "← Camada anterior", na barra de passos abaixo, para ver o que foi descartado — ou escolha outro município.'
              : 'Nenhuma região passou neste filtro. Escolha outro município ou outro estado na barra de busca.'}
          </p>
        ) : (
          itens.map((it) => {
            const ativo = it.hex_id === selecionado
            const acionar = () =>
              it.municipio ? onDrillMunicipio?.(it.municipio) : onSelecionarHex(it.hex_id)
            const temDetalhe = Boolean(it.dims || it.series)
            return (
              <div
                key={it.municipio ?? it.hex_id}
                style={{
                  // SELECAO = branco, a mesma cor do contorno do hex selecionado no
                  // mapa (HexMap). Era turquesa 8%/30% — o MESMO retangulo do card de
                  // KPI do header, entao um so' tratamento visual significava
                  // "selecionado" aqui e "numero fixo do territorio" la'.
                  border: `1px solid ${ativo ? 'var(--tx-max)' : 'var(--line-soft)'}`,
                  borderRadius: 'var(--r-lg)',
                  background: ativo ? 'var(--surf-pending)' : 'var(--surf-raised)',
                  transition: 'background .15s ease, border-color .15s ease',
                }}
              >
              <div
                role="button"
                tabIndex={0}
                onClick={acionar}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault()
                    acionar()
                  }
                }}
                style={{
                  padding: '12px 13px',
                  display: 'flex',
                  alignItems: 'center',
                  gap: 12,
                  cursor: 'pointer',
                }}
              >
                <span
                  className="num"
                  aria-hidden
                  style={{
                    font: '700 14px/1 var(--f-num)',
                    color: ativo ? 'var(--tx-max)' : 'var(--tx-rank)',
                    width: 24,
                    textAlign: 'center',
                    flexShrink: 0,
                  }}
                >
                  {passo.n === 5 ? `${it.rank}º` : String(it.rank).padStart(2, '0')}
                </span>

                <span style={{ flex: 1, minWidth: 0 }}>
                  <span
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: 7,
                      flexWrap: 'wrap',
                    }}
                  >
                    <span
                      style={{
                        font: '600 14px/1.2 var(--f-ui)',
                        color: 'var(--tx-strong)',
                      }}
                    >
                      {it.titulo}
                    </span>
                    {it.tag && (
                      <Chip tom={it.tom} cor={it.tag_cor}>
                        {it.tag}
                      </Chip>
                    )}
                  </span>
                  {it.sub && (
                    <span
                      style={{
                        display: 'block',
                        font: '400 11.5px/1.3 var(--f-ui)',
                        color: 'var(--tx-label)',
                        marginTop: 3,
                      }}
                    >
                      {it.sub}
                    </span>
                  )}
                  {passo.n === 5 && (
                    <EtiquetaCrescimento cres={cresMun?.[it.municipio ?? it.titulo ?? '']} />
                  )}
                </span>

                <span style={{ textAlign: 'right', flexShrink: 0 }}>
                  <span
                    className="num"
                    style={{
                      display: 'block',
                      font: '700 15px/1 var(--f-num)',
                      color: 'var(--tx-max)',
                    }}
                  >
                    {it.label === 'residual' ? alunos(it.valor) : num(it.valor)}
                  </span>
                  <span
                    style={{
                      display: 'block',
                      font: '400 9.5px/1 var(--f-ui)',
                      color: 'var(--tx-sub)',
                      marginTop: 4,
                    }}
                  >
                    {it.label}
                  </span>
                </span>
              </div>

              {/* O detalhe e DESTE municipio, nao o da capital. */}
              {temDetalhe && (
                <div style={{ padding: '0 13px 12px' }}>
                  <Detalhes dims={it.dims ?? null} series={it.series ?? null} de={it.titulo} />
                </div>
              )}
              </div>
            )
          })
        )}

        {/* Turquesa continua aqui de proposito: e' ACAO (a unica desta lista). */}
        {selecionado && (
          <button
            type="button"
            onClick={() => onAnalisar(selecionado)}
            style={{
              marginTop: 4,
              padding: '12px',
              borderRadius: 'var(--r-md)',
              border: '1px solid var(--ac-a30)',
              background: 'var(--ac-a12)',
              color: 'var(--ac-text)',
              font: '600 12.5px/1 var(--f-ui)',
            }}
          >
            Testar viabilidade desta região →
          </button>
        )}
      </div>

      <footer
        style={{
          padding: '13px 20px',
          borderTop: '1px solid var(--line-soft)',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          gap: 10,
        }}
      >
        <span style={{ font: '400 11.5px/1 var(--f-ui)', color: 'var(--tx-sub)' }}>
          Camada visual · read-only M1
        </span>
      </footer>
    </aside>
  )
}

/**
 * Etiqueta de crescimento do municipio, no passo 5.
 *
 * CONTEXTO, nao criterio: a fila continua ordenada pelo residual que o motor
 * entregou. A etiqueta so' responde "e como essa cidade esta indo?", que era a
 * pergunta que o operador tinha de ir buscar no passo 4.
 *
 * Sem medicao, aparece assim mesmo — o silencio leria como "cresce normal".
 */
function EtiquetaCrescimento({ cres }: { cres?: CrescimentoMunicipio | null }) {
  const { classe, rotulo, delta } = lerCrescimento(cres)

  // Semantica, nao acento: verde/vermelho aqui dizem "bom/ruim para expansao", e
  // sao independentes do turquesa da marca.
  const cor =
    classe === 'acima' ? 'var(--pos-text)'
    : classe === 'abaixo' ? 'var(--neg)'
    : 'var(--tx-sub)'

  return (
    <span
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: 5,
        marginTop: 5,
        font: '500 10.5px/1.3 var(--f-ui)',
        color: cor,
      }}
    >
      <span aria-hidden style={{ width: 5, height: 5, borderRadius: '50%', background: cor }} />
      {rotulo}
      {delta != null && classe !== 'na-mediana' && (
        <span className="num" style={{ font: '500 10px/1 var(--f-num)', opacity: 0.8 }}>
          ({delta > 0 ? '+' : ''}{delta.toFixed(1).replace('.', ',')} p.p.)
        </span>
      )}
    </span>
  )
}
