import { useCallback, useEffect, useRef, useState } from 'react'

import type { PontoEscolhido } from '../App'

import BlocoViabilidadePonto from '../components/BlocoViabilidadePonto'
import BotaoInicio from '../components/BotaoInicio'
import CampoPonto from '../components/CampoPonto'
import DetalheRegiao from '../components/DetalheRegiao'
import HexMap, { type SearchPin } from '../components/HexMap'
import JanelaFicha from '../components/JanelaFicha'
import MapaPonto from '../components/MapaPonto'
import PainelPontos from '../components/PainelPontos'
import Recomendacao from '../components/Recomendacao'
import ScoreLegend from '../components/ScoreLegend'
import StepperBar from '../components/StepperBar'
import { Aviso, Botao, Chip, Eyebrow, Glass, Kpi, Spinner } from '../components/primitives'
import { api, ApiError } from '../lib/api'
import { MAX_PONTOS } from '../lib/comparacao-pontos'
import { linkGoogleMaps, type EntradaClassificada } from '../lib/entrada-ponto'
import { num } from '../lib/format'
import type {
  BlocoOpcional,
  MunicipioPayload,
  PontoPayload,
  ViabilidadeOut,
} from '../lib/types'

/**
 * Modo 1 — analise de um PONTO/IMOVEL.
 *
 * LAYOUT DE MAPA, nao de ficha. A tela ABRE no mapa e a ficha vira uma GAVETA que se
 * puxa por um unico botao. Antes era o contrario: a ficha era a tela e o mapa uma caixa
 * de 300px no meio dela. A inversao e' pedido do Juan (2026-08-10) e tem uma razao de
 * leitura: a pergunta do modo e' "o que ha' em volta deste endereco?", e a resposta e'
 * geografica — a lista de numeros e' a evidencia, nao a manchete.
 *
 * O MAPA E' O MESMO DO "EXPLORAR" (`HexMap` + funil + stepper + legenda), centrado no
 * ponto. REVERTE a decisao que este docstring registrava ate 2026-08-10 ("continua sem
 * funil e sem StepperBar", com o `MapaPonto` desenhando so' o hexagono do imovel e os 18
 * vizinhos). O pedido e' do Juan e a razao dele vence a minha: quem cola um endereco
 * quer decidir, e decidir exige ver a cidade em volta na MESMA regua com que o resto do
 * produto fala — nao um recorte de 19 hexagonos com vocabulario proprio. O custo
 * (carregar a particao do municipio) e' o mesmo que o Explorar ja paga.
 *
 * O `MapaPonto` SOBREVIVE como degradacao. Municipio nao resolvido pelo `/api/ponto` (o
 * campo e' `string | null`) ou falha na carga do territorio: em vez de tela preta, volta
 * o mapa de vizinhanca, que so' precisa da propria ficha. Nao e' codigo morto — e' o
 * caminho de quando o funil nao se aplica.
 *
 * ESTADO VAZIO POR BLOCO. Cada bloco pergunta ao SERVIDOR se tem dado (`disponivel`) e
 * mostra o `motivo` que ele devolveu. A cadeia de dados degrada em silencio por desenho
 * (staging ausente -> `(None, None)` sem excecao), entao um bloco que sumisse sozinho
 * seria lido como defeito. Nenhum texto de estado vazio e' inventado aqui.
 */
