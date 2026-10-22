import { latLngToCell } from 'h3-js'
import { useUfsDaBase } from '../lib/base-contexto'
import {
  useCallback,
  useEffect,
  useLayoutEffect,
  useMemo,
  useState,
  useRef,
  useSyncExternalStore,
  type ReactNode,
} from 'react'

import type { PontoEscolhido } from '../App'
import BarraCamadas, {
  LinhaDeEstado,
  RodapeDoPainel,
  type ChaveDeCamada,
} from '../components/BarraCamadas'
import BotaoInicio from '../components/BotaoInicio'
import FichaHex from '../components/FichaHex'
import FichaImovel from '../components/FichaImovel'
import FichaUnidadeNoMapa from '../components/FichaUnidadeNoMapa'
import HexMap, { type AlvoDaCaptura, type SearchPin, type ViewState } from '../components/HexMap'
import JanelaFicha from '../components/JanelaFicha'
import MethodologyPanel from '../components/MethodologyPanel'
import NarrativePanel from '../components/NarrativePanel'
import PainelComparacao from '../components/PainelComparacao'
import ScoreLegend, { LegendaCalor } from '../components/ScoreLegend'
import { alternarCalor, alternarCoresHex, type ModoCalor } from '../lib/camadas-calor'
import Select from '../components/Select'
import StepperBar from '../components/StepperBar'
import { Botao } from '../components/primitives'
import { api, ApiError, baixar } from '../lib/api'
import { relatarAcessoNegado, relatarFalhaDeRede } from '../lib/sessao'
import { parseCoordinate } from '../lib/coord'
import { alunos, coord, num } from '../lib/format'
import { ACC } from '../lib/imovel'

/* O magenta da camada imobiliaria com o mesmo alpha .16 que o turquesa usa em
   `--ac-a16`. Nao vive em `lib/imovel` porque la' a escada de alphas (08/10/12/24/30/50)
   foi montada para a ABA; este e' o realce da LINHA do painel de camadas do mapa. */
const ACC_16 = 'rgba(221,61,151,.16)'
import { chaveContexto, fotoAplicavel, type EstadoMapa } from '../lib/mapa-estado'
import { REDES_LIGADAS_POR_PADRAO, pinsVisiveis, subDaChaveRedes, temAlunos } from '../lib/pins'
import { Z_CABECALHO_MAPA, Z_CORPO_MAPA } from '../lib/camadas-mapa'
import { registrarCabecalhoMapa } from '../lib/registro-cabecalho'
import { criarViagemUnidade } from '../lib/viagem-unidade'
import {
  ROTULO_SEM_REDE,
  unidadeDoPin,
  unidadesDaBusca,
  type UnidadeNoMapa,
} from '../lib/ficha-unidade'
import { type UnidadeComTerritorio, viajarAoTerritorioDaUnidade } from '../lib/territorio-unidade'
import { MAX_COMPARADOS, ranquear } from '../lib/ranking-comparacao'
import { rodapeDaBase, tituloEscolhaUnidade } from '../lib/rodape-base'
import { type AlvoCaptura, alvoDoHex, pinsDoAlvo } from '../lib/captura-mapa'
import { DIMENSOES, rotuloDoHex, rotulosDosHexes } from '../lib/comparacao'
import { cliqueSelecionaHex, type FerramentaMapa } from '../lib/ferramenta-mapa'
import {
  desenhoPausado,
  rascunhoSobrevive,
  transicaoTrilho,
  type AcaoTrilho,
  type EstadoTrilho,
  type MotivoFimDoDesenho,
} from '../lib/painel-trilho'
import type { PosicaoGeoJson } from '../lib/comparacao-pontos'
import {
  AREA_MAX_KM2,
  DIAGONAL_MAX_KM,
  MAX_VERTICES,
  adicionarVertice,
  avaliarDesenho,
  desfazerVertice,
  formatarKm2,
  interpretarClique,
  paraGeoJson,
} from '../lib/geometria-desenho'
import type { Coord } from '../lib/medicao'
import { assinarJanelas, deslocamentoDoTrilho, janelasAbertas } from '../lib/ocupacao-janelas'
import { degrauSobreFichaDePonto, janelaDoHexVisivel, pontoSeleciona } from '../lib/janela-hex'
import { selecaoMarcadaNoMapa } from '../lib/alcance'
import type { PinDoPonto } from '../lib/pontos-estado'
import type { Tema } from '../lib/tema'
import { hexesComTop10, legendaTop10, mapaTop10, textosTop10 } from '../lib/top10'
import type {
  Cobertura1k,
  RedeUnidade,
  RedeUnidadeSemRede,
  Hex,
  MunicipioItem,
  MunicipioPayload,
  Oportunidade,
  Pins,
  SetoresHeatmapPayload,
} from '../lib/types'

/* A CAMADA em que o raio de 1 km vale. Camada 3 e' "Pressao concorrencial", e o modelo de
   1 km E' a medida dessa pressao — nas outras o mapa mede outra grandeza (1 = censo, 2 =
   demanda nao atendida, 4 = crescimento, 5 = faixa do M1) e o recorte de cobertura
   responderia a uma pergunta que ninguem fez ali.

   Constante nomeada porque o mesmo numero governa DUAS coisas em arquivos diferentes:
   este portao e o `PASSOS_DA_PRESSAO` do `HexMap`. Mudar um sem o outro deixa o mapa
   pintando por uma regua e desenhando o recorte por outra. */
const CAMADA_DO_RAIO = 3

/** Filtro global "melhores hexes": faixas M1 permitidas por nível. */
const FAIXA_FILTROS: Record<string, Set<string>> = {
  prioridade: new Set(['Prioridade máxima']),
  alta: new Set(['Prioridade máxima', 'Alta']),
  media: new Set(['Prioridade máxima', 'Alta', 'Média']),
}

export interface MapScreenProps {
  ufs: string[]
  uf: string
  onUf: (uf: string) => void
  municipios: MunicipioItem[]
  /**
   * De que UF e' a lista `municipios` (a resposta do `/api/municipios` diz). Logo depois de
   * uma troca de estado a lista ainda e' a do estado ANTERIOR ate' a nova chegar; sem saber
   * de quem ela e', a unidade escolhida aqui seria procurada na lista errada. Ausente = nao
   * se sabe, e o mapa pede a lista da UF da unidade ao servidor.
   */
  municipiosUf?: string
  municipio: string
  onMunicipio: (m: string) => void
  dados: MunicipioPayload | null
  carregando: boolean
  erro: string | null
  onAnalisarPonto: (p: PontoEscolhido) => void
  /**
   * Foto do mapa guardada pelo App. O `App` renderiza as telas por CONDICIONAL, entao
   * ir para a Viabilidade DESMONTA esta tela e mata todo o `useState` local: passo do
   * funil, hexagono selecionado, pin da busca, cenario multi-hex e a camera do deck.gl.
   * Era isso que fazia o mapa "resetar" na volta pelo breadcrumb "vindo do mapa".
   * A UF e o municipio nunca se perderam — moram no App desde sempre.
   */
  estadoInicial: EstadoMapa
  onEstado: (e: EstadoMapa) => void
  /** Volta ao menu de modos. Não limpa nada — ver `components/BotaoInicio`. */
  onInicio: () => void
  /**
   * DESTINO escolhido numa LISTA fora desta tela (o ranking nacional do Modo 3): leva a
   * camera, o contorno de selecao e a FICHA DO HEXAGONO ate' ele.
   *
   * Vem do pai porque um pin em state local nao serviria — o efeito que zera a tela ao
   * trocar de UF/municipio (logo abaixo) limpa `pin`, e a troca de municipio e'
   * exatamente o que acontece quando se chega por uma lista de outra cidade. Vindo do
   * pai, ele sobrevive a essa limpeza, que continua valendo para a busca manual.
   */
  pinFixo?: SearchPin | null
  /**
   * O PONTO ATIVO da analise de pontos (lista do `App`, `lib/pontos-estado`): o da aba
   * aberta, ou o provisorio que acabou de ser pedido.
   *
   * Separado do `pinFixo` porque pede OUTRA leitura do mesmo hexagono: o destino de uma
   * lista e' "mostre este hexagono" (abre a ficha dele), o ponto e' "analise este lugar"
   * (a ficha e' a do PONTO, publicada pelo `PontoScreen`). Os dois selecionam o hexagono
   * — contorno no mapa e linha do ranking —, mas so' o destino abre a ficha do hexagono.
   *
   * PRECEDENCIA: `pontoAtivo` vence `pinFixo`, que vence o pin local da unidade/imovel. O
   * `App` limpa o `pontoAtivo` quando outro passa a valer: nos destinos de lista e nas
   * trocas de territorio, por conta propria; na UNIDADE escolhida aqui, avisado por
   * `onSoltarPonto`.
   */
  pontoAtivo?: SearchPin | null
  /**
   * Uma unidade da rede foi escolhida aqui (seletor UNIDADES ou pin da Ultra): o pin LOCAL
   * dela tem de valer, entao o `App` tira do ponto ativo o comando da camera. Sem este
   * aviso o `pontoAtivo` seguia vencendo a precedencia e a camera nunca chegava a' unidade
   * (o ponto continua na comparacao; escolher a aba dele devolve o comando).
   */
  onSoltarPonto?: () => void
  /**
   * TODOS os pontos da comparacao, cada um na sua cor de identidade (decisao do dono,
   * 2026-10-14), prontos para o mapa desenhar.
   *
   * Repassada ao `HexMap`, que desenha um pin por ponto (anel na cor da aba, o ativo
   * maior, o provisorio esmaecido) e suprime o pin neutro do `pontoAtivo` quando ele e'
   * um deles. Aqui ela tambem decide de que lado nasce a ficha do hexagono.
   */
  pontosComparados?: readonly PinDoPonto[]
  /**
   * Clique num pin colorido da comparacao: abre a aba daquele ponto (e a janela da
   * ficha, se estiver fechada). Ausente = o pin so' mostra o rotulo no hover.
   */
  onPontoComparado?: (indice: number) => void
  /**
   * A busca do cabecalho resolveu uma coordenada: ela vira um PONTO ANALISADO.
   *
   * Vale nas DUAS entradas do mapa ("Explorar uma regiao" e "Analisar um ponto", decisao
   * do dono, 2026-10-14): buscar abre a ficha de ponto e o comparativo de pontos, nos dois
   * casos. Esta tela nao poe pin nem seleciona nada por conta propria — o ponto volta por
   * `pontoAtivo`, que e' a regra unica de pin. Antes a busca soltava um pin LOCAL que
   * gerava o cartao "Estudo pontual", uma terceira leitura do mesmo lugar.
   *
   * `doMapa` = o pedido veio de um clique no proprio mapa ("Selecionar ponto"): o lugar ja'
   * esta' na tela, e o pin dele nao voa nem aproxima a camera.
   */
  onPontoBuscado: (lat: number, lng: number, doMapa?: boolean) => void
  /**
   * "Estudar a região desta unidade", na ficha da unidade Ultra (emenda da DEC-070): abre a
   * análise de ponto na coordenada da unidade JÁ no estudo da unidade — o consumo dela sai
   * do mercado. Ausente = o botão não aparece.
   */
  onEstudarUnidade?: (lat: number, lng: number) => void
  /**
   * "Analisar geometria" concluiu uma área (DEC-071, fase 1): os anéis do polígono
   * desenhado, em `[lng, lat]`, fechados. Quem recebe (o `App`) a leva ao
   * `/api/ponto/geometria` e a põe na MESMA comparação dos pontos.
   *
   * Ausente = a ferramenta não aparece no trilho nem no painel: sem destino, o desenho
   * não levaria a lugar nenhum.
   */
  onGeometriaDesenhada?: (geometria: PosicaoGeoJson[][]) => void
  /** Sem UF escolhida, não desenha o hero — quem o publica é a camada de cima. */
  semLanding?: boolean
  /**
   * ID do imóvel a ABRIR assim que a lista da UF chegar — a porta de entrada da ficha
   * do imóvel, que não existia (relato do Felipe, 2026-09-23: "abre o popup do
   * hexágono em vez do popup de informações do imóvel").
   *
   * Vem como ID e não como objeto de propósito: a `FichaImovel` precisa do registro
   * inteiro, e ele já está em `imoveisUf`, que este componente carrega para desenhar
   * os pins. Receber o objeto pronto criaria uma segunda cópia do mesmo dado.
   */
  imovelInicial?: string | null
  /** Avisa que a intenção acima foi consumida, para não reabrir a cada volta ao mapa. */
  onImovelAberto?: () => void
  /**
   * Se o usuário pode ver as UNIDADES da rede aqui: o seletor de unidades do cabeçalho e a
   * ficha da unidade em janela (2026-10-01). Os dois leem `/api/rede/*`, que o backend só
   * serve a quem tem a aba `executiva` — quem decide é o App, pelo mesmo `telaLiberada` do
   * resto. `false` = o cabeçalho fica como sempre foi, com o filtro "Melhores".
   */
  verUnidades?: boolean
  /**
   * Publica a função de CAPTURA do mapa para quem está fora deste componente.
   *
   * O modo de ponto é irmão na árvore e usa o MESMO mapa (`App.tsx`), então ele precisa
   * pedir capturas sem ter o mapa em mãos. Mesmo motivo pelo qual o `pinFixo` mora no App:
   * quem consome o mapa é o mapa, e o App só reparte o canal.
   */
  registrarCaptura?: (capturar: (alvos: AlvoCaptura[]) => Promise<string[]>) => void
  /**
   * Leva para a ABA de Oportunidades Imobiliárias já focada num imóvel — o caminho
   * INVERSO do "Ver no Mapa Territorial" daquela aba. Quem troca de tela é o App
   * (mesmo motivo do `onAnalisarPonto`); ausente = o botão da janela não aparece.
   */
  onVerImovelNaAba?: (o: Oportunidade) => void
  /**
   * Tema do app, repassado ao `HexMap`.
   *
   * Só o mapa precisa dele nesta tela: o resto do `MapScreen` é DOM e lê os tokens pela
   * cascata, sem saber que existe tema. O deck.gl e o MapLibre não leem `var()` — o
   * basemap e as cores de seleção têm de chegar como valor.
   */
  tema: Tema
}

