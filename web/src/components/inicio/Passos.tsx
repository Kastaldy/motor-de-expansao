import { useEffect, useMemo, useRef, useState } from 'react'

import Select from '../Select'
import { api } from '../../lib/api'
import { filtrarUnidades } from '../../lib/exec'
import {
  DIMENSOES_RECORTE,
  type DimensaoRecorte,
  type EntradaInicio,
} from '../../lib/inicio'
import type { RedeFiltros, RedeUnidade } from '../../lib/types'

/**
 * O SEGUNDO PASSO dos cards do Início — o que aparece no lugar da ilustração depois do
 * clique (2026-09-22).
 *
 * A pergunta é sempre a MESMA que a tela de destino faria no primeiro gesto: qual
 * estado (a `Landing` do mapa), que endereço (a caixa de colar do modo de ponto), por
 * que eixo recortar a carteira, qual unidade abrir. Respondê-la aqui é o que faz o
 * operador cair no resultado em vez de cair na tela vazia que pede a resposta.
 *
 * POR QUE NO LUGAR DA ILUSTRAÇÃO, e não empurrando o card para baixo. O quadro da arte
 * tem proporção fixa e é ele quem dá altura ao card; um painel que nascesse abaixo dele
 * faria os três cards crescerem juntos (a fila é `stretch`) e a tela pularia no clique.
 * Ocupando o quadro, o card não muda de tamanho: a ilustração cede lugar à ferramenta.
 *
 * POR QUE ALGUNS BUSCAM DADO. O Início não fazia uma chamada sequer — era a sua melhor
 * propriedade (entrada do app a custo zero). Isto continua verdade na ABERTURA: nada é
 * pedido antes de um card ser aberto. Dos quatro painéis, só os dois de operações pedem
 * rede; os dois de expansão usam a lista de UFs que o `App` já carregou.
 *
 * "Recortar a rede" pede `/api/rede/filtros`, que é o vocabulário; "Abrir a ficha" pede
 * a carteira inteira, porque não existe rota de listagem enxuta de unidades hoje — são
 * ~230 KB para montar uma busca por nome, e a Executiva vai pedi-la de novo ao abrir. É
 * a dívida declarada desta etapa; uma rota enxuta resolve as duas.
 */

/* O painel ocupa o quadro inteiro e CENTRALIZA o conteúdo (pedido do Felipe,
   2026-09-22: os seletores nasciam colados no canto superior esquerdo). O que fica no
   topo, quando fica, é sempre um controle de largura inteira — chips ou campo de busca;
   o miolo é que se centra. */
const PAINEL: React.CSSProperties = {
  position: 'absolute',
  inset: 0,
  display: 'flex',
  flexDirection: 'column',
  gap: 10,
  padding: 16,
  boxSizing: 'border-box',
}

/** Miolo centrado nos dois eixos — onde mora o seletor de fato. */
const MIOLO: React.CSSProperties = {
  flex: '1 1 auto',
  minHeight: 0,
  display: 'flex',
  flexDirection: 'column',
  alignItems: 'center',
  justifyContent: 'center',
  gap: 10,
  textAlign: 'center',
}

/** Largura do seletor dentro do miolo: cheio, mas com teto para não encostar na borda. */
const LARGURA_SELETOR = 260

function Aviso({ children }: { children: React.ReactNode }) {
  return (
    <span
      style={{
        font: '400 12.5px/1.5 var(--f-ui)',
        color: 'var(--tx-sub)',
        textAlign: 'center',
        maxWidth: 260,
      }}
    >
      {children}
    </span>
  )
}

/** Legenda do que vai acontecer ao escolher. Some quando há um aviso no lugar. */
function Dica({ children }: { children: React.ReactNode }) {
  return (
    <span
      style={{
        font: '400 12px/1.45 var(--f-ui)',
        color: 'var(--tx-sub)',
        maxWidth: 260,
      }}
    >
      {children}
    </span>
  )
}

/* ---------------------------------------------------------------------------
   Expansão · qual estado (Explorar uma região)
   --------------------------------------------------------------------------- */

