import { useCallback, useEffect, useRef, useState } from 'react'

import AvisoConfidencialidade from './components/AvisoConfidencialidade'
import Dock from './components/Dock'
import type { SearchPin } from './components/HexMap'
import AcessosScreen from './screens/AcessosScreen'
import ExecutiveScreen from './screens/ExecutiveScreen'
import InicioScreen from './screens/InicioScreen'
import MapScreen from './screens/MapScreen'
import OportunidadesScreen from './screens/OportunidadesScreen'
import OportunidadesImobiliariasScreen from './screens/OportunidadesImobiliariasScreen'
import PontoScreen from './screens/PontoScreen'
import ViabilityScreen from './screens/ViabilityScreen'
import { abasDoPayload, modosLiberados, telaInicial, telaLiberada, type Aba } from './lib/acesso'
import { api, ApiError } from './lib/api'
import type { AlvoCaptura } from './lib/captura-mapa'
import { modoPorId, passoAlvoDoModo, type ModoInicio } from './lib/inicio'
import { ESTADO_MAPA_VAZIO, type EstadoMapa } from './lib/mapa-estado'
import type { Hex, MunicipioItem, MunicipioPayload } from './lib/types'

export type Tela =
  | 'inicio'
  | 'ponto'
  | 'oportunidades'
  | 'oportunidades-imob'
  | 'mapa'
  | 'viabilidade'
  | 'executiva'
  | 'acessos'

/** O ponto que viaja do mapa para a Viabilidade — a costura entre as duas telas. */
export interface PontoEscolhido {
  hex: Hex
  rotulo: string
  municipio: string
  uf: string
  /**
   * Coordenada EXATA do imóvel, quando o ponto veio da busca (endereço geocodificado
   * ou lat/lng digitada). `hex.lat/hex.lng` NÃO servem para isso: são o centroide do
   * hexágono res-7 (h3.cell_to_latlng no pipeline), a até ~1,5 km do endereço — o
   * bastante para a foto de satélite (400 m) e o mapa de quadra (~300 m) do PDF
   * saírem de outro lugar, e para o ponto cair no mar na orla (400 na malha IBGE).
   * Ausente quando o ponto veio do clique num hexágono do ranking: ali o centroide
   * é mesmo a única coordenada que existe.
   */
  lat?: number
  lng?: number
}

