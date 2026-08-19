import { useCallback, useEffect, useRef, useState } from 'react'

import type { PontoEscolhido } from '../App'

import BlocoViabilidadePonto from '../components/BlocoViabilidadePonto'
import CampoPonto from '../components/CampoPonto'
import DetalheRegiao from '../components/DetalheRegiao'
import type { SearchPin } from '../components/HexMap'
import JanelaFicha from '../components/JanelaFicha'
import { Landing } from './MapScreen'
import {
  BarraMercado,
  FilaApoio,
  MedidorScore,
  NumeroApoio,
  ReguaConcorrentes,
} from '../components/LeiturasVisuais'
import { FAIXAS_DEMANDA, FAIXAS_POTENCIAL } from '../lib/faixas'
import PainelPontos from '../components/PainelPontos'
import Recomendacao from '../components/Recomendacao'
import { Aviso, Botao, Chip, Eyebrow, Glass, Spinner } from '../components/primitives'
import { api, ApiError } from '../lib/api'
import {
  MAX_PONTOS,
  chaveDaCoordenada,
  indiceDoMesmoPonto,
  rotulosDosPontos,
} from '../lib/comparacao-pontos'
import type { AlvoCaptura } from '../lib/captura-mapa'
import { linkGoogleMaps, type EntradaClassificada } from '../lib/entrada-ponto'
import { num } from '../lib/format'
import type { BlocoOpcional, PontoPayload, ViabilidadeOut } from '../lib/types'

/**
 * Modo 1 — analise de um PONTO/IMOVEL.
 *
 * ESTA TELA NAO DESENHA MAPA. Ela e' uma CAMADA por cima do "Explorar uma regiao": o
 * `App` renderiza o `MapScreen` inteiro no fundo — mesmo cabecalho, mesmos seletores de
 * UF/municipio, mesmo funil, mesma legenda, mesmo painel de ranking — e este componente
 * poe por cima so' o que e' proprio do modo: a caixa de colar e a JANELA da ficha.
 *
 * POR QUE ASSIM (pedido do Juan, 2026-08-11: "deixe as duas iguais ao explorar regiao e
 * so' ter a janela de analise"). As duas telas vinham DIVERGINDO: o modo de ponto tinha
 * ganhado uma copia parcial do Explorar (mapa + funil + stepper + legenda, sem o painel
 * de ranking), e copia parcial e' o pior dos mundos — parece a mesma tela, responde
 * diferente, e cada melhoria no Explorar precisava ser reimplementada aqui. Agora nao ha'
 * copia: e' o MESMO componente.
 *
 * QUEM ESCOLHE O TERRITORIO E' O ENDERECO. Resolver o ponto devolve UF e municipio, e o
 * `onLocalizar` os empurra para o `App`, que ja' sabe carregar o territorio (e' o mesmo
 * caminho do drill-down do Explorar). Nada de carga propria aqui: a versao anterior
 * chamava `/api/municipio` por conta e mantinha um segundo estado de territorio, que
 * podia divergir do que o mapa mostrava.
 *
 * ESTADO VAZIO POR BLOCO. Cada bloco pergunta ao SERVIDOR se tem dado (`disponivel`) e
 * mostra o `motivo` que ele devolveu. A cadeia de dados degrada em silencio por desenho
 * (staging ausente -> `(None, None)` sem excecao), entao um bloco que sumisse sozinho
 * seria lido como defeito. Nenhum texto de estado vazio e' inventado aqui.
 */