export default function PontoScreen({
  onInicio,
  onAnalisarPonto,
}: {
  onInicio: () => void
  /** Leva ESTE ponto para a tela de Viabilidade (a costura com o resto do app). */
  onAnalisarPonto: (p: PontoEscolhido) => void
}) {
  const [carregando, setCarregando] = useState(false)
  const [erro, setErro] = useState<string | null>(null)
  /**
   * Os pontos colados, na ordem em que entraram.
   *
   * Lista e nao objeto unico porque a pergunta do operador quase nunca e' "este imovel
   * serve?" isolada — e' "qual DESTES serve mais?". Cada ponto e' uma leitura completa
   * do `/api/ponto`; o teto de `MAX_PONTOS` existe porque cada um custa uma leitura de
   * particao de municipio no servidor.
   */
  const [fichas, setFichas] = useState<PontoPayload[]>([])
  /** Qual ficha esta aberta em detalhe. Com 1 ponto e' sempre ela. */
  const [aberto, setAberto] = useState(0)
  /** A caixa de colar so' aparece quando pedida — depois do 1o ponto ela some. */
  const [colando, setColando] = useState(true)
  /**
   * A janela da ficha.
   *
   * Abre SOZINHA quando uma leitura chega: o operador colou o ponto justamente para
   * saber se ele serve, e cobrar um clique a mais pela resposta seria burocracia. Depois
   * disso quem manda e' ele — fechou, o mapa fica limpo ate' pedir de novo.
   */
  const [janela, setJanela] = useState(false)

  const ficha = fichas[aberto] ?? null

  /**
   * O TERRITORIO em volta do ponto: a mesma carga que o "Explorar" faz no drill-down de
   * um municipio (`/api/municipio/{uf}/{municipio}`), com os 5 passos do funil, os
   * hexagonos e os pins de concorrentes.
   *
   * Municipio e nao UF: o `/api/ponto` ja devolve a cidade do endereco, e o estado
   * inteiro seria contexto demais para a pergunta "este imovel serve?" — a partir de
   * zoom 10 o operador nem enxerga o resto da UF. No servidor o custo e' o mesmo: os dois
   * endpoints leem a MESMA particao `uf=XX`, cacheada por processo.
   */
  const [territorio, setTerritorio] = useState<MunicipioPayload | null>(null)
  const [carregandoTerritorio, setCarregandoTerritorio] = useState(false)
  /** Qual camada do funil colore o mapa. Mesma numeracao do "Explorar" (1..5). */
  const [passoN, setPassoN] = useState(1)
  const [hexSelecionado, setHexSelecionado] = useState<string | null>(null)

  const uf = ficha?.local.uf ?? null
  const municipio = ficha?.local.municipio ?? null

  /**
   * Carrega o territorio quando o ponto aberto muda de CIDADE.
   *
   * A chave e' `uf|municipio`, nao a ficha: comparar cinco pontos do mesmo municipio tem
   * de custar UMA carga, nao cinco. O `cancelado` fecha a corrida — trocar de ponto
   * durante a carga faria a resposta antiga chegar depois e pintar o mapa com a cidade
   * errada.
   */
  const chaveCarregada = useRef<string | null>(null)
  useEffect(() => {
    if (!uf || !municipio) {
      chaveCarregada.current = null
      setTerritorio(null)
      return
    }
    const chave = `${uf}|${municipio}`
    // A chave JA TENTADA mora em ref, nao no `territorio`. Com `territorio` na lista de
    // dependencias, uma carga que FALHA (-> setTerritorio(null)) mudava o estado e
    // disparava o efeito de novo, refazendo a mesma requisicao que acabou de falhar.
    if (chaveCarregada.current === chave) return
    chaveCarregada.current = chave

    let cancelado = false
    setCarregandoTerritorio(true)
    // Hexagono selecionado e' de OUTRA cidade a partir daqui: mante-lo deixaria um
    // contorno branco sobre um hexagono que nao esta mais no `hexes`.
    setHexSelecionado(null)
    api
      .municipio(uf, municipio)
      .then((d) => {
        if (!cancelado) setTerritorio(d)
      })
      .catch(() => {
        // Silencioso DE PROPOSITO: a ficha ja esta na tela e o `MapaPonto` assume o
        // fundo. Um erro vermelho aqui culparia o operador por uma degradacao que nao
        // muda a resposta que ele veio buscar.
        if (!cancelado) setTerritorio(null)
      })
      .finally(() => {
        if (!cancelado) setCarregandoTerritorio(false)
      })
    return () => {
      cancelado = true
    }
  }, [uf, municipio])

  /** O passo que colore o mapa. `passos` vem com 5; o estado e' 1-based. */
  const passo = territorio?.passos[passoN - 1] ?? null

  /** O pin do imovel colado — a mesma marca que a busca por coordenada solta no Explorar. */
  const pinDoPonto: SearchPin | null = ficha
    ? { lat: ficha.lat, lng: ficha.lng, hexId: ficha.hex_id }
    : null

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
          return
        }
        coord = { lat: r.lat, lng: r.lng }
      }
      const nova = await api.ponto(coord.lat, coord.lng)
      // O ponto novo entra no fim e vira o aberto: quem acabou de colar quer ver ele.
      setFichas((atuais) => {
        const proximas = [...atuais, nova].slice(0, MAX_PONTOS)
        setAberto(proximas.length - 1)
        return proximas
      })
      setColando(false)
      setJanela(true)
    } catch (e) {
      // NAO limpa os pontos ja lidos: perder tres leituras porque a quarta falhou
      // seria punir o operador por um endereco mal digitado.
      setErro(e instanceof ApiError ? e.message : 'Falha ao analisar o ponto.')
    } finally {
      setCarregando(false)
    }
  }

  const mostrandoCaixa = colando || fichas.length === 0

  return (
    <div style={{ position: 'absolute', inset: 0, overflow: 'hidden' }}>
      {/* O mapa É a tela: fica no fundo, ocupando tudo, com o resto flutuando por cima.
          É o MESMO `HexMap` do Explorar — mesmas camadas, mesma rampa, mesmos pins —,
          centrado na cidade do imóvel. Sem o território (município não resolvido ou carga
          falhou) cai no mapa de vizinhança, que só precisa da própria ficha. */}
      {territorio && passo ? (
        <HexMap
          hexes={territorio.hexes}
          passo={passo}
          cresMun={territorio.cres_mun}
          centro={territorio.centro}
          municipio={territorio.municipio ?? undefined}
          uf={territorio.uf}
          pins={territorio.pins}
          selecionado={hexSelecionado}
          onSelecionar={(h) => setHexSelecionado(h.id)}
          /* O pin é o IMÓVEL COLADO, não uma busca: é ele que manda a câmera voar para cá
             na montagem, e é o que amarra a leitura da ficha ao que está desenhado. */
          searchPin={pinDoPonto}
        />
      ) : (
        <MapaPonto ficha={ficha} />
      )}

      {/* ---------------- Chrome flutuante ----------------
          Coluna flex em vez de peças com `top` fixo: o cabeçalho quebra em duas linhas
          em tela estreita, e com posições fixas ele passaria por cima da caixa de colar.
          `pointerEvents: none` no contêiner devolve ao mapa o mouse nos vãos entre as
          peças — sem isso, uma faixa invisível no topo engoliria o arraste. */}
      <div
        style={{
          position: 'absolute',
          top: 0,
          left: 0,
          right: 0,
          zIndex: 30,
          padding: 16,
          display: 'flex',
          flexDirection: 'column',
          gap: 12,
          pointerEvents: 'none',
        }}
      >
        <header
          style={{
            pointerEvents: 'auto',
            alignSelf: 'stretch',
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
              {fichas.length > 1
                ? `${fichas.length} pontos · raio de ${num(ficha.raio_km * 1000)} m`
                : `raio de ${num(ficha.raio_km * 1000)} m · ${ficha.censo.n_setores ?? '—'} setores`}
            </Chip>
          )}
        </header>

        {mostrandoCaixa && (
          <Glass
            style={{
              pointerEvents: 'auto',
              alignSelf: 'center',
              width: 'min(620px, 100%)',
              padding: 16,
              display: 'grid',
              gap: 10,
            }}
          >
            <CampoPonto onResolver={resolver} ocupado={carregando} erro={erro} />
            {fichas.length > 0 ? (
              <button
                type="button"
                onClick={() => {
                  setColando(false)
                  setErro(null)
                }}
                style={{
                  justifySelf: 'start',
                  padding: '6px 10px',
                  borderRadius: 8,
                  border: '1px solid var(--line-soft)',
                  background: 'var(--surf-raised)',
                  color: 'var(--tx-soft)',
                  font: '600 11px/1 var(--f-ui)',
                }}
              >
                Cancelar
              </button>
            ) : (
              /* A régua e a fonte, que antes viviam no aviso de tela vazia. Sem isto,
                 a origem do número sumiria junto com a tela de ficha. */
              <p
                style={{
                  font: '400 11.5px/1.5 var(--f-ui)',
                  color: 'var(--tx-sub)',
                  margin: 0,
                }}
              >
                A leitura sai do Censo 2022 do IBGE, no raio de 1,0 km — a mesma régua do
                Relatório Pontual.
              </p>
            )}
          </Glass>
        )}

        {carregando && (
          <Glass
            style={{
              pointerEvents: 'auto',
              alignSelf: 'center',
              padding: '10px 14px',
              display: 'flex',
              alignItems: 'center',
              gap: 8,
              font: '400 12.5px/1 var(--f-ui)',
              color: 'var(--tx-muted)',
            }}
          >
            <Spinner /> Lendo os setores censitários do entorno…
          </Glass>
        )}
      </div>

      {/* ---------------- Camadas do funil ----------------
          As mesmas do Explorar: a legenda diz o que a cor significa e o stepper troca a
          camada. Sem território (ou enquanto ele carrega) as duas somem — o mapa de
          vizinhança não tem funil para explicar. */}
      {territorio && passo && (
        <>
          <div style={{ position: 'absolute', left: 16, bottom: 84, zIndex: 25 }}>
            <ScoreLegend passoN={passo.n} />
          </div>

          <div
            style={{
              position: 'absolute',
              left: 0,
              right: 0,
              bottom: 0,
              zIndex: 24,
              padding: '0 16px 16px',
            }}
          >
            <StepperBar
              passos={territorio.passos}
              atual={passoN}
              onIr={(n) => setPassoN(Math.min(territorio.passos.length, Math.max(1, n)))}
              /* O PDF municipal é a saída do modo "Explorar uma região", não deste. Aqui a
                 entrega é a ficha do imóvel, que já tem o próprio caminho na janela —
                 gerar um relatório da cidade inteira a partir de um endereço colado
                 responderia outra pergunta. */
              onGerarRelatorio={() => setJanela(true)}
              rotuloFinal="Ver a ficha do imóvel ›"
              gerando={false}
            />
          </div>
        </>
      )}

      {/* Enquanto o território não chegou, o mapa de vizinhança já está no fundo e o
          operador merece saber que vem mais — a carga da partição leva segundos. */}
      {carregandoTerritorio && (
        <Glass
          style={{
            position: 'absolute',
            left: 16,
            bottom: 16,
            zIndex: 25,
            padding: '10px 14px',
            display: 'flex',
            alignItems: 'center',
            gap: 9,
            font: '400 12px/1 var(--f-ui)',
            color: 'var(--tx-muted)',
          }}
        >
          <Spinner /> Lendo o território de {municipio}…
        </Glass>
      )}

      {/* ---------------- A ÚNICA opção que puxa a janela ----------------
          Some enquanto a janela está aberta: quem já a tem na tela fecha pelo × ou Esc. */}
      {ficha && !janela && (
        <div
          style={{
            position: 'absolute',
            right: 16,
            /* Acima do stepper quando ele existe: os dois no mesmo `bottom` se sobrepõem
               em tela estreita, e o stepper ocupa a largura toda. */
            bottom: territorio && passo ? 84 : 16,
            zIndex: 25,
          }}
        >
          <Botao onClick={() => setJanela(true)}>
            Ver a ficha {fichas.length > 1 ? `(${fichas.length} pontos)` : ''} ›
          </Botao>
        </div>
      )}

      {/* ---------------- A janela ---------------- */}
      <JanelaFicha
        aberta={janela && ficha != null}
        titulo={ficha?.local.bairro ?? ficha?.local.municipio ?? 'Ponto analisado'}
        subtitulo={
          ficha ? [ficha.local.municipio, ficha.local.uf].filter(Boolean).join(' · ') : undefined
        }
        onFechar={() => setJanela(false)}
        /* Mesmo recuo do botão que a abre: com o funil na tela o stepper ocupa a largura
           toda no pé, e a janela cobriria os botões das camadas. */
        recuoInferior={territorio && passo ? 96 : 16}
      >
        {ficha && (
          <div style={{ display: 'grid', gap: 16 }}>
            <PainelPontos
              fichas={fichas}
              aberto={aberto}
              onAbrir={setAberto}
              onRemover={(i) => {
                setFichas((atuais) => {
                  const proximas = atuais.filter((_, k) => k !== i)
                  setAberto((k) => Math.max(0, Math.min(k, proximas.length - 1)))
                  if (proximas.length === 0) {
                    setColando(true)
                    // Sem ponto nao ha' ficha: a janela ficaria vazia, e uma janela
                    // vazia por cima do mapa se le como defeito.
                    setJanela(false)
                  }
                  return proximas
                })
              }}
              onAdicionar={() => {
                setColando(true)
                setErro(null)
              }}
            />
            <Ficha
              key={`${ficha.hex_id}-${aberto}`}
              ficha={ficha}
              onAnalisarPonto={onAnalisarPonto}
            />
          </div>
        )}
      </JanelaFicha>
    </div>
  )
}