export function PassoUf({
  ufs,
  onEscolher,
}: {
  /** Lista que o `App` já carregou de `/api/ufs` — este painel não busca nada. */
  ufs: readonly string[]
  onEscolher: (e: EntradaInicio) => void
}) {
  return (
    <div style={PAINEL}>
      <div style={MIOLO}>
        {ufs.length === 0 ? (
          <Aviso>A base ainda não respondeu a lista de estados.</Aviso>
        ) : (
          <>
            <div style={{ width: LARGURA_SELETOR }}>
              <Select
                label="Escolha o estado"
                value=""
                placeholder="Escolha o estado"
                maxWidth={LARGURA_SELETOR}
                larguraCheia
                buscavel
                options={ufs.map((u) => ({ value: u, label: u }))}
                onChange={(v) => onEscolher({ tipo: 'uf', uf: v })}
              />
            </div>
            <Dica>O mapa abre no estado escolhido, na camada 1 do funil.</Dica>
          </>
        )}
      </div>
    </div>
  )
}

/* ---------------------------------------------------------------------------
   Expansão · qual endereço (Analisar um ponto ou imóvel)
   --------------------------------------------------------------------------- */

export function PassoEndereco({ onEscolher }: { onEscolher: (e: EntradaInicio) => void }) {
  const [texto, setTexto] = useState('')
  const campo = useRef<HTMLInputElement>(null)

  useEffect(() => {
    campo.current?.focus()
  }, [])

  /* Nada é classificado nem resolvido aqui: o texto vai CRU para o `PontoScreen`, que já
     sabe separar coordenada, link longo, link curto e endereço — e é ele quem tem as
     mensagens de erro de cada caso (`lib/entrada-ponto.ts`). Duplicar essa classificação
     no card criaria uma segunda régua para a mesma pergunta. */
  const enviar = () => {
    if (texto.trim()) onEscolher({ tipo: 'endereco', texto: texto.trim() })
  }

  return (
    <div style={PAINEL}>
      <div style={MIOLO}>
        <input
          ref={campo}
          value={texto}
          onChange={(e) => setTexto(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter') enviar()
          }}
          placeholder="Cole o link do Maps ou a coordenada"
          aria-label="Endereço, link do Maps ou coordenada"
          style={{ width: LARGURA_SELETOR, boxSizing: 'border-box' }}
        />
        <button
          type="button"
          onClick={enviar}
          disabled={!texto.trim()}
          style={{
            width: LARGURA_SELETOR,
            height: 36,
            border: 0,
            borderRadius: 'var(--r-md)',
            background: texto.trim() ? 'var(--ac)' : 'var(--surf-raised)',
            color: texto.trim() ? 'var(--ac-on)' : 'var(--tx-off)',
            font: '700 13px/1 var(--f-ui)',
            cursor: texto.trim() ? 'pointer' : 'default',
          }}
        >
          Analisar este ponto
        </button>
        <Dica>Também vale um endereço escrito — o servidor resolve.</Dica>
      </div>
    </div>
  )
}

/* ---------------------------------------------------------------------------
   Operações · recortar a rede (estado, master ou consultor)
   --------------------------------------------------------------------------- */

/** As três listas do vocabulário, na ordem dos chips. */
function opcoesDaDimensao(filtros: RedeFiltros | null, dim: DimensaoRecorte): string[] {
  if (!filtros) return []
  if (dim === 'uf') return filtros.ufs
  /* `masters` e `consultores` são as MESMAS listas que os seletores do cabeçalho da
     Visão Executiva consomem: o vocabulário do card não pode divergir do de lá.

     As duas vêm do CADASTRO (`master_franquia` e `consultor`), não da base Growth — a
     DEC-053 trocou a sigla de região pelo nome do franqueado porque uma sigla como
     `DF/GO` cobre 2 masters e `RJ/SP 01` cobre 3, então ela nunca respondeu "as
     unidades de quem". Consequência prática: sem o cadastro montado, estes dois eixos
     ficam VAZIOS enquanto o de estado funciona — ver `avisoDoEixo`. */
  if (dim === 'master') return filtros.masters
  return filtros.consultores
}

