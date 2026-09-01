import { useCallback, useEffect, useMemo, useRef, useState } from 'react'

import BotaoInicio from '../components/BotaoInicio'
import ExecMap from '../components/ExecMap'
import PeriodoPicker from '../components/PeriodoPicker'
import Select from '../components/Select'
import Tabela, { type Coluna } from '../components/Tabela'
import FichaUnidade from '../components/exec/FichaUnidade'
import { FunilComercial } from '../components/exec/ExecCharts'
import {
  CrescimentoComparavel,
  Destaques,
  DistribuicaoFaixas,
  EvolucaoRecorte,
  Maturidade,
} from '../components/exec/PainelRede'
import {
  Aviso,
  BarraSegmentada,
  Botao,
  Delta,
  Glass,
  Semaforo,
  SparklineSvg,
  Spinner,
} from '../components/primitives'
import { api, ApiError, baixar } from '../lib/api'
import type { BaseDoDestaque } from '../lib/exec'
import {
  COR_SEVERIDADE,
  METRICAS_EM_PONTOS,
  ORDEM_SEVERIDADE,
  corComAlfa,
  creditoDaFonte,
  destaquesDoRecorte,
  filtrarUnidades,
  formatarMetrica,
  lerDelta,
  narrativaDoRecorte,
  ordenarUnidades,
  rotuloMesCompetencia,
  tituloDaCelula,
} from '../lib/exec'
import { brlCurto, num, pct } from '../lib/format'
import type { Periodo } from '../lib/periodo'
import { rotuloDoPeriodo } from '../lib/periodo'
import type { Tema } from '../lib/tema'
import type { RedeCarteira, RedeFiltros, RedeSeveridade, RedeUnidade } from '../lib/types'

/* ---------------------------------------------------------------------------
   Visão Executiva 2.0 — a rede Ultra como CARTEIRA acionável (DEC-023).

   Dois níveis: carteira priorizada -> ficha da unidade. O mapa, que era o plano
   de fundo em tela cheia, virou um card ao lado — a pergunta que a aba responde
   deixou de ser "onde estão as unidades" e passou a ser "o que fazer com elas".

   Um único scroller (o `body` tem `overflow: hidden`): nada de scroll aninhado.
   A tela não declara componente nenhum além de composição — as primitivas vivem
   em `components/`, para não repetir o erro da v1, que tinha `Kpi`/`Delta`/
   `Legenda` locais divergentes dos homônimos de `primitives.tsx`.

   A UF NUNCA é herdada do Mapa Territorial, nem na primeira montagem: a aba abre
   com o Brasil inteiro e filtra por dentro.
   --------------------------------------------------------------------------- */

const KPIS = [
  // Faturamento por extenso, com centavo: é o número que vai para a conversa com o
  // franqueado, e "R$ 2,4M" não se confere contra extrato nenhum.
  { chave: 'faturamento', rotulo: 'Faturamento', formato: 'brl_pleno' as const, bomSubindo: true, destaque: true },
  { chave: 'ativos', rotulo: 'Alunos ativos', formato: 'int' as const, bomSubindo: true },
  // `contagem` = a métrica cujo valor ABSOLUTO vai entre parênteses ao lado do percentual.
  // 10% de churn em 80 alunos e 10% em 4.000 pedem conversas diferentes, e era o operador
  // que fazia essa conta de cabeça.
  { chave: 'churn_pct', rotulo: 'Churn', formato: 'pct' as const, bomSubindo: false, contagem: 'cancelados' },
  { chave: 'receita_por_recorrente', rotulo: 'Receita por recorrente', formato: 'brl' as const, bomSubindo: true },
  { chave: 'nps', rotulo: 'NPS', formato: 'nota' as const, bomSubindo: true },
  { chave: 'saldo_operacional', rotulo: 'Saldo operacional', formato: 'int' as const, bomSubindo: true },
]

/* Colunas de métrica da carteira.

   As larguras são PROPORÇÕES, não pixels: a `Tabela` usa `table-layout: fixed` com
   `width: 100%`, e o navegador distribui a sobra na razão das larguras declaradas.
   Por isso elas somam 1000 junto das colunas de texto — ler cada número como
   "tantos por mil da largura da tabela" é o que evita a tabela arejada demais.

   `R$/recorrente` saiu a pedido do Felipe (2026-08-06). O número continua no KPI do
   topo, no `title` da célula de cada métrica e na ficha da unidade — o que saiu foi a
   COLUNA, que era a mais larga de todas e a que menos entra na conversa de campo. */
const COLUNAS_METRICA = [
  // `folgada` / `apertada`: as proporções mudam com o espaço porque o que precisa caber
  // muda de lugar. Apertada, "FATURAMENTO" (o RÓTULO, não o número) é o texto mais largo
  // da tabela e sai com reticências se a coluna não crescer; a sparkline, que encolhe sem
  // mentir, é quem cede o espaço.
  //
  // As proporções foram RETUNADAS em 2026-08-10, quando o faturamento passou a sair por
  // extenso ("R$ 141.389,00" no lugar de "R$ 141k") e o churn ganhou a contagem entre
  // parênteses ("5,7% (486)"). As duas colunas cresceram; o espaço veio da sparkline, do
  // nome e do diagnóstico, que degradam com elegância — a sparkline encolhe sem mentir e
  // os outros dois já cortam com reticências e têm o texto inteiro no `title`.
  { chave: 'faturamento', rotulo: 'Faturamento', formato: 'brl_pleno' as const, bomSubindo: true, folgada: 152, apertada: 158 },
  { chave: 'ativos', rotulo: 'Ativos', formato: 'int' as const, bomSubindo: true, folgada: 84, apertada: 84 },
  // Churn e NPS não são as mais estreitas apesar de o VALOR ser curto: quem manda na
  // largura é o delta embaixo ("▲ 11,9 pts"), bem mais largo que "22,6%". Apertadas, era
  // o delta que saía com reticências — e delta cortado é número que engana.
  { chave: 'churn_pct', rotulo: 'Churn', formato: 'pct' as const, bomSubindo: false, contagem: 'cancelados', folgada: 120, apertada: 124 },
  { chave: 'nps', rotulo: 'NPS', formato: 'nota' as const, bomSubindo: true, folgada: 78, apertada: 80 },
]