export default function MapScreen({
  registrarCaptura,
  ufs,
  uf,
  onUf,
  municipios,
  municipiosUf = '',
  municipio,
  onMunicipio,
  dados,
  carregando,
  erro,
  onAnalisarPonto,
  estadoInicial,
  onEstado,
  onInicio,
  pinFixo = null,
  pontoAtivo = null,
  pontosComparados,
  onPontoComparado,
  onSoltarPonto,
  onPontoBuscado,
  onEstudarUnidade,
  onGeometriaDesenhada,
  semLanding = false,
  imovelInicial = null,
  onImovelAberto,
  verUnidades = false,
  onVerImovelNaAba,
  tema,
}: MapScreenProps) {
  // A foto so' vale se tiver sido tirada NESTA uf/municipio — `fotoAplicavel` faz esse
  // portao (lib/mapa-estado). Sem ele, um pin de Sao Paulo reapareceria depois de um
  // drill-down em Campinas. `useState(() => ...)` roda so' na montagem: e' o unico
  // momento em que a foto e' consumida.
  const [foto] = useState(() => fotoAplicavel(estadoInicial, uf, municipio))

  // Todo estado abaixo NASCE da foto, nao de um valor fixo — e' o que devolve a tela
  // como estava quando o operador volta da Viabilidade.
  const [passoN, setPassoN] = useState(foto.passoN)
  const [metodologiaAberta, setMetodologiaAberta] = useState(false)
  const [selecionado, setSelecionado] = useState<string | null>(foto.selecionado)
  /* A selecao veio da busca de um ponto (true) ou de um clique no hexagono (false)? E' o
     que decide se a ficha do HEXAGONO abre — ver `lib/janela-hex`. Nasce `false`: a foto
     guarda a selecao, e se ela era a de um ponto, o efeito do `pontoAtivo` religa. */
  const [selecaoDaBusca, setSelecaoDaBusca] = useState(false)
  const [gerando, setGerando] = useState(false)
  const [aviso, setAviso] = useState<string | null>(null)

  /* Texto da busca do cabecalho. O `pin` local NAO e' mais o da busca (ela vira ponto
     analisado, ver `onPontoBuscado`): sobrou para a unidade escolhida no seletor e para o
     imovel que chega da aba de imoveis, que marcam um lugar sem pedir analise. */
  const [busca, setBusca] = useState(foto.busca)
  const [pin, setPin] = useState<SearchPin | null>(foto.pin)
  const [buscaErro, setBuscaErro] = useState<string | null>(null)
  const [buscando, setBuscando] = useState(false)

  // Filtro global: mostra só os melhores hexes (por faixa M1).
  const [filtroFaixa, setFiltroFaixa] = useState(foto.filtroFaixa)
  // Cenário multi-hex: seleção de vários hexes para somar.
  const [modoCenario, setModoCenario] = useState(foto.modoCenario)
  const [cenario, setCenario] = useState<string[]>(foto.cenario)
  const [copiado, setCopiado] = useState(false)

  /* Somatorio ao vivo dos dois modelos (2 km x 1 km) sobre os hexes que o backend serviu
     para o recorte atual. Vive aqui, ANTES do `raio1km`, porque e' ele quem responde se a
     base tem os campos do modelo novo — sem isso nao ha' o que desenhar. O funil (numeros
     grandes e narrativa) continua vindo do modelo de 2 km: trocar aquilo exige mexer no
     payload do servidor. */
  const comparativoRaio = useMemo(() => {
    const hs = dados?.hexes ?? []
    if (!hs.length || hs[0].conc1k == null) return null
    let res2 = 0
    let res1 = 0
    let comConc = 0
    for (const h of hs) {
      res2 += h.oferta ?? 0
      res1 += h.oferta1k ?? 0
      if ((h.conc1k ?? 0) > 0) comConc += 1
    }
    return { res2, res1, comConc, total: hs.length }
  }, [dados])

  /* RAIO DE 1 KM — deixou de ser chave e virou o PADRAO DA CAMADA 3 (Juan, 2026-09-02:
     "tirar o botão de ver raio de 1 km de concorrentes, deixar ele funcionando por
     padrão... e só poder ser visto essa visão na camada 3").

     Era um prototipo com liga/desliga em duas camadas (2 e 3), aberto sempre desligado
     para o piloto continuar identico ao de antes. O experimento acabou: o modelo de 1 km
     e' a leitura da PRESSAO CONCORRENCIAL, e pressao concorrencial e' a camada 3 — nas
     outras o mapa mede outra grandeza (1 = censo, 2 = demanda nao atendida, 4 =
     crescimento, 5 = faixa do M1) e o recorte de cobertura respondia a uma pergunta que
     ninguem tinha feito ali.

     DERIVADO, e nao state: o valor e' uma FUNCAO da camada aberta, e guarda-lo num
     `useState` abriria a porta para os dois divergirem (camada 4 na tela, raio ligado
     por um clique antigo). `comparativoRaio` continua no portao porque a geometria so'
     existe quando o backend serviu os campos do modelo novo — base velha desenha o mapa
     de sempre, sem cobertura. */
  const raio1km = comparativoRaio != null && passoN === CAMADA_DO_RAIO
  /* A FERRAMENTA do trilho, UM estado so' (`lib/ferramenta-mapa`): a regua, e depois
     "Selecionar ponto" e "Analisar geometria". Comeca DESLIGADA. Ligada, o clique e' da
     ferramenta e nao seleciona hexagono — por isso e' chave explicita e nao um gesto
     escondido. Era o booleano `medindo` (BLK-CONC-MEDIR); com tres ferramentas disputando
     o mesmo clique, tres booleanos deixariam ligar duas ao mesmo tempo. */
  /* A ferramenta e o painel de camadas andam JUNTOS desde 2026-10-16: o painel do desenho
     É a ferramenta "geometria" ligada e divide o lugar com o de camadas — um fecha o outro.
     A regra (e por que abrir as camadas PAUSA o desenho em vez de apagá-lo) mora em
     `lib/painel-trilho`, testada; aqui só se despacha. */
  const [trilho, setTrilho] = useState<EstadoTrilho>({ camadasAberto: false, ferramenta: 'nenhuma' })
  const ferramenta: FerramentaMapa = trilho.ferramenta
  const acaoTrilho = useCallback((a: AcaoTrilho) => setTrilho((e) => transicaoTrilho(e, a)), [])
  const alternarRegua = useCallback(
    () => acaoTrilho({ tipo: 'alternar-ferramenta', alvo: 'regua' }),
    [acaoTrilho],
  )
  /* "Selecionar ponto" (decisao do dono, 2026-10-14): com ela ligada, cada clique no mapa
     ACRESCENTA um ponto a' comparacao pelo MESMO caminho da lupa (`aplicarPonto` ->
     `onPontoBuscado` -> `/api/ponto`), e a ferramenta continua ligada para o proximo
     clique. Ponto de outro municipio troca o mapa de municipio pelo fluxo que ja' existe
     (`local` da ficha -> `App`), sem nada novo aqui. */
  const alternarPonto = useCallback(
    () => acaoTrilho({ tipo: 'alternar-ferramenta', alvo: 'ponto' }),
    [acaoTrilho],
  )
  /* "Analisar geometria" (DEC-071, fase 1): com ela ligada, cada clique no mapa acrescenta
     um VÉRTICE; a área fecha no 1º vértice ou em "Concluir" e vira um item da comparação.
     O desenho (os vértices) mora AQUI, e não no `HexMap`, porque é daqui a barra de
     Concluir/Desfazer/Cancelar — o mapa só desenha o provisório e repassa o clique. As
     regras (fechar por pixels, área, autointerseção, limites) são de `lib/geometria-desenho`. */
  const alternarGeometria = useCallback(
    () => acaoTrilho({ tipo: 'alternar-ferramenta', alvo: 'geometria' }),
    [acaoTrilho],
  )
  const [vertices, setVertices] = useState<Coord[]>([])
  /** Recusa do último gesto (concluir inválido, teto de vértices) — some no próximo clique. */
  const [avisoDesenho, setAvisoDesenho] = useState<string | null>(null)
  /* Desligar a ferramenta NÃO apaga mais o desenho (2026-10-16): fechar o painel, abrir as
     camadas, tocar o polígono de novo ou ligar outra ferramenta PAUSAM — os vértices ficam
     no mapa, esmaecidos, e o botão do polígono retoma de onde parou. Quem apaga é
     `encerrarDesenho` com um motivo que não seja pausa (`rascunhoSobrevive`): Cancelar, Esc
     com o desenho ligado, Concluir e a troca de território (efeito logo abaixo). A recusa
     pendente some ao pausar: ela falava do gesto anterior. */
  useEffect(() => {
    if (ferramenta !== 'geometria') setAvisoDesenho(null)
  }, [ferramenta])
  const encerrarDesenho = useCallback(
    (motivo: MotivoFimDoDesenho) => {
      acaoTrilho({ tipo: 'desligar-ferramenta' })
      if (!rascunhoSobrevive(motivo)) setVertices([])
      setAvisoDesenho(null)
    },
    [acaoTrilho],
  )
  /* Trocar de município/UF também: o polígono é de um território, e os vértices de uma
     cidade desenhados sobre o mapa de outra são o "número certo no lugar errado" da régua. */
  useEffect(() => {
    setVertices([])
    setAvisoDesenho(null)
  }, [uf, municipio])

  const avaliacaoDesenho = avaliarDesenho(vertices)
  function concluirDesenho(vs: Coord[] = vertices) {
    const a = avaliarDesenho(vs)
    if (!a.podeConcluir) {
      setAvisoDesenho(a.motivo)
      return
    }
    onGeometriaDesenhada?.(paraGeoJson(vs).coordinates)
    /* A área desenhada é UM gesto completo: a ferramenta desliga ao concluir, e o próximo
       clique no mapa volta a ser o de sempre (ou o da ficha que acabou de abrir). Para
       outra área, liga de novo. */
    encerrarDesenho('concluir')
  }
  function cliqueNoDesenho(c: Coord, mpp: number) {
    const acao = interpretarClique(vertices, c, mpp)
    if (acao.tipo === 'fechar') {
      concluirDesenho()
      return
    }
    if (acao.tipo === 'cheio') {
      setAvisoDesenho(`Máximo de ${MAX_VERTICES} vértices. Conclua a área ou desfaça um vértice.`)
      return
    }
    setAvisoDesenho(null)
    setVertices((vs) => adicionarVertice(vs, c))
  }

  /* Esc DESLIGA a ferramenta ligada — e so' ela. Escuta na fase de CAPTURA e para a
     propagacao: sem isso o mesmo Esc tambem fecharia a janela da ficha que estiver por
     cima (`JanelaFicha` fecha no Esc), e quem so' queria parar de marcar pontos perderia
     a ficha que estava lendo. Sem ferramenta, o Esc segue o caminho de sempre. */
  useEffect(() => {
    if (ferramenta === 'nenhuma') return
    const aoTeclar = (e: KeyboardEvent) => {
      if (e.key !== 'Escape') return
      e.stopPropagation()
      /* Com o desenho ligado, Esc CANCELA (apaga os vértices) — é o que o título do botão
         promete. Com as outras, só desliga. */
      if (ferramenta === 'geometria') encerrarDesenho('esc')
      else acaoTrilho({ tipo: 'desligar-ferramenta' })
    }
    window.addEventListener('keydown', aoTeclar, true)
    return () => window.removeEventListener('keydown', aoTeclar, true)
  }, [ferramenta, encerrarDesenho, acaoTrilho])

  /* Legenda das faixas: VISIVEL por padrao, e agora com chave propria no trilho de
     camadas. Ela sempre foi obrigatoria na tela — quem esconde a legenda de um mapa
     colorido tira a unica coisa que traduz a cor. A chave existe para o caso oposto:
     o operador que ja sabe a regua e quer o territorio embaixo dela, tipicamente para
     tirar print. Nao entra no `EstadoMapa`: e' preferencia do momento, nao da analise. */
  const [legendaVisivel, setLegendaVisivel] = useState(true)
  /* CORES DOS HEXÁGONOS (pedido do Vinicius, 2026-10-16): ligadas por padrão. Desligadas, o
     mapa fica só com a grade (contorno discreto, ainda clicável) — para ler pins, pontos e a
     área desenhada sobre o basemap limpo. A legenda sai junto: ela traduz cor, e sem cor
     não explica nada. Mesma política das outras chaves do painel: estado do momento, sem
     persistência, e fora do `EstadoMapa`. A captura do PDF não lê esta chave (ela já
     esvazia a coropleta por conta própria). */
  const [coresHex, setCoresHex] = useState(true)

  /* O TRILHO SAI DE BAIXO DAS JANELAS (pedido do Vinicius, 2026-10-14): a ficha do
     hexágono e a do ponto nascem à esquerda e cobriam o trilho inteiro — Selecionar ponto,
     régua, geometria, camadas e legenda sumiam justamente com a ficha aberta. A regra de
     quanto andar mora em `lib/ocupacao-janelas` (testada); aqui só se mede e aplica.

     A posição NATURAL sai de `offsetLeft`/`offsetTop`, que ignoram o `transform` — medir
     pelo `getBoundingClientRect` do próprio trilho no meio da animação devolveria a
     posição já deslocada (ou meio deslocada) e o trilho correria atrás de si mesmo.
     Callback ref (estado), e não `useRef`: o trilho só monta quando os dados chegam, e o
     efeito precisa rodar de novo nesse momento. */
  const [trilhoEl, setTrilhoEl] = useState<HTMLDivElement | null>(null)
  const janelasNaTela = useSyncExternalStore(assinarJanelas, janelasAbertas)
  const [dxTrilho, setDxTrilho] = useState(0)
  useLayoutEffect(() => {
    if (!trilhoEl) return
    const medir = () => {
      const pai = trilhoEl.offsetParent as HTMLElement | null
      if (!pai) return
      const base = pai.getBoundingClientRect()
      const natural = {
        esquerda: base.left + trilhoEl.offsetLeft,
        topo: base.top + trilhoEl.offsetTop,
        largura: trilhoEl.offsetWidth,
        altura: trilhoEl.offsetHeight,
      }
      setDxTrilho(deslocamentoDoTrilho(natural, janelasNaTela, window.innerWidth))
    }
    medir()
    /* O trilho muda de tamanho sozinho (painel de camadas, legenda, barra do desenho). */
    const obs = new ResizeObserver(medir)
    obs.observe(trilhoEl)
    window.addEventListener('resize', medir)
    return () => {
      obs.disconnect()
      window.removeEventListener('resize', medir)
    }
  }, [trilhoEl, janelasNaTela])

  /* Pins das academias INDEPENDENTES com score (BLK-MA-15). Comeca DESLIGADO pela mesma razao da
     chave de raio: o piloto abre identico ao de hoje. Sao ate ~1,3 mil pontos numa capital, e
     desenha-los sem pedido roubaria a leitura dos hexagonos por baixo. */
  const [verIndependentes, setVerIndependentes] = useState(false)
  const independentes = dados?.independentes ?? null
  const temIndependentes = independentes?.disponivel === true && independentes.itens.length > 0

  /* A chave morre com o recorte que a justificava: sair de um municipio COM camada para um SEM
     deixaria a pilula ligada sem nada para desenhar. */
  useEffect(() => {
    if (!temIndependentes) setVerIndependentes(false)
  }, [temIndependentes])

  /* Bandeiras das academias de REDE (as cadeias). Nasce LIGADA — o piloto abre identico ao de
     hoje — e existe pelo gesto inverso, que faltava: apagar as bandeiras para ler o territorio
     (ou as independentes) por baixo. Esconde bandeira, nao tira concorrente da conta: raio,
     ficha, cenario e a foto do slide seguem lendo `dados.pins`. Preferencia do momento, como
     a legenda: fora do `EstadoMapa`. */
  const [verRedes, setVerRedes] = useState(REDES_LIGADAS_POR_PADRAO)
  const temRedes = (dados?.pins?.concorrentes.length ?? 0) > 0
  const pinsNoMapa = useMemo(() => pinsVisiveis(dados?.pins, verRedes), [dados?.pins, verRedes])

  /* Camada de OPORTUNIDADES IMOBILIARIAS (a oferta da aba, sobre o territorio).
     Comeca DESLIGADA pela mesma razao das outras chaves: o piloto abre identico ao
     de hoje. O dado vem por UF assim que ela e' escolhida — NAO espera a chave —
     porque tambem alimenta a secao "Imoveis disponiveis aqui" da ficha do hexagono,
     que vale com a camada apagada. E' leve perto do raio (payload JSON do top da UF,
     cacheado no servidor), por isso nao repete o padrao sob demanda da cobertura. */
  const [verImoveis, setVerImoveis] = useState(false)
  const [imoveisUf, setImoveisUf] = useState<Oportunidade[] | null>(null)
  /* A janela de DETALHE de um imovel — aberta pelo pin da camada ou pela secao da
     ficha do hexagono. Janela propria (ancora direita), nao um modo da FichaHex:
     o operador compara o imovel COM o hexagono, entao as duas ficam lado a lado. */
  const [imovelAberto, setImovelAberto] = useState<Oportunidade | null>(null)

  /* A VIAGEM da unidade ate' o territorio dela (`abrirUnidade`, abaixo): declarada aqui
     porque os gestos que a cancelam (imovel, hexagono, lista, busca, comparacao) vem antes
     e depois. Regra e motivo em `lib/viagem-unidade`. */
  const [viagem] = useState(() =>
    criarViagemUnidade<{ unidade: UnidadeNoMapa; pin: SearchPin | null }>(),
  )
  // Desmontar o mapa (Viabilidade, Executiva...) com a lista ainda em voo: nada muda depois.
  useEffect(() => () => viagem.cancelar(), [viagem])
  /* Destino de lista ou ponto analisado NOVO (ranking, lupa, aba de ponto): e' outro pedido
     de para onde olhar, e vence a viagem. So' quando aparece -- a propria unidade SOLTA o
     ponto e o destino (`onSoltarPonto`), e isso nao pode cancelar a viagem dela. */
  useEffect(() => {
    if (pontoAtivo || pinFixo) viagem.cancelar()
  }, [pontoAtivo, pinFixo, viagem])

  /* Porta UNICA de abertura por gesto humano: o pin da camada e a secao "Imoveis
     disponiveis aqui" da ficha do hexagono passam os dois por aqui, entao o rastro
     (DEC-027) sai UMA vez por clique, nao um por caminho. O fechamento segue chamando
     `setImovelAberto(null)` direto — so a abertura e' intencao que a trilha precisa ver —
     e o HOVER do pin NAO passa por aqui de proposito: dispara dezenas de vezes num
     arrasto e afogaria a trilha. */
  const abrirImovel = useCallback((o: Oportunidade) => {
    api.eventoImobiliaria('abrir-imovel', {
      imovel: o.id,
      /* UF/municipio do IMOVEL, nao do recorte da tela: a ficha do hexagono lista imovel
         pelo `hex_id` (inclusive sem coordenada), e e' o imovel que identifica o alvo. */
      uf: o.uf,
      municipio: o.municipio,
      origem: 'mapa',
    })
    viagem.cancelar()
    setImovelAberto(o)
  }, [viagem])

  useEffect(() => {
    if (!uf) {
      setImoveisUf(null)
      return
    }
    let vivo = true
    /* Zera ANTES de buscar: sem isto, trocar de UF com a camada ligada deixava os
       pontinhos (e a contagem da pilula) da UF ANTERIOR na tela ate' a resposta nova. */
    setImoveisUf(null)
    api
      .oportunidades(uf, 3000)
      .then((r) => {
        if (vivo) setImoveisUf(r.itens)
      })
      .catch(() => {
        /* Lista VAZIA, nao null: null e' "carregando" e pula o auto-desligamento da
           chave — com null, um fetch falho deixava `verImoveis` ligado invisivel e a
           camada reacendia sozinha na UF seguinte. Vazia, o efeito abaixo desliga.
           Sem a camada o mapa segue como antes — a pilula nem aparece. */
        if (vivo) setImoveisUf([])
      })
    return () => {
      vivo = false
    }
  }, [uf])

  /* O recorte da camada acompanha o drill-down: na visao da UF desenha a UF inteira,
     no municipio so' o municipio (mesma chave de nome que o `onVerNoMapa` da aba ja
     usa para chegar aqui). So' entram no MAPA os imoveis com coordenada; os sem
     coordenada continuam aparecendo na secao da ficha do hexagono (via `hex_id`). */
  const imoveisNoMapa = useMemo(() => {
    const xs = (imoveisUf ?? []).filter((o) => o.lat != null && o.lng != null)
    return municipio ? xs.filter((o) => o.municipio === municipio) : xs
  }, [imoveisUf, municipio])
  const temImoveis = imoveisNoMapa.length > 0

  /* Mesma regra das independentes: a chave morre com o recorte que a justificava. */
  useEffect(() => {
    if (imoveisUf != null && !temImoveis) setVerImoveis(false)
  }, [imoveisUf, temImoveis])

  /*
   * CHEGADA VINDA DA ABA DE IMÓVEIS (2026-09-23) — abre a ficha do IMÓVEL e acende a
   * camada, em vez de subir a ficha do hexágono.
   *
   * Espera `imoveisUf` chegar de propósito: a lista é buscada por UF e começa `null`,
   * então no primeiro render não existe o registro que a `FichaImovel` precisa. Tentar
   * abrir antes daria uma ficha vazia — e o efeito de troca de contexto (uf/município)
   * ainda zeraria `imovelAberto` logo em seguida, apagando a abertura em silêncio.
   *
   * A camada é acesa SÓ aqui, nesta chegada: ela continua nascendo desligada para quem
   * abre o mapa por qualquer outra porta, e quem a desligou de propósito não é
   * surpreendido depois (decisão do Felipe). Sem acendê-la, o pin do imóvel nem seria
   * desenhado e a ficha flutuaria sobre um mapa que não mostra do que ela fala.
   *
   * O `ref` garante UMA execução por intenção mesmo que o efeito seja reexecutado
   * antes de o aviso de consumo voltar do App (é o que o StrictMode faz em dev).
   *
   * Imóvel não encontrado na lista é degradação DECLARADA, não silêncio: cai no
   * comportamento antigo — seleciona o hexágono, que abre a ficha dele. Acontece se o
   * registro sair do recorte servido (a lista vem com teto de 3.000 por UF).
   */
  const imovelInicialFeito = useRef<string | null>(null)
  useEffect(() => {
    if (!imovelInicial || imoveisUf == null) return
    if (imovelInicialFeito.current === imovelInicial) return
    imovelInicialFeito.current = imovelInicial

    const alvo = imoveisUf.find((o) => o.id === imovelInicial)
    if (alvo) {
      setVerImoveis(true)
      abrirImovel(alvo)
    } else if (pin?.hexId) {
      setSelecionado(pin.hexId)
    }
    onImovelAberto?.()
  }, [imovelInicial, imoveisUf, abrirImovel, onImovelAberto, pin])

  /*
   * UNIDADES DA REDE NO MAPA (2026-10-01, pedido do Juan) — o seletor do cabeçalho lista as
   * unidades do ESTADO aberto, e escolher uma (ou clicar no pin dela) leva a câmera até lá e
   * abre a ficha em janela.
   *
   * A carteira é buscada UMA vez, e só para quem pode vê-la (`verUnidades`): é a rede
   * inteira (~230 KB), e o recorte por estado é feito aqui, sem nova ida ao servidor a cada
   * troca de UF. Falha vira lista VAZIA, não `null`: `null` é "carregando", e uma rota que
   * negou não pode deixar o seletor esperando para sempre.
   */
  const [unidadesRede, setUnidadesRede] = useState<RedeUnidade[] | null>(null)
  /* As unidades do CADASTRO que a Growth ainda não tem (em contrato, em pré-venda: Santana),
     pedido do Juan em 14/10. Lista à parte e opcional: falhar aqui não esvazia o seletor. */
  const [unidadesSemRede, setUnidadesSemRede] = useState<RedeUnidadeSemRede[]>([])
  useEffect(() => {
    if (!verUnidades) {
      setUnidadesRede(null)
      setUnidadesSemRede([])
      return
    }
    let vivo = true
    api
      .redeCarteira()
      .then((c) => vivo && setUnidadesRede(c.unidades))
      .catch(() => vivo && setUnidadesRede([]))
    api
      .redeUnidadesSemRede()
      .then((r) => vivo && setUnidadesSemRede(r.unidades))
      .catch(() => vivo && setUnidadesSemRede([]))
    return () => {
      vivo = false
    }
  }, [verUnidades])
  const opcoesUnidades = useMemo(
    () => unidadesDaBusca(unidadesRede ?? [], unidadesSemRede, uf),
    [unidadesRede, unidadesSemRede, uf],
  )

  const [unidadeAberta, setUnidadeAberta] = useState<UnidadeNoMapa | null>(null)
  /* Porta única de abertura: o seletor e o pin do mapa passam os dois por aqui. O pin marca
     a unidade e a câmera voa até ele com o zoom do hexágono (é o `searchPin` do `HexMap`),
     mas o hexágono NÃO é selecionado — senão a ficha dele subiria junto com a da unidade,
     duas janelas falando do mesmo ponto. Unidade sem coordenada abre a ficha e não voa.

     Com um ponto em análise, o pin dele VENCE o pin local (`searchPin`): por isso a unidade
     avisa o `App` (`onSoltarPonto`), que tira do ponto o comando da câmera. Sem o aviso, a
     ficha da unidade abria mas a câmera nunca chegava a ela. */
  /* E O TERRITORIO VEM JUNTO (pedido do Vinicius, 21/10/2026: "ao selecionar uma unidade,
     o municipio da unidade deve ser selecionado junto"). Antes o cabecalho ficava no
     territorio anterior -- a visao do estado, ou OUTRA cidade -- e painel, funil e ranking
     falavam de um lugar que nao era o da unidade aberta. Agora a unidade pede o municipio
     dela (e a UF, se for outra) pelos MESMOS `onUf`/`onMunicipio` do cabecalho: o efeito e'
     o de o operador ter escolhido -- carga do municipio, painel, funil. A camera fica na
     UNIDADE, nao no centro da cidade: o pin vence o centro no `HexMap`, e e' a unidade que
     foi pedida. Qual municipio, e o que acontece sem resolver, e' `lib/territorio-unidade`.

     TRES CUIDADOS:
     - Trocar de territorio FECHA a ficha da unidade (efeito de contexto, abaixo). Aqui a
       troca foi causada pela propria unidade, entao ela viaja em `viagem` e o
       efeito a reabre -- com o pin -- se o contexto novo for exatamente o que ela pediu.
       Nao re-dispara selecao: reabrir so' poe de volta o estado, nao chama `abrirUnidade`.
     - A lista de municipios tem de ser a da UF DA UNIDADE -- a da COORDENADA, quando o
       servidor a resolve (`municipiosUf`); se nao for (UF
       trocada ha' pouco, ou unidade de OUTRA UF -- o pin da divisa), ela e' pedida ao
       servidor. A resposta so' vale se, desde a escolha, o operador nao fez mais nada
       (`lib/viagem-unidade`): fechar a ficha, escolher outra unidade, clicar num hexagono,
       num ponto da comparacao ou num imovel, buscar, comparar, um destino de lista, trocar
       o territorio a mao e SAIR do mapa cancelam a viagem -- senao a resposta atrasada
       mudaria de cidade por baixo do gesto novo, ou o territorio do App com o operador ja'
       em outra tela (revisao de 21/10/2026).
     - Nenhuma troca quando a unidade ja' esta' no territorio aberto (`planoDeTroca`). */
  // `viagem` e' declarada antes de `abrirImovel`, que tambem a cancela.
  const atualRef = useRef({ uf, municipio, municipios, municipiosUf, dados, onUf, onMunicipio })
  atualRef.current = { uf, municipio, municipios, municipiosUf, dados, onUf, onMunicipio }
  /* A COORDENADA PRIMEIRO (defeito de 21/10/2026: a primeira escolha levava a "Todos os
     municipios"). A unidade com pin pergunta ao servidor em que municipio a coordenada cai
     (`/api/municipio-do-ponto`); so' sem resposta util valem cadastro, UF de municipio unico e
     hexagono -- este ultimo so' existe no payload aberto quando ele e' a UF inteira. A ordem e
     o descarte da resposta atrasada sao `lib/territorio-unidade` (`viajarAoTerritorioDaUnidade`). */
  const levarAoTerritorioDaUnidade = useCallback(
    (u: UnidadeComTerritorio, seq: number, unidade: UnidadeNoMapa, pinU: SearchPin | null) => {
      void viajarAoTerritorioDaUnidade({
        viagem,
        seq,
        carga: { unidade, pin: pinU },
        unidade: u,
        coordenada: pinU ? { lat: pinU.lat, lng: pinU.lng } : null,
        atual: () => ({ uf: atualRef.current.uf, municipio: atualRef.current.municipio }),
        fontes: {
          municipioDoPonto: (lat, lng) => api.municipioDoPonto(lat, lng),
          municipiosDaUf: (ufAlvo) => {
            const a = atualRef.current
            if (a.municipiosUf && a.municipiosUf.toUpperCase() === ufAlvo) return Promise.resolve(a.municipios)
            return api
              .municipios(ufAlvo)
              .then((r) => ((r.uf ?? '').toUpperCase() === ufAlvo ? r.municipios : []))
              .catch(() => [])
          },
          /* O municipio do HEXAGONO da unidade, se o payload aberto for da UF dela e o tiver. */
          munDoHexagono: (ufAlvo) => {
            const a = atualRef.current
            return pinU && a.dados && a.dados.uf.toUpperCase() === ufAlvo
              ? (a.dados.hexes.find((h) => h.id === pinU.hexId)?.mun ?? null)
              : null
          },
        },
        chave: chaveContexto,
        trocar: (plano) => {
          const a = atualRef.current
          if (plano.uf !== null) a.onUf(plano.uf)
          if (plano.municipio !== null) a.onMunicipio(plano.municipio)
        },
      })
    },
    [viagem],
  )
  const abrirUnidade = useCallback(
    (u: {
      id: string
      nome: string
      lat: number | null
      lng: number | null
      semRede?: boolean
      uf?: string | null
      cidade?: string | null
    }) => {
      const seq = viagem.iniciar()
      const unidade: UnidadeNoMapa = { id: u.id, nome: u.nome, semRede: u.semRede ?? false }
      setUnidadeAberta(unidade)
      const pinU =
        u.lat == null || u.lng == null
          ? null
          : { lat: u.lat, lng: u.lng, hexId: latLngToCell(u.lat, u.lng, 7) }
      if (pinU) {
        setBusca('')
        setBuscaErro(null)
        onSoltarPonto?.()
        setPin(pinU)
      }
      levarAoTerritorioDaUnidade(u, seq, unidade, pinU)
    },
    [onSoltarPonto, levarAoTerritorioDaUnidade, viagem],
  )
  /* Fechar a ficha cancela a viagem pendente: a lista de municipios que chegar depois nao
     pode trocar o territorio (nem reabrir a ficha) de uma unidade que o operador fechou. */
  const fecharUnidade = useCallback(() => {
    viagem.cancelar()
    setUnidadeAberta(null)
  }, [viagem])
  /* Clicar num ponto da comparacao e' pedir para olhar para ele: vence a viagem. */
  const aoClicarPontoComparado = useCallback(
    (i: number) => {
      viagem.cancelar()
      onPontoComparado?.(i)
    },
    [viagem, onPontoComparado],
  )

  /* "Estudar a região desta unidade": fecha a ficha da unidade (a de ponto abre no lugar,
     à esquerda — duas janelas sobre o mesmo lugar seriam duas leituras dele) e pede o
     ponto no estudo da unidade. `undefined` sem o pedido do `App`: o botão não aparece. */
  const estudarRegiaoDaUnidade = useMemo(
    () =>
      onEstudarUnidade
        ? (lat: number, lng: number) => {
            fecharUnidade()
            onEstudarUnidade(lat, lng)
          }
        : undefined,
    [onEstudarUnidade, fecharUnidade],
  )

  /* Geometria do raio: buscada SOB DEMANDA, so' quando a CAMADA 3 esta aberta. Fora do
     payload do mapa de proposito — custa ~2,4 s e ~3,9 MB na UF de SP, e quem so' passa
     pelas camadas 1, 2, 4 e 5 nao deve pagar isso. Trocar de UF/municipio zera a
     geometria (ela e' daquele recorte) e dispara nova busca se a camada 3 seguir aberta.

     Com o raio virando padrao a busca deixou de depender de um clique: entrar na camada 3
     ja' a dispara. Por isso `carregandoRaio` continua existindo e agora aparece na barra
     de ferramentas — antes quem esperava tinha ligado a chave e sabia por que esperava;
     hoje o custo chega sem pedido, e uma tela que demora calada e' o defeito, nao a
     demora. */
  const [cobertura, setCobertura] = useState<Cobertura1k | null>(null)
  const [carregandoRaio, setCarregandoRaio] = useState(false)

  useEffect(() => {
    if (!raio1km || !uf) {
      setCobertura(null)
      return
    }
    let vivo = true
    setCarregandoRaio(true)
    api
      .cobertura(uf, municipio || undefined)
      .then((c) => {
        if (vivo) setCobertura(c)
      })
      .catch(() => {
        // Sem geometria o mapa apenas nao desenha a cobertura — nao derruba a tela.
        if (vivo) setCobertura(null)
      })
      .finally(() => {
        if (vivo) setCarregandoRaio(false)
      })
    return () => {
      vivo = false
    }
  }, [raio1km, uf, municipio])

  /* Bloco D — mapa de calor de SETOR censitario (densidade/renda), SOB DEMANDA e so' no
     drill-down de municipio (mesmo motivo do raio: Sao Paulo capital sozinha chega a
     ~9 MB). As duas chaves sao MUTUAMENTE EXCLUSIVAS — sao duas leituras da MESMA malha
     de poligonos, e mostrar as duas ao mesmo tempo so' decidiria por sorte qual cor
     desenha por cima. Comeca desligado, como toda camada opcional do mapa. */
  const [verCalorDensidade, setVerCalorDensidade] = useState(false)
  const [verCalorRenda, setVerCalorRenda] = useState(false)
  const [heatmap, setHeatmap] = useState<SetoresHeatmapPayload | null>(null)
  const [carregandoCalor, setCarregandoCalor] = useState(false)
  const calorLigado = verCalorDensidade || verCalorRenda
  const modoCalor: ModoCalor | null = verCalorDensidade ? 'densidade' : verCalorRenda ? 'renda' : null
  /* Calor e cores dos hexágonos são exclusivos nos dois sentidos: ligar um desliga o
     outro. A regra mora em `lib/camadas-calor`. */
  const aplicarChaves = useCallback((prox: { calor: ModoCalor | null; coresHex: boolean }) => {
    setVerCalorDensidade(prox.calor === 'densidade')
    setVerCalorRenda(prox.calor === 'renda')
    setCoresHex(prox.coresHex)
  }, [])
  const clicarCalor = useCallback(
    (modo: ModoCalor) => aplicarChaves(alternarCalor({ calor: modoCalor, coresHex }, modo)),
    [aplicarChaves, modoCalor, coresHex],
  )
  const clicarCoresHex = useCallback(
    () => aplicarChaves(alternarCoresHex({ calor: modoCalor, coresHex })),
    [aplicarChaves, modoCalor, coresHex],
  )
  /* A legenda do calor só aparece quando ele está DESENHADO: carregando ou sem malha
     para o município, ela explicaria uma cor que não está no mapa. */
  const calorDesenhado =
    modoCalor !== null && !carregandoCalor && !!heatmap?.disponivel && (heatmap?.setores.length ?? 0) > 0

  useEffect(() => {
    // `dados?.nivel === 'uf'` direto (nao a const `nivelUf`, declarada mais abaixo neste
    // componente) -- so' para nao introduzir uma dependencia de ordem de declaracao.
    if (!calorLigado || !uf || !municipio || dados?.nivel === 'uf') {
      setHeatmap(null)
      return
    }
    let vivo = true
    setCarregandoCalor(true)
    api
      .setoresHeatmap(uf, municipio)
      .then((h) => {
        if (vivo) setHeatmap(h)
      })
      .catch(() => {
        // Sem poligono o mapa so' nao desenha o calor — nao derruba a tela.
        if (vivo) setHeatmap(null)
      })
      .finally(() => {
        if (vivo) setCarregandoCalor(false)
      })
    return () => {
      vivo = false
    }
  }, [calorLigado, uf, municipio, dados?.nivel])

  /* A chave morre com o recorte que a justificava — trocar de municipio com o calor
     ligado nao pode deixar a tela mostrando o poligono da cidade ANTERIOR. */
  useEffect(() => {
    setVerCalorDensidade(false)
    setVerCalorRenda(false)
  }, [uf, municipio])

  // Camera do deck.gl em REF, nao em state, de proposito: o `onViewStateChange` do
  // deck dispara a cada quadro de um voo (centenas de vezes em 800 ms). Em state, cada
  // quadro re-renderizaria esta tela E o App inteiro (StepperBar, NarrativePanel,
  // MethodologyPanel...). Em ref, gravar e' de graca e a camera segue sempre atual.
  const cameraRef = useRef<ViewState | null>(foto.camera)

  // Estavel de proposito (`[]`): o HexMap tem `onCamera` nas dependencias do efeito que
  // publica a camera. Um callback inline mudaria de identidade a cada render e faria
  // aquele efeito disparar em todo render, nao so' quando a camera muda.
  const publicarCamera = useCallback((v: ViewState) => {
    /* Copia so' os campos de CAMERA. O `onViewStateChange` do deck.gl emite a cada
       quadro DURANTE o voo, carregando `transitionDuration` e a instancia de
       `FlyToInterpolator` junto. Guardando o objeto cru: (a) clicar em "Estudo pontual"
       dentro dos 800 ms congelava um quadro do meio do caminho — e, na volta, o guard do
       pin suprime o voo corretivo, entao o enquadramento intermediario virava
       permanente; (b) a foto deixava de ser serializavel. */
    cameraRef.current = {
      longitude: v.longitude,
      latitude: v.latitude,
      zoom: v.zoom,
      pitch: v.pitch,
      bearing: v.bearing,
    }
  }, [])

  // Trocar de UF/município recomeça a história do passo 1 e limpa a busca/cenário.
  // O guarda por ref e' ESSENCIAL: sem ele o efeito rodaria tambem na MONTAGEM da tela
  // e apagaria na hora o estado que acabou de ser restaurado — o mapa continuaria
  // "resetando" na volta, so' que por outro caminho.
  const contextoAnterior = useRef(chaveContexto(uf, municipio))
  useEffect(() => {
    const contexto = chaveContexto(uf, municipio)
    if (contextoAnterior.current === contexto) return
    contextoAnterior.current = contexto
    setPassoN(1)
    setSelecionado(null)
    setPin(null)
    setBuscaErro(null)
    setBuscando(false)
    setFiltroFaixa('')
    setModoCenario(false)
    setCenario([])
    setImovelAberto(null)
    /* A ficha da unidade fala de um ponto do território anterior, como a do imóvel — SALVO
       quando foi a própria unidade que trouxe o mapa até aqui (`viagem`, ver
       `abrirUnidade`): aí ela continua aberta, com o pin. Qualquer outra troca cancela uma
       viagem ainda pendente (`viagem.chegar`). */
    const transito = viagem.chegar(contexto)
    if (transito) {
      setUnidadeAberta(transito.unidade)
      setPin(transito.pin)
    } else {
      setUnidadeAberta(null)
    }
    cameraRef.current = null
  }, [uf, municipio])

  /**
   * O pin vindo de fora TAMBEM seleciona o hexagono dele.
   *
   * Sem isto o endereco colado no modo de ponto so' ganhava a marca e o voo da camera: o
   * hexagono em que ele cai ficava sem o contorno de selecao, e o painel lateral seguia
   * mostrando o item errado (ou nenhum). Selecionar e' o que amarra as tres leituras — o
   * ponto no mapa, o hexagono em volta dele e a linha correspondente no ranking.
   *
   * DEPOIS do efeito que zera a tela ao trocar de UF/municipio, e nao antes: colar um
   * endereco muda as duas coisas na mesma passagem, e aquele efeito poe `selecionado` em
   * `null`. A ordem de declaracao e' a ordem de execucao — invertida, a limpeza apagaria
   * a selecao que este acabou de fazer.
   */
  useEffect(() => {
    if (!pinFixo) return
    setSelecionado(pinFixo.hexId)
    // Destino de LISTA: a ficha do hexagono abre (e' o que o operador pediu na lista).
    setSelecaoDaBusca(false)
  }, [pinFixo])

  /* O PONTO ATIVO tambem seleciona o hexagono dele — mas marcando que a selecao veio da
     BUSCA, e por isso a ficha do hexagono NAO abre (`lib/janela-hex`): a pergunta e' sobre
     o ponto, e a resposta e' a ficha de ponto. Clicar depois no proprio hexagono desliga
     a marca e abre a ficha dele, nas duas entradas do mapa.

     Mesma regra de ordem do efeito acima: depois do que zera a tela ao trocar de
     territorio. E depois do `pinFixo` tambem, para o ponto vencer o destino quando os dois
     chegam juntos (a mesma precedencia do `searchPin`). */
  /* Na REMONTAGEM (volta da Viabilidade) o mesmo pin ja' existia: se a foto devolveu a
     selecao de OUTRO hexagono — o que o operador clicou depois do ponto e levou ao
     Simulador —, ela fica, e a ficha dele volta aberta (`pontoSeleciona`). Identidade e
     nao flag one-shot, pelo mesmo motivo do voo no `HexMap` (StrictMode roda o efeito duas
     vezes na montagem). */
  const pontoDaMontagem = useRef(pontoAtivo)
  useEffect(() => {
    if (!pontoAtivo) return
    if (
      !pontoSeleciona({
        pinDaMontagem: pontoAtivo === pontoDaMontagem.current,
        selecaoRestaurada: foto.selecionado,
        hexDoPonto: pontoAtivo.hexId,
      })
    ) {
      return
    }
    setSelecionado(pontoAtivo.hexId)
    setSelecaoDaBusca(true)
  }, [pontoAtivo, foto.selecionado])


  // Espelho SEMPRE atual do estado, mantido num ref. Existe para o cleanup do efeito
  // abaixo poder ler valores frescos: um cleanup enxerga o closure do render em que foi
  // criado, entao ler as variaveis de estado direto ali guardaria uma foto velha.
  // SEM `camera`: ela nao vive aqui de proposito (ver o efeito de publicacao abaixo).
  // O tipo declara isso, para nao voltar por engano e reintroduzir a foto velha.
  const estadoRef = useRef<Omit<EstadoMapa, 'camera'>>(foto)
  useEffect(() => {
    estadoRef.current = {
      // O contexto viaja COM a foto: e' o que permite descarta-la depois se o operador
      // trocar de UF/municipio antes de voltar ao mapa.
      uf,
      municipio,
      passoN,
      selecionado,
      pin,
      busca,
      filtroFaixa,
      modoCenario,
      cenario,
    }
  })

  /* Publica a foto no App UMA vez, ao desmontar — que e' exatamente quando ela passa a
     importar (o operador saiu para a Viabilidade). Publicar a cada mudanca faria o App
     re-renderizar a arvore inteira a cada clique no mapa, sem ganho nenhum.
     `onEstado` e' o `setEstadoMapa` do `useState` do App, cuja identidade o React
     garante estavel — o efeito nao remonta e nao publica antes da hora.

     A CAMERA E' LIDA AQUI, do ref, e nao do `estadoRef`. Motivo: `estadoRef` so' e
     atualizado quando o MapScreen RE-RENDERIZA, e a camera muda sem render — o voo ate
     o pin acontece dentro do HexMap (setView local) DEPOIS do ultimo render do
     MapScreen. Guardando a camera no espelho, o que se publicava era o enquadramento
     de ANTES do voo: o operador buscava o endereco, ia ao estudo pontual e voltava para
     o municipio inteiro em zoom 9.6 — e, como a camera restaurada nao e' nula, o voo de
     aproximacao ficava suprimido e o enquadramento nunca voltava. Quebrava justamente o
     caso de uso que motivou este PR. Mesmo caminho ao dar zoom num hex antes de
     "Analisar". */
  useEffect(() => {
    return () => onEstado({ ...estadoRef.current, camera: cameraRef.current })
  }, [onEstado])

  const passo = dados?.passos.find((p) => p.n === passoN) ?? dados?.passos[0] ?? null
  const nivelUf = dados?.nivel === 'uf'

  const porId = useMemo(
    () => new Map((dados?.hexes ?? []).map((h) => [h.id, h])),
    [dados],
  )

  /* O hexágono da janela da ficha. Sai do `porId` e não de uma cópia do payload: o mesmo
     objeto que o mapa desenha é o que a janela lê, então não há como as duas leituras
     divergirem depois de uma troca de município. */
  const hexSelecionado = selecionado ? (porId.get(selecionado) ?? null) : null
  const cresMunDoHex = hexSelecionado?.mun ? (dados?.cres_mun?.[hexSelecionado.mun] ?? null) : null
  /* Camadas de leitura do pacote argentino, pela MESMA chave (`Hex.mun`) e com o mesmo
     `?? null`: no Brasil `ctx_mun` vem `{}`, o hexágono não acha entrada e a ficha não
     desenha a seção. É a ausência que decide, não uma bandeira de país. */
  const ctxMunDoHex = hexSelecionado?.mun ? (dados?.ctx_mun?.[hexSelecionado.mun] ?? null) : null

  /* Os imoveis DESTE hexagono, para a secao da ficha. Casa por `hex_id` (H3 res-7,
     a MESMA malha do M1) sobre o conjunto da UF inteira — independe da chave da
     camada e do drill-down: o hexagono aberto ja' e' um recorte. */
  const imoveisDoHex = useMemo(
    () =>
      hexSelecionado && imoveisUf
        ? imoveisUf.filter((o) => o.hex_id === hexSelecionado.id)
        : [],
    [imoveisUf, hexSelecionado],
  )

  // Municípios do dropdown: "Todos" (volta à UF) + lista alfabética.
  const opcoesMunicipio = useMemo(
    () => [
      { value: '', label: 'Todos os municípios' },
      ...[...municipios]
        .sort((a, b) => a.nome.localeCompare(b.nome, 'pt-BR'))
        .map((m) => ({ value: m.nome, label: m.nome })),
    ],
    [municipios],
  )

  /* O Top 10 da recomendação única (DEC-077), indexado por hexágono para o mapa. `null`
     sem o bloco no payload (AR): a camada 5 segue a legada, pela faixa M1. */
  const top10 = useMemo(
    () => (dados?.recomendacao ? mapaTop10(dados.recomendacao) : null),
    [dados],
  )

  // Filtro global de "melhores hexes" por faixa M1 (aplicado ao mapa).
  /* As 10 regiões do Top 10 voltam para o mapa mesmo que o filtro as tire
     (`hexesComTop10`): um Premium de faixa "Média" sumiria do território enquanto o painel
     o lista. Sem Top 10 o resultado é exatamente o filtro de sempre. */
  const hexesFiltrados = useMemo(() => {
    const hs = dados?.hexes ?? []
    const permitidas = FAIXA_FILTROS[filtroFaixa]
    const filtradosPelaFaixa = permitidas
      ? hs.filter((h) => h.faixa != null && permitidas.has(h.faixa))
      : hs
    return hexesComTop10(filtradosPelaFaixa, hs, top10?.ids ?? [])
  }, [dados, filtroFaixa, top10])

  /**
   * Os hexes a COMPARAR: de 2 a 5 selecionados.
   *
   * Somar e comparar respondem perguntas diferentes ("quanto vale este pedaço junto"
   * x "qual destes é melhor"), e o número de hexes escolhidos já diz qual delas o
   * operador está fazendo — 2 a 5 é comparação, 1 ou 6+ é soma. Por isso o painel
   * troca sozinho, sem mais um botão para ele decidir.
   */
  const hexesComparacao = useMemo(() => {
    if (cenario.length < 2 || cenario.length > MAX_COMPARADOS) return null
    const hs = cenario.map((id) => porId.get(id)).filter(Boolean) as Hex[]
    return hs.length === cenario.length ? hs : null
  }, [cenario, porId])

  // Agregação do cenário multi-hex (soma no cliente a partir dos hexes servidos).
  const resumoCenario = useMemo(() => {
    const hs = cenario.map((id) => porId.get(id)).filter(Boolean) as Hex[]
    if (!hs.length) return null
    const soma = (f: (h: Hex) => number | null) => hs.reduce((a, h) => a + (f(h) ?? 0), 0)
    const scores = hs.map((h) => h.censo).filter((v): v is number => v != null)
    return {
      n: hs.length,
      residual: soma((h) => h.oferta),
      pop: soma((h) => h.pop),
      conc: soma((h) => h.conc),
      scoreMedio: scores.length ? scores.reduce((a, b) => a + b, 0) / scores.length : null,
    }
  }, [cenario, porId])

  function copiarCenario() {
    navigator.clipboard?.writeText(cenario.join('\n')).then(() => {
      setCopiado(true)
      setTimeout(() => setCopiado(false), 1500)
    })
  }

  /**
   * Clique num item da LISTA: seleciona e LEVA A CAMERA ate' o hexagono.
   *
   * Antes so' desenhava o contorno branco. Num municipio grande o item escolhido podia
   * estar fora do enquadramento, entao a tela respondia ao clique num lugar que o
   * operador nao estava vendo — parecia que nada acontecia (Juan, 2026-08-12). O contorno
   * CONTINUA: chegar sem marca nenhuma deixaria a duvida de qual dos hexagonos e' o item.
   *
   * O clique no proprio mapa segue por `setSelecionado` direto, sem voo: la' o hexagono
   * ja' esta' sob o cursor, e recentrar seria mexer no que o operador acabou de mirar.
   */
  const [voo, setVoo] = useState<{ hexId: string; n: number } | null>(null)
  const selecionarDaLista = useCallback((hexId: string) => {
    viagem.cancelar()
    setSelecionado(hexId)
    setSelecaoDaBusca(false)
    setPin(null)
    setVoo((v) => ({ hexId, n: (v?.n ?? 0) + 1 }))
  }, [viagem])

  /* ---- Deck de comparacao (PDF) --------------------------------------------
     O MapScreen orquestra porque so' ele tem as duas pontas: o mapa (que captura) e a
     lista comparada (que vira o ranking). O painel so' pede.

     A ORDEM importa: primeiro as capturas, depois o POST. O ranking e' calculado AQUI, no
     mesmo `ranquear` que a tela usa, e viaja pronto — o servidor so' desenha, para nao
     existir uma segunda regra de "quem vence" que possa divergir da tela. */
  const [pedidoCaptura, setPedidoCaptura] = useState<{
    alvos: AlvoDaCaptura[]
    n: number
  } | null>(null)
  const [gerandoDeck, setGerandoDeck] = useState(false)

  /* A captura vira uma PROMESSA, e nao um par pedido/callback espalhado pela tela. Duas
     razoes: o fluxo do deck fica linear (`await capturar(...)` e segue), e o modo de PONTO
     — que e' irmao deste componente na arvore e usa o MESMO mapa — precisa pedir capturas
     tambem. Publicar a funcao por `registrarCaptura` e' o mesmo caminho que o `pinFixo` do
     App ja' usa: quem consome o mapa e' o mapa, entao o canal mora aqui e o App so' o
     reparte. */
  const resolveCaptura = useRef<((imagens: string[]) => void) | null>(null)

  /* Pins ja' buscados, por contexto. A captura de um deck de 5 pontos pode repetir
     cidade, e o payload do municipio nao e' barato — buscar duas vezes a mesma coisa no
     meio da geracao atrasaria o voo e nao mudaria a foto. */
  const pinsPorContexto = useRef(new Map<string, Pins | null>())

  const capturar = useCallback(
    async (alvos: AlvoCaptura[]) => {
      /* CAMADAS ANTES DO VOO. O mapa carrega um municipio por vez, entao um alvo de
         outra cidade seria fotografado com os pins da cidade aberta — o rodape do slide
         promete "concorrentes mapeados e unidades Ultra" do entorno DAQUELE ponto.
         Falha na busca vira `null` de proposito: camada nenhuma e' honesta, camada de
         outra cidade e' mentira com cara de dado. */
      const atual = chaveContexto(dados?.uf ?? '', dados?.municipio ?? '')
      const comCamadas: AlvoDaCaptura[] = []
      for (const alvo of alvos) {
        const chave =
          alvo.uf && alvo.municipio ? chaveContexto(alvo.uf, alvo.municipio) : atual
        const mesmaCidade = chave === atual
        let buscados: Pins | null = null
        if (!mesmaCidade && alvo.uf && alvo.municipio) {
          if (!pinsPorContexto.current.has(chave)) {
            try {
              const payload = await api.municipio(alvo.uf, alvo.municipio)
              pinsPorContexto.current.set(chave, payload.pins ?? null)
            } catch {
              // Falha fica MEMOIZADA: cinco pontos da mesma cidade nao repetem a espera.
              pinsPorContexto.current.set(chave, null)
            }
          }
          buscados = pinsPorContexto.current.get(chave) ?? null
        }
        /* Quem decide e' `pinsDoAlvo`: busca que falhou vira camada VAZIA, nunca a da
           cidade aberta — o consumidor faz `pinsDaCaptura ?? pins`, e um `null` aqui
           reintroduziria os concorrentes da cidade errada sob o nome certo. */
        comCamadas.push({ ...alvo, pins: pinsDoAlvo(buscados, mesmaCidade) })
      }
      return new Promise<string[]>((resolve) => {
        resolveCaptura.current = resolve
        setPedidoCaptura((p) => ({ alvos: comCamadas, n: (p?.n ?? 0) + 1 }))
      })
    },
    [dados?.uf, dados?.municipio],
  )

  const aoCapturarMapas = useCallback((imagens: string[]) => {
    const resolver = resolveCaptura.current
    resolveCaptura.current = null
    resolver?.(imagens)
  }, [])

  useEffect(() => {
    registrarCaptura?.(capturar)
  }, [registrarCaptura, capturar])

  /* Os MESMOS rótulos do painel, e desambiguados: cinco hexágonos da mesma cidade davam
     cinco itens "São Paulo" no PDF, indistinguíveis entre si. A regra vive no `lib/` —
     duas cópias divergiriam no primeiro ajuste, e uma delas é o que vai para o PDF. */
  const rotulosComparacao = useCallback((hs: Hex[]) => rotulosDosHexes(hs), [])

  const pedirDeck = useCallback(
    async () => {
      const hs = hexesComparacao
      if (!hs?.length || gerandoDeck) return
      setGerandoDeck(true)
      try {
        // Mesmo molde do deck de pontos: cidade do proprio hexagono e pin no centro dele.
        const alvos = hs.map((h) => alvoDoHex(h, dados?.uf ?? null))
        const imagens = await capturar(alvos)
        const rotulos = rotulosComparacao(hs)
        const ranking = ranquear(DIMENSOES, hs, rotulos)
        /* O subtítulo nomeia a cidade só quando TODAS são da mesma. Na visão de UF o mapa
           serve 15.000 hexágonos de 163 municípios (medido em SP), então o cenário pode
           misturar cidades — e usar o município do primeiro fazia a capa afirmar
           "São Paulo" para um conjunto que tinha só um hexágono de lá. */
        const cidades = [...new Set(hs.map((h) => h.mun).filter(Boolean))] as string[]
        const cidade =
          cidades.length === 1
            ? `${cidades[0]} - `
            : cidades.length > 1
              ? `${cidades.length} municípios - `
              : ''
        /* Este POST não passa por `lib/api.ts` — o deck monta o próprio download —, então
           o aviso de sessão precisa ser ligado aqui na mão. Sem isto, com a sessão vencida
           o Authelia responde 302, o `fetch` morre por CORS como `TypeError` e o deck falha
           MUDO, sem pop-up nenhum. O conserto de raiz é a chamada migrar para
           `pedirArquivo`, que já faz isto; fica para um PR próprio, para não alargar este. */
        const resposta = await fetch('/api/relatorio/comparacao', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            ...ranking,
            titulo: 'Comparação de hexágonos',
            subtitulo: `${cidade}${hs.length} áreas`,
            imagens,
            // Na ordem de COLAGEM, como `imagens`: o PDF imprime o centro sob cada foto
            // para o operador voltar ao hexagono escolhido colando-o na busca.
            coordenadas: alvos.map((a) => ({ lat: a.lat, lng: a.lng })),
          }),
        }).catch((erro: unknown) => {
          // Falha de REDE: quem separa sessão vencida de servidor fora do ar é a sonda de
          // `lib/sessao`. O erro segue subindo para o `catch` de baixo, intacto.
          void relatarFalhaDeRede()
          throw erro
        })
        // 401 = o Authelia negou; o status já é prova, dispensa sonda.
        if (resposta.status === 401) relatarAcessoNegado()
        if (!resposta.ok) throw new Error(`HTTP ${resposta.status}`)
        const blob = await resposta.blob()
        // Baixa pelo link temporario e REVOGA a URL: sem o revoke o blob fica retido pela
        // aba enquanto ela viver, e um deck tem alguns MB de imagem dentro.
        const url = URL.createObjectURL(blob)
        const a = document.createElement('a')
        a.href = url
        a.download = 'comparacao-hexagonos.pdf'
        a.click()
        URL.revokeObjectURL(url)
      } catch (erro) {
        console.error('[deck] falhou ao gerar o PDF da comparação', erro)
      } finally {
        setGerandoDeck(false)
      }
    },
    [hexesComparacao, rotulosComparacao, capturar, gerandoDeck, dados?.uf],
  )

  /**
   * Poe ou tira um hexagono da comparacao, direto da lista.
   *
   * LIGA o modo cenario junto: sem isso o painel de comparacao — que so' aparece com
   * `modoCenario` — ficaria escondido, e o operador veria o item marcado sem nenhum
   * resultado na tela. O teto de `MAX_COMPARADOS` e' respeitado aqui tambem, e nao so'
   * no clique do mapa.
   */
  const comparar = useCallback((hexId: string) => {
    viagem.cancelar()
    setModoCenario(true)
    setCenario((cs) => {
      if (cs.includes(hexId)) return cs.filter((x) => x !== hexId)
      if (cs.length >= MAX_COMPARADOS) return cs
      return [...cs, hexId]
    })
  }, [viagem])

  /* A busca resolveu: vira ponto analisado, e so'. O pin (provisorio e depois o da ficha)
     e a selecao do hexagono voltam pelo `pontoAtivo` — uma regra so' de pin, em vez de um
     pin local que convivia com o da ficha e trazia o cartao "Estudo pontual" junto. Quem
     leva o ponto a' Viabilidade agora e' o "Simulador" da ficha de ponto. */
  function aplicarPonto(lat: number, lng: number, doMapa = false) {
    viagem.cancelar()
    setBuscaErro(null)
    onPontoBuscado(lat, lng, doMapa)
  }

  async function buscarCoordenada() {
    const termo = busca.trim()
    if (!termo || buscando) return
    // 1) coordenada / link do Maps (offline, instantâneo)
    const c = parseCoordinate(termo)
    if (c) {
      aplicarPonto(c.lat, c.lng)
      return
    }
    // 2) endereço livre -> geocoding (Nominatim, DEC-010)
    setBuscando(true)
    setBuscaErro(null)
    try {
      const r = await api.geocode(termo)
      if (r.found && r.lat != null && r.lng != null) {
        aplicarPonto(r.lat, r.lng)
      } else {
        setBuscaErro(
          'Não encontrei esse endereço. Tente "lat, lng", um link do Google Maps ou um endereço mais completo.',
        )
        setPin(null)
      }
    } catch {
      setBuscaErro('Busca de endereço indisponível agora. Use "lat, lng" ou um link do Google Maps.')
    } finally {
      setBuscando(false)
    }
  }

  async function gerarRelatorioMunicipal() {
    if (!dados || dados.nivel !== 'municipio' || !dados.municipio) return
    setGerando(true)
    setAviso(null)
    try {
      const { blob, filename } = await api.relatorioMunicipal(dados.uf, dados.municipio)
      baixar(blob, filename)
    } catch (e) {
      setAviso(e instanceof ApiError ? e.message : 'Não foi possível gerar o relatório.')
    } finally {
      setGerando(false)
    }
  }

  function analisar(hexId: string) {
    const h = porId.get(hexId)
    if (!h || !dados) return
    const item = dados.passos.flatMap((p) => p.itens).find((i) => i.hex_id === hexId)
    onAnalisarPonto({
      hex: h,
      rotulo: item?.titulo ?? dados.municipio ?? dados.uf,
      municipio: dados.municipio ?? '',
      uf: dados.uf,
    })
  }

  /* Liga/desliga do cenario multi-hex. Extraido porque agora tem DOIS chamadores — a
     linha do painel e o icone do trilho — e duplicar o corpo deixaria os dois divergirem
     no primeiro ajuste (sair do modo tem de limpar a selecao E o cenario). */
  const alternarCenario = useCallback(() => {
    /* O `setCenario` fica FORA do updater de proposito: updater de estado tem de ser puro,
       e em StrictMode ele roda duas vezes. Ler `modoCenario` do fecho custa a dependencia
       abaixo e paga com um corpo que faz o que parece fazer. */
    if (modoCenario) setCenario([])
    setModoCenario((m) => !m)
    setSelecionado(null)
  }, [modoCenario])

  /* AS CHAVES DO PAINEL, na ordem fixa do desenho.

     Regua e comparacao sao FERRAMENTAS (mudam o que o clique no mapa faz); independentes
     e imoveis sao CAMADAS DE DADO (desenham pontos por cima). Convivem no mesmo painel
     porque, do ponto de vista de quem opera, as quatro respondem a mesma pergunta — "o
     que este mapa esta me mostrando agora?" — e tê-las em dois lugares foi justamente o
     que a pilha de pilulas fazia de errado.

     As condicionais somem em vez de aparecerem desabilitadas: chave apagada que nao pode
     acender mente sobre a disponibilidade do dado. Quem some do painel some com o dado,
     nao com a permissao. */
  const chavesDoMapa = useMemo<ChaveDeCamada[]>(() => {
    const lista: ChaveDeCamada[] = [
      /* ANTES da regua, como no trilho (ordem do dono): o painel e o trilho falam a mesma
         lista na mesma ordem. */
      {
        id: 'selecionar-ponto',
        icone: 'alvo',
        titulo: 'Selecionar ponto',
        sub: ferramenta === 'ponto' ? 'clique no mapa para analisar' : 'clique para ativar',
        ligado: ferramenta === 'ponto',
        onToggle: alternarPonto,
        cor: 'var(--ac-text)',
        corTexto: 'var(--ac-chip)',
        corRealce: 'var(--ac-a16)',
      },
      {
        id: 'medir',
        icone: 'regua',
        titulo: 'Medir distância',
        sub: ferramenta === 'regua' ? 'clique 2 pontos no mapa' : 'clique para ativar',
        ligado: ferramenta === 'regua',
        onToggle: alternarRegua,
        cor: 'var(--ac-text)',
        corTexto: 'var(--ac-chip)',
        corRealce: 'var(--ac-a16)',
      },
    ]
    /* "Analisar geometria" DEPOIS da régua, como no trilho (ordem do dono). Só quando há
       quem receba a área — a mesma condição do botão do trilho. */
    if (onGeometriaDesenhada) {
      lista.push({
        id: 'analisar-geometria',
        icone: 'poligono',
        titulo: 'Analisar geometria',
        sub:
          ferramenta === 'geometria'
            ? 'clique os vértices da área'
            : desenhoPausado(ferramenta, vertices.length)
              ? `desenho pausado · ${vertices.length} ${vertices.length === 1 ? 'vértice' : 'vértices'} · clique para retomar`
              : 'clique para ativar',
        ligado: ferramenta === 'geometria',
        onToggle: alternarGeometria,
        cor: 'var(--ac-text)',
        corTexto: 'var(--ac-chip)',
        corRealce: 'var(--ac-a16)',
      })
    }

    /* So' no drill-down: na visao de UF a lista e' de cidades, e comparar cidades tem
       tela propria. */
    if (!nivelUf) {
      lista.push({
        id: 'comparar',
        icone: 'comparar',
        titulo: 'Comparar hexes',
        sub: modoCenario
          ? `${cenario.length} de ${MAX_COMPARADOS} selecionados`
          : 'some vários num cenário',
        ligado: modoCenario,
        onToggle: alternarCenario,
        cor: 'var(--ac-text)',
        corTexto: 'var(--ac-chip)',
        corRealce: 'var(--ac-a16)',
      })
    }

    /* Academias de REDE — as bandeiras das cadeias. Vem ANTES das independentes porque e' a
       camada instalada (na sobreposicao do mapa a rede vence), e some com o dado como as
       demais. Cor neutra de proposito: sao 107 marcas, nenhuma cor as representa. */
    if (temRedes) {
      const n = dados?.pins?.concorrentes.length ?? 0
      lista.push({
        id: 'redes',
        icone: 'halter',
        titulo: 'Academias de rede',
        sub: subDaChaveRedes(n, verRedes),
        ligado: verRedes,
        onToggle: () => setVerRedes((v) => !v),
        cor: 'var(--ac-text)',
        corTexto: 'var(--ac-chip)',
        corRealce: 'var(--ac-a16)',
      })
    }

    /* Academias INDEPENDENTES com score (BLK-MA-15). Vale em QUALQUER camada: a pergunta
       "quem ja opera aqui e esta espremido?" e' a INVERSAO do funil (comprar, nao abrir).
       O titulo diz de QUEM e' o pin — o mapa ja tem bandeiras de CADEIA, e os dois
       universos sao opostos. O TETO e' declarado quando morde: corte silencioso num
       municipio grande mentiria sobre a densidade. */
    if (temIndependentes) {
      const n = independentes?.itens.length ?? 0
      const total = independentes?.total ?? 0
      lista.push({
        id: 'indep',
        /* O símbolo do WELLHUB, em silhueta monocromática (Felipe, 2026-09-23). É a
           marca do app de onde estas academias vêm — hoje 19.930 de 19.930, medido no
           artefato servido.

           Entra como MÁSCARA e não como `<img>`: assim é pintado com a cor da linha
           (branco apagado, acento aceso) e acompanha o tema claro, em vez de ficar
           rosa ao lado de ícones monocromáticos. A arte veio do PNG oficial, recortada
           na silhueta — o `logo-wellhub.png` que o mapa usa no pin continua colorido e
           intocado, porque lá a cor DISTINGUE os dois apps (DEC-066).

           RESSALVA: a DEC-066 já colocou o TotalPass neste entregável e a regeneração
           das duas fontes ainda não subiu para a VPS. No dia em que subir, esta chave
           passará a exibir a marca do Wellhub sobre uma lista que também tem TotalPass
           — o mesmo tipo de imprecisão que aquela DEC corrigiu no pin. Não é defeito
           hoje; é dívida com data marcada. */
        mascara: '/logo-wellhub-mono.png',
        titulo: 'Academias independentes',
        sub: verIndependentes
          ? `${n} · visível${independentes?.truncado ? ` de ${total} (teto)` : ''}`
          : `${total} no recorte`,
        ligado: verIndependentes,
        onToggle: () => setVerIndependentes((v) => !v),
        cor: '#e8663c',
        corTexto: 'var(--indep-tx)',
        corRealce: 'rgba(232,102,60,.16)',
      })
    }

    /* OPORTUNIDADES IMOBILIARIAS do recorte. Tambem vale em qualquer camada: "que imovel
       existe aqui?" e' pergunta de territorio, nao de camada do funil. */
    if (temImoveis) {
      lista.push({
        id: 'imoveis',
        icone: 'imoveis',
        titulo: 'Oportunidades imobiliárias',
        sub: verImoveis
          ? `${imoveisNoMapa.length} · visível`
          : `${imoveisNoMapa.length} no recorte`,
        ligado: verImoveis,
        onToggle: () => {
          /* Rastro (DEC-027) so' no LIGAR: apagar a camada nao e' interesse pela oferta
             imobiliaria, e o auto-desligamento por recorte sem imovel nem passa por aqui
             (mexe no estado direto), entao nao vira gesto falso. Fora do updater de
             proposito — em StrictMode ele roda duas vezes. */
          if (!verImoveis) {
            api.eventoImobiliaria('filtrar', { uf, origem: 'mapa', detalhe: 'camada-imoveis' })
          }
          setVerImoveis((v) => !v)
        },
        cor: ACC,
        corTexto: 'var(--imovel-tx)',
        corRealce: ACC_16,
      })
    }

    /* CORES DOS HEXÁGONOS — sempre presente (não depende de recorte). Fica LOGO ACIMA dos
       mapas de calor (pedido do Vinicius, 2026-10-20): as três chaves são as coropletas do
       mapa e se excluem entre si (`lib/camadas-calor`), então leem melhor juntas. */
    lista.push({
      id: 'cores-hex',
      icone: 'hexagono',
      titulo: 'Cores dos hexágonos',
      sub: coresHex ? 'mapa de calor das faixas · visível' : 'só a grade, sem cor',
      ligado: coresHex,
      onToggle: clicarCoresHex,
      cor: 'var(--ac-text)',
      corTexto: 'var(--ac-chip)',
      corRealce: 'var(--ac-a16)',
    })

    /* Bloco D — mapa de calor de setor censitario. So' no drill-down de municipio (mesmo
       gate dos pins de concorrente): a malha de setor de uma UF inteira seria pesada
       demais e nao e' o recorte em que o operador le densidade/renda de bairro. As duas
       chaves sao mutuamente exclusivas (mesma malha, cor diferente) — ligar uma desliga
       a outra, em vez de deixar as duas acesas decidindo por sorte qual pinta por cima. */
    if (!nivelUf) {
      const nSetoresCalor = heatmap?.setores.length ?? 0
      const subCalor = (ligada: boolean) => {
        if (carregandoCalor) return 'carregando…'
        if (!ligada) return 'densidade/renda por setor'
        return heatmap?.disponivel ? `${nSetoresCalor} setores · visível` : 'sem dado para este município'
      }
      lista.push({
        id: 'calor-densidade',
        icone: 'pessoa',
        titulo: 'Densidade demográfica',
        sub: subCalor(verCalorDensidade),
        ligado: verCalorDensidade,
        onToggle: () => clicarCalor('densidade'),
        cor: '#dc4141',
        corTexto: 'var(--ac-chip)',
        corRealce: 'rgba(220,65,65,.16)',
      })
      lista.push({
        id: 'calor-renda',
        icone: 'dinheiro',
        titulo: 'Renda domiciliar',
        sub: subCalor(verCalorRenda),
        ligado: verCalorRenda,
        onToggle: () => clicarCalor('renda'),
        cor: '#00a844',
        corTexto: 'var(--ac-chip)',
        corRealce: 'rgba(0,168,68,.16)',
      })
    }

    return lista
  }, [
    ferramenta,
    vertices.length,
    coresHex,
    alternarRegua,
    alternarPonto,
    alternarGeometria,
    onGeometriaDesenhada,
    nivelUf,
    modoCenario,
    cenario.length,
    heatmap,
    carregandoCalor,
    verCalorDensidade,
    verCalorRenda,
    clicarCalor,
    clicarCoresHex,
    alternarCenario,
    temRedes,
    verRedes,
    dados?.pins,
    temIndependentes,
    independentes,
    verIndependentes,
    temImoveis,
    imoveisNoMapa.length,
    verImoveis,
    uf,
  ])

  // ---------------- Passo 2 do modo de região: escolha de estado ----------------
  // Já NÃO é a porta de entrada do produto — essa é a `InicioScreen`. Aqui só se
  // pergunta o estado, e por isso o hero grande saiu daqui (ver `Landing`).
  if (!uf) {
    /* No modo de ponto quem manda na tela vazia é o `PontoScreen`, que publica o mesmo
       hero com o texto DELE e a caixa de colar. Sem isto, os dois apareciam juntos:
       "Escolha o estado" no fundo e a caixa de endereço por cima. */
    if (semLanding) return null
    return (
      <Landing
        marcador="Explorar uma região"
        titulo={tituloEscolhaUnidade()}
        /* Texto por PAÍS (tabela, DEC-047): onde há a recomendação única, a landing fala de
           camadas de leitura + Top 10; fora da tabela (AR), o texto de sempre. */
        explicacao={
          textosTop10()?.landingMapa ??
          'O mapa lê o território inteiro e monta a sequência de camadas — do potencial socioeconômico até os municípios com mais espaço para abrir.'
        }
        onInicio={onInicio}
      >
        {/* A caixa E' o seletor. Ate' 2026-09-22 havia DUAS: este painel com o rotulo
            "Selecione um estado" e, dentro dele, o botao do dropdown com placeholder
            "Escolha…" — duas bordas aninhadas dizendo a mesma coisa, e so' a de dentro
            clicavel. Quem mirava a de fora nao abria nada. */}
        {ufs.length ? (
          /* O `textAlign: 'center'` do Landing so' centraliza elemento INLINE, e a raiz do
             `Select` e' um <div> de bloco — precisa ser `position: relative` para ancorar o
             popup. Dai este wrapper de layout: sem borda, fundo ou sombra, entao a unica
             caixa visivel continua sendo o proprio botao. */
          <div style={{ display: 'flex', justifyContent: 'center' }}>
            <Select
              label="Escolha um estado para começar"
              value=""
              onChange={onUf}
              maxWidth={280}
              buscavel
              variante="painel"
              placeholder="Selecione um estado"
              options={ufs.map((u) => ({ value: u, label: u }))}
            />
          </div>
        ) : (
          /* O carregando mantem a moldura do painel: sem ela a landing saltaria quando a
             lista chegasse — a caixa sumiria e voltaria. */
          <div
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              padding: '14px 16px',
              background: 'var(--surf-panel)',
              border: '1px solid var(--ac-a30)',
              borderRadius: 'var(--r-lg)',
              backdropFilter: 'blur(16px)',
              boxShadow: 'var(--ac-glow)',
            }}
          >
            <span className="num" style={{ font: '500 12px/1 var(--f-num)', color: 'var(--tx-muted)' }}>
              carregando estados…
            </span>
          </div>
        )}
      </Landing>
    )
  }

  return (
    <div style={{ position: 'absolute', inset: 0, display: 'flex', flexDirection: 'column' }}>
      {/* ---------------- Mapa ao fundo ---------------- */}
      {dados && passo && (
        <HexMap
          hexes={hexesFiltrados}
          passo={passo}
          tema={tema}
          cresMun={dados.cres_mun}
          centro={dados.centro}
          municipio={dados.municipio ?? undefined}
          uf={dados.uf}
          pins={pinsNoMapa}
          /* A seleção que veio do PONTO ativo não é contornada quando o alcance dele já
             está desenhado: o recorte é a marca (`selecaoMarcadaNoMapa`). Clique direto no
             hexágono segue marcado. */
          selecionado={
            modoCenario
              ? null
              : selecaoMarcadaNoMapa(
                  selecionado,
                  selecaoDaBusca,
                  pontosComparados?.find((p) => p.ativo) ?? null,
                )
          }
          cenario={cenario}
          raio1km={raio1km}
          medindo={ferramenta === 'regua'}
          selecionandoPonto={ferramenta === 'ponto'}
          /* `doMapa`: o ponto clicado já está na tela — o pin dele não voa nem aproxima, e a
             ferramenta (que fica ligada) segue marcando os próximos sem perder o bairro. */
          onSelecionarPonto={(lat, lng) => aplicarPonto(lat, lng, true)}
          desenhando={ferramenta === 'geometria'}
          verticesDesenho={vertices}
          coresHex={coresHex}
          top10={top10}
          onCliqueDesenho={cliqueNoDesenho}
          pontosComparados={pontosComparados}
          onPontoClicado={aoClicarPontoComparado}
          independentes={verIndependentes ? independentes?.itens : undefined}
          imoveis={verImoveis ? imoveisNoMapa : undefined}
          onImovel={abrirImovel}
          /* Clique no pin da Ultra: a mesma porta do seletor. O pin não tem id, então casa
             pelo ponto (`unidadeDoPin`); unidade fora da base da rede não abre nada.
             Contra a REDE INTEIRA, e não só a do estado aberto (21/10/2026): o pin de uma
             unidade do outro lado da divisa não abria nada, e agora abre a ficha e leva o
             mapa à UF e ao município dela (`abrirUnidade`). */
          onUltra={
            verUnidades
              ? (p) => {
                  const u = unidadeDoPin(p, unidadesRede ?? [])
                  if (u) abrirUnidade(u)
                }
              : undefined
          }
          cobertura1k={cobertura}
          heatmapSetores={heatmap?.setores}
          modoCalor={modoCalor}
          /* A foto CONGELA na montagem, e trocar de UF/municipio zera `cameraRef` mas
             nao tem como zerar `foto.camera`. Sem este portao: SP/Sao Paulo -> volta da
             Viabilidade (foto.camera = zoom 14 sobre SP) -> troca a UF -> a carga falha
             e o App zera `dados`, o que DESMONTA o HexMap -> nova selecao remonta com a
             camera de Sao Paulo e, como `centroAnterior` ja e' o centro novo, nem voa:
             territorio novo com a camera parada sobre SP. */
          cameraInicial={
            chaveContexto(uf, municipio) === chaveContexto(foto.uf, foto.municipio)
              ? foto.camera
              : null
          }
          onCamera={publicarCamera}
          onSelecionar={(h) => {
            /* Com ferramenta ligada o clique e' dela (`lib/ferramenta-mapa`). O `HexMap` ja'
               nao chama isto com a regua ligada; a guarda aqui vale tambem para as
               ferramentas novas do trilho, quem quer que as ligue. */
            if (!cliqueSelecionaHex(ferramenta)) return
            viagem.cancelar()
            setPin(null)
            // Clique DIRETO: a ficha do hexagono abre, mesmo que seja o hexagono do ponto.
            setSelecaoDaBusca(false)
            if (modoCenario) {
              setCenario((cs) =>
                cs.includes(h.id) ? cs.filter((x) => x !== h.id) : [...cs, h.id],
              )
            } else {
              setSelecionado(h.id)
            }
          }}
          /* A regra unica de precedencia (ver `pontoAtivo`): o ponto analisado vence o
             destino de lista, que vence o pin local da unidade/imovel. Escolher uma
             unidade solta o ponto (`onSoltarPonto`), e entao o pin local passa a valer. */
          searchPin={pontoAtivo ?? pinFixo ?? pin}
          voarPara={voo}
          pedidoCaptura={pedidoCaptura}
          onCapturas={aoCapturarMapas}
        />
      )}

      {/* ---------------- Header ---------------- */}
      <header
        className="barra-ultra"
        /* Publicado para quem mede a borda de baixo dele (janelas e camada do ponto). */
        ref={registrarCabecalhoMapa}
        style={{
          position: 'relative',
          /* ACIMA do corpo, das janelas e das peças soltas do ponto, abaixo da Metodologia
             (ver `lib/camadas-mapa`): UF e município sempre clicáveis, e a lista aberta de
             um seletor daqui pinta por cima de qualquer ficha. */
          zIndex: Z_CABECALHO_MAPA,
          margin: '16px 16px 0',
          padding: '9px 12px',
          display: 'flex',
          alignItems: 'center',
          gap: 12,
          background: 'var(--surf-chrome)',
          border: '1px solid var(--line-soft)',
          borderRadius: 'var(--r-xl)',
          backdropFilter: 'blur(14px)',
          flexWrap: 'wrap',
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
          Inteligência de Expansão
        </h1>

        <Divisor />

        {/* Os rotulos dos seletores chegaram a alternar as cores da marca (2026-09-09,
            manha), mas o Juan reverteu no mesmo dia: "a barra de uf, municipio deixar
            com uma cor que gere contraste (seja preto ou um cinza)". Ficou --tx-strong
            — o neutro FORTE de cada tema — com o peso 600 da rodada colorida. */}
        <label style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <span className="num" style={{ font: '600 11px/1 var(--f-num)', color: 'var(--tx-strong)' }}>
            UF
          </span>
          <Select
            label="Unidade federativa"
            value={uf}
            onChange={onUf}
            maxWidth={74}
            options={ufs.map((u) => ({ value: u, label: u }))}
          />
        </label>

        <label style={{ display: 'flex', alignItems: 'center', gap: 6, minWidth: 0 }}>
          <span className="num" style={{ font: '600 11px/1 var(--f-num)', color: 'var(--tx-strong)' }}>
            MUNICÍPIO
          </span>
          <Select
            label="Município"
            value={municipio}
            onChange={onMunicipio}
            maxWidth={210}
            options={opcoesMunicipio}
          />
        </label>

        {/* Saida VISIVEL do drill-down. Voltar a' visao do estado ja era possivel,
            mas so' abrindo o seletor e achando "Todos os municipios" no meio da
            lista — caminho que existe e nao se anuncia (relato de Felipe,
            2026-07-31). So' aparece quando ha' municipio selecionado. */}
        {municipio && (
          <Botao
            variante="ghost"
            onClick={() => onMunicipio('')}
            title="Voltar à visão do estado inteiro"
            style={{ padding: '6px 11px', font: '600 11.5px/1 var(--f-ui)', whiteSpace: 'nowrap' }}
          >
            ← Todos os municípios
          </Botao>
        )}

        <Divisor />

        {/* Lupa de busca por coordenada */}
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 7,
            background: 'var(--surf-input)',
            border: `1px solid ${buscaErro ? 'rgba(255,90,110,.5)' : 'var(--line)'}`,
            borderRadius: 9,
            padding: '6px 10px',
            minWidth: 210,
          }}
        >
          <svg
            width="14"
            height="14"
            viewBox="0 0 24 24"
            fill="none"
            stroke={buscando ? 'var(--ac)' : 'var(--ac-text)'}
            strokeWidth="1.8"
            strokeLinecap="round"
            aria-hidden
            style={buscando ? { animation: 'pulse 1s ease-in-out infinite' } : undefined}
          >
            <circle cx="11" cy="11" r="7" />
            <path d="m21 21-4.3-4.3" />
          </svg>
          <input
            value={busca}
            onChange={(e) => {
              setBusca(e.target.value)
              if (buscaErro) setBuscaErro(null)
            }}
            onKeyDown={(e) => {
              if (e.key === 'Enter') buscarCoordenada()
            }}
            placeholder={buscando ? 'Buscando endereço…' : 'Buscar endereço, coordenada ou link'}
            aria-label="Buscar por endereço ou coordenada"
            style={{
              flex: 1,
              minWidth: 0,
              background: 'transparent',
              border: 'none',
              padding: 0,
              font: '500 12.5px/1 var(--f-ui)',
              color: 'var(--tx-strong)',
            }}
          />
          {(pin || busca) && (
            <button
              type="button"
              aria-label="Limpar busca"
              /* Limpa a CAIXA (e o pin local de unidade/imovel). O ponto que a busca gerou
                 continua na comparacao: quem o tira de la' e' o painel dela. Cancela a
                 viagem pendente da unidade: sem isso, a resposta atrasada do municipio
                 chegava depois e o efeito de contexto devolvia o pin recem-limpo. */
              onClick={() => {
                viagem.cancelar()
                setPin(null)
                setBusca('')
                setBuscaErro(null)
                setSelecionado(null)
              }}
              style={{ color: 'var(--tx-muted)', font: '500 15px/1 var(--f-ui)', padding: 0 }}
            >
              ×
            </button>
          )}
        </div>

        {/* UNIDADES no lugar do MELHORES (pedido do Juan, 2026-10-01), para quem pode ver a
            rede: as unidades do estado aberto, por nome; escolher uma abre a ficha dela.
            Quem não tem a aba da rede segue com o filtro de sempre — trocar para ele também
            deixaria um seletor que só responde 403. */}
        {verUnidades ? (
          <label style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <span className="num" style={{ font: '600 11px/1 var(--f-num)', color: 'var(--tx-strong)' }}>
              UNIDADES
            </span>
            <Select
              label={`Unidades da Ultra em ${uf}`}
              value={unidadeAberta?.id ?? ''}
              onChange={(id) => {
                const u = opcoesUnidades.find((x) => x.id === id)
                if (u) abrirUnidade(u)
              }}
              maxWidth={190}
              buscavel
              placeholder={
                unidadesRede === null
                  ? 'Carregando…'
                  : opcoesUnidades.length === 0
                    ? `Nenhuma em ${uf}`
                    : `Escolher (${opcoesUnidades.length})`
              }
              options={opcoesUnidades.map((u) => ({ value: u.id, label: u.rotulo }))}
            />
          </label>
        ) : (
        <label style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          {/* A faixa M1 é LEITURA, não recomendação: onde há o Top 10 o filtro se chama
              pelo que ele é ("FAIXA M1"). Os identificadores (`prioridade|alta|media`,
              `FAIXA_FILTROS`) não mudam; fora da tabela de textos (AR), o rótulo de sempre. */}
          <span className="num" style={{ font: '600 11px/1 var(--f-num)', color: 'var(--tx-strong)' }}>
            {textosTop10()?.filtroFaixaRotulo ?? 'MELHORES'}
          </span>
          <Select
            label={textosTop10()?.filtroFaixaLabel ?? 'Filtrar pelos melhores hexes'}
            value={filtroFaixa}
            onChange={setFiltroFaixa}
            maxWidth={150}
            options={[
              { value: '', label: 'Todos os hexes' },
              { value: 'prioridade', label: 'Prioridade máxima' },
              { value: 'alta', label: 'Alta ou +' },
              { value: 'media', label: 'Média ou +' },
            ]}
          />
        </label>
        )}

        {/* Manual do funil. Ao lado do MELHORES e ANTES do `flex:1`: ocupa a folga do
            meio, entao o bloco de metricas segue ancorado na borda direita.

            A quebra do header em duas linhas a 100% de zoom NAO vem daqui, e nao se
            resolve mexendo em peca nenhuma dele: a linha inteira pede ~1860px e um
            notebook Full HD com a escala de 150% do Windows (padrao de fabrica) da ~1265.
            Ja se tentou enxugar o cabecalho (tirar este rotulo, o titulo, os rotulos dos
            seletores, e mudar os tres numeros de lugar) — o Juan recusou em 2026-09-02:
            "o residual, espaco para academias foi pra outra coluna q nao gostei". A
            resposta passou a ser ESCALA global (`--escala-app` em `styles/global.css`):
            69% no PR #301, revertida em 2026-09-08, e fixada em 85% pelo Juan em
            2026-09-09 (PR #324; lib/escala-app.test.ts guarda o valor). */}
        <Botao
          variante="ghost"
          onClick={() => setMetodologiaAberta((v) => !v)}
          title="Metodologia — o que cada camada mede e onde corta"
          style={{
            padding: '6px 11px',
            font: '600 11.5px/1 var(--f-ui)',
            whiteSpace: 'nowrap',
            ...(metodologiaAberta
              ? { color: 'var(--ac)', borderColor: 'var(--ac)', background: 'var(--ac-a12)' }
              : {}),
          }}
        >
          Metodologia
        </Botao>

        <div style={{ flex: 1 }} />

        {dados && (
          <div
            style={{
              display: 'flex',
              alignItems: 'stretch',
              background: 'var(--surf-raised)',
              border: '1px solid var(--line-soft)',
              borderRadius: 'var(--r-lg)',
              overflow: 'hidden',
            }}
          >
            <Metrica rotulo="hexágonos" valor={num(dados.n_hex_total)} />
            <MetricaDivisor />
            <Metrica rotulo="residual" valor={alunos(dados.resumo.residual_total)} />
            <MetricaDivisor />
            <Metrica rotulo="espaço p/ academias" valor={num(dados.resumo.espaco_academias)} destaque />
          </div>
        )}
      </header>

      {buscaErro && (
        <div
          role="alert"
          style={{
            position: 'relative',
            zIndex: 10,
            margin: '8px 16px 0',
            padding: '8px 12px',
            width: 'fit-content',
            borderRadius: 'var(--r-md)',
            background: 'rgba(255,90,110,.12)',
            border: '1px solid rgba(255,90,110,.3)',
            color: 'var(--neg)',
            font: '500 12px/1.4 var(--f-ui)',
          }}
        >
          {buscaErro}
        </div>
      )}

      {/* ---------------- Corpo: painel + rodapé ---------------- */}
      <div
        style={{
          position: 'relative',
          zIndex: Z_CORPO_MAPA,
          flex: 1,
          display: 'flex',
          justifyContent: 'flex-end',
          padding: '14px 16px 0',
          minHeight: 0,
          pointerEvents: 'none',
        }}
      >
        {dados && passo && (
          <div
            ref={setTrilhoEl}
            style={{
              position: 'absolute',
              left: 16,
              bottom: 10,
              display: 'flex',
              flexDirection: 'column',
              gap: 8,
              pointerEvents: 'none',
              /* Anda para a direita das janelas abertas (ver `dxTrilho`). */
              transform: dxTrilho ? `translateX(${dxTrilho}px)` : undefined,
              transition: 'transform .22s cubic-bezier(.4,0,.2,1)',
            }}
          >
            {/* ---------------- Trilho + painel "Camadas do mapa" ----------------
                O desenho e o porque moram em `components/BarraCamadas`. Aqui fica so a
                LIGACAO: quais chaves existem neste recorte, o texto de cada uma e a
                identidade de cor de cada camada.

                A ORDEM E' FIXA e comeca pelas ferramentas do clique ("Selecionar ponto" e
                a regua, nessa ordem — a do dono, 2026-10-14) — elas nao dependem de
                camada, nivel nem recorte, entao sao as que estao SEMPRE la'. As
                condicionais entram depois; assim o que existe sempre nunca muda de lugar
                quando o que e' condicional aparece ou some.

                A LEGENDA ficou LADO A LADO com o painel, e nao embaixo: empilhada, ela
                subia e descia conforme o recorte tivesse ou nao independentes e imoveis
                — exatamente o defeito que este redesenho veio corrigir. */}
            <div style={{ display: 'flex', alignItems: 'flex-end', gap: 12 }}>
              <BarraCamadas
                chaves={chavesDoMapa}
                selecionarPonto={{ ligado: ferramenta === 'ponto', onToggle: alternarPonto }}
                regua={{ ligado: ferramenta === 'regua', onToggle: alternarRegua }}
                geometria={
                  onGeometriaDesenhada
                    ? {
                        ligado: ferramenta === 'geometria',
                        onToggle: alternarGeometria,
                        pausado: desenhoPausado(ferramenta, vertices.length) ? vertices.length : 0,
                      }
                    : null
                }
                comparar={
                  nivelUf
                    ? null
                    : {
                        ligado: modoCenario,
                        onToggle: alternarCenario,
                      }
                }
                legendaVisivel={legendaVisivel}
                legendaDisponivel={coresHex || calorDesenhado}
                onLegenda={() => setLegendaVisivel((v) => !v)}
                camadasAberto={trilho.camadasAberto}
                onAlternarCamadas={() => acaoTrilho({ tipo: 'alternar-camadas' })}
                onFecharCamadas={() => acaoTrilho({ tipo: 'fechar-camadas' })}
                /* ---------------- Painel do DESENHO ("Analisar geometria", DEC-071) ----------------
                   Na MESMA caixa e no MESMO lugar do painel de camadas (pedido do Vinicius,
                   2026-10-16) — antes era uma barra própria empilhada acima do trilho, com outra
                   cara. Abre com a ferramenta e só com ela (`lib/painel-trilho`); o × PAUSA (os
                   vértices ficam no mapa, e o botão do polígono retoma), Cancelar e Esc apagam.
                   A área vai AO VIVO (o operador quer saber se cabe nos limites antes de
                   concluir), e o "Concluir" travado diz POR QUÊ em texto — botão cinza mudo se
                   lê como defeito. */
                painelDesenho={
                  ferramenta === 'geometria'
                    ? {
                        onFechar: () => encerrarDesenho('pausa'),
                        conteudo: (
                          <div style={{ display: 'grid', gap: 10 }}>
                            <LinhaDeEstado
                              icone="poligono"
                              titulo="Área desenhada"
                              sub={
                                <>
                                  {avaliacaoDesenho.areaKm2 != null
                                    ? formatarKm2(avaliacaoDesenho.areaKm2)
                                    : '—'}
                                  {' · '}
                                  {vertices.length} {vertices.length === 1 ? 'vértice' : 'vértices'}
                                </>
                              }
                              cor="var(--gr-verde)"
                              corTexto="var(--gr-verde)"
                              corRealce="color-mix(in srgb, var(--gr-verde) 14%, transparent)"
                            />
                            <span
                              style={{
                                padding: '0 12px',
                                font: '400 11.5px/1.45 var(--f-ui)',
                                color: 'var(--tx-sub)',
                              }}
                            >
                              {vertices.length === 0
                                ? `Clique no mapa para marcar o 1º vértice. Entre 0,1 e ${AREA_MAX_KM2} km², até ${MAX_VERTICES} vértices e até ${DIAGONAL_MAX_KM} km de ponta a ponta; faixa estreita não é aceita.`
                                : 'Clique para o próximo vértice; feche clicando no 1º ou em Concluir. Fechar este painel pausa o desenho sem apagá-lo.'}
                            </span>
                            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', padding: '0 12px 2px' }}>
                              <Botao
                                onClick={() => concluirDesenho()}
                                disabled={!avaliacaoDesenho.podeConcluir}
                                title={avaliacaoDesenho.motivo ?? 'Analisar a área desenhada'}
                              >
                                Concluir
                              </Botao>
                              <Botao
                                variante="ghost"
                                onClick={() => {
                                  setAvisoDesenho(null)
                                  setVertices((vs) => desfazerVertice(vs))
                                }}
                                disabled={vertices.length === 0}
                              >
                                Desfazer
                              </Botao>
                              <Botao
                                variante="ghost"
                                onClick={() => encerrarDesenho('cancelar')}
                                title="Apagar o desenho e desligar a ferramenta (Esc)"
                              >
                                Cancelar
                              </Botao>
                            </div>
                          </div>
                        ),
                        rodape:
                          (avisoDesenho ?? (vertices.length > 0 ? avaliacaoDesenho.motivo : null)) ? (
                            <RodapeDoPainel tom={avisoDesenho ? 'erro' : 'neutro'}>
                              {avisoDesenho ?? avaliacaoDesenho.motivo}
                            </RodapeDoPainel>
                          ) : null,
                      }
                    : null
                }
                /* A espera do raio de 1 km. Ela nasceu quando o raio deixou de ser chave
                   e virou o padrao da camada 3: a geometria custa ~2,4 s numa UF grande e
                   agora e' buscada sem ninguem pedir, entao o unico jeito honesto de
                   cobrar essa espera e' dizer que ela esta acontecendo. */
                aviso={carregandoRaio ? 'Carregando o raio de 1 km das concorrentes…' : null}
              />

              {/* Sem as cores dos hexágonos a legenda sai junto: ela só traduz cor. */}
              {legendaVisivel && coresHex && (
                <ScoreLegend
                  passoN={passo.n}
                  /* Explica o aro indigo SO' quando ele esta desenhado. Legenda que
                     nomeia simbolo ausente ensina o operador a procurar o que nao
                     existe naquele recorte. */
                  comAlunos={(pinsNoMapa?.concorrentes ?? []).some(temAlunos)}
                  /* Camada 5 com o Top 10: Mata Virgem / Premium / fora do Top 10. */
                  top10={
                    passo.n === 5 && dados.recomendacao ? legendaTop10(dados.recomendacao) : null
                  }
                />
              )}
              {legendaVisivel && calorDesenhado && modoCalor && <LegendaCalor modo={modoCalor} />}
            </div>

          </div>
        )}

        <div style={{ pointerEvents: 'auto', display: 'flex', minHeight: 0 }}>
          {carregando && !dados ? (
            <PainelMensagem>
              {nivelUf || !municipio
                ? `Lendo o território de ${uf}…`
                : `Lendo ${municipio}…`}{' '}
              A primeira leitura de uma UF carrega a partição inteira e pode levar alguns segundos.
            </PainelMensagem>
          ) : erro ? (
            <PainelMensagem>
              {erro}
              <br />
              {/* A porta 8899 nao lidera mais a frase: em producao ela nao diz nada ao
                  operador e fazia a tela parecer "sistema caiu" (era o sintoma do pedido
                  do Felipe). Sessao vencida agora tem pop-up proprio — `lib/sessao.ts`. */}
              <br />Se você estiver rodando o piloto na sua própria máquina, confira se o
              backend subiu: é o <code>iniciar-piloto-web.cmd</code> que o liga (porta 8899).
            </PainelMensagem>
          ) : dados && passo ? (
            <NarrativePanel
              passo={passo}
              hexes={dados.hexes}
              totalPassos={dados.passos.length}
              cresMun={dados.cres_mun}
              uf={dados.uf}
              passos={dados.passos}
              nivel={dados.nivel}
              crescimentoEstado={dados.crescimento_estado}
              recomendacao={dados.recomendacao ?? null}
              selecionado={selecionado}
              onSelecionarHex={selecionarDaLista}
              onAnalisar={analisar}
              onDrillMunicipio={onMunicipio}
              onComparar={comparar}
              comparados={cenario}
              maxComparados={MAX_COMPARADOS}
            />
          ) : null}
        </div>
      </div>

      {/* ---------------- Barra dos 4 passos ---------------- */}
      {dados && passo && (
        <div style={{ position: 'relative', zIndex: 10, padding: '14px 16px 16px' }}>
          {aviso && (
            <div
              role="alert"
              style={{
                marginBottom: 10,
                padding: '10px 14px',
                borderRadius: 'var(--r-md)',
                background: 'rgba(217,164,65,.14)',
                border: '1px solid rgba(217,164,65,.35)',
                color: 'var(--warn-text)',
                font: '500 12.5px/1.4 var(--f-ui)',
                display: 'flex',
                justifyContent: 'space-between',
                gap: 12,
                alignItems: 'center',
              }}
            >
              <span>{aviso}</span>
              <Botao variante="ghost" onClick={() => setAviso(null)} style={{ padding: '6px 10px' }}>
                Fechar
              </Botao>
            </div>
          )}
          <StepperBar
            passos={dados.passos}
            atual={passoN}
            onIr={(n) => setPassoN(Math.min(dados.passos.length, Math.max(1, n)))}
            onGerarRelatorio={gerarRelatorioMunicipal}
            gerando={gerando}
            nivelUf={nivelUf}
          />
        </div>
      )}

      {/* Gaveta da metodologia. Ultima na arvore e com zIndex acima do header para
          cobrir o chrome do mapa; o mapa em si continua visivel a' esquerda. */}
      {/* ---------------- Janela da FICHA DO HEXÁGONO ----------------
          Mesma janela da análise de ponto (arrasta, redimensiona, recolhe), agora para o
          hexágono escolhido. Antes o dado dele só existia em dois lugares efêmeros — o
          tooltip, que some com o mouse, e a linha do ranking, que mostra UMA métrica (a da
          camada ativa). Comparar dois bairros exigia trocar de camada quatro vezes.

          Some no modo de comparação: ali quem manda é o conjunto, e duas janelas dizendo
          coisas diferentes sobre a mesma seleção competiriam entre si.

          Também não abre quando a seleção veio da BUSCA de um ponto (`lib/janela-hex`):
          ali a ficha é a do ponto. O clique direto num hexágono abre, nas duas entradas.

          À ESQUERDA, sempre, lado a lado com a do imóvel e a da unidade (que nascem à
          direita). Com pontos em análise a ficha de ponto também nasce à esquerda, e com o
          clique em hexágono liberado as duas podem ficar abertas juntas: esta nasce em
          DEGRAU (`degrauSobreFichaDePonto`), deixando à vista a barra de título da de
          baixo. Mandá-la para a direita a punha em cima da do imóvel e da unidade. */}
      <JanelaFicha
        aberta={
          hexSelecionado != null &&
          janelaDoHexVisivel({
            selecionado,
            hexDaBusca: pontoAtivo?.hexId ?? null,
            selecaoDaBusca,
            modoCenario,
          })
        }
        degrau={degrauSobreFichaDePonto(pontosComparados?.length ?? 0)}
        /* BAIRRO, o MESMO nome que o painel da direita usa na lista. O titulo saia como
           o municipio, entao clicar em "Aracaré" no ranking abria uma ficha chamada
           "Itaquaquecetuba" — e o item de baixo abria outra com o mesmo nome (Juan,
           2026-08-19). Duas fichas com o titulo da cidade nao dizem qual area e' qual. */
        titulo={hexSelecionado ? rotuloDoHex(hexSelecionado) : 'Hexágono'}
        /* O id do hexágono NÃO entra abreviado aqui. H3 é hierárquico: vizinhos dividem o
           prefixo, então `87a8c0ce…` é o mesmo texto para hexágonos diferentes — piorava
           exatamente o que se quer resolver, que é saber qual é qual. A coordenada
           distingue de imediato; o id inteiro fica no corpo da ficha. */
        subtitulo={
          hexSelecionado
            ? [
                // O MUNICIPIO entra aqui quando o titulo virou bairro — senao "Aracaré"
                // sozinho nao diz em que cidade fica. Quando o titulo JA' e' o municipio
                // (visao de UF, ou hexagono fora da malha de bairros), nao se repete.
                hexSelecionado.bairro ? hexSelecionado.mun : null,
                dados?.uf,
                coord(hexSelecionado.lat, hexSelecionado.lng),
              ]
                .filter(Boolean)
                .join(' · ')
            : undefined
        }
        onFechar={() => setSelecionado(null)}
        recuoInferior={96}
      >
        {hexSelecionado && (
          <FichaHex
            hex={hexSelecionado}
            cres={cresMunDoHex}
            ctx={ctxMunDoHex}
            /* `comparar` já põe na lista E liga o modo cenário — sem isso o hexágono
               entraria marcado e o painel de comparação ficaria escondido. */
            onComparar={() => comparar(hexSelecionado.id)}
            imoveis={imoveisDoHex}
            onVerImovel={abrirImovel}
          />
        )}
      </JanelaFicha>

      {/* ---------------- Janela do IMÓVEL (detalhe da oportunidade) ----------------
          Aberta pelo pin da camada imobiliária ou pela seção "Imóveis disponíveis
          aqui" da ficha do hexágono. Nasce à DIREITA: a ficha do hexágono usa a
          âncora padrão (esquerda) e o fluxo natural é ler as duas lado a lado. */}
      <JanelaFicha
        aberta={imovelAberto != null}
        ancora="direita"
        titulo={imovelAberto?.titulo ?? 'Imóvel'}
        subtitulo={
          imovelAberto
            ? [imovelAberto.bairro, imovelAberto.municipio, imovelAberto.uf]
                .filter(Boolean)
                .join(' · ')
            : undefined
        }
        onFechar={() => setImovelAberto(null)}
        recuoInferior={96}
      >
        {imovelAberto && (
          <FichaImovel
            op={imovelAberto}
            onVerNaAba={onVerImovelNaAba ? () => onVerImovelNaAba(imovelAberto) : undefined}
          />
        )}
      </JanelaFicha>

      {/* ---------------- Janela da UNIDADE ULTRA ----------------
          Aberta pelo seletor UNIDADES do cabeçalho ou pelo clique no pin da unidade. À
          DIREITA, como a do imóvel: a ficha do hexágono usa a âncora padrão, e quem clicar
          no hexágono da unidade lê as duas lado a lado. */}
      <JanelaFicha
        aberta={unidadeAberta != null}
        ancora="direita"
        /* As duas da DIREITA nasciam no MESMO retângulo: com o imóvel aberto, a da
           unidade o cobria inteiro, título incluído. Em degrau, a barra dele fica à vista. */
        degrau={imovelAberto != null ? 1 : 0}
        titulo={unidadeAberta?.nome ?? 'Unidade'}
        subtitulo={unidadeAberta?.semRede ? `Unidade Ultra · ${ROTULO_SEM_REDE}` : 'Unidade Ultra'}
        onFechar={fecharUnidade}
        recuoInferior={96}
      >
        {unidadeAberta && (
          <FichaUnidadeNoMapa
            unidadeId={unidadeAberta.id}
            semRede={unidadeAberta.semRede ?? false}
            onEstudarRegiao={estudarRegiaoDaUnidade}
          />
        )}
      </JanelaFicha>

      {/* ---------------- Janela da COMPARAÇÃO ----------------
          À ESQUERDA, a âncora padrão. Ela não convive com a ficha do hexágono, que some no
          modo de comparação — mas convive com a ficha de PONTO, que também nasce à
          esquerda nas duas entradas: com pontos na lista, nasce em degrau sobre ela, como
          a ficha do hexágono. Arrastar continua livre para todas. */}
      <JanelaFicha
        aberta={modoCenario}
        degrau={degrauSobreFichaDePonto(pontosComparados?.length ?? 0)}
        titulo="Comparando hexágonos"
        subtitulo={`${cenario.length} de ${MAX_COMPARADOS} selecionados`}
        onFechar={() => {
          setModoCenario(false)
          setCenario([])
        }}
        recuoInferior={96}
      >
        {hexesComparacao ? (
          <PainelComparacao
            hexes={hexesComparacao}
            onLimpar={() => setCenario([])}
            /* `selecionarDaLista` já é o caminho de "clicou na lista, leve-me lá": ele
               seleciona e pede o voo. Clicar no mapa continua sem voo, porque lá o
               hexágono já está sob o cursor. */
            onIrPara={selecionarDaLista}
            onRelatorio={pedirDeck}
            gerandoRelatorio={gerandoDeck}
          />
        ) : (
          <div>
            <div style={{ font: '700 12px/1 var(--f-ui)', color: 'var(--tx-max)' }}>
              Cenário multi-hex · {resumoCenario?.n ?? 0} hex
            </div>
            {resumoCenario ? (
              <div style={{ marginTop: 8, display: 'flex', flexDirection: 'column', gap: 5 }}>
                <LinhaC rotulo="Residual somado" valor={`${alunos(resumoCenario.residual)} alunos`} forte />
                <LinhaC rotulo="População" valor={num(resumoCenario.pop)} />
                <LinhaC rotulo="Score censo médio" valor={num(resumoCenario.scoreMedio, 1)} />
                <LinhaC rotulo="Concorrentes 2 km" valor={num(resumoCenario.conc)} />
              </div>
            ) : (
              <p style={{ margin: '8px 0 0', font: '400 11.5px/1.5 var(--f-ui)', color: 'var(--tx-muted)' }}>
                Clique nos hexágonos do mapa — ou no <strong style={{ color: 'var(--tx-soft)' }}>+</strong>{' '}
                dos itens da lista — para somar residual, população e score. De{' '}
                <strong style={{ color: 'var(--tx-soft)' }}>dois a {MAX_COMPARADOS}</strong>{' '}
                selecionados, esta janela compara e diz qual é o melhor.
              </p>
            )}
            {resumoCenario && (
              <div style={{ marginTop: 11, display: 'flex', gap: 8 }}>
                <button type="button" onClick={() => setCenario([])} style={botaoGhost}>
                  Limpar
                </button>
                <button type="button" onClick={copiarCenario} style={botaoGhost}>
                  {copiado ? 'Copiado ✓' : 'Copiar IDs'}
                </button>
              </div>
            )}
          </div>
        )}
      </JanelaFicha>

      <MethodologyPanel
        aberto={metodologiaAberta}
        onFechar={() => setMetodologiaAberta(false)}
        passoAtivo={passoN}
        escopo={nivelUf ? 'uf' : 'municipio'}
      />
    </div>
  )
}

