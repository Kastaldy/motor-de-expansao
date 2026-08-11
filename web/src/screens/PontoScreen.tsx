import { useCallback, useEffect, useRef, useState } from 'react'

import type { PontoEscolhido } from '../App'

import BlocoViabilidadePonto from '../components/BlocoViabilidadePonto'
import CampoPonto from '../components/CampoPonto'
import DetalheRegiao from '../components/DetalheRegiao'
import type { SearchPin } from '../components/HexMap'
import JanelaFicha from '../components/JanelaFicha'
import PainelPontos from '../components/PainelPontos'
import Recomendacao from '../components/Recomendacao'
import { Aviso, Botao, Chip, Eyebrow, Glass, Kpi, Spinner } from '../components/primitives'
import { api, ApiError } from '../lib/api'
import { MAX_PONTOS } from '../lib/comparacao-pontos'
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
  onAnalisarPonto,
  onLocalizar,
  mapaPronto,
  pedido,
  onFocarBusca,
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
  /**
   * Pede o foco no campo de busca do cabecalho.
   *
   * E' o que faz "+ Adicionar mais um ponto" funcionar sem caixa propria: com o mapa na
   * tela, adicionar um ponto e' digitar na lupa que ja' esta' la'.
   */
  onFocarBusca: () => void
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
   * Nasce FECHADA se o mapa ja' estava montado ao entrar no modo (quem explorou uma
   * regiao e depois trocou para "analisar um ponto"): nesse caso a busca do cabecalho ja'
   * esta' na tela e abrir a caixa seria duplica-la de saida.
   */
  const [colando, setColando] = useState(() => !mapaPronto)
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
        const nova = await api.ponto(lat, lng)
        // O ponto novo entra no fim e vira o aberto: quem acabou de pedir quer ver ele.
        setFichas((atuais) => {
          const proximas = [...atuais, nova].slice(0, MAX_PONTOS)
          setAberto(proximas.length - 1)
          return proximas
        })
        setColando(false)
        setJanela(true)
        // O mapa do fundo vai para a cidade do endereco, com o pin na coordenada EXATA e
        // o hexagono dela selecionado. Depois disto quem manda no territorio e' o
        // operador: os seletores do cabecalho continuam valendo, como no Explorar.
        onLocalizar(nova.local.uf ?? '', nova.local.municipio ?? '', {
          lat: nova.lat,
          lng: nova.lng,
          hexId: nova.hex_id,
        })
      } catch (e) {
        // NAO limpa os pontos ja lidos: perder tres leituras porque a quarta falhou
        // seria punir o operador por um endereco mal digitado.
        setErro(e instanceof ApiError ? e.message : 'Falha ao analisar o ponto.')
      } finally {
        setCarregando(false)
      }
    },
    [onLocalizar],
  )

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
   * A caixa e a busca do cabecalho NUNCA convivem.
   *
   * Regra dura, e nao "quase nunca": duas caixas pedindo endereco na mesma tela sao
   * redundantes ainda que uma delas tenha sido aberta a pedido (foi o defeito que sobrou
   * da primeira tentativa — o "+ Adicionar mais um ponto" reabria a caixa por cima da
   * busca). Com o mapa montado a entrada e' a lupa do cabecalho, ponto final; sem mapa a
   * caixa e' a unica entrada que existe, porque a tela vazia do Explorar so' oferece o
   * seletor de estado.
   */
  const mostrandoCaixa = !mapaPronto && (colando || fichas.length === 0)

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
        titulo={ficha?.local.bairro ?? ficha?.local.municipio ?? 'Ponto analisado'}
        /* A régua e a contagem de setores vinham do cabeçalho próprio, que saiu junto com
           a cópia do Explorar. Vivem aqui porque é a ficha que elas qualificam — e some
           uma linha de chrome da tela. */
        subtitulo={
          ficha
            ? [
                [ficha.local.municipio, ficha.local.uf].filter(Boolean).join(' · '),
                `raio de ${num(ficha.raio_km * 1000)} m`,
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
                setErro(null)
                // Com o mapa na tela NAO abre caixa nenhuma: leva o cursor para a busca
                // do cabecalho, que e' a entrada unica. Abrir uma segunda caixa por cima
                // dela era o defeito apontado — redundante ainda que sob pedido.
                if (mapaPronto) onFocarBusca()
                else setColando(true)
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
