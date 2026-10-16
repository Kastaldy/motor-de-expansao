import { useCallback, useEffect, useLayoutEffect, useRef, useState } from 'react'
import { censoDaBase, institutoDoCenso } from '../lib/rodape-base'

import type { PontoEscolhido } from '../App'

import CampoPonto from '../components/CampoPonto'
import DetalheRegiao from '../components/DetalheRegiao'
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
import { api, ApiError, baixar } from '../lib/api'
import { RAIO_PADRAO_KM, ehAreaDesenhada, rotuloDoRaio } from '../lib/recorte'
import {
  rotuloDoRecorte,
  nomeDoLugar,
  rotulosDosPontos,
  rotulosPartidosDosPontos,
} from '../lib/comparacao-pontos'
import type { RotuloPartido } from '../lib/comparacao'
import type { AlvoCaptura } from '../lib/captura-mapa'
import { classificarEntrada, linkGoogleMaps, type EntradaClassificada } from '../lib/entrada-ponto'
import { alunos, num } from '../lib/format'
import { leituraDoMercado } from '../lib/mercado-ponto'
import { ehEstudoDaUnidade, ofertaDeEstudoUltra, type OfertaEstudoUltra } from '../lib/estudo-ultra'
import { chaveDaCoordenada } from '../lib/comparacao-pontos'
import {
  estadoDoEstudo,
  estadoDoSimulador,
  rotuloParaSimulador,
  type EstadoBotao,
} from '../lib/rodape-ponto'
import { erroFlutuanteVisivel, janelaNaMontagem } from '../lib/pontos-estado'
import { TOPO_BOTAO_PADRAO, topoDoBotaoVerFicha } from '../lib/botao-ver-ficha'
import type { BlocoOpcional, PontoPayload } from '../lib/types'

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
 * `App` leva o mapa para la' (e' o mesmo caminho do drill-down do Explorar). Nada de carga
 * propria aqui: a versao anterior chamava `/api/municipio` por conta e mantinha um segundo
 * estado de territorio, que podia divergir do que o mapa mostrava.
 *
 * A LISTA DE PONTOS NAO MORA AQUI (2026-10-14). Ela e' do `App` (`lib/use-pontos`, regras
 * em `lib/pontos-estado`): ir ao Simulador desmonta esta tela, e a analise tem de estar
 * la' na volta; o mapa precisa da lista inteira para desenhar todos os pontos; e a lupa
 * do mapa e o "Selecionar ponto" pedem pontos sem passar por esta tela. Aqui fica so' o
 * que e' de TELA: a caixa de colar, a janela e a resolucao de endereco/link.
 *
 * NAS DUAS ENTRADAS DO MAPA. "Analisar um ponto" (`comHero`) abre no hero de colar; o
 * "Explorar uma regiao" monta esta camada SEM hero — ela fica invisivel ate' o primeiro
 * ponto, para nao cobrir o mapa de quem veio explorar.
 *
 * ESTADO VAZIO POR BLOCO. Cada bloco pergunta ao SERVIDOR se tem dado (`disponivel`) e
 * mostra o `motivo` que ele devolveu. A cadeia de dados degrada em silencio por desenho
 * (staging ausente -> `(None, None)` sem excecao), entao um bloco que sumisse sozinho
 * seria lido como defeito. Nenhum texto de estado vazio e' inventado aqui.
 *
 * SEM VIABILIDADE NA FICHA (2026-10-14, decisao do dono). A secao "Fecha a conta?" (o
 * antigo `BlocoViabilidadePonto`) saiu: a ficha le o TERRITORIO, e a conta do contrato e'
 * do Simulador. No lugar dela, dois botoes FIXOS no rodape da janela, sobre o ponto
 * ABERTO: "Estudo" (o Relatorio Pontual so' demografico, o modo do bot) e "Simulador"
 * (a tela de Viabilidade na coordenada exata). Regras de trava em `lib/rodape-ponto`.
 */
export default function PontoScreen({
  onCapturarMapas,
  onAnalisarPonto,
  fichas,
  aberto,
  revelar,
  carregandoPonto,
  erroPonto,
  onAnalisar,
  onTrocarModo,
  trocandoModo = [],
  onAbrir,
  onRemover,
  onLimpar,
  onLimparErro,
  comHero = true,
  reabrirFicha = false,
  textoInicial,
  onTextoAplicado,
  onInicio,
}: {
  /**
   * A tela está sendo MONTADA na volta do Simulador aberto por esta ficha: a janela nasce
   * aberta. Lida só na montagem (`janelaNaMontagem`); quem decide é o `App`, o único que
   * sabe de onde a navegação veio.
   */
  reabrirFicha?: boolean
  /**
   * Leva ESTE ponto para a tela de Viabilidade — o botão "Simulador".
   *
   * OPCIONAL de propósito: `undefined` = a conta não tem a aba Viabilidade, e o botão
   * aparece TRAVADO com o motivo escrito (`estadoDoSimulador`). O `App` deve passar
   * `telaLiberada('viabilidade', abas) ? irParaViabilidade : undefined` — o mesmo
   * contrato do `onVerImovelNaAba`. Passar sempre deixaria o botão ativo e o clique
   * morreria calado, porque o `irParaViabilidade` retorna em silêncio quando a aba é
   * vetada.
   */
  onAnalisarPonto?: (p: PontoEscolhido) => void
  /**
   * Os pontos lidos, na ordem em que entraram — a lista do `App`.
   *
   * Lista e nao objeto unico porque a pergunta do operador quase nunca e' "este imovel
   * serve?" isolada — e' "qual DESTES serve mais?". Cada ponto e' uma leitura completa
   * do `/api/ponto`; o teto de `MAX_PONTOS` existe porque cada um custa uma leitura de
   * particao de municipio no servidor.
   */
  fichas: PontoPayload[]
  /** Qual ficha esta aberta em detalhe. Com 1 ponto e' sempre ela. */
  aberto: number
  /**
   * Contador que sobe quando um ponto acaba de chegar (ou foi pedido de novo): e' o sinal
   * para a janela abrir. O pedido pode ter nascido fora daqui — na lupa do mapa.
   */
  revelar: number
  /** Ha' leitura do `/api/ponto` em voo. */
  carregandoPonto: boolean
  /** Erro da ultima leitura (ou do teto cheio), vindo da lista. */
  erroPonto: string | null
  /** Pede a analise de uma coordenada ja' resolvida. */
  onAnalisar: (lat: number, lng: number) => Promise<void>
  /**
   * Troca o modo de estudo do ponto `i` — estudo de ponto <-> estudo da unidade Ultra
   * (emenda da DEC-070). Ausente = a chave não aparece.
   */
  onTrocarModo?: (i: number, estudoUltra: boolean) => void
  /** `chaveDaCoordenada` dos pontos sendo relidos em outro modo (a chave mostra a espera). */
  trocandoModo?: readonly string[]
  onAbrir: (i: number) => void
  onRemover: (i: number) => void
  /** Tira todos os pontos da lista (e, com eles, as marcas do mapa). */
  onLimpar: () => void
  onLimparErro: () => void
  /**
   * Se a tela vazia e' o HERO de colar. `true` em "Analisar um ponto"; `false` no
   * "Explorar uma regiao", onde a camada fica invisivel ate' o primeiro ponto — o hero
   * cobriria o mapa de quem veio explorar.
   */
  comHero?: boolean
  /* `mapaPronto` SAIU daqui (2026-08-26). Ele dizia "o Explorar já tem território na
     tela", e era o que decidia entre o hero e a camada flutuante. Só que o território
     fica carregado no `App` depois da primeira análise, de propósito — então a resposta
     era "sim" para sempre e o hero virava inalcançável. Quem manda agora é o que a tela
     de fato tem: ficha, ou nenhuma. Sem consumidor, a prop não fica de enfeite. */
  /**
   * O que o operador colou NO CARD do Início (2026-09-22) — texto cru, do mesmo jeito
   * que ele sairia da caixa desta tela. Resolvido uma vez, na montagem, pelo MESMO
   * `resolver()` da caixa daqui: é o que garante que colar no card e colar aqui tratem
   * link curto, link longo, coordenada e endereço com as mesmas regras e as mesmas
   * mensagens de erro.
   */
  textoInicial?: string | null
  /** Avisa que o texto foi consumido — ele vale uma entrada, não todas. */
  onTextoAplicado?: () => void
  /** Volta ao menu de modos — só o hero de entrada usa, como o Explorar faz. */
  onInicio: () => void
  /** Captura do mapa, publicada pelo App. Ausente = o PDF sai sem mapas. */
  onCapturarMapas?: (alvos: AlvoCaptura[]) => Promise<string[]>
}) {
  const institutoDaBase = institutoDoCenso()
  /* Resolucao de ENDERECO/LINK (geocodificar, expandir link curto) — a unica ida ao
     servidor que ainda e' desta tela. A leitura do ponto em si e' da lista, no `App`. */
  const [resolvendo, setResolvendo] = useState(false)
  const [erroLocal, setErroLocal] = useState<string | null>(null)
  const carregando = resolvendo || carregandoPonto
  const erro = erroLocal ?? erroPonto
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
   *
   * Com a lista no `App`, "nasce aberta" passou a valer para a tela VAZIA: voltando do
   * Simulador com pontos na lista, a caixa nao reaparece por cima da analise.
   */
  const [colando, setColando] = useState(() => fichas.length === 0)
  /**
   * A janela da ficha.
   *
   * Abre SOZINHA quando uma leitura chega: o operador colou o ponto justamente para
   * saber se ele serve, e cobrar um clique a mais pela resposta seria burocracia. Depois
   * disso quem manda e' ele — fechou, o mapa fica limpo ate' pedir de novo.
   *
   * Nasce ABERTA SO' na volta do Simulador (`reabrirFicha`): quem foi simular um dos
   * pontos volta para a analise que deixou, nao para um botao "Ver a ficha". Qualquer
   * outra remontagem com pontos na lista (Executiva e de volta pelo Dock, ranking
   * nacional, aba de imoveis) nasce FECHADA — nesses caminhos o operador fechou a ficha
   * ou foi a outro destino, e reabri-la sozinha cobriria a ficha do destino.
   */
  const [janela, setJanela] = useState(() => janelaNaMontagem(reabrirFicha, fichas.length))

  /* Topo do botão "Ver a ficha": logo abaixo do cabeçalho do mapa, MEDIDO — o cabeçalho
     é `flex-wrap` e quebra em duas linhas em tela estreita (regra em `lib/botao-ver-ficha`).
     O cabeçalho é do `MapScreen` (irmão desta tela na árvore), então ele é achado pelo DOM:
     sobe-se pelos ancestrais do botão até o primeiro que contém a `barra-ultra`. */
  const [botaoFichaEl, setBotaoFichaEl] = useState<HTMLDivElement | null>(null)
  const [topoBotaoFicha, setTopoBotaoFicha] = useState(TOPO_BOTAO_PADRAO)
  useLayoutEffect(() => {
    const el = botaoFichaEl
    if (!el) return
    const pai = el.offsetParent as HTMLElement | null
    let cabecalho: HTMLElement | null = null
    for (let anc = el.parentElement; anc && !cabecalho; anc = anc.parentElement) {
      cabecalho = anc.querySelector<HTMLElement>('header.barra-ultra')
    }
    const medir = () => {
      const caixaPai = pai?.getBoundingClientRect()
      /* A escala do `#root` (transform), lida do próprio contêiner: tela / layout. */
      const escala = caixaPai && pai?.offsetHeight ? caixaPai.height / pai.offsetHeight : 1
      setTopoBotaoFicha(
        topoDoBotaoVerFicha(
          cabecalho ? cabecalho.getBoundingClientRect().bottom : null,
          caixaPai ? caixaPai.top : null,
          escala,
        ),
      )
    }
    medir()
    const obs = typeof ResizeObserver === 'undefined' || !cabecalho ? null : new ResizeObserver(medir)
    if (obs && cabecalho) obs.observe(cabecalho)
    window.addEventListener('resize', medir)
    return () => {
      obs?.disconnect()
      window.removeEventListener('resize', medir)
    }
  }, [botaoFichaEl])

  const ficha = fichas[aberto] ?? null
  /* Os mesmos rótulos que o painel de abas usa — desambiguados entre si ("Centro #1",
     "Centro #2"). A forma inteira vai para o título da janela, o PDF e o Simulador; a
     partida, para onde o nome pode ser truncado e o "#k" não pode sumir. */
  const rotulos = rotulosDosPontos(fichas)
  const partidos = rotulosPartidosDosPontos(fichas)
  /** O rótulo do ponto aberto, com o "#k" quando há empate de nome. */
  const rotuloAberto = rotulos[aberto] ?? 'Ponto analisado'

  /* ---------------- Rodapé: "Estudo" e "Simulador" ----------------
     Agem sobre o ponto ABERTO. O estado do PDF é da tela, não da ficha: o semáforo do
     servidor gera um PDF por vez, e travar o botão durante a geração (mesmo trocando de
     aba) é o que evita o segundo clique enfileirar um duplicado. */
  const [gerandoEstudo, setGerandoEstudo] = useState(false)
  const [erroEstudo, setErroEstudo] = useState<string | null>(null)
  /* O erro é DO ponto que falhou: trocar de aba não pode deixá-lo falando pelo outro.
     Chaveado também na coordenada, porque remover um ponto antes do aberto troca a
     ficha sem mudar o índice. */
  useEffect(() => setErroEstudo(null), [aberto, ficha?.lat, ficha?.lng])

  const gerarEstudo = useCallback(async () => {
    if (!ficha || !estadoDoEstudo(ficha, gerandoEstudo).habilitado) return
    setGerandoEstudo(true)
    setErroEstudo(null)
    try {
      /* `soEstudo`: o Relatório Pontual EXCLUSIVAMENTE demográfico — sem viabilidade,
         DRE, aluguel, payback nem teto; Conclusão só com o selo demográfico (DEC-030).
         A coordenada é a EXATA do ponto, então `origemCentroideHex` fica de fora. */
      const { blob, filename } = await api.relatorioPontual({
        lat: ficha.lat,
        lng: ficha.lng,
        rotulo: rotuloAberto,
        soEstudo: true,
        /* O MODO da ficha vai junto (emenda da DEC-070): o PDF do estudo da unidade Ultra
           sai sem o consumo dela, como a tela — e o Big Numbers declara isso. */
        excluirUltraProxima: ehEstudoDaUnidade(ficha),
      })
      baixar(blob, filename)
    } catch (e) {
      setErroEstudo(e instanceof ApiError ? e.message : 'Não foi possível gerar o estudo. Tente de novo.')
    } finally {
      setGerandoEstudo(false)
    }
  }, [ficha, gerandoEstudo, rotuloAberto])

  /**
   * Monta o `PontoEscolhido` que a tela de Viabilidade espera — o antigo "Mais detalhes →"
   * do bloco de viabilidade, agora o botão "Simulador".
   *
   * Ela lê só `ponto.rotulo` (breadcrumb), `ponto.hex.id` (chave do efeito que semeia a
   * faixa de alunos) e a coordenada via `coordenadaDoEstudo` — que prefere `lat`/`lng`
   * quando existem. Aqui existem, e são a coordenada EXATA que o operador colou: é por
   * isso que o estudo lá não cai no centroide do hexágono, que fica a até ~1,5 km do
   * imóvel. Os demais campos do `Hex` a Viabilidade não consulta; ficam `null` em vez de
   * receber zero inventado.
   */
  const irParaSimulador = () => {
    if (!ficha || !onAnalisarPonto) return
    const { local, censo, concorrencia, mercado } = ficha
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
      /* O MESMO rótulo das abas: dois "Centro" chegam à Viabilidade como "#1" e "#2". A
         área desenhada chega como "Ponto central da área desenhada": lá o estudo (e o PDF)
         é do RAIO em volta desse ponto, e o nome da área no título mentiria o recorte. */
      rotulo: rotuloParaSimulador(ficha, rotuloAberto),
      municipio: local.municipio ?? '',
      uf: local.uf,
      lat: ficha.lat,
      lng: ficha.lng,
      /* O nome acima carrega " (unidade Ultra)" no estudo da unidade: o PDF do Simulador
         tem de calcular no mesmo modo (emenda da DEC-070). */
      ...(ehEstudoDaUnidade(ficha) ? { estudoUltra: true } : {}),
    })
  }

  /**
   * Chegou ponto (ou foi pedido de novo um que ja' estava na lista): mostra a janela.
   *
   * Abre SOZINHA pelo mesmo motivo de sempre — o operador pediu o ponto justamente para
   * saber se ele serve. O contador vem da lista, e nao de um retorno desta tela, porque o
   * pedido pode ter nascido na lupa do mapa. O `ref` comeca no valor da MONTAGEM: um
   * contador ja' alto na volta do Simulador nao e' evento novo.
   */
  const ultimoRevelar = useRef(revelar)
  useEffect(() => {
    if (revelar === ultimoRevelar.current) return
    ultimoRevelar.current = revelar
    setColando(false)
    setJanela(true)
  }, [revelar])

  /** Tira TUDO da tela: os pontos, a janela e a marca do mapa. */
  const limparPontos = useCallback(() => {
    setJanela(false)
    setErroLocal(null)
    setColando(true)
    onLimpar()
  }, [onLimpar])

  /* O endereço colado NO CARD do Início. Consumido UMA vez, na montagem: o efeito não
     depende de `textoInicial` de propósito — reagir a ele reanalisaria o mesmo ponto a
     cada re-render desta tela, que re-renderiza a cada resposta de API.

     Passa pelo MESMO `resolver()` do `CampoPonto`, com a mesma classificação: colar no
     card e colar aqui têm de tratar link curto, link longo, coordenada e endereço com
     as mesmas regras — e falhar com as mesmas mensagens. */
  useEffect(() => {
    const texto = textoInicial?.trim()
    if (!texto) return
    onTextoAplicado?.()
    void resolver(classificarEntrada(texto), texto)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  async function resolver(entrada: EntradaClassificada, texto: string) {
    // O front resolve coordenada e link longo sozinho; o resto custa uma ida ao servidor
    // (expandir redirect do link curto, ou geocodificar endereço).
    setErroLocal(null)
    onLimparErro()
    let coord = entrada.coord
    if (!coord) {
      setResolvendo(true)
      try {
        const r = await api.resolverPonto(texto)
        if (!r.found || r.lat == null || r.lng == null) {
          setErroLocal(r.motivo ?? 'Não consegui resolver esse endereço.')
          return
        }
        coord = { lat: r.lat, lng: r.lng }
      } catch (e) {
        setErroLocal(e instanceof ApiError ? e.message : 'Falha ao resolver o endereço.')
        return
      } finally {
        setResolvendo(false)
      }
    }
    // A MESMA porta da lupa do mapa: repetição, teto e erro de leitura são da lista.
    await onAnalisar(coord.lat, coord.lng)
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
   * Dock deixou de oferecer os modos (2026-08-12).
   *
   * Hoje, com fichas.length === 0 a tela inteira e' o hero (ver `semMapa` abaixo), entao
   * esta caixa flutuante so' aparece no caso que ela existe para servir: acrescentar o
   * 2o..5o ponto a uma comparacao ja' em andamento.
   */
  const mostrandoCaixa = colando || fichas.length === 0

  /* SEM PONTO NA TELA: a tela é o HERO do modo — o mesmo desenho do "Explorar uma região",
     com o texto desta análise e a caixa de colar no lugar do seletor de estado (pedido do
     Juan, 2026-08-12). Antes, o hero do Explorar aparecia no fundo falando de território
     enquanto a caixa de endereço flutuava por cima: dois assuntos na mesma tela.

     A CONDIÇÃO É SÓ "NÃO HÁ FICHA" (Juan, 2026-08-26: "coloca um endereço e ele não volta
     para a tela que aparece 'Cole o link do Google Maps ou a coordenada'"). O `!mapaPronto`
     que a guardava tornava o hero INALCANÇÁVEL depois da primeira análise: o território
     fica carregado no `App` de propósito — custa uma leitura de servidor —, então
     `mapaPronto` segue `true` para sempre, e quem saía do modo e voltava caía direto no
     mapa com uma caixa flutuante por cima. O ajuste de 2026-08-18 tinha atacado a metade
     errada do problema: garantiu que a CAIXA existisse, não que a TELA DE ENTRADA
     voltasse — e é a tela de entrada que o card do Início promete.

     O território NÃO é descartado junto: o hero cobre o mapa, e o primeiro endereço colado
     reaproveita a carga que já está lá. Sair e voltar continua de graça para o servidor; o
     que muda é só o que a pessoa vê ao entrar.

     Vale também para o botão "Limpar", que zera as fichas: limpar tudo passa a devolver a
     tela de entrada, em vez de deixar a caixa flutuando sobre um mapa sem ficha nenhuma. */
  const semMapa = fichas.length === 0
  /* Sem hero (Explorar), a tela vazia NÃO cobre nada: o mapa é de quem veio explorar.
     Cai no render de baixo, que com `semMapa` só desenha a espera e o erro da leitura. */
  if (semMapa && comHero) {
    return (
      <div style={{ position: 'absolute', inset: 0, zIndex: 40 }}>
        <Landing
          marcador="Analisar um ponto ou imóvel"
          titulo="Cole o link do Google Maps ou a coordenada"
          explicacao={`A ficha lê quem mora no ${rotuloDoRaio(RAIO_PADRAO_KM)}, quanto de mercado sobra e quem já disputa o aluno ali — e o mapa abre na cidade do endereço, com as mesmas camadas do Explorar.`}
          onInicio={onInicio}
        >
          <Glass style={{ width: 'min(620px, 100%)', padding: 16, display: 'grid', gap: 10, textAlign: 'left' }}>
            {/* A linha "Funciona com o link da barra de endereço…" NÃO se repete aqui: o
                próprio `CampoPonto` já a publica. Repeti-la foi um defeito da primeira
                versão desta tela — a mesma frase duas vezes, uma embaixo da outra. */}
            <CampoPonto onResolver={resolver} ocupado={carregando} erro={erro} />
            <p style={{ font: '400 11.5px/1.5 var(--f-ui)', color: 'var(--tx-sub)', margin: 0 }}>
              A leitura sai do Censo 2022{institutoDaBase ? ` do ${institutoDaBase}` : ''}, no
              {rotuloDoRaio(RAIO_PADRAO_KM)} — a mesma régua do Relatório Pontual.
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
            {/* Só "Cancelar": aqui já existe ficha na tela, sempre. O ramo `fichas.length
                === 0` desta escolha — que repetia a régua do Censo — virou inalcançável
                quando o hero passou a cobrir esse caso, e ramo morto em JSX é pior do que
                em código comum: ninguém consegue provar na tela que ele ainda funciona.
                A régua continua publicada onde ela é lida de fato: no hero e na ficha. */}
            <button
              type="button"
              onClick={() => {
                setColando(false)
                setErroLocal(null)
                onLimparErro()
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

        {/* Erro de leitura FORA da caixa de colar — a regra é de `erroFlutuanteVisivel`.
            Vale sem ficha (o Explorar antes do 1o ponto, sem caixa onde ele apareceria) E
            com fichas: o 6o ponto, o clique no mar e a área recusada chegam pela lupa, pelo
            "Selecionar ponto" ou pelo "Analisar geometria", e o `CampoPonto` de dentro da
            janela só existe com "+ Adicionar" aberto. Sem este aviso o pin provisório
            sumia e nada dizia por quê. */}
        {erroFlutuanteVisivel({
          nFichas: fichas.length,
          caixaAberta: mostrandoCaixa,
          carregando,
          erro,
        }) && (
          <Glass
            style={{
              pointerEvents: 'auto',
              alignSelf: 'center',
              padding: '10px 14px',
              display: 'flex',
              alignItems: 'center',
              gap: 10,
              maxWidth: 'min(620px, 100%)',
            }}
          >
            <span role="alert" style={{ font: '500 12.5px/1.4 var(--f-ui)', color: 'var(--neg)' }}>
              {erro}
            </span>
            <button
              type="button"
              onClick={() => {
                setErroLocal(null)
                onLimparErro()
              }}
              style={{
                flexShrink: 0,
                padding: '6px 10px',
                borderRadius: 8,
                border: '1px solid var(--line-soft)',
                background: 'var(--surf-raised)',
                color: 'var(--tx-soft)',
                font: '600 11px/1 var(--f-ui)',
              }}
            >
              Fechar
            </button>
          </Glass>
        )}
      </div>

      {/* ---------------- A ÚNICA opção que puxa a janela ----------------
          Some enquanto a janela está aberta: quem já a tem na tela fecha pelo × ou Esc.
          Mora no canto superior ESQUERDO, logo abaixo do cabeçalho flutuante, no mesmo
          ponto em que a janela nasce (MARGEM 16, ver `JanelaFicha`): o botão fica onde a
          ficha estava. No canto inferior direito ele caía em cima da caixa de informações
          da direita; e no pé da esquerda cobriria o trilho. O topo é medido do cabeçalho. */}
      {ficha && !janela && (
        <div
          ref={setBotaoFichaEl}
          style={{ position: 'absolute', left: 16, top: topoBotaoFicha, pointerEvents: 'auto' }}
        >
          <Botao onClick={() => setJanela(true)}>
            Ver a ficha {fichas.length > 1 ? `(${fichas.length} pontos)` : ''} ›
          </Botao>
        </div>
      )}

      {/* ---------------- A janela ---------------- */}
      <JanelaFicha
        aberta={janela && ficha != null}
        /* O MESMO rótulo desambiguado das abas: com dois pontos da mesma cidade, o título
           "Goiânia" não dizia qual dos dois estava aberto — agora diz "Goiânia #2". */
        titulo={rotuloAberto}
        /* A régua e a contagem de setores vinham do cabeçalho próprio, que saiu junto com
           a cópia do Explorar. Vivem aqui porque é a ficha que elas qualificam — e some
           uma linha de chrome da tela. */
        subtitulo={
          ficha
            ? [
                [ficha.local.municipio, ficha.local.uf].filter(Boolean).join(' · '),
                /* "raio de 1 km" ou "área desenhada de 2,40 km²" (DEC-071): com uma área
                   na lista, o raio escrito à mão mentiria sobre ela. */
                rotuloDoRecorte(ficha),
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
        /* FIXO, fora da área que rola: são a SAÍDA da leitura, e com a ficha longa botões
           no fim do conteúdo só apareceriam para quem rolasse tudo. */
        rodape={
          ficha ? (
            <RodapePonto
              estudo={estadoDoEstudo(ficha, gerandoEstudo)}
              simulador={estadoDoSimulador(ficha, onAnalisarPonto != null)}
              gerando={gerandoEstudo}
              erro={erroEstudo}
              onEstudo={() => void gerarEstudo()}
              onSimulador={irParaSimulador}
            />
          ) : undefined
        }
      >
        {ficha && (
          <div style={{ display: 'grid', gap: 16 }}>
            <PainelPontos
            onCapturarMapas={onCapturarMapas}
              fichas={fichas}
              aberto={aberto}
              onAbrir={onAbrir}
              onRemover={(i) => {
                if (fichas.length === 1) {
                  setColando(true)
                  // Sem ponto nao ha' ficha: a janela ficaria vazia, e uma janela
                  // vazia por cima do mapa se le como defeito.
                  setJanela(false)
                }
                onRemover(i)
              }}
              onResolver={resolver}
              onLimpar={limparPontos}
              carregando={carregando}
              erro={erro}
            />
            <Ficha
              key={`${ficha.hex_id}-${aberto}`}
              ficha={ficha}
              partido={partidos[aberto] ?? null}
              onTrocarModo={onTrocarModo ? (ligado) => onTrocarModo(aberto, ligado) : undefined}
              trocando={trocandoModo.includes(chaveDaCoordenada(ficha.lat, ficha.lng))}
            />
          </div>
        )}
      </JanelaFicha>
    </div>
  )
}

/**
 * Os dois botões do rodapé, um degrau acima do `Botao` padrão (pedido do Vinicius,
 * 2026-10-16: "aumentar um pouco mais"). Fonte 13 -> 15 px e padding na mesma proporção
 * (~+16% de altura), e os DOIS com o mesmo padding vertical: o ghost tem 1 px de borda de
 * cada lado, então desconta 1 px no padding para as duas pílulas saírem da MESMA altura e
 * o rodapé continuar alinhado. Cabem lado a lado na largura mínima da janela (320 px).
 */
const ESTILO_RODAPE_PRIMARIO = { font: '700 15px/1 var(--f-ui)', padding: '14px 22px' } as const
const ESTILO_RODAPE_GHOST = { font: '600 15px/1 var(--f-ui)', padding: '13px 18px' } as const

/**
 * O rodapé fixo da janela: "Estudo" e "Simulador".
 *
 * Botão travado SEMPRE diz por quê, em texto na tela — `title` em botão desabilitado não
 * aparece em todo navegador, e um botão cinza mudo se lê como defeito.
 */
function RodapePonto({
  estudo,
  simulador,
  gerando,
  erro,
  onEstudo,
  onSimulador,
}: {
  estudo: EstadoBotao
  simulador: EstadoBotao
  gerando: boolean
  erro: string | null
  onEstudo: () => void
  onSimulador: () => void
}) {
  const motivos = [estudo.travadoPorque, simulador.travadoPorque].filter((m): m is string => m != null)
  return (
    <div style={{ flex: 1, minWidth: 0, display: 'grid', gap: 8 }}>
      <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', alignItems: 'center' }}>
        <Botao
          onClick={onEstudo}
          disabled={!estudo.habilitado}
          title={estudo.dica}
          style={ESTILO_RODAPE_PRIMARIO}
        >
          <span style={{ display: 'inline-flex', alignItems: 'center', gap: 8 }}>
            {gerando && <Spinner />}
            {estudo.rotulo}
          </span>
        </Botao>
        <Botao
          variante="ghost"
          onClick={onSimulador}
          disabled={!simulador.habilitado}
          title={simulador.dica}
          style={ESTILO_RODAPE_GHOST}
        >
          {simulador.rotulo} →
        </Botao>
      </div>
      {motivos.map((m) => (
        <p key={m} style={{ margin: 0, font: '400 11px/1.4 var(--f-ui)', color: 'var(--tx-sub)' }}>
          {m}
        </p>
      ))}
      {erro && (
        /* A falha é DITA, não engolida: um botão que volta ao normal sem PDF nenhum faz o
           operador clicar de novo e achar que a tela travou. */
        <p role="alert" style={{ margin: 0, font: '500 11.5px/1.4 var(--f-ui)', color: 'var(--neg)' }}>
          {erro}
        </p>
      )}
    </div>
  )
}

function Ficha({
  ficha,
  partido,
  onTrocarModo,
  trocando = false,
}: {
  ficha: PontoPayload
  /** O rótulo desambiguado deste ponto na lista ("Centro" + "#2"), ou nulo. */
  partido: RotuloPartido | null
  /** Troca o modo de estudo deste ponto (emenda da DEC-070). Ausente = sem chave. */
  onTrocarModo?: (estudoUltra: boolean) => void
  /** A releitura no outro modo está em voo. */
  trocando?: boolean
}) {
  const { local, censo, concorrencia, mercado } = ficha
  const contaDoMercado = mercado.disponivel ? leituraDoMercado(mercado) : null
  const ofertaUltra = ofertaDeEstudoUltra(ficha)
  /* ÁREA DESENHADA (DEC-071, fase 1): a mesma ficha, com o polígono no lugar do raio. O
     que muda é só o que a ficha AFIRMA sobre o recorte — os blocos e as contas são os
     mesmos, calculados pelo servidor dentro da área. */
  const area = ehAreaDesenhada(ficha)
  const recorte = rotuloDoRecorte(ficha)
  const onde = area ? 'na área' : 'no raio'

  return (
    <div style={{ display: 'grid', gap: 16 }}>
      {/* ---------------- Identificação ----------------
          O mapa lá atrás mostra ONDE; esta seção diz QUAL. A coordenada e o link de
          saída continuam aqui porque são conferência, não navegação. */}
      <Glass style={{ padding: 18, display: 'grid', gap: 10 }}>
        <Eyebrow dot>{area ? 'Área desenhada' : 'Ponto analisado'}</Eyebrow>
        <div
          style={{
            font: '600 20px/1.2 var(--f-ui)',
            color: 'var(--tx-max)',
            letterSpacing: '-.01em',
          }}
        >
          {/* O MESMO nome da aba, com o "#k" quando dois pontos empatam no nome: a
              ficha aberta tem de dizer QUAL dos "Centro" ela é. O "#k" fica fora do texto
              do nome, para nunca ser o pedaço que um corte esconde. */}
          {partido?.base ?? nomeDoLugar(local) ?? 'Local sem bairro identificado'}
          {partido?.sufixo && (
            <span style={{ marginLeft: 8, color: 'var(--tx-sub)', whiteSpace: 'nowrap' }}>
              {partido.sufixo}
            </span>
          )}
        </div>
        <div style={{ font: '400 13px/1.4 var(--f-ui)', color: 'var(--tx-narrative)' }}>
          {/* Sem bairro resolvido o nome acima é o do município (ou a coordenada): a
              ausência continua DECLARADA aqui, em vez de sumir com a troca do título. */}
          {(area
            ? /* A área não tem UM bairro: o do ponto central é só onde ele caiu. Diz o
                 recorte, que é o que identifica a área. */
              [local.municipio, local.uf, recorte]
            : [
                local.municipio,
                local.uf,
                local.hexagono || local.bairro ? null : 'sem bairro identificado',
              ]
          )
            .filter(Boolean)
            .join(' · ')}
        </div>
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
          <Chip>hex {ficha.hex_id}</Chip>
          {/* O modo do estudo, discreto, ao lado da identidade (emenda da DEC-070). */}
          {ofertaUltra?.ligado && <Chip>estudo da unidade Ultra {ofertaUltra.nome}</Chip>}
          <Chip>
            {/* Na área, a coordenada é a do PONTO CENTRAL (o `representative_point`,
                sempre dentro do polígono) — é ele que o Simulador recebe. */}
            {area ? 'ponto central ' : ''}
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
            {area ? 'Abrir o ponto central no Google Maps ↗' : 'Abrir no Google Maps ↗'}
          </a>
        </div>
      </Glass>

      {/* A chave do estudo da unidade Ultra fica logo abaixo da identificação (pedido do
          Vinicius, 2026-10-16): ela muda a PERGUNTA da ficha inteira (estudo de ponto x
          estudo da unidade), e no fim do bloco de mercado exigia rolar a ficha toda para
          ser achada. */}
      {ofertaUltra && (
        <ChaveEstudoUltra oferta={ofertaUltra} trocando={trocando} onTrocar={onTrocarModo} />
      )}

      {/* ---------------- Socioeconomia (sempre disponível) ---------------- */}
      <Secao titulo={area ? 'Quem mora na área' : 'Quem mora em volta'} nota={`${censoDaBase() ?? 'Censo 2022'} · ${recorte}`}>
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
          realmente intersectada, não pela área {area ? 'desenhada' : 'do círculo'}.
        </Rodape>
        {censo.detalhe && (
          <DetalheRegiao detalhe={censo.detalhe} concorrencia={concorrencia} area={area} />
        )}
      </Secao>

      {/* ---------------- Concorrência ---------------- */}
      <Secao titulo="Quem já disputa o aluno aqui" bloco={concorrencia}>
        <div style={{ display: 'grid', gap: 14 }}>
          {/* A régua vai "do imóvel até a borda do raio": num polígono não há borda a uma
              distância só, e a régua afirmaria uma escala que não existe. Na área, a lista
              simples — quem está dentro, a que distância do ponto central. */}
          {area || ficha.raio_km == null ? (
            <ListaConcorrentesArea lista={concorrencia.lista} />
          ) : (
            <ReguaConcorrentes lista={concorrencia.lista} raioKm={ficha.raio_km} />
          )}
          <FilaApoio>
            <NumeroApoio rotulo={`Concorrentes ${onde}`} valor={num(concorrencia.n_concorrentes)} />
            <NumeroApoio rotulo={`Unidades Ultra ${onde}`} valor={num(concorrencia.n_ultra)} />
          </FilaApoio>
        </div>
      </Secao>

      {/* ---------------- Mercado / residual ----------------
          DO RAIO, não do hexágono (DEC-070). SAM e consumo são calculados no MESMO
          recorte da população (raio de 1,0 km do ponto), e o consumo aparece nas DUAS
          parcelas — concorrentes de rede e a própria Ultra — para a conta fechar na
          frente do operador: Residual = SAM − consumo. Antes só SAM e residual
          apareciam, e um residual zero com SAM maior que o consumo dos concorrentes
          (Santana/SP) não tinha explicação na tela: faltava a parcela da Ultra. */}
      <Secao
        titulo="Quanto de mercado sobra"
        nota={contaDoMercado ? contaDoMercado.recorte : undefined}
        bloco={mercado}
      >
        {/* Barra primeiro: "SAM 12.000" e "residual 4.000" lado a lado exigem conta de
            cabeça para responder o que interessa — a sobra é a maior parte do mercado ou
            uma margem? A conta inteira continua abaixo, linha a linha. */}
        <div style={{ display: 'grid', gap: 14 }}>
          <BarraMercado sam={mercado.sam} residual={mercado.residual} />
          <MedidorScore
            rotulo="Score de residual"
            valor={mercado.score_residual}
            faixas={FAIXAS_DEMANDA}
            nota="satura em 100 acima de 2.500 alunos — uma unidade cheia"
          />
          {contaDoMercado && <ContaDoMercado leitura={contaDoMercado} />}
        </div>

        <Rodape>
          O mapa atrás desta janela colore cada hexágono pelo residual dele; a conta acima
          é a do recorte {area ? 'desenhado' : 'do ponto'} ({contaDoMercado?.recorte ?? recorte}). As
          duas leituras podem divergir: o recorte pega pedaços de vários hexágonos.
        </Rodape>
      </Secao>

      {/* ---------------- Recomendação ----------------
          Só os critérios do TERRITÓRIO. A viabilidade saiu da ficha (2026-10-14) e virou
          o botão "Simulador" do rodapé: com `viavel` nulo a recomendação não opina sobre
          contrato — nenhuma ação financeira (aluguel, metragem, teto) é gerada. */}
      <Secao
        titulo="Serve este imóvel?"
        nota="cada métrica contra a régua da rede"
      >
        <Recomendacao
          criterios={ficha.criterios}
          reguas={ficha.reguas}
          viavel={null}
          m2={null}
          aluguel={null}
          tetoAluguel={null}
          melhoria={null}
          gradeSemViavel={false}
        />
      </Secao>
    </div>
  )
}

/**
 * A CHAVE do estudo da unidade Ultra (emenda da DEC-070), logo abaixo da identificação.
 *
 * Aparece quando o ponto cai a até 150 m de uma unidade Ultra (Santana: 9 m). DESLIGADA por
 * padrão: o estudo de ponto continua contando a Ultra, porque quem estuda um imóvel ao lado
 * dela precisa ver o mercado ocupado. Ligada, o consumo DA unidade sai — e a frase do
 * servidor diz isso, com quanto saiu. Trocar relê o ponto no servidor; nada é recalculado
 * aqui.
 */
function ChaveEstudoUltra({
  oferta,
  trocando,
  onTrocar,
}: {
  oferta: OfertaEstudoUltra
  trocando: boolean
  onTrocar?: (estudoUltra: boolean) => void
}) {
  return (
    <div
      style={{
        display: 'grid',
        gap: 6,
        padding: '10px 12px',
        borderRadius: 10,
        border: `1px solid ${oferta.ligado ? 'var(--ac-text)' : 'var(--line-soft)'}`,
        background: 'var(--surf-raised)',
      }}
    >
      <label
        style={{
          display: 'flex',
          alignItems: 'flex-start',
          gap: 8,
          cursor: onTrocar && !trocando ? 'pointer' : 'default',
          font: '500 12px/1.4 var(--f-ui)',
          color: 'var(--tx-soft)',
        }}
      >
        <input
          type="checkbox"
          role="switch"
          aria-checked={oferta.ligado}
          checked={oferta.ligado}
          disabled={!onTrocar || trocando}
          onChange={(e) => onTrocar?.(e.target.checked)}
          style={{ marginTop: 2, accentColor: 'var(--ac-text)' }}
        />
        <span>
          {oferta.pergunta}
          {trocando && (
            <span style={{ marginLeft: 8, display: 'inline-flex', verticalAlign: 'middle' }}>
              <Spinner />
            </span>
          )}
        </span>
      </label>
      <span style={{ font: '400 11px/1.4 var(--f-ui)', color: 'var(--tx-sub)' }}>
        {oferta.ligado
          ? (oferta.declaracao ??
            `Estudo da unidade Ultra ${oferta.nome}: consumo da própria unidade desconsiderado.`)
          : 'Desligado: estudo de ponto — a Ultra próxima conta no mercado ocupado.'}
      </span>
    </div>
  )
}

/**
 * A conta do mercado, linha a linha: SAM − concorrentes − Ultra = residual.
 *
 * Parcela ausente sai com travessão e o motivo do servidor abaixo — nunca zero, que
 * afirmaria mercado livre por falta de dado.
 */
function ContaDoMercado({ leitura }: { leitura: ReturnType<typeof leituraDoMercado> }) {
  return (
    <div style={{ display: 'grid', gap: 6 }}>
      {leitura.linhas.map((l) => {
        const total = l.chave === 'residual'
        return (
          <div
            key={l.chave}
            style={{
              display: 'grid',
              gridTemplateColumns: '14px 1fr auto',
              alignItems: 'baseline',
              gap: 8,
              paddingTop: total ? 6 : 0,
              borderTop: total ? '1px solid var(--line-soft)' : undefined,
            }}
          >
            <span
              aria-hidden
              className="num"
              style={{ font: '600 12px/1.3 var(--f-num)', color: 'var(--tx-sub)' }}
            >
              {l.sinal === '-' ? '−' : l.sinal}
            </span>
            <span style={{ minWidth: 0, display: 'grid', gap: 1 }}>
              <span
                style={{
                  font: `${total ? 600 : 400} 11.5px/1.3 var(--f-ui)`,
                  color: total ? 'var(--tx-max)' : 'var(--tx-soft)',
                }}
              >
                {l.rotulo}
              </span>
              {l.detalhe && (
                <span style={{ font: '400 10.5px/1.3 var(--f-ui)', color: 'var(--tx-sub)' }}>
                  {l.detalhe}
                </span>
              )}
            </span>
            <span
              className="num"
              style={{
                font: `${total ? 700 : 600} 12.5px/1.3 var(--f-num)`,
                color: total ? 'var(--tx-max)' : 'var(--tx-strong)',
                fontVariantNumeric: 'tabular-nums',
                whiteSpace: 'nowrap',
              }}
            >
              {l.valor == null ? alunos(l.valor) : `${alunos(l.valor)} alunos`}
            </span>
          </div>
        )
      })}
      {leitura.avisoGate && <Rodape>{leitura.avisoGate}</Rodape>}
      {leitura.motivoParcial && <Rodape>{leitura.motivoParcial}</Rodape>}
    </div>
  )
}

/**
 * Concorrentes DENTRO da área desenhada, com a distância ao ponto central — o par da
 * `ReguaConcorrentes` para o polígono, que não tem "borda do raio" para servir de escala.
 * Truncada como a lista do servidor (30), e dizendo quando truncou.
 */
function ListaConcorrentesArea({
  lista,
}: {
  lista: { rede: string | null; dist_km: number | null }[] | null | undefined
}) {
  if (!lista?.length) return null
  return (
    <div style={{ display: 'grid', gap: 4 }}>
      {lista.map((c, i) => (
        <div
          key={`${c.rede}-${i}`}
          style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', gap: 10 }}
        >
          <span style={{ font: '400 11.5px/1.3 var(--f-ui)', color: 'var(--tx-soft)', minWidth: 0 }}>
            {c.rede ?? 'Academia sem nome'}
          </span>
          <span className="num" style={{ font: '400 10.5px/1.3 var(--f-num)', color: 'var(--tx-sub)', whiteSpace: 'nowrap' }}>
            {c.dist_km == null ? num(null) : `${num(c.dist_km, 2)} km do ponto central`}
          </span>
        </div>
      ))}
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