/* ---------------- Passo 2 do modo de região: seletor de estado ----------------
   Isto JA FOI a porta de entrada do produto, com o hero "Por onde a Ultra deve crescer?".
   O hero migrou para a `InicioScreen`, que agora pergunta QUAL ANALISE antes de qualquer
   coisa; aqui sobrou a pergunta que sempre foi desta tela — qual estado —, e por isso o
   titulo encolheu de 44px para 26px. Manter os dois grandes deixava o operador diante de
   duas telas de abertura em sequencia, com o mesmo titulo. */

/**
 * O HERO de entrada de um modo: marcador, titulo, explicacao e UM controle.
 *
 * Exportado porque o modo de ponto usa o MESMO desenho com o proprio texto e a caixa de
 * colar no lugar do seletor de estado (pedido do Juan, 2026-08-12). Antes, entrar na
 * analise de ponto sem endereco mostrava este hero falando de "Explorar uma regiao" com a
 * caixa de colar flutuando por cima — dois assuntos disputando a mesma tela.
 */
export function Landing({
  marcador,
  titulo,
  explicacao,
  onInicio,
  children,
}: {
  marcador: string
  titulo: string
  explicacao: ReactNode
  onInicio: () => void
  /** O controle da tela: o seletor de estado, a caixa de colar, o que o modo pedir. */
  children: ReactNode
}) {
  const ufsDaBase = useUfsDaBase()
  return (
    <div
      style={{
        position: 'absolute',
        inset: 0,
        display: 'grid',
        placeItems: 'center',
        padding: 24,
        background:
          'radial-gradient(120% 90% at 50% 30%, var(--bg-lift) 0%, var(--bg-base) 72%)',
      }}
    >
      {/* Mesma posicao do botao nas outras telas: canto superior esquerdo. */}
      <div style={{ position: 'absolute', top: 16, left: 16 }}>
        <BotaoInicio onInicio={onInicio} />
      </div>

      <div style={{ maxWidth: 560, textAlign: 'center' }}>
        <span
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: 8,
            font: '600 11px/1 var(--f-ui)',
            letterSpacing: '.14em',
            textTransform: 'uppercase',
            color: 'var(--ac-text)',
          }}
        >
          <span style={{ width: 6, height: 6, borderRadius: '50%', background: 'var(--ac)' }} />
          {marcador}
        </span>

        <h1
          className="story"
          style={{
            font: '400 26px/1.15 var(--f-story)',
            color: 'var(--tx-max)',
            margin: '14px 0 0',
            letterSpacing: '.005em',
          }}
        >
          {titulo}
        </h1>

        <p
          style={{
            font: '400 15px/1.6 var(--f-ui)',
            color: 'var(--tx-narrative)',
            margin: '14px auto 0',
            maxWidth: 460,
          }}
        >
          {explicacao}
        </p>

        <div style={{ marginTop: 30 }}>{children}</div>

        {/* Sem base carregada nao ha' procedencia a declarar — o <p> inteiro sai, em
            vez de anunciar "0 estados". */}
        {rodapeDaBase(ufsDaBase) && (
          <p
            style={{
              font: '400 11.5px/1.5 var(--f-ui)',
              color: 'var(--tx-sub)',
              margin: '18px 0 0',
            }}
          >
            {rodapeDaBase(ufsDaBase)}
          </p>
        )}
      </div>
    </div>
  )
}