function Ficha({
  ficha,
  onAnalisarPonto,
}: {
  ficha: PontoPayload
  onAnalisarPonto: (p: PontoEscolhido) => void
}) {
  const { local, censo, concorrencia, mercado } = ficha

  /* A viabilidade e as entradas sobem do bloco filho porque a RECOMENDACAO precisa
     das duas metades: os criterios do territorio (que vem do payload) e o veredito do
     contrato (que so' existe depois de o operador calcular). Sem isso a secao teria de
     opinar sobre aluguel sem saber se a conta fecha. */
  const [viab, setViab] = useState<ViabilidadeOut | null>(null)
  const [entradas, setEntradas] = useState({ m2: 1500, aluguel: 20000 })
  // Estavel: o filho tem `onEntradas` nas dependencias de um efeito.
  const guardarEntradas = useCallback((e: { m2: number; aluguel: number }) => setEntradas(e), [])

  /**
   * Monta o `PontoEscolhido` que a tela de Viabilidade espera.
   *
   * Ela le so' `ponto.rotulo` (breadcrumb), `ponto.hex.id` (chave do efeito que
   * semeia a faixa de alunos) e a coordenada via `coordenadaDoEstudo` — que prefere
   * `lat`/`lng` quando existem. Aqui existem, e sao a coordenada EXATA que o operador
   * colou: e' por isso que o estudo la nao cai no centroide do hexagono, que fica a
   * ate ~1,5 km do imovel. Os demais campos do `Hex` a Viabilidade nao consulta;
   * ficam `null` em vez de receber zero inventado.
   */
  const irParaDetalhes = () =>
    onAnalisarPonto({
      hex: {
        id: ficha.hex_id,
        lat: ficha.lat,
        lng: ficha.lng,
        m1: null, censo: censo.score_socioeconomico, hib: null,
        res: mercado.score_residual, oferta: mercado.residual, sam: mercado.sam,
        pop: censo.populacao, renda: censo.renda_per_capita,
        renda_dom: censo.renda_media_domiciliar,
        faixa: null,
        conc: concorrencia.n_concorrentes ?? 0,
        ultra: concorrencia.n_ultra ?? 0,
        mun: local.municipio,
        cres_hex_taxa: null, cres_hex_classe: null,
      },
      rotulo: local.bairro ?? local.municipio ?? 'Ponto analisado',
      municipio: local.municipio ?? '',
      uf: local.uf,
      lat: ficha.lat,
      lng: ficha.lng,
    })

  return (
    <div style={{ display: 'grid', gap: 16 }}>
      {/* ---------------- Identificação ----------------
          O mapa lá atrás mostra ONDE; esta seção diz QUAL. A coordenada e o link de
          saída continuam aqui porque são conferência, não navegação. */}
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
        {censo.detalhe && (
          <DetalheRegiao detalhe={censo.detalhe} concorrencia={concorrencia} />
        )}
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
        <Rodape>
          O mapa atrás desta janela colore os vizinhos por este mesmo residual — um
          hexágono saturado pode ter espaço sobrando a 1 km dali.
        </Rodape>
      </Secao>

      {/* ---------------- Recomendação ----------------
          Antes da viabilidade de propósito: é a resposta à pergunta que trouxe o
          operador aqui ("serve ou não?"), e os números acima são a evidência dela. */}
      <Secao
        titulo="Serve este imóvel?"
        nota="cada métrica contra a régua da rede"
      >
        <Recomendacao
          criterios={ficha.criterios}
          reguas={ficha.reguas}
          viavel={viab ? viab.dre?.flag_viavel === true : null}
          m2={entradas.m2}
          aluguel={entradas.aluguel}
          tetoAluguel={viab?.aluguel_teto?.teto ?? null}
          melhoria={viab?.melhoria_payback ?? null}
          gradeSemViavel={
            Array.isArray(viab?.grade) && viab.grade.length > 0
              ? !viab.grade.some((c) => c.viavel)
              : false
          }
        />
      </Secao>

      {/* ---------------- Viabilidade ---------------- */}
      <Secao
        titulo="Fecha a conta?"
        nota="metragem e aluguel são seus; o resto vem do motor"
      >
        <BlocoViabilidadePonto
          lat={ficha.lat}
          lng={ficha.lng}
          onDetalhes={irParaDetalhes}
          onResultado={setViab}
          onEntradas={guardarEntradas}
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