/** Abaixo disto a carteira não comporta dois chips de diagnóstico sem cortar o segundo. */
const LARGURA_CARTEIRA_FOLGADA = 1060

/* A banda principal é uma grade de DUAS colunas que se repete faixa a faixa: o bloco
   grande à esquerda e o trilho de apoio à direita, sempre nas mesmas proporções. É o
   que faz as bordas verticais coincidirem da carteira até os gráficos de baixo — com
   cada faixa escolhendo a sua própria divisão, nenhuma aresta batia com a de cima. */
const COLUNA_PRINCIPAL = { flex: '3 1 640px', minWidth: 0 } as const
const COLUNA_TRILHO = { flex: '1 1 330px', minWidth: 0, maxWidth: 430 } as const

const TODOS = '__todos__'

export default function ExecutiveScreen({
  onInicio,
  tema,
}: {
  onInicio: () => void
  /** Tema do app (`App`). A aba já foi dona dele; hoje só o LÊ, para o `ExecMap`. */
  tema: Tema
}) {
  const [filtros, setFiltros] = useState<RedeFiltros | null>(null)
  const [carteira, setCarteira] = useState<RedeCarteira | null>(null)
  const [carregando, setCarregando] = useState(true)
  const [erro, setErro] = useState<string | null>(null)
  const [baixando, setBaixando] = useState<string | null>(null)

  // Recorte. Tudo vazio = a rede do Brasil inteiro.
  // O período começa NULO de propósito: quem sabe qual é o último intervalo com dado
  // é o servidor, e chutar "mês atual" no cliente abriria a tela num mês vazio
  // sempre que a ingestão atrasasse. A primeira resposta traz o período que ele
  // escolheu, e é dela que o calendário nasce.
  const [periodo, setPeriodo] = useState<Periodo | null>(null)
  const [uf, setUf] = useState('')
  const [master, setMaster] = useState('')
  const [consultor, setConsultor] = useState('')
  const [coorte, setCoorte] = useState('')
  const [severidades, setSeveridades] = useState<RedeSeveridade[]>([])
  const [busca, setBusca] = useState('')

  const [ordenar, setOrdenar] = useState('prioridade')
  const [direcao, setDirecao] = useState<'asc' | 'desc'>('desc')
  const [aberta, setAberta] = useState<string | null>(null)
  // Uma métrica por vez no painel de evolução. Seis gráficos empilhados é o que a
  // planilha do time já faz, e é por isso que ninguém lê nenhum deles até o fim.
  const [metricaEvolucao, setMetricaEvolucao] = useState('faturamento')
  // Base do painel de destaques e se ele está aberto na lista completa. O estado vive
  // aqui, e não no componente, para sobreviver ao refetch de um filtro: mudar de consultor
  // não pode fechar a lista que a pessoa acabou de abrir.
  const [baseDestaque, setBaseDestaque] = useState<BaseDoDestaque>('sss')
  const [destaquesAbertos, setDestaquesAbertos] = useState(false)

  // Largura REAL da carteira, medida. Não dá para decidir por media query: a tabela divide
  // a linha com o trilho do mapa, então a largura que ela tem depende também da janela do
  // navegador, do dock e do recorte — e é o corte de conteúdo que muda, não só o estilo.
  const [larguraCarteira, setLarguraCarteira] = useState(0)
  const observador = useRef<ResizeObserver | null>(null)
  const medirCarteira = useCallback((no: HTMLDivElement | null) => {
    observador.current?.disconnect()
    if (!no || typeof ResizeObserver === 'undefined') return
    const obs = new ResizeObserver(([entrada]) => setLarguraCarteira(entrada.contentRect.width))
    obs.observe(no)
    observador.current = obs
  }, [])
  useEffect(() => () => observador.current?.disconnect(), [])
  const carteiraFolgada = larguraCarteira === 0 || larguraCarteira >= LARGURA_CARTEIRA_FOLGADA

  const query = useMemo(
    () => ({
      inicio: periodo?.inicio,
      fim: periodo?.fim,
      uf: uf || undefined,
      master: master || undefined,
      consultor: consultor || undefined,
      coorte: coorte || undefined,
      severidade: severidades.length ? severidades.join(',') : undefined,
    }),
    [periodo, uf, master, consultor, coorte, severidades],
  )

  useEffect(() => {
    let vivo = true
    api
      // O vocabulário dos filtros (UFs, consultores, coortes) é da COMPETÊNCIA do fim do
      // período: as contagens de coorte mudam de mês para mês, e pedir por intervalo
      // faria a lista de opções piscar a cada arrasto no calendário.
      .redeFiltros(periodo?.fim?.slice(0, 7))
      .then((f) => vivo && setFiltros(f))
      .catch((e: ApiError) => vivo && setErro(e.message))
    return () => {
      vivo = false
    }
  }, [periodo?.fim])

  useEffect(() => {
    let vivo = true
    setCarregando(true)
    setErro(null)
    api
      .redeCarteira(query)
      .then((c) => {
        if (!vivo) return
        setCarteira(c)
        // Semeia o calendário com o que o servidor escolheu. Só na primeira vez: depois
        // disso quem manda é a pessoa, e sobrescrever aqui desfaria o arrasto dela.
        setPeriodo((atual) => atual ?? c.periodo)
      })
      .catch((e: ApiError) => {
        if (vivo) {
          setErro(e.message)
          setCarteira(null)
        }
      })
      .finally(() => vivo && setCarregando(false))
    return () => {
      vivo = false
    }
  }, [query])

  // Voltar do browser e Esc fecham a ficha — é o gesto natural de quem abriu uma.
  useEffect(() => {
    const aoVoltar = () => setAberta(null)
    window.addEventListener('popstate', aoVoltar)
    return () => window.removeEventListener('popstate', aoVoltar)
  }, [])

  useEffect(() => {
    if (!aberta) return
    const aoTeclar = (e: KeyboardEvent) => {
      if (e.key === 'Escape') fecharFicha()
    }
    window.addEventListener('keydown', aoTeclar)
    return () => window.removeEventListener('keydown', aoTeclar)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [aberta])

  const abrirFicha = useCallback((u: RedeUnidade) => {
    window.history.pushState({ unidade: u.id }, '', '')
    setAberta(u.id)
  }, [])

  function fecharFicha() {
    setAberta(null)
    if (window.history.state?.unidade) window.history.back()
  }

  const unidades = useMemo(() => {
    if (!carteira) return []
    return ordenarUnidades(filtrarUnidades(carteira.unidades, busca), ordenar, direcao)
  }, [carteira, busca, ordenar, direcao])

  function aoOrdenar(chave: string) {
    if (chave === ordenar) {
      setDirecao((d) => (d === 'asc' ? 'desc' : 'asc'))
      return
    }
    setOrdenar(chave)
    // Default por natureza da métrica: churn asc (menor é melhor), o resto desc.
    setDirecao(chave === 'churn_pct' || chave === 'nome' ? 'asc' : 'desc')
  }

  const temRecorte = Boolean(uf || master || consultor || coorte || busca || severidades.length)

  /* Sujeito das frases do panorama. A busca NÃO entra: ela é filtro de tabela, feito no
     cliente, e os painéis descrevem o recorte que o SERVIDOR somou. Dizer "MARISE" numa
     frase que conta 24 unidades enquanto a tabela mostra 3 seria mentira; por isso, com
     busca ativa, uma linha logo abaixo avisa que ela não alcança os painéis. */
  const rotuloRecorte = useMemo(() => {
    const rotuloCoorte = coorte ? filtros?.coortes.find((c) => c.chave === coorte)?.rotulo : null
    const partes = [consultor, master, uf, rotuloCoorte].filter(Boolean) as string[]
    return partes.length ? partes.join(' · ') : 'a rede'
  }, [consultor, master, uf, coorte, filtros])

  const narrativa = useMemo(
    () => (carteira ? narrativaDoRecorte(carteira, rotuloRecorte) : []),
    [carteira, rotuloRecorte],
  )

  // Sai da carteira do SERVIDOR, não da lista já filtrada pela busca — pelo mesmo motivo
  // da narrativa: os painéis falam todos do mesmo conjunto.
  const destaques = useMemo(
    () => destaquesDoRecorte(carteira?.unidades ?? [], baseDestaque),
    [carteira, baseDestaque],
  )

  function limparRecorte() {
    setUf('')
    setMaster('')
    setConsultor('')
    setCoorte('')
    setSeveridades([])
    setBusca('')
  }

  async function baixarArquivo(formato: 'csv' | 'xlsx' | 'pdf') {
    setBaixando(formato)
    try {
      const { blob, filename } = await api.redeCarteiraArquivo(formato, { ...query, ordenar, direcao })
      baixar(blob, filename)
    } catch (e) {
      setErro((e as ApiError).message)
    } finally {
      setBaixando(null)
    }
  }

  const colunas: Coluna<RedeUnidade>[] = useMemo(
    () => [
      {
        chave: 'nome',
        rotulo: 'Unidade',
        largura: carteiraFolgada ? 226 : 214,
        render: (u) => (
          <span style={{ display: 'flex', alignItems: 'center', gap: 8, minWidth: 0 }}>
            <Semaforo nivel={u.severidade} rotulo={u.severidade_rotulo} />
            <span style={{ minWidth: 0 }}>
              <span
                style={{
                  display: 'block',
                  font: '600 12.5px/1.2 var(--f-ui)',
                  color: 'var(--tx-strong)',
                  overflow: 'hidden',
                  textOverflow: 'ellipsis',
                }}
              >
                {u.nome}
              </span>
              <span style={{ display: 'block', font: '400 10px/1.2 var(--f-ui)', color: 'var(--tx-muted)', marginTop: 2 }}>
                {[u.uf, u.consultor ?? 'sem consultor', u.coorte_rotulo].join(' · ')}
              </span>
            </span>
          </span>
        ),
      },
      {
        chave: 'sparkline',
        // "12 meses" saía como "12 M…" depois que a coluna cedeu espaço para o
        // faturamento por extenso. Cabeçalho cortado no meio da palavra parece defeito;
        // a explicação inteira já está no `ajuda`, que vira o `title` da coluna.
        rotulo: '12M',
        largura: carteiraFolgada ? 72 : 56,
        ordenavel: false,
        ajuda: 'Faturamento dos 12 meses fechados',
        render: (u) => <SparklineSvg valores={u.sparkline} largura={carteiraFolgada ? 62 : 40} />,
      },
      ...COLUNAS_METRICA.map<Coluna<RedeUnidade>>((c) => ({
        chave: c.chave,
        rotulo: c.rotulo,
        largura: carteiraFolgada ? c.folgada : c.apertada,
        alinhamento: 'right',
        ajuda: `${c.rotulo} — clique para ordenar. Passe o mouse na célula para ver ranking e % vs média da rede.`,
        render: (u) => {
          const m = u.metricas[c.chave]
          const leitura = lerDelta(m, c.bomSubindo, METRICAS_EM_PONTOS.has(c.chave))
          // A contagem entra ao lado do percentual, em peso menor: o percentual continua
          // sendo o que ordena a leitura, e o absoluto diz o TAMANHO do problema.
          const contagem = c.contagem ? u.metricas[c.contagem]?.atual : null
          return (
            <span
              title={tituloDaCelula(c.rotulo, m, c.formato)}
              style={{ display: 'inline-flex', flexDirection: 'column', alignItems: 'flex-end', gap: 2 }}
            >
              <span className="num" style={{ font: '600 12px/1 var(--f-num)', color: 'var(--tx-strong)', whiteSpace: 'nowrap' }}>
                {formatarMetrica(m?.atual, c.formato)}
                {contagem !== null && contagem !== undefined && (
                  <span style={{ font: '500 10.5px/1 var(--f-num)', color: 'var(--tx-muted)' }}>
                    {' '}({num(contagem)})
                  </span>
                )}
              </span>
              <Delta leitura={leitura} tamanho={9.5} />
            </span>
          )
        },
      })),
      {
        chave: 'resumo',
        rotulo: 'Diagnóstico',
        largura: carteiraFolgada ? 268 : 284,
        ordenavel: false,
        render: (u) =>
          u.alertas.length ? (
            <span style={{ display: 'flex', gap: 5, flexWrap: 'nowrap', overflow: 'hidden' }}>
              {/* Quantos chips cabem depende da largura MEDIDA, não de um número fixo: com o
                  mapa de volta ao lado, o corte antigo de três deixava o último cortado no
                  meio da palavra, e chip pela metade parece defeito. O contador "+N" diz a
                  mesma coisa e cabe; o resto está no `title` dele, na ficha e no PDF. */}
              {u.alertas.slice(0, carteiraFolgada ? 2 : 1).map((a) => (
                <span
                  key={a.codigo}
                  title={a.detalhe}
                  style={{
                    font: '600 9.5px/1 var(--f-ui)',
                    textTransform: 'uppercase',
                    letterSpacing: '.04em',
                    padding: '4px 7px',
                    borderRadius: 'var(--r-sm)',
                    color: a.nivel === 'grave' ? COR_SEVERIDADE.alta : COR_SEVERIDADE.media,
                    background: corComAlfa(
                      a.nivel === 'grave' ? COR_SEVERIDADE.alta : COR_SEVERIDADE.media,
                      12,
                    ),
                    whiteSpace: 'nowrap',
                  }}
                >
                  {a.titulo}
                </span>
              ))}
              {u.alertas.length > (carteiraFolgada ? 2 : 1) && (
                <span
                  title={u.alertas.slice(carteiraFolgada ? 2 : 1).map((a) => a.titulo).join(' · ')}
                  style={{ font: '500 10px/1 var(--f-ui)', color: 'var(--tx-muted)', alignSelf: 'center' }}
                >
                  +{u.alertas.length - (carteiraFolgada ? 2 : 1)}
                </span>
              )}
            </span>
          ) : (
            <span style={{ font: '400 11px/1 var(--f-ui)', color: 'var(--tx-muted)' }}>
              {u.comparavel ? 'sem alerta' : 'unidade nova'}
            </span>
          ),
      },
    ],
    [carteiraFolgada],
  )

  if (erro && !carteira) {
    return <Aviso titulo="Rede indisponível" corpo={erro} />
  }

  return (
    // `data-tema` NÃO mora mais aqui: desde 2026-08-25 ele está no <html> (ver `App`), e
    // repetí-lo neste container criaria uma segunda fonte da verdade que só divergiria.
    // O `background`/`color` explícitos ficam — a aba é `position: absolute; inset: 0`
    // sobre o `main`, então ela precisa pintar o próprio fundo em qualquer tema.
    <div
      style={{
        position: 'absolute',
        inset: 0,
        display: 'flex',
        flexDirection: 'column',
        background: 'var(--bg-base)',
        color: 'var(--tx-strong)',
      }}
    >
      <header
        style={{
          flexShrink: 0,
          margin: '16px 16px 0',
          padding: '9px 14px 7px',
          background: 'var(--surf-chrome)',
          border: '1px solid var(--line-soft)',
          borderRadius: 'var(--r-xl)',
          backdropFilter: 'blur(14px)',
          // `position: relative` + `zIndex` são OBRIGATÓRIOS aqui, e não são enfeite:
          // `backdropFilter` cria um CONTEXTO DE EMPILHAMENTO, então o `zIndex: 40` do
          // popup do Select vale só dentro deste cabeçalho. Sem elevar o cabeçalho
          // inteiro, o scroller — que vem depois no DOM e cujos cards também têm
          // `backdropFilter` — pinta por cima, e a lista de opções abre ATRÁS dos cards.
          position: 'relative',
          zIndex: 30,
        }}
      >
        {/* Faixa 1 — só o que o operador MANIPULA. O período de referência e a contagem
            de unidades saíram daqui para a legenda de baixo: eram duas linhas de texto
            no meio da fila de controles, e a cada filtro que entrava empurravam os
            botões de export para a linha seguinte. */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
        <BotaoInicio onInicio={onInicio} />
        <h1 style={{ font: '600 14px/1 var(--f-ui)', letterSpacing: '-.01em', color: 'var(--tx-max)', margin: 0 }}>
          Rede Ultra
        </h1>
        <span aria-hidden style={{ width: 1, height: 20, background: 'var(--line-mid)' }} />

        {/* O período fica na FILA dos filtros, e não numa faixa própria: são dois campos
            de data e nada mais, exatamente para o cabeçalho não crescer. Os seis chips de
            atalho ("Mês atual", "Últimos 90 dias"…) que existiram aqui saíram por isso
            (Felipe, 2026-08-10) — quebravam a linha e empurravam os botões de export. */}
        {carteira && periodo && (
          <Filtro rotulo="Período">
            <PeriodoPicker periodo={periodo} limite={carteira.limites} onChange={setPeriodo} />
          </Filtro>
        )}

        <Filtro rotulo="UF">
          <Select
            label="Estado"
            value={uf || TODOS}
            onChange={(v) => setUf(v === TODOS ? '' : v)}
            maxWidth={96}
            options={[
              { value: TODOS, label: 'Brasil' },
              ...(filtros?.ufs ?? []).map((u) => ({ value: u, label: u })),
            ]}
          />
        </Filtro>
        <Filtro rotulo="Consultor">
          <Select
            label="Consultor"
            value={consultor || TODOS}
            onChange={(v) => setConsultor(v === TODOS ? '' : v)}
            maxWidth={148}
            options={[
              { value: TODOS, label: 'Todos' },
              ...(filtros?.consultores ?? []).map((c) => ({ value: c, label: c })),
            ]}
          />
        </Filtro>
        <Filtro rotulo="Master">
          <Select
            label="Master"
            value={master || TODOS}
            onChange={(v) => setMaster(v === TODOS ? '' : v)}
            maxWidth={126}
            options={[
              { value: TODOS, label: 'Todos' },
              ...(filtros?.masters ?? []).map((m) => ({ value: m, label: m })),
            ]}
          />
        </Filtro>
        <Filtro rotulo="Maturidade">
          <Select
            label="Coorte de maturidade"
            value={coorte || TODOS}
            onChange={(v) => setCoorte(v === TODOS ? '' : v)}
            maxWidth={152}
            options={[
              { value: TODOS, label: 'Todas' },
              ...(filtros?.coortes ?? []).map((c) => ({ value: c.chave, label: `${c.rotulo} (${c.n})` })),
            ]}
          />
        </Filtro>

        <input
          value={busca}
          onChange={(e) => setBusca(e.target.value)}
          placeholder="Buscar unidade, cidade…"
          aria-label="Buscar unidade"
          style={{ width: 176 }}
        />
        {temRecorte && (
          <Botao variante="ghost" onClick={limparRecorte}>
            Limpar filtros
          </Botao>
        )}

        {/* O sol/lua morava aqui, encostado na borda direita, e saiu em 2026-08-25: com o
            tema valendo para o app inteiro ele passou para o pé do Dock, o único chrome
            presente nas cinco telas. Dois alternadores para um estado só fariam o daqui
            parecer que troca a pele apenas desta aba.

            O vão flexível que o empurrava saiu JUNTO. Sozinho no fim de uma linha
            `flexWrap: 'wrap'` ele não empurrava mais nada, e em tela estreita — quando os
            filtros quebram — caía numa linha própria de altura zero, somando os 10px do
            `gap` como uma faixa vazia sob o cabeçalho. Os filtros já ficam à esquerda pelo
            `flex-start` padrão do contêiner. */}
        </div>

        {/* Faixa 2 — legenda: o que o número em cima significa. Uma linha discreta, que
            quebra sozinha em tela estreita sem empurrar controle nenhum. */}
        {carteira && (
          <div
            style={{
              marginTop: 7,
              paddingTop: 6,
              borderTop: '1px solid var(--line-soft)',
              display: 'flex',
              alignItems: 'center',
              gap: 14,
              flexWrap: 'wrap',
              font: '400 10.5px/1.4 var(--f-ui)',
              color: 'var(--tx-muted)',
            }}
          >
            <span>
              Período{' '}
              <strong style={{ color: 'var(--tx-sub)' }}>{rotuloDoPeriodo(carteira.periodo)}</strong>
              {carteira.periodo.mes_inteiro
                ? carteira.mes_completo
                  ? ' (mês fechado)'
                  : ' (mês em curso)'
                : ` (${carteira.periodo.dias} dias)`}
            </span>
            <span className="num">
              até {carteira.referencia} · compara com {carteira.referencia_m1}
            </span>
            <span className="num">
              {carteira.totais.no_recorte} de {carteira.totais.rede} unidades
              {carteira.totais.com_coordenada < carteira.totais.no_recorte
                ? ` · ${carteira.totais.com_coordenada} no mapa`
                : ''}
            </span>
            {carteira.competencia_diagnostico && carteira.competencia_diagnostico !== carteira.mes && (
              <span>
                diagnóstico de{' '}
                <strong style={{ color: 'var(--tx-sub)' }}>
                  {rotuloMesCompetencia(carteira.competencia_diagnostico)}
                </strong>
                , o último mês fechado
              </span>
            )}
            <div style={{ flex: 1 }} />
            {/* O crédito da fonte segue o que a aba REALMENTE está mostrando. Enquanto
                dizia só "Growth API", já era faturamento da planilha do Financeiro no
                gráfico de 12 meses — e o crédito errado é o tipo de detalhe que derruba a
                confiança no painel inteiro. */}
            <span>{creditoDaFonte(carteira.fonte_faturamento)}</span>
            {/* Os exports moram na faixa da LEGENDA desde 2026-08-10. Na fila dos
                controles eles eram os primeiros a cair para uma segunda linha quando o
                seletor de datas entrou — e cabeçalho de três linhas come a altura da
                carteira. Aqui embaixo sobra espaço, e baixar o arquivo não é filtrar. */}
            <div style={{ display: 'flex', gap: 6, marginLeft: 4 }}>
              {(['csv', 'xlsx', 'pdf'] as const).map((f) => (
                <Botao
                  key={f}
                  variante="ghost"
                  onClick={() => baixarArquivo(f)}
                  disabled={baixando !== null}
                  style={{ padding: '5px 9px', font: '600 10.5px/1 var(--f-ui)' }}
                >
                  {baixando === f ? <Spinner tamanho={10} /> : '↓'} {f.toUpperCase()}
                </Botao>
              ))}
            </div>
          </div>
        )}
      </header>

      <div
        style={{
          flex: 1,
          overflowY: 'auto',
          overflowX: 'hidden',
          padding: '14px 16px 22px',
          minHeight: 0,
          // Explícito para não voltar a competir com o cabeçalho por ordem de DOM.
          position: 'relative',
          zIndex: 0,
        }}
      >
        {carregando && !carteira ? (
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, padding: 40, color: 'var(--tx-sub)' }}>
            <Spinner /> Lendo a rede Ultra…
          </div>
        ) : !carteira ? null : aberta ? (
          <FichaUnidade unidadeId={aberta} mes={carteira.mes} onVoltar={fecharFicha} />
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
            <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
              {KPIS.map((k) => {
                const m = carteira.kpis[k.chave]
                return (
                  <Glass key={k.chave} style={{ flex: '1 1 168px', padding: '13px 15px', minWidth: 0 }}>
                    <div style={{ font: '500 10.5px/1.2 var(--f-ui)', color: 'var(--tx-label)' }}>{k.rotulo}</div>
                    <div
                      className="num"
                      style={{
                        // 19px, e nao 21: "R$ 2.441.416,10" por extenso e' o valor mais
                        // largo da fileira e estourava o card no ponto em que os seis KPIs
                        // ainda cabem numa linha so.
                        font: '700 19px/1 var(--f-num)',
                        color: k.destaque ? 'var(--ac-text)' : 'var(--tx-max)',
                        marginTop: 7,
                        whiteSpace: 'nowrap',
                      }}
                    >
                      {formatarMetrica(m?.atual, k.formato)}
                      {k.contagem && carteira.kpis[k.contagem]?.atual !== null && (
                        <span style={{ font: '500 12px/1 var(--f-num)', color: 'var(--tx-muted)' }}>
                          {' '}({num(carteira.kpis[k.contagem]?.atual)})
                        </span>
                      )}
                    </div>
                    <div style={{ marginTop: 6 }}>
                      <Delta leitura={lerDelta(m, k.bomSubindo, METRICAS_EM_PONTOS.has(k.chave))} />
                      <span style={{ font: '400 9px/1 var(--f-ui)', color: 'var(--tx-muted)', marginLeft: 4 }}>
                        vs M-1
                      </span>
                    </div>
                  </Glass>
                )
              })}
            </div>

            {/* Carteira e mapa LADO A LADO (pedido do Felipe, 2026-08-06).
                A tentativa anterior — carteira em largura total, mapa na faixa de baixo —
                resolvia a falta de espaço das colunas e criava dois problemas piores: a
                tabela esticada em ~1800 px virava um campo de vãos entre números, e o mapa
                ficava numa faixa com dois cards curtos ao lado, cada um terminando numa
                altura, o que jogava as bordas de todas as faixas seguintes fora de esquadro.

                O que faz caber agora, e antes não cabia: uma coluna a menos
                (`R$/recorrente` saiu) e larguras declaradas como PROPORÇÃO. O trilho da
                direita empilha mapa, composição e SSS — assim ele termina na mesma linha
                que a carteira, e o mapa absorve a diferença (`flex: 1`), em vez de sobrar
                um vazio embaixo dos cards curtos. */}
            <div style={{ display: 'flex', gap: 14, alignItems: 'stretch', flexWrap: 'wrap' }}>
              <Glass style={{ ...COLUNA_PRINCIPAL, padding: 0, overflow: 'hidden' }}>
                <div
                  style={{
                    padding: '13px 16px 11px',
                    display: 'flex',
                    alignItems: 'center',
                    gap: 10,
                    flexWrap: 'wrap',
                    borderBottom: '1px solid var(--line-soft)',
                  }}
                >
                  <span style={{ font: '600 10.5px/1 var(--f-ui)', letterSpacing: '.09em', textTransform: 'uppercase', color: 'var(--tx-muted)' }}>
                    Carteira
                  </span>
                  <div style={{ flex: 1 }} />
                  {ORDEM_SEVERIDADE.map((s) => {
                    const n = carteira.semaforo[s] ?? 0
                    const ativo = severidades.includes(s)
                    // Um chip com contagem zero continua na tela SE estiver ativo. Sem
                    // isso, filtrar por "alta" e depois trocar para uma UF sem nenhuma
                    // unidade alta fazia o chip sumir com o filtro ainda aplicado: a
                    // carteira ficava vazia e não havia como desfazer, a não ser F5.
                    if (!n && !ativo) return null
                    return (
                      <button
                        key={s}
                        type="button"
                        onClick={() =>
                          setSeveridades((atual) =>
                            atual.includes(s) ? atual.filter((x) => x !== s) : [...atual, s],
                          )
                        }
                        title={`Filtrar por ${s}`}
                        style={{
                          display: 'inline-flex',
                          alignItems: 'center',
                          gap: 6,
                          padding: '5px 9px',
                          borderRadius: 'var(--r-sm)',
                          border: `1px solid ${ativo ? COR_SEVERIDADE[s] : 'var(--line-soft)'}`,
                          background: ativo ? corComAlfa(COR_SEVERIDADE[s], 12) : 'transparent',
                          color: 'var(--tx-soft)',
                          font: '600 10.5px/1 var(--f-ui)',
                          cursor: 'pointer',
                        }}
                      >
                        <Semaforo nivel={s} tamanho={7} />
                        {n}
                      </button>
                    )
                  })}
                </div>
                <div ref={medirCarteira} style={{ maxHeight: 560, overflowY: 'auto' }}>
                  <Tabela
                    colunas={colunas}
                    dados={unidades}
                    chaveDe={(u) => u.id}
                    ordenarPor={ordenar}
                    direcao={direcao}
                    onOrdenar={aoOrdenar}
                    onLinha={abrirFicha}
                    vazio="Nenhuma unidade neste recorte. Limpe um filtro ou a busca."
                  />
                </div>
              </Glass>

              {/* Trilho de apoio. Empilhado numa coluna só, e não três cards soltos na
                  mesma linha: soltos, cada um parava numa altura diferente e a faixa
                  terminava em serrilha. */}
              <div style={{ ...COLUNA_TRILHO, display: 'flex', flexDirection: 'column', gap: 14 }}>
                <Glass style={{ flex: '1 1 auto', minHeight: 300, padding: 0, overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
                  <div style={{ padding: '13px 16px 9px', font: '600 10.5px/1 var(--f-ui)', letterSpacing: '.09em', textTransform: 'uppercase', color: 'var(--tx-muted)' }}>
                    Onde estão
                  </div>
                  {/* O mapa é quem ESTICA: `flex: 1` faz a altura dele ser a sobra da
                      coluna, de modo que o trilho termine exatamente onde a carteira
                      termina. Altura fixa aqui deixaria um vão no pé de uma das duas. */}
                  <div style={{ position: 'relative', flex: 1, minHeight: 190 }}>
                    <ExecMap
                      unidades={unidades}
                      centro={carteira.centro}
                      bbox={carteira.bbox}
                      iconeUltra={carteira.ultra_icon}
                      tema={tema}
                      onUnidade={(id) => {
                        const u = unidades.find((x) => x.id === id)
                        if (u) abrirFicha(u)
                      }}
                    />
                  </div>
                  <div style={{ padding: '9px 16px 12px', font: '400 10.5px/1.45 var(--f-ui)', color: 'var(--tx-muted)' }}>
                    {carteira.totais.com_coordenada} de {carteira.totais.no_recorte} unidades com
                    coordenada. Bolha = faturamento; cor = diagnóstico.
                  </div>
                </Glass>

                <Glass style={{ flexShrink: 0, padding: '14px 16px' }}>
                  <Rotulo>Recorrentes × agregadores</Rotulo>
                  <div style={{ display: 'flex', justifyContent: 'space-between', font: '500 10.5px/1 var(--f-ui)', color: 'var(--tx-label)', marginBottom: 6 }}>
                    <span>Recorrentes {pct(carteira.split.pct_recorrentes, 0)}</span>
                    <span>Agregadores {pct(carteira.split.pct_agregadores, 0)}</span>
                  </div>
                  <BarraSegmentada
                    partes={[
                      { chave: 'rec', valor: carteira.split.recorrentes ?? 0, cor: 'var(--ac)', rotulo: 'Recorrentes' },
                      { chave: 'agr', valor: carteira.split.agregadores ?? 0, cor: 'var(--gr-rosa)', rotulo: 'Agregadores' },
                    ]}
                  />
                  <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 7, font: '400 10.5px/1 var(--f-ui)', color: 'var(--tx-sub)' }}>
                    <span className="num">{num(carteira.split.recorrentes)}</span>
                    <span className="num">{num(carteira.split.agregadores)}</span>
                  </div>
                </Glass>

                {carteira.sss.disponivel && carteira.sss.metricas && (
                  <Glass style={{ flexShrink: 0, padding: '14px 16px' }}>
                    <Rotulo>Mesma base, ano a ano (SSS)</Rotulo>
                    <div style={{ font: '400 10.5px/1.5 var(--f-ui)', color: 'var(--tx-muted)', marginBottom: 10 }}>
                      {carteira.sss.unidades} unidades presentes nos dois períodos. Comparar total
                      contra total infla o crescimento numa rede que abre lojas.
                    </div>
                    {(['faturamento', 'ativos'] as const).map((chave) => {
                      const m = carteira.sss.metricas?.[chave]
                      if (!m) return null
                      return (
                        <div key={chave} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginTop: 6 }}>
                          <span style={{ font: '400 11.5px/1 var(--f-ui)', color: 'var(--tx-label)' }}>
                            {chave === 'faturamento' ? 'Faturamento' : 'Alunos ativos'}
                          </span>
                          <span className="num" style={{ font: '600 12px/1 var(--f-num)', color: 'var(--tx-strong)' }}>
                            {chave === 'faturamento' ? brlCurto(m.atual) : num(m.atual)}{' '}
                            <span
                              style={{
                                color:
                                  (m.var_pct ?? 0) >= 0 ? 'var(--pos, #37b26b)' : 'var(--neg, #ff5a6e)',
                              }}
                            >
                              {m.var_pct === null ? '' : `${m.var_pct > 0 ? '+' : ''}${pct(m.var_pct, 1)}`}
                            </span>
                          </span>
                        </div>
                      )
                    })}
                  </Glass>
                )}
              </div>
            </div>

            {/* ================= PANORAMA DO RECORTE =================

                A carteira acima responde "com quem falar hoje". Daqui para baixo é o
                AGREGADO: para onde o recorte anda, se o crescimento é da operação ou da
                expansão, onde a massa está e quem puxa. Tudo obedece aos mesmos filtros
                do cabeçalho — foi justamente o que faltava ao SSS, que somava a rede
                inteira mesmo com um consultor selecionado.

                As faixas repetem a divisão da faixa de cima (bloco grande + trilho) para
                as bordas verticais correrem retas da carteira até o fim da tela. Os
                painéis já vêm dentro do próprio `Glass`, então o que se monta aqui é só a
                grade: `display: grid` no invólucro faz o card preencher as duas direções
                da coluna, e cards de alturas diferentes param na mesma linha. */}
            <Glass style={{ padding: '16px 18px' }}>
              <Rotulo>Panorama do recorte</Rotulo>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 7 }}>
                {narrativa.map((frase, i) => (
                  <p
                    key={frase}
                    style={{
                      margin: 0,
                      // A primeira frase é o lide: ela sozinha responde "como estamos".
                      font: i === 0 ? '400 13.5px/1.6 var(--f-ui)' : '400 12.5px/1.7 var(--f-ui)',
                      color: i === 0 ? 'var(--tx-strong)' : 'var(--tx-narrative)',
                    }}
                  >
                    {frase}
                  </p>
                ))}
              </div>
              {busca.trim() && (
                <div style={{ marginTop: 9, font: '400 10.5px/1.5 var(--f-ui)', color: 'var(--tx-muted)' }}>
                  A busca por “{busca.trim()}” filtra a carteira e o mapa; os painéis abaixo
                  continuam somando o recorte inteiro dos filtros.
                </div>
              )}
            </Glass>

            <div style={{ display: 'flex', gap: 14, alignItems: 'stretch', flexWrap: 'wrap' }}>
              <div style={{ ...COLUNA_PRINCIPAL, display: 'grid' }}>
                <EvolucaoRecorte
                  meses={carteira.serie_meses}
                  series={carteira.series}
                  metrica={metricaEvolucao}
                  onMetrica={setMetricaEvolucao}
                  fonte={carteira.fonte_faturamento}
                />
              </div>
              <div style={{ ...COLUNA_TRILHO, display: 'grid' }}>
                <CrescimentoComparavel sss={carteira.sss} />
              </div>
            </div>

            <div style={{ display: 'flex', gap: 14, alignItems: 'stretch', flexWrap: 'wrap' }}>
              <Glass style={{ ...COLUNA_PRINCIPAL, padding: '15px 17px' }}>
                <Rotulo>Funil comercial do recorte</Rotulo>
                <FunilComercial
                  visitas={carteira.funil.visitas}
                  convertidos={carteira.funil.convertidos}
                  vendas={carteira.funil.vendas}
                  novosAlunos={carteira.funil.novos_alunos}
                  conversao={carteira.funil.conversao_pct}
                  aviso={carteira.funil.aviso}
                />
                <div style={{ marginTop: 10, font: '400 10.5px/1.5 var(--f-ui)', color: 'var(--tx-muted)' }}>
                  Etapas somadas do recorte
                  {carteira.mes_completo
                    ? ` no fechamento de ${rotuloMesCompetencia(carteira.mes)}.`
                    : ` até ${carteira.referencia}, com a competência ${rotuloMesCompetencia(carteira.mes)} ainda em curso.`}{' '}
                  A conversão é a mesma do KPI: ponderada por visitas, nunca a média das
                  unidades.
                </div>
              </Glass>
              {/* Faixas e maturidade ficam em faixas DIFERENTES, uma em cada trilho: os
                  dois empilhados aqui somavam mais altura que o funil ao lado, e o card
                  do funil — que tem quatro barras e nada mais — esticava com um vão de
                  quase 200 px no pé. Um card por trilho deixa as duas faixas em esquadro. */}
              <div style={{ ...COLUNA_TRILHO, display: 'grid' }}>
                <DistribuicaoFaixas faixas={carteira.faixas} />
              </div>
            </div>

            <div style={{ display: 'flex', gap: 14, alignItems: 'stretch', flexWrap: 'wrap' }}>
              <div style={{ ...COLUNA_PRINCIPAL, display: 'grid' }}>
                <Destaques
                  destaques={destaques}
                  base={baseDestaque}
                  onBase={setBaseDestaque}
                  expandido={destaquesAbertos}
                  onExpandir={setDestaquesAbertos}
                  onUnidade={abrirFicha}
                />
              </div>
              <div style={{ ...COLUNA_TRILHO, display: 'grid' }}>
                <Maturidade coortes={carteira.coortes} />
              </div>
            </div>

            <div style={{ display: 'flex', gap: 14, alignItems: 'stretch', flexWrap: 'wrap' }}>
              <Glass style={{ ...COLUNA_PRINCIPAL, padding: '14px 18px' }}>
                <Rotulo>Notas de método</Rotulo>
                <ul style={{ margin: 0, paddingLeft: 18, font: '400 11.5px/1.7 var(--f-ui)', color: 'var(--tx-narrative)' }}>
                  {carteira.notas.map((n) => (
                    <li key={n}>{n}</li>
                  ))}
                  <li>
                    Ranking e “% vs média da rede” saem sempre da rede inteira, nunca do recorte
                    filtrado — mudar um filtro não muda a posição de ninguém.
                  </li>
                  <li>{creditoDaFonte(carteira.fonte_faturamento, true)}</li>
                </ul>
              </Glass>
              <Glass style={{ ...COLUNA_TRILHO, padding: '15px 17px' }}>
                <Rotulo>Réguas vigentes</Rotulo>
                <ul style={{ margin: 0, paddingLeft: 16, font: '400 11.5px/1.7 var(--f-ui)', color: 'var(--tx-narrative)' }}>
                  {Object.entries(carteira.reguas).map(([chave, r]) => (
                    <li key={chave}>
                      {r.rotulo}:{' '}
                      <strong style={{ color: 'var(--tx-strong)' }}>
                        {r.sentido === 'persistencia'
                          ? `negativo por ${r.meses} meses fechados`
                          : `${r.sentido === 'acima' ? 'acima de' : 'abaixo de'} ${num(r.limiar, 1)}${r.unidade === '%' ? '%' : ` ${r.unidade ?? ''}`}`}
                      </strong>
                    </li>
                  ))}
                  <li>
                    Meta de NPS da rede: <strong style={{ color: 'var(--tx-strong)' }}>{carteira.meta_nps}</strong> —
                    meta não é alerta.
                  </li>
                </ul>
              </Glass>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

function Filtro({ rotulo, children }: { rotulo: string; children: React.ReactNode }) {
  return (
    <label style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
      <span className="num" style={{ font: '500 10px/1 var(--f-num)', color: 'var(--tx-muted)', textTransform: 'uppercase' }}>
        {rotulo}
      </span>
      {children}
    </label>
  )
}

function Rotulo({ children }: { children: React.ReactNode }) {
  return (
    <div
      style={{
        font: '600 10.5px/1 var(--f-ui)',
        letterSpacing: '.09em',
        textTransform: 'uppercase',
        color: 'var(--tx-muted)',
        marginBottom: 11,
      }}
    >
      {children}
    </div>
  )
}