const botaoGhost: React.CSSProperties = {
  flex: 1,
  padding: '7px 10px',
  borderRadius: 8,
  border: '1px solid var(--line-soft)',
  background: 'var(--surf-raised)',
  color: 'var(--tx-soft)',
  font: '600 11.5px/1 var(--f-ui)',
}

/** Linha do resumo do CENARIO multi-hex. O `forte` continua turquesa de proposito:
 *  o cenario e' o unico bloco que pertence ao modo turquesa (botao "◆ Comparando
 *  hexes" + contorno turquesa do hex no mapa). Fora dele o turquesa nao significa
 *  mais "numero importante" — ver --l1..--l4 em tokens.css. */
function LinhaC({ rotulo, valor, forte }: { rotulo: string; valor: string; forte?: boolean }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', gap: 14 }}>
      <span style={{ font: '400 11.5px/1 var(--f-ui)', color: 'var(--tx-label)' }}>{rotulo}</span>
      <span
        className="num"
        style={{
          font: `${forte ? 700 : 500} 12px/1 var(--f-num)`,
          color: forte ? 'var(--ac-text)' : 'var(--tx-soft)',
        }}
      >
        {valor}
      </span>
    </div>
  )
}

function Divisor() {
  return (
    <span
      aria-hidden
      style={{ width: 1, height: 20, background: 'var(--line-mid)', flexShrink: 0 }}
    />
  )
}