export default function PontoScreen({
  onCapturarMapas,
  onAnalisarPonto,
  onLocalizar,
  mapaPronto,
  pedido,
  onLimparPin,
  onInicio,
}: {
  /** Leva ESTE ponto para a tela de Viabilidade (a costura com o resto do app). */
  onAnalisarPonto: (p: PontoEscolhido) => void
  /**
   * Avisa o `App` de onde caiu o endereco, para o mapa do fundo ir para la'.
   *
   * `municipio` pode vir vazio: o `/api/ponto` declara o municipio como `string | null`.
   * Nesse caso o `App` fica na visao da UF — o mapa continua util e honesto, so' menos
   * fechado do que seria com a cidade resolvida.
   */
  onLocalizar: (uf: string, municipio: string, pin: SearchPin) => void
  /**
   * O Explorar ja' esta' com territorio na tela — e, portanto, com a busca dele no
   * cabecalho.
   *
   * E' o que decide se a caixa de colar aparece. Com o mapa montado ela seria uma SEGUNDA
   * caixa pedindo endereco, ao lado da que ja' existe; sem o mapa (nenhuma UF escolhida)
   * ela e' a unica entrada que o modo tem, porque a tela vazia do Explorar so' oferece o
   * seletor de estado.
   */
  mapaPronto: boolean
  /**
   * Coordenada resolvida pela busca do Explorar, para virar ficha aqui.
   *
   * Carrega um `n` que so' cresce porque a MESMA coordenada pode ser pedida duas vezes
   * seguidas (buscar, fechar a janela, buscar igual): comparando so' lat/lng o efeito nao
   * dispararia na segunda, e o operador ficaria olhando um botao que nao responde.
   */
  pedido: { lat: number; lng: number; n: number } | null
  /** Apaga a marca do endereço no mapa. Usado pela limpeza. */
  onLimparPin: () => void
  /** Volta ao menu de modos — só o hero de entrada usa, como o Explorar faz. */
  onInicio: () => void
  /** Captura do mapa, publicada pelo App. Ausente = o PDF sai sem mapas. */
  onCapturarMapas?: (alvos: AlvoCaptura[]) => Promise<string[]>
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
  /**
   * A caixa de colar so' aparece quando pedida — depois do 1o ponto ela some.
   *
   * Nasce ABERTA, sempre. Ela nascia fechada quando o mapa ja' estava montado, para nao
   * duplicar a busca do cabecalho de quem "explorou uma regiao e depois trocou para
   * analisar um ponto" — mas esse caminho nao existe mais: o Dock deixou de oferecer os
   * modos (2026-08-12) e a UNICA porta para ca' e' o card do Inicio. Hoje "entrar com o
   * mapa montado" so' significa uma coisa: o territorio ficou carregado no `App` de uma
   * analise anterior. Nesse caso a tela abria direto no mapa, sem lugar nenhum para colar
   * o endereco que o proprio card acabou de prometer (Juan, 2026-08-18).
   */
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
  /* Os mesmos rótulos que o painel de abas usa — desambiguados entre si. */
  const rotulos = rotulosDosPontos(fichas)

  /**
   * De uma coordenada ja' resolvida ate' a ficha na tela.
   *
   * Separado de `resolver` porque agora ha' DUAS portas para o mesmo trabalho: a caixa de
   * colar daqui e a busca do cabecalho do Explorar. As duas terminam neste ponto — e' o
   * que garante que buscar um endereco pela lupa produza exatamente a mesma leitura que
   * cola-lo aqui, em vez de so' soltar um pin no mapa.
   */
  const analisarCoordenada = useCallback(
    async (lat: number, lng: number) => {
      setCarregando(true)
      setErro(null)
      try {
        // JA ESTA' NA LISTA? Abre a aba dele em vez de ler de novo. Dar Enter duas vezes
        // na mesma coordenada é gesto normal de quem não viu a tela reagir; virar dois
        // pontos idênticos, comparados contra si mesmos, não é resposta para isso.
        const repetido = indiceDoMesmoPonto(fichas, lat, lng)
        if (repetido >= 0) {
          setAberto(repetido)
          setColando(false)
          setJanela(true)
          return
        }
        /* TETO CHEIO: recusa e DIZ, em vez de engolir o ponto. O `slice(0, MAX_PONTOS)`
           que estava aqui mantinha os cinco PRIMEIROS e descartava justamente o novo, e
           ainda abria a aba do quinto antigo — o operador colava um endereço, esperava a
           leitura e recebia um ponto velho, sem nenhum aviso. Foi a outra metade do
           "depois de algumas vezes ele buga" (Juan, 2026-08-14). A regra já estava
           escrita na tela ("Máximo de N pontos - remova um para colar outro"); o que
           faltava era o código honrá-la. A checagem vem ANTES da chamada: não faz sentido
           gastar uma leitura de servidor para descartar o resultado. */
        if (fichas.length >= MAX_PONTOS) {
          setErro(
            `Máximo de ${MAX_PONTOS} pontos na comparação. Remova um para analisar outro.`,
          )
          return
        }
        const nova = await api.ponto(lat, lng)
        // O ponto novo entra no fim e vira o aberto: quem acabou de pedir quer ver ele.
        setFichas((atuais) => {
          const proximas = [...atuais, nova]
          setAberto(proximas.length - 1)
          return proximas
        })
        setColando(false)
        setJanela(true)
        // O mapa vai para o ponto novo pelo efeito de `ficha` acima, que cuida TAMBEM da
        // troca de aba. Localizar aqui de novo seria um segundo voo para o mesmo lugar.
      } catch (e) {
        // NAO limpa os pontos ja lidos: perder tres leituras porque a quarta falhou
        // seria punir o operador por um endereco mal digitado.
        setErro(e instanceof ApiError ? e.message : 'Falha ao analisar o ponto.')
      } finally {
        setCarregando(false)
      }
    },
    [onLocalizar, fichas],
  )

  /** Tira TUDO da tela: os pontos, a janela e a marca do mapa. */
  const limparPontos = useCallback(() => {
    setFichas([])
    setAberto(0)
    setJanela(false)
    setErro(null)
    setColando(true)
    onLimparPin()
  }, [onLimparPin])

  /**
   * TROCAR DE ABA leva o mapa ate' o hexagono daquele ponto.
   *
   * Sem isto, comparar dois enderecos era cego: as abas trocavam os numeros da ficha mas
   * o mapa continuava parado no ultimo ponto colado, entao nao dava para ver QUAL area
   * cada coluna da comparacao descreve (relato do Juan, 2026-08-12).
   *
   * A chave e' a COORDENADA da ficha aberta — nao o indice, e NAO o `hex_id`.
   *
   * Nao o indice: remover um ponto do meio muda o indice de todos os seguintes sem mudar o
   * ponto aberto, e re-localizar ali seria um voo sem motivo.
   *
   * NAO O HEX_ID, e isso era um DEFEITO (relato do Juan em 2026-08-14: "ao mudar algumas
   * vezes as coordenadas ele buga, seja a camera, janela, ou nao busca a coordenada"). Um
   * hexagono res-7 tem ~5 km2, entao dois enderecos a MAIS DE 1 KM um do outro cabem no
   * mesmo. Medido contra a API: -23.61369,-46.84487 e -23.60569,-46.83687 (1,2 km, ambos
   * em Cotia) devolvem `hex_id` 87a81006bffffff nos DOIS. Com a guarda por hexagono o
   * segundo endereco entrava na lista e trocava a janela, mas o mapa e o pin ficavam no
   * primeiro — janela e mapa descrevendo pontos diferentes, sem erro nenhum na tela.
   *
   * Trocar de aba entre pontos da MESMA cidade nao recarrega territorio nenhum:
   * `uf`/`municipio` continuam iguais e so' o pin muda.
   */
  const ultimoLocalizado = useRef<string | null>(null)
  useEffect(() => {
    if (!ficha) {
      ultimoLocalizado.current = null
      return
    }
    const chave = chaveDaCoordenada(ficha.lat, ficha.lng)
    if (ultimoLocalizado.current === chave) return
    ultimoLocalizado.current = chave
    onLocalizar(ficha.local.uf ?? '', ficha.local.municipio ?? '', {
      lat: ficha.lat,
      lng: ficha.lng,
      hexId: ficha.hex_id,
    })
  }, [ficha, onLocalizar])

  /* A busca do Explorar pediu um ponto. O `n` e' a chave: a mesma coordenada pedida duas
     vezes tem de produzir duas leituras. */
  const ultimoPedido = useRef(0)
  useEffect(() => {
    if (!pedido || pedido.n === ultimoPedido.current) return
    ultimoPedido.current = pedido.n
    void analisarCoordenada(pedido.lat, pedido.lng)
  }, [pedido, analisarCoordenada])

  async function resolver(entrada: EntradaClassificada, texto: string) {
    // O front resolve coordenada e link longo sozinho; o resto custa uma ida ao servidor
    // (expandir redirect do link curto, ou geocodificar endereço).
    let coord = entrada.coord
    if (!coord) {
      setCarregando(true)
      setErro(null)
      try {
        const r = await api.resolverPonto(texto)
        if (!r.found || r.lat == null || r.lng == null) {
          setErro(r.motivo ?? 'Não consegui resolver esse endereço.')
          return
        }
        coord = { lat: r.lat, lng: r.lng }
      } catch (e) {
        setErro(e instanceof ApiError ? e.message : 'Falha ao resolver o endereço.')
        return
      } finally {
        setCarregando(false)
      }
    }
    await analisarCoordenada(coord.lat, coord.lng)
  }

  /**
   * A caixa aparece exatamente quando NAO HA' PONTO na tela.
   *
   * `colando` so' vira `true` em tres momentos, e os tres sao esse mesmo estado: ao
   * montar, ao limpar tudo, e ao remover o ultimo ponto. Com ponto na tela quem
   * acrescenta o 2o..5o e' o `CampoPonto` de dentro do `PainelPontos`, que nao mexe neste
   * estado — entao a caixa NAO volta a conviver com a busca do cabecalho, que era o
   * defeito da primeira versao ("+ Adicionar mais um ponto" reabria a caixa por cima da
   * lupa).
   *
   * O `!mapaPronto` que guardava isto SAIU. Ele existia para o operador que explorava uma
   * regiao e trocava de modo com o mapa montado — caminho que nao existe mais desde que o
   * Dock deixou de oferecer os modos (2026-08-12). O que sobrou dele foi impedir a caixa
   * de aparecer para quem volta ao Inicio e pede "analisar um ponto" de novo: o
   * territorio da analise anterior continua carregado no `App`, `mapaPronto` e' `true`, e
   * a tela abria direto no mapa sem lugar nenhum para colar o endereco (Juan, 2026-08-18).
   */
  const mostrandoCaixa = colando || fichas.length === 0

  /* SEM MAPA AINDA: a tela é o HERO do modo — o mesmo desenho do "Explorar uma região",
     com o texto desta análise e a caixa de colar no lugar do seletor de estado (pedido do
     Juan, 2026-08-12). Antes, o hero do Explorar aparecia no fundo falando de território
     enquanto a caixa de endereço flutuava por cima: dois assuntos na mesma tela. */
  const semMapa = !mapaPronto && fichas.length === 0
  if (semMapa) {
    return (
      <div style={{ position: 'absolute', inset: 0, zIndex: 40 }}>
        <Landing
          marcador="Analisar um ponto ou imóvel"
          titulo="Cole o link do Google Maps ou a coordenada"
          explicacao="A ficha lê quem mora no raio de 1,0 km, quanto de mercado sobra e quem já disputa o aluno ali — e o mapa abre na cidade do endereço, com as mesmas camadas do Explorar."
          onInicio={onInicio}
        >
          <Glass style={{ width: 'min(620px, 100%)', padding: 16, display: 'grid', gap: 10, textAlign: 'left' }}>
            {/* A linha "Funciona com o link da barra de endereço…" NÃO se repete aqui: o
                próprio `CampoPonto` já a publica. Repeti-la foi um defeito da primeira
                versão desta tela — a mesma frase duas vezes, uma embaixo da outra. */}
            <CampoPonto onResolver={resolver} ocupado={carregando} erro={erro} />
            <p style={{ font: '400 11.5px/1.5 var(--f-ui)', color: 'var(--tx-sub)', margin: 0 }}>
              A leitura sai do Censo 2022 do IBGE, no raio de 1,0 km — a mesma régua do
              Relatório Pontual.
            </p>
          </Glass>
        </Landing>
      </div>
    )
  }

  return (
    /* CAMADA, e nao tela. O `MapScreen` inteiro fica atrás — mapa, cabeçalho com os
       seletores de UF/município, lupa, funil, legenda e painel de ranking. Aqui só entra
       o que é próprio do modo de ponto.

       `pointerEvents: none` no contêiner é o que devolve o mouse ao mapa nos vãos entre
       as peças; cada peça reativa pede `auto` de volta. Sem isso, uma folha invisível
       cobriria a tela inteira e o mapa do fundo não receberia nem arraste nem clique.

       `zIndex` acima do chrome do Explorar (cabeçalho 10, stepper 24, legenda 25) para a
       caixa de colar e a janela ficarem por cima dele — mas o clique nos seletores e no
       stepper continua chegando, porque o contêiner não intercepta. */
    <div style={{ position: 'absolute', inset: 0, zIndex: 40, pointerEvents: 'none' }}>
      {/* ---------------- Caixa de colar ----------------
          Abaixo do cabeçalho do Explorar, que continua sendo o de lá. NÃO há cabeçalho
          próprio: era justamente ele — "Análise de ponto" com botão de início repetido —
          que fazia as duas telas parecerem coisas diferentes. */}
      <div
        style={{
          position: 'absolute',
          top: 88,
          left: 16,
          right: 16,
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          gap: 12,
        }}
      >
        {mostrandoCaixa && !semMapa && (
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

      {/* ---------------- A ÚNICA opção que puxa a janela ----------------
          Some enquanto a janela está aberta: quem já a tem na tela fecha pelo × ou Esc.
          Sempre acima do stepper do Explorar, que ocupa a largura toda no pé. */}
      {ficha && !janela && (
        <div style={{ position: 'absolute', right: 16, bottom: 96, pointerEvents: 'auto' }}>
          <Botao onClick={() => setJanela(true)}>
            Ver a ficha {fichas.length > 1 ? `(${fichas.length} pontos)` : ''} ›
          </Botao>
        </div>
      )}

      {/* ---------------- A janela ---------------- */}
      <JanelaFicha
        aberta={janela && ficha != null}
        /* O MESMO rótulo desambiguado das abas: com dois pontos da mesma cidade, o título
           "Goiânia" não dizia qual dos dois estava aberto. */
        titulo={rotulos[aberto] ?? 'Ponto analisado'}
        /* A régua e a contagem de setores vinham do cabeçalho próprio, que saiu junto com
           a cópia do Explorar. Vivem aqui porque é a ficha que elas qualificam — e some
           uma linha de chrome da tela. */
        subtitulo={
          ficha
            ? [
                [ficha.local.municipio, ficha.local.uf].filter(Boolean).join(' · '),
                `raio de ${num(ficha.raio_km * 1000)} m`,
                /* A COORDENADA no subtítulo é o que resolve o empate de verdade: o número
                   da aba diz "é o segundo", e isto diz QUAL endereço é. */
                `${ficha.lat.toFixed(4)}, ${ficha.lng.toFixed(4)}`,
                ficha.censo.n_setores != null ? `${ficha.censo.n_setores} setores` : null,
              ]
                .filter(Boolean)
                .join(' · ')
            : undefined
        }
        onFechar={() => setJanela(false)}
        /* O stepper do Explorar ocupa a largura toda no pé; sem este recuo a janela
           cobriria os botões das camadas. */
        recuoInferior={96}
      >
        {ficha && (
          <div style={{ display: 'grid', gap: 16 }}>
            <PainelPontos
            onCapturarMapas={onCapturarMapas}
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
              onResolver={resolver}
              onLimpar={limparPontos}
              carregando={carregando}
              erro={erro}
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
        {/* ---- O VISUAL VEM PRIMEIRO ----
            A hierarquia estava invertida: cinco cards de 24px dominavam o bloco e a barra
            aparecia como rodapé. Quem escolhe imóvel pergunta "isso é muito?", e essa
            resposta é a do desenho. Os números continuam inteiros e auditáveis, logo
            abaixo, em tipo de apoio. */}
        <div style={{ display: 'grid', gap: 14 }}>
          {/* As FAIXAS são as publicadas em `lib/faixas.ts` — a mesma régua e as mesmas
              cores que o mapa pinta e a legenda explica. É o que permite colorir sem
              inventar limiar: "Forte" aqui é o "Forte" de lá. */}
          <MedidorScore
            rotulo="Score socioeconômico"
            valor={censo.score_socioeconomico}
            faixas={FAIXAS_POTENCIAL}
            nota="renda e densidade do censo, na mesma régua que colore o mapa"
          />

          <FilaApoio>
            <NumeroApoio rotulo="População" valor={num(censo.populacao)} />
            <NumeroApoio rotulo="Domicílios" valor={num(censo.domicilios)} />
            <NumeroApoio rotulo="Renda per capita" valor={comPrefixo('R$ ', censo.renda_per_capita)} />
            <NumeroApoio rotulo="Renda domiciliar" valor={comPrefixo('R$ ', censo.renda_media_domiciliar)} />
            <NumeroApoio rotulo="Densidade" valor={comSufixo(censo.densidade_hab_km2, ' hab/km²')} />
          </FilaApoio>
        </div>

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
        <div style={{ display: 'grid', gap: 14 }}>
          <ReguaConcorrentes lista={concorrencia.lista} raioKm={ficha.raio_km} />
          <FilaApoio>
            <NumeroApoio rotulo="Concorrentes no raio" valor={num(concorrencia.n_concorrentes)} />
            <NumeroApoio rotulo="Unidades Ultra no raio" valor={num(concorrencia.n_ultra)} />
          </FilaApoio>
        </div>
      </Secao>

      {/* ---------------- Mercado / residual ---------------- */}
      <Secao titulo="Quanto de mercado sobra" bloco={mercado}>
        {/* Barra primeiro: "SAM 12.000" e "residual 4.000" lado a lado exigem conta de
            cabeça para responder o que interessa — a sobra é a maior parte do mercado ou
            uma margem? Os dois números continuam abaixo, em tipo de apoio. */}
        <div style={{ display: 'grid', gap: 14 }}>
          <BarraMercado sam={mercado.sam} residual={mercado.residual} />
          <MedidorScore
            rotulo="Score de residual"
            valor={mercado.score_residual}
            faixas={FAIXAS_DEMANDA}
            nota="satura em 100 acima de 2.500 alunos — uma unidade cheia"
          />
          <FilaApoio>
            <NumeroApoio rotulo="Mercado potencial (SAM)" valor={comSufixo(mercado.sam, ' alunos')} />
            <NumeroApoio rotulo="Residual disponível" valor={comSufixo(mercado.residual, ' alunos')} />
          </FilaApoio>
        </div>

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

function Rodape({ children }: { children: React.ReactNode }) {
  return (
    <p style={{ font: '400 11.5px/1.5 var(--f-ui)', color: 'var(--tx-sub)', margin: 0 }}>
      {children}
    </p>
  )
}