export default function App() {
  // O app abre no MENU, nao no mapa: a primeira pergunta e' "qual analise?", nao
  // "qual estado?". A escolha de UF continua existindo, como passo 2 do modo de regiao.
  const [tela, setTela] = useState<Tela>('inicio')
  // Ciencia do aviso de confidencialidade — nasce false a CADA carga do app.
  const [cienteConfidencialidade, setCienteConfidencialidade] = useState(false)

  /**
   * Abas que o usuário logado pode usar (controle temporário, /api/me).
   * `null` = ainda não sabemos (ou o backend não tem a rota) -> tudo liberado,
   * espelhando o fail-open do backend — que é quem barra de verdade, rota a rota.
   */
  const [abas, setAbas] = useState<Set<Aba> | null>(null)
  useEffect(() => {
    api
      .me()
      .then((r) => {
        const s = abasDoPayload(r)
        setAbas(s)
        // Se o usuário abriu numa tela que não pode ver (estado antigo, deep state),
        // leva para o lugar certo em vez de deixar a tela vazia atrás de 403s.
        if (s) setTela((t) => (telaLiberada(t, s) ? t : telaInicial(s)))
      })
      .catch(() => {
        /* sem /api/me -> segue sem controle; o backend continua barrando o que deve */
      })
  }, [])

  /** Toda troca de tela vinda de navegação passa por aqui: tela vetada é ignorada. */
  const navegar = useCallback(
    (t: Tela) => {
      if (telaLiberada(t, abas)) setTela(t)
    },
    [abas],
  )

  const [ufs, setUfs] = useState<string[]>([])
  // Começa SEM estado: o app abre na porta de entrada (escolha de UF).
  const [uf, setUf] = useState('')
  const [municipios, setMunicipios] = useState<MunicipioItem[]>([])
  // Vazio = visão da UF inteira; preenchido = drill-down no município.
  const [municipio, setMunicipio] = useState('')

  const [dados, setDados] = useState<MunicipioPayload | null>(null)
  const [carregando, setCarregando] = useState(false)
  const [erro, setErro] = useState<string | null>(null)

  const [ponto, setPonto] = useState<PontoEscolhido | null>(null)

  /**
   * Pin do endereco colado no modo de ponto, entregue ao `MapScreen` por `pinFixo`.
   *
   * Mora AQUI e nao no `PontoScreen` porque quem o consome e' o mapa, que e' irmao dele
   * na arvore — e porque o pin da busca interna do `MapScreen` e' apagado toda vez que a
   * UF ou o municipio mudam, que e' exatamente o que colar um endereco provoca.
   */
  const [pinPonto, setPinPonto] = useState<SearchPin | null>(null)

  /**
   * O endereco colado escolheu o territorio: leva o mapa do fundo para la'.
   *
   * `setUf` + `setMunicipio` na mesma passagem — o React agrupa as duas, entao o efeito
   * de carga roda UMA vez, com o par ja' completo. Chamar `aoTrocarUf` aqui seria errado:
   * ele zera o municipio de proposito (trocar de estado recomeca na visao da UF), o que
   * desfaria o drill-down que o endereco acabou de determinar.
   */
  const localizarPonto = useCallback((u: string, m: string, pin: SearchPin) => {
    setUf(u)
    setMunicipio(m)
    setPinPonto(pin)
  }, [])

  /**
   * A busca do cabecalho do mapa pediu a analise de uma coordenada (so' no modo de ponto).
   *
   * O `n` que so' cresce e' o que permite pedir a MESMA coordenada duas vezes: sem ele, o
   * objeto teria o mesmo conteudo e o efeito que ouve do outro lado nao dispararia.
   */
  const [pedidoPonto, setPedidoPonto] = useState<{ lat: number; lng: number; n: number } | null>(
    null,
  )
  const pedirPonto = useCallback((lat: number, lng: number) => {
    setPedidoPonto((p) => ({ lat, lng, n: (p?.n ?? 0) + 1 }))
  }, [])

  /** Tira a marca do endereço do mapa (a limpeza do modo de ponto). */
  const limparPinPonto = useCallback(() => setPinPonto(null), [])

  /* CANAL DE CAPTURA do mapa, repartido entre as duas telas.
     Mora aqui pelo mesmo motivo do `pinPonto` acima: quem tem o mapa é o `MapScreen`, e o
     `PontoScreen` — que é irmão dele na árvore e usa o MESMO mapa — precisa pedir capturas
     para montar o PDF dele. O App não captura nada; só guarda a função que o mapa publica
     e a entrega a quem precisa.

     `ref` e não `state`: trocar a função não deve redesenhar tela nenhuma. */
  const capturaDoMapa = useRef<((alvos: AlvoCaptura[]) => Promise<string[]>) | null>(null)
  const registrarCaptura = useCallback((fn: (alvos: AlvoCaptura[]) => Promise<string[]>) => {
    capturaDoMapa.current = fn
  }, [])
  const capturarMapas = useCallback(
    // Sem mapa montado devolve lista vazia em vez de pendurar a promessa: o gerador do PDF
    // já sabe desenhar a moldura declarando "mapa não capturado".
    (alvos: AlvoCaptura[]) => capturaDoMapa.current?.(alvos) ?? Promise.resolve([]),
    [],
  )

  // Foto do Mapa Territorial (ver lib/mapa-estado): vive AQUI porque o App nao desmonta
  // ao trocar de tela — e' o que devolve o mapa como estava na volta da Viabilidade.
  const [estadoMapa, setEstadoMapa] = useState<EstadoMapa>(ESTADO_MAPA_VAZIO)

  /**
   * Modo escolhido no menu que ainda nao pode ser aplicado porque falta a UF.
   *
   * POR QUE PRECISA EXISTIR. O card "melhores oportunidades" quer abrir o mapa direto no
   * passo 5, mas no instante do clique nao ha UF nenhuma — e semear a foto com
   * `uf: ''` seria inutil: `fotoAplicavel` (lib/mapa-estado) DESCARTA por desenho toda
   * foto sem contexto, justamente para nao restaurar pin/camera de outro municipio.
   * Entao a intencao fica pendurada aqui e e' convertida em foto no momento em que a UF
   * aparece — ai o contexto casa e o passo sobrevive.
   */
  const [modoPendente, setModoPendente] = useState<ModoInicio | null>(null)

  // Catálogo de UFs, uma vez.
  useEffect(() => {
    api
      .ufs()
      .then((r) => setUfs(r.ufs))
      .catch((e: ApiError) => setErro(e.message))
  }, [])

  // Municípios da UF corrente (alimenta o seletor do cabeçalho no drill-down).
  useEffect(() => {
    if (!uf) {
      setMunicipios([])
      return
    }
    let vivo = true
    api
      .municipios(uf)
      .then((r) => {
        if (vivo) setMunicipios(r.municipios)
      })
      .catch(() => {
        /* o seletor de município degrada gracioso */
      })
    return () => {
      vivo = false
    }
  }, [uf])

  // Carga dos dados: UF inteira (sem município) ou drill-down do município.
  useEffect(() => {
    if (!uf) {
      setDados(null)
      return
    }
    let vivo = true
    setCarregando(true)
    setErro(null)
    const pedido = municipio ? api.municipio(uf, municipio) : api.ufView(uf)
    pedido
      .then((d) => {
        if (vivo) setDados(d)
      })
      .catch((e: ApiError) => {
        if (vivo) {
          setErro(e.message)
          setDados(null)
        }
      })
      .finally(() => {
        if (vivo) setCarregando(false)
      })
    return () => {
      vivo = false
    }
  }, [uf, municipio])

  // Trocar de estado recomeça na visão da UF inteira. Não é preciso limpar a foto aqui:
  // ela carrega o contexto em que foi tirada e `fotoAplicavel` a descarta sozinha se a
  // UF/município não bater (lib/mapa-estado).
  const aoTrocarUf = useCallback(
    (u: string) => {
      setUf(u)
      setMunicipio('')

      // Agora que existe UF, a intenção guardada no menu vira foto — com o contexto
      // certo, senão `fotoAplicavel` a jogaria fora. Consumimos a intenção aqui: ela
      // vale para a PRIMEIRA entrada no mapa, não para toda troca de estado seguinte.
      if (!modoPendente) return
      const passo = passoAlvoDoModo(modoPendente)
      setModoPendente(null)
      if (passo === null) return
      setEstadoMapa({ ...ESTADO_MAPA_VAZIO, uf: u, municipio: '', passoN: passo })
    },
    [modoPendente],
  )

  /**
   * De qual tela o ponto veio. A Viabilidade e' alcancavel por DOIS caminhos (clique
   * num hexagono do mapa, e "Mais detalhes" na ficha do modo de ponto), e sem isto o
   * botao de volta devolvia sempre ao mapa — tirando do modo de ponto quem nunca
   * esteve no mapa.
   */
  const [origemViab, setOrigemViab] = useState<Tela>('mapa')

  const irParaViabilidade = useCallback(
    (p: PontoEscolhido) => {
      if (!telaLiberada('viabilidade', abas)) return
      setPonto(p)
      setOrigemViab(tela === 'ponto' ? 'ponto' : 'mapa')
      setTela('viabilidade')
    },
    [tela, abas],
  )

  /** Um card do menu foi escolhido: guarda a intenção e abre a tela que a atende hoje. */
  const escolherModo = useCallback(
    (modo: ModoInicio) => {
      const def = modoPorId(modo)
      if (!def) return
      // Card de modo vetado nem aparece no Início, mas a checagem fica aqui também:
      // a intenção pode chegar por outro caminho (estado guardado, clique programático).
      if (!telaLiberada(def.destino, abas)) return
      // Só faz sentido guardar a intenção enquanto ela ainda não pôde ser aplicada.
      // Com UF já escolhida, aplicamos na hora — o operador que volta ao menu e pede a
      // fila não deveria ter de trocar de estado para ela aparecer.
      /* PEDIR "analisar um ponto" RECOMECA a analise de ponto. O `PontoScreen` desmonta
         ao sair do modo e volta sem ficha nenhuma, mas o pin do endereco anterior mora
         AQUI e sobrevivia — o mapa reabria com a marca de um endereco que nao tem mais
         ficha para explica-la (Juan, 2026-08-18). O territorio (uf/municipio/dados) fica:
         ele custa uma carga de servidor e continua sendo um mapa util. */
      if (modo === 'ponto') setPinPonto(null)
      const passo = passoAlvoDoModo(modo)
      if (passo !== null && uf) {
        setEstadoMapa({ ...ESTADO_MAPA_VAZIO, uf, municipio, passoN: passo })
        setModoPendente(null)
      } else {
        setModoPendente(passo !== null ? modo : null)
      }
      setTela(def.destino)
    },
    [uf, municipio, abas],
  )

  const voltarAoInicio = useCallback(() => setTela('inicio'), [])

  return (
    <div
      style={{
        height: '100vh',
        display: 'flex',
        background: 'var(--bg-base)',
        overflow: 'hidden',
      }}
    >
      <Dock tela={tela} onTela={navegar} abas={abas} />

      <main style={{ flex: 1, position: 'relative', minWidth: 0 }}>
        {tela === 'inicio' ? (
          <InicioScreen onEscolher={escolherModo} modos={modosLiberados(abas)} />
        ) : tela === 'ponto' ? (
          /* O modo de ponto É o Explorar, com a janela da ficha por cima (pedido do Juan,
             2026-08-11). O `MapScreen` vem inteiro e com as MESMAS props do modo `mapa` —
             não uma versão reduzida —, e o `PontoScreen` entra depois na árvore, por isso
             flutua sobre ele. Antes o modo de ponto trazia uma cópia parcial do Explorar
             e as duas telas divergiam. */
          <>
            <MapScreen
              registrarCaptura={registrarCaptura}
              ufs={ufs}
              uf={uf}
              onUf={aoTrocarUf}
              municipios={municipios}
              municipio={municipio}
              onMunicipio={setMunicipio}
              dados={dados}
              carregando={carregando}
              erro={erro}
              onAnalisarPonto={irParaViabilidade}
              estadoInicial={estadoMapa}
              onEstado={setEstadoMapa}
              onInicio={voltarAoInicio}
              pinFixo={pinPonto}
              /* A lupa do cabeçalho vira a entrada do modo de ponto: buscar um endereço
                 ali produz a MESMA ficha que colá-lo. Sem isto havia duas caixas pedindo
                 endereço na mesma tela, e a de cima só soltava um pin. */
              onPontoBuscado={pedirPonto}
              /* A ficha aqui é a do PONTO, publicada pelo `PontoScreen`. Sem isto o
                 endereço abria duas janelas: a dele e a do hexágono em que ele caiu. */
              janelaDoHex={false}
              /* O hero da tela vazia é o do modo de ponto, publicado pelo `PontoScreen`. */
              semLanding
            />
            <PontoScreen
              onCapturarMapas={capturarMapas}
              onAnalisarPonto={irParaViabilidade}
              onLocalizar={localizarPonto}
              mapaPronto={dados != null}
              pedido={pedidoPonto}
              onLimparPin={limparPinPonto}
              onInicio={voltarAoInicio}
            />
          </>
        ) : tela === 'oportunidades' ? (
          <OportunidadesScreen
            ufs={ufs}
            uf={uf}
            onUf={aoTrocarUf}
            municipios={municipios}
            municipio={municipio}
            onMunicipio={setMunicipio}
            dados={dados}
            carregando={carregando}
            erro={erro}
            onInicio={voltarAoInicio}
            onVerNoMapa={(m) => {
              setMunicipio(m)
              navegar('mapa')
            }}
          />
        ) : tela === 'mapa' ? (
          <MapScreen
            ufs={ufs}
            uf={uf}
            onUf={aoTrocarUf}
            municipios={municipios}
            municipio={municipio}
            onMunicipio={setMunicipio}
            dados={dados}
            carregando={carregando}
            erro={erro}
            onAnalisarPonto={irParaViabilidade}
            estadoInicial={estadoMapa}
            onEstado={setEstadoMapa}
            onInicio={voltarAoInicio}
          />
        ) : tela === 'executiva' ? (
          // A Executiva NÃO recebe `uf` nem `onUf` (DEC-023): ela abre com a rede do
          // Brasil inteiro e filtra por dentro. Herdar a UF do Mapa Territorial, além
          // de confundir dois produtos diferentes, disparava um refetch de
          // `/api/uf/{uf}` no Mapa toda vez que se trocava o estado aqui — leitura que
          // pode passar de 15 s.
          <ExecutiveScreen onInicio={voltarAoInicio} />
        ) : tela === 'acessos' ? (
          // Painel restrito (emenda DEC-027). Autônomo como a Executiva: não herda
          // UF/município — a trilha é da rede inteira, não de um recorte do mapa.
          <AcessosScreen onInicio={voltarAoInicio} />
        ) : tela === 'oportunidades-imob' ? (
          // Camada de oferta (imóveis de locação joinados ao M1). Autônoma: nacional,
          // filtra por dentro; READ-ONLY e sem PII (contato do corretor só no dossiê).
          <OportunidadesImobiliariasScreen onInicio={voltarAoInicio} />
        ) : (
          <ViabilityScreen
            ponto={ponto}
            dados={dados}
            onVoltar={() => setTela(origemViab)}
            onInicio={voltarAoInicio}
            origemRotulo={origemViab === 'ponto' ? 'da análise de ponto' : 'do mapa'}
          />
        )}
      </main>

      {/* Pop-up de confidencialidade (2026-08-19): estado LOCAL de propósito — some no
          OK e volta em toda nova entrada (recarga do app). Sem localStorage/sessionStorage:
          a regra é "sempre que a pessoa entrar, clicar em OK". Último filho da raiz +
          z-index alto: cobre Dock e telas até a confirmação. */}
      {!cienteConfidencialidade && (
        <AvisoConfidencialidade
          onConfirmar={() => {
            setCienteConfidencialidade(true)
            // Registro da ciência na trilha (DEC-027) — best-effort de propósito: a
            // falha da chamada não pode travar a entrada de quem já confirmou.
            void api.cienciaConfidencialidade().catch(() => {})
          }}
        />
      )}
    </div>
  )
}