function Metrica({
  rotulo,
  valor,
  destaque,
}: {
  rotulo: string
  valor: string
  destaque?: boolean
}) {
  return (
    <div
      style={{
        // Largura igual nos três cards (o rótulo "espaço p/ academias" é o mais
        // largo; sem isto ele fica maior que os outros — pedido do Felipe).
        width: 116,
        flexShrink: 0,
        boxSizing: 'border-box',
        padding: '6px 8px',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        gap: 4,
        // O destaque e' FORMA, nao matiz: fundo neutro + regra vertical. Em turquesa
        // este card usava a mesma familia do numero do funil (numero mono turquesa em
        // caixa turquesa fraca) para grandezas opostas — aqui um TOTAL fixo do
        // territorio, la' o CONTADOR da camada ativa. No passo 2, em que o funil
        // tambem fala de residual, o olho concluia que eram o mesmo numero em dois
        // lugares (relato de Juan, 2026-08-04: "leva o usuario a entender q sao as
        // mesmas coisas").
        //
        // A regra ja' foi `--ultra` (vermelho da marca) e `--info` (azul), e as duas
        // erraram pelo mesmo motivo: TODA matiz deste tema ja' significa outra coisa.
        // Vermelho e' alerta, e este numero e' oportunidade (Juan, 2026-08-05: "deixar
        // um azul para nao levar o usuario a entender q e' algo ruim"). Azul e' a
        // camada 1, e ai' o card passou a parecer parente do Potencial socioeconomico
        // (Juan, 2026-08-05: "o azul leva a entender q o potencial de socio e espaco
        // sao a mesma coisa").
        //
        // Restam violeta (camada 2), ambar (camada 3), turquesa (acao e camada 4) e
        // verde (positivo, e ainda por cima e' o topo da rampa de score do mapa). Nao
        // ha' matiz livre — entao o destaque fica SEM matiz: regra clara e neutra.
        // Ausencia de cor nao afirma parentesco com camada nenhuma, que era o defeito
        // comum das duas tentativas. Quem diz "este e' o numero em destaque" continua
        // sendo o par regra + fundo levantado, e nao o hue.
        background: destaque ? 'var(--surf-pending)' : 'transparent',
        borderLeft: destaque ? '2px solid var(--tx-max)' : undefined,
      }}
    >
      <div
        className="num"
        style={{
          font: '700 18px/1 var(--f-num)',
          // Neutro tambem no destaque: --ultra da' 3,26:1, serve como regra
          // grafica e reprova como cor de texto (mais ainda no rotulo de 8px).
          color: 'var(--tx-max)',
        }}
      >
        {valor}
      </div>
      <div
        style={{
          font: '600 8px/1 var(--f-ui)',
          color: 'var(--tx-label)',
          textTransform: 'uppercase',
          letterSpacing: '.05em',
          whiteSpace: 'nowrap',
        }}
      >
        {rotulo}
      </div>
    </div>
  )
}

function MetricaDivisor() {
  return (
    <span
      aria-hidden
      style={{ width: 1, background: 'var(--line-soft)', alignSelf: 'stretch' }}
    />
  )
}

function PainelMensagem({ children }: { children: React.ReactNode }) {
  return (
    <aside
      style={{
        width: 394,
        padding: '22px 20px',
        background: 'var(--surf-panel)',
        border: '1px solid var(--line-soft)',
        borderRadius: 'var(--r-2xl)',
        backdropFilter: 'blur(18px)',
        font: '400 13px/1.6 var(--f-ui)',
        color: 'var(--tx-narrative)',
        alignSelf: 'flex-start',
      }}
    >
      {children}
    </aside>
  )
}