/** Por que este eixo está vazio — a diferença importa para quem lê. */
function avisoDoEixo(filtros: RedeFiltros, dim: DimensaoRecorte): string {
  if (dim === 'uf') return 'A base não tem estado nesta competência.'
  const eixo = dim === 'master' ? 'master' : 'consultor'
  // `disponivel: false` = o volume do cadastro não está montado nesta instância. É o
  // caso do ambiente de desenvolvimento sem `MOTOR_CADASTRO_DIR`, e dizer "a base não
  // tem master" ali culparia a competência por uma configuração de deploy.
  if (!filtros.cadastro.disponivel) {
    return `O cadastro não está carregado nesta instância, então não há ${eixo} para escolher.`
  }
  return `Nenhuma unidade tem ${eixo} atribuído ainda — isso se preenche na ficha.`
}

export function PassoRecorte({ onEscolher }: { onEscolher: (e: EntradaInicio) => void }) {
  const [filtros, setFiltros] = useState<RedeFiltros | null>(null)
  const [erro, setErro] = useState(false)
  const [dimensao, setDimensao] = useState<DimensaoRecorte>('uf')

  useEffect(() => {
    let vivo = true
    api
      .redeFiltros()
      .then((f) => vivo && setFiltros(f))
      .catch(() => vivo && setErro(true))
    return () => {
      vivo = false
    }
  }, [])

  const opcoes = opcoesDaDimensao(filtros, dimensao)
  const definicao = DIMENSOES_RECORTE.find((d) => d.id === dimensao)!

  return (
    <div style={PAINEL}>
      <div style={{ display: 'flex', gap: 6 }} role="group" aria-label="Recortar por">
        {DIMENSOES_RECORTE.map((d) => {
          const vazio = filtros !== null && opcoesDaDimensao(filtros, d.id).length === 0
          const ativo = d.id === dimensao
          return (
            <button
              key={d.id}
              type="button"
              aria-pressed={ativo}
              /* Eixo sem vocabulário fica DESABILITADO, e não só com mensagem depois do
                 clique: o operador vê de imediato quais recortes esta instância entrega.
                 O `title` diz o porquê, que é o que ele precisa para agir. */
              disabled={vazio}
              title={vazio && filtros ? avisoDoEixo(filtros, d.id) : undefined}
              onClick={() => setDimensao(d.id)}
              style={{
                flex: 1,
                height: 32,
                border: `1px solid ${ativo ? 'var(--ops)' : 'var(--line)'}`,
                borderRadius: 999,
                background: ativo ? 'var(--ops)' : 'transparent',
                color: ativo ? 'var(--ops-on)' : vazio ? 'var(--tx-off)' : 'var(--tx-soft)',
                font: '600 12px/1 var(--f-ui)',
                cursor: vazio ? 'default' : 'pointer',
                opacity: vazio ? 0.55 : 1,
              }}
            >
              {d.rotulo}
            </button>
          )
        })}
      </div>

      <div style={MIOLO}>
        {erro ? (
          <Aviso>Não foi possível carregar os filtros da rede. Entre pelo panorama.</Aviso>
        ) : !filtros ? (
          <Aviso>Carregando os filtros da rede…</Aviso>
        ) : opcoes.length === 0 ? (
          <Aviso>{avisoDoEixo(filtros, dimensao)}</Aviso>
        ) : (
          <>
            <div style={{ width: LARGURA_SELETOR }}>
              <Select
                // `key` na dimensão: sem ela o seletor guardaria o valor escolhido na
                // dimensão anterior e mostraria um master selecionado na lista de estados.
                key={dimensao}
                label={definicao.convite}
                value=""
                placeholder={definicao.convite}
                maxWidth={LARGURA_SELETOR}
                larguraCheia
                // Sempre buscável: com 27 estados, dezenas de masters e de consultores, o
                // padrão (>8 opções) já ligaria a busca em todas as três — declarar remove
                // a pergunta "esta lista tem busca?" da leitura do código.
                buscavel
                options={opcoes.map((o) => ({ value: o, label: o }))}
                onChange={(v) => onEscolher({ tipo: 'recorte', dimensao, valor: v })}
              />
            </div>
            <Dica>A carteira abre já filtrada por {definicao.rotulo.toLowerCase()}.</Dica>
          </>
        )}
      </div>
    </div>
  )
}

/* ---------------------------------------------------------------------------
   Operações · abrir a ficha de uma unidade
   --------------------------------------------------------------------------- */

/** Quantas unidades a lista mostra. Acima disto ela vira rolagem sem fim dentro de um
 *  quadro de 300px; a resposta certa é digitar mais uma letra. */
const MAX_RESULTADOS = 30

export function PassoUnidade({ onEscolher }: { onEscolher: (e: EntradaInicio) => void }) {
  const [unidades, setUnidades] = useState<RedeUnidade[] | null>(null)
  const [erro, setErro] = useState(false)
  const [termo, setTermo] = useState('')
  const campo = useRef<HTMLInputElement>(null)

  useEffect(() => {
    let vivo = true
    api
      .redeCarteira()
      .then((c) => vivo && setUnidades(c.unidades))
      .catch(() => vivo && setErro(true))
    campo.current?.focus()
    return () => {
      vivo = false
    }
  }, [])

  /* Ordenação por NOME, e não pela prioridade com que a carteira chega: aqui a pergunta
     é "onde está a unidade X", e uma lista alfabética responde isso; a fila de visita é
     a pergunta da tela seguinte. */
  const achados = useMemo(() => {
    if (!unidades) return []
    return filtrarUnidades(unidades, termo)
      .slice()
      .sort((a, b) => a.nome.localeCompare(b.nome, 'pt-BR'))
      .slice(0, MAX_RESULTADOS)
  }, [unidades, termo])

  return (
    <div style={PAINEL}>
      <input
        ref={campo}
        value={termo}
        onChange={(e) => setTermo(e.target.value)}
        placeholder="Buscar por nome, cidade ou estado…"
        aria-label="Buscar unidade"
        disabled={!unidades}
        style={{ width: '100%', boxSizing: 'border-box' }}
      />

      {erro || !unidades || achados.length === 0 ? (
        <div style={MIOLO}>
          {erro ? (
            <Aviso>Não foi possível carregar a rede. Entre pelo panorama.</Aviso>
          ) : !unidades ? (
            <Aviso>Carregando as unidades…</Aviso>
          ) : (
            <Aviso>Nenhuma unidade para “{termo.trim()}”.</Aviso>
          )}
        </div>
      ) : (
        /* A LISTA não é centrada, ao contrário dos outros painéis: ela cresce de cima
           para baixo e rola: centrada, cada tecla digitada mexeria a primeira linha de
           lugar, e é justamente nela que o operador está mirando. */
        <ul
          style={{
            listStyle: 'none',
            margin: 0,
            padding: 0,
            overflowY: 'auto',
            display: 'flex',
            flexDirection: 'column',
            gap: 2,
            minHeight: 0,
          }}
        >
          {achados.map((u) => (
            <li key={u.id}>
              <button
                type="button"
                onClick={() => onEscolher({ tipo: 'unidade', id: u.id })}
                style={{
                  width: '100%',
                  display: 'flex',
                  alignItems: 'baseline',
                  justifyContent: 'space-between',
                  gap: 10,
                  padding: '7px 9px',
                  border: '1px solid transparent',
                  borderRadius: 'var(--r-md)',
                  background: 'transparent',
                  textAlign: 'left',
                  cursor: 'pointer',
                }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.background = 'var(--surf-raised)'
                  e.currentTarget.style.borderColor = 'var(--line)'
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.background = 'transparent'
                  e.currentTarget.style.borderColor = 'transparent'
                }}
              >
                <span
                  style={{
                    font: '600 13px/1.3 var(--f-ui)',
                    color: 'var(--tx-max)',
                    overflow: 'hidden',
                    textOverflow: 'ellipsis',
                    whiteSpace: 'nowrap',
                  }}
                >
                  {u.nome}
                </span>
                {/* Cidade desempata homônimos — a rede tem unidades de mesmo nome em
                    cidades diferentes, e só o nome deixaria a escolha no escuro. A UF
                    fica de fora: o nome já a carrega ("FLOW - PR"), e repeti-la produzia
                    "FLOW - PR · PR". */}
                <span
                  style={{
                    font: '400 11.5px/1.3 var(--f-num)',
                    color: 'var(--tx-sub)',
                    flexShrink: 0,
                  }}
                >
                  {u.cidade ?? u.uf}
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
