/* Anotações do time sobre uma academia concorrente (migration 023).
 *
 * Abre pelo clique no pino do concorrente, dentro de uma `JanelaFicha` à direita. O que cada
 * pessoa vê já vem decidido do servidor — este componente NÃO esconde nada:
 *
 *   - quem não é Growth recebe "Pessoa 1, Pessoa 2…" e nunca o nome (nem no JSON);
 *   - Growth recebe o nome, o histórico de versões e as anotações apagadas;
 *   - `pode_editar`/`pode_apagar` vêm por anotação: só o autor edita, e Growth também apaga a
 *     dos outros (moderação).
 *
 * Nada some do banco: "Apagar" marca, e "Editar" guarda a versão anterior. A confirmação de
 * apagar é inline (diálogo nativo do navegador trava o mapa).
 */
import { useCallback, useEffect, useMemo, useState } from 'react'
import { api, ApiError } from '../lib/api'
import {
  apenasDigitos,
  camposDoFormulario,
  dataHora,
  DIGITOS_MAXIMOS,
  estrelas,
  formularioDe,
  linhasDaObservacao,
  mediaDaNota,
  metragemMaisRecente,
  NOTA_MAXIMA,
  NOTAS,
  numeroDoRotulo,
  TEXTO_MAXIMO,
  type Formulario,
} from '../lib/observacoes'
import type { Observacao, ObservacoesPayload, Pin } from '../lib/types'
import { Botao, Spinner } from './primitives'

const CORES_AVATAR = ['#82e6dc', '#e9c07a', '#a98cf0', '#7fe6a6', '#6fa4f7', '#f9a8d4']

const fmt = new Intl.NumberFormat('pt-BR')

function mensagem(e: unknown): string {
  if (e instanceof ApiError) {
    if (e.status === 403) return e.message || 'Você não tem permissão para esta ação.'
    if (e.status === 503) return 'O banco do piloto não respondeu. Tente novamente em instantes.'
    return e.message
  }
  return 'Não foi possível concluir. Tente novamente.'
}

const rotuloSecao: React.CSSProperties = {
  font: '600 10.5px/1 var(--f-ui)',
  letterSpacing: '.08em',
  textTransform: 'uppercase',
  color: 'var(--tx-label)',
  margin: '16px 0 8px',
}

export function PainelObservacoes({
  pin,
  onContagem,
}: {
  pin: Pin
  /** Avisa o mapa quantas anotações vivas o pino tem agora, para o selo acompanhar. */
  onContagem?: (chave: string, n: number) => void
}) {
  const chave = pin.chave ?? ''
  const [dados, setDados] = useState<ObservacoesPayload | null>(null)
  const [carregando, setCarregando] = useState(true)
  const [erro, setErro] = useState<string | null>(null)
  const [form, setForm] = useState<Formulario | null>(null)
  const [erroForm, setErroForm] = useState<string | null>(null)
  const [salvando, setSalvando] = useState(false)
  const [confirmar, setConfirmar] = useState<number | null>(null)
  const [histAberto, setHistAberto] = useState<Set<number>>(new Set())
  const [mostrarApagadas, setMostrarApagadas] = useState(false)

  const aplicar = useCallback(
    (p: ObservacoesPayload) => {
      setDados(p)
      onContagem?.(chave, p.observacoes.filter((o) => !o.apagada).length)
    },
    [chave, onContagem],
  )

  useEffect(() => {
    if (!chave) return
    let vivo = true
    setCarregando(true)
    setErro(null)
    api
      .observacoes(chave)
      .then((p) => vivo && aplicar(p))
      .catch((e) => vivo && setErro(mensagem(e)))
      .finally(() => vivo && setCarregando(false))
    return () => {
      vivo = false
    }
  }, [chave, aplicar])

  const ativas = useMemo(() => (dados?.observacoes ?? []).filter((o) => !o.apagada), [dados])
  const apagadas = useMemo(() => (dados?.observacoes ?? []).filter((o) => o.apagada), [dados])
  const pessoas = useMemo(() => new Set(ativas.map((o) => o.autor_rotulo)).size, [ativas])
  const metragem = useMemo(() => metragemMaisRecente(ativas), [ativas])

  async function salvar() {
    if (!form) return
    const campos = camposDoFormulario(form)
    if (typeof campos === 'string') {
      setErroForm(campos)
      return
    }
    setSalvando(true)
    setErroForm(null)
    try {
      const p =
        form.id === 'nova'
          ? await api.observacaoCriar(chave, campos)
          : await api.observacaoEditar(form.id, chave, form.versao, campos)
      aplicar(p)
      setForm(null)
    } catch (e) {
      setErroForm(mensagem(e))
    } finally {
      setSalvando(false)
    }
  }

  async function apagar(id: number) {
    setSalvando(true)
    try {
      aplicar(await api.observacaoApagar(id, chave))
      setConfirmar(null)
    } catch (e) {
      setErro(mensagem(e))
    } finally {
      setSalvando(false)
    }
  }

  if (!chave) {
    return <p style={{ color: 'var(--tx-sub)' }}>Esta academia não tem coordenada válida para receber anotação.</p>
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 0, paddingBottom: 12 }}>
      <div style={{ ...rotuloSecao, marginTop: 2 }}>O que o time anotou</div>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
        <Kpi
          valor={metragem ? `${fmt.format(metragem.metragem_m2 ?? 0)} m²` : '—'}
          rotulo={
            metragem
              ? `metragem mais recente · ${dataHora(metragem.atualizada_em, false)}`
              : 'metragem ainda não informada'
          }
        />
        <Kpi
          valor={String(ativas.length)}
          rotulo={`${ativas.length === 1 ? 'anotação' : 'anotações'} de ${pessoas} ${pessoas === 1 ? 'pessoa' : 'pessoas'}`}
        />
      </div>
      <MediasDasNotas ativas={ativas} />
      {divergencia(ativas) && (
        <p style={{ color: 'var(--tx-off)', font: '400 11px/1.4 var(--f-ui)', margin: '8px 0 0' }}>
          As anotações divergem na metragem ({divergencia(ativas)}). Vale a mais recente, e as
          outras continuam visíveis.
        </p>
      )}

      <div style={rotuloSecao}>Anotações</div>
      {erro && (
        <p role="alert" style={{ color: 'var(--neg)', font: '500 12px/1.4 var(--f-ui)', margin: '0 0 8px' }}>
          {erro}
        </p>
      )}
      {carregando ? (
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, color: 'var(--tx-sub)' }}>
          <Spinner /> Carregando anotações…
        </div>
      ) : (
        <>
          {dados?.pode_anotar &&
            (form?.id === 'nova' ? (
              <FormularioObservacao
                form={form}
                setForm={setForm}
                erro={erroForm}
                salvando={salvando}
                rotulo="Salvar anotação"
                onSalvar={salvar}
                onCancelar={() => {
                  setForm(null)
                  setErroForm(null)
                }}
              />
            ) : (
              <button
                type="button"
                onClick={() => {
                  setForm(formularioDe(null))
                  setErroForm(null)
                  setConfirmar(null)
                }}
                style={{
                  width: '100%',
                  padding: 10,
                  borderRadius: 'var(--r-sm)',
                  border: '1px dashed var(--ac-a45)',
                  background: 'var(--ac-a10)',
                  color: 'var(--ac-text)',
                  font: '600 12.5px/1 var(--f-ui)',
                  cursor: 'pointer',
                }}
              >
                + Nova anotação
              </button>
            ))}
          <div style={{ height: 10 }} />
          {!ativas.length && !(dados?.pode_moderar && apagadas.length) && (
            <div
              style={{
                color: 'var(--tx-sub)',
                textAlign: 'center',
                padding: '18px 8px',
                border: '1px dashed var(--line-strong)',
                borderRadius: 'var(--r-md)',
              }}
            >
              Ninguém anotou nada sobre esta unidade ainda.
            </div>
          )}
          {[...ativas].reverse().map((o) =>
            form && form.id === o.id ? (
              <FormularioObservacao
                key={o.id}
                form={form}
                setForm={setForm}
                erro={erroForm}
                salvando={salvando}
                rotulo="Salvar edição"
                onSalvar={salvar}
                onCancelar={() => {
                  setForm(null)
                  setErroForm(null)
                }}
              />
            ) : (
              <CartaoObservacao
                key={o.id}
                o={o}
                moderador={!!dados?.pode_moderar}
                confirmando={confirmar === o.id}
                salvando={salvando}
                historicoAberto={histAberto.has(o.id)}
                onEditar={() => {
                  setForm(formularioDe(o))
                  setErroForm(null)
                  setConfirmar(null)
                }}
                onPedirApagar={() => {
                  setConfirmar(o.id)
                  setForm(null)
                }}
                onCancelarApagar={() => setConfirmar(null)}
                onApagar={() => void apagar(o.id)}
                onHistorico={() =>
                  setHistAberto((s) => {
                    const n = new Set(s)
                    if (n.has(o.id)) n.delete(o.id)
                    else n.add(o.id)
                    return n
                  })
                }
              />
            ),
          )}
          {dados?.pode_moderar && apagadas.length > 0 && (
            <div style={{ margin: '6px 0 10px' }}>
              <button
                type="button"
                onClick={() => setMostrarApagadas((v) => !v)}
                style={{
                  background: 'none',
                  border: 'none',
                  padding: 0,
                  color: 'var(--ops-text)',
                  cursor: 'pointer',
                  font: '500 12px/1.3 var(--f-ui)',
                  textDecoration: 'underline',
                  textUnderlineOffset: 3,
                }}
              >
                {mostrarApagadas
                  ? 'Ocultar apagadas'
                  : `Mostrar apagadas (${apagadas.length}), só Growth vê`}
              </button>
            </div>
          )}
          {mostrarApagadas &&
            apagadas.map((o) => (
              <CartaoObservacao
                key={o.id}
                o={o}
                moderador
                confirmando={false}
                salvando={false}
                historicoAberto={histAberto.has(o.id)}
                onHistorico={() =>
                  setHistAberto((s) => {
                    const n = new Set(s)
                    if (n.has(o.id)) n.delete(o.id)
                    else n.add(o.id)
                    return n
                  })
                }
              />
            ))}
        </>
      )}
      <p
        style={{
          color: 'var(--tx-off)',
          font: '400 11px/1.45 var(--f-ui)',
          marginTop: 16,
          paddingTop: 12,
          borderTop: '1px solid var(--line)',
        }}
      >
        Anotação é informação de campo: não altera score, ranking, carteira nem relatório oficial.
      </p>
    </div>
  )
}

function divergencia(ativas: Observacao[]): string | null {
  const valores = [...new Set(ativas.map((o) => o.metragem_m2).filter((m): m is number => m != null))]
  return valores.length > 1 ? valores.map((m) => `${fmt.format(m)} m²`).join(', ') : null
}

/** As três notas (estrelas de 1 a NOTA_MAXIMA), como MÉDIA das anotações vivas que as deram:
 *  a média em estrelas inteiras e o número exato ao lado. Opinião de campo: o "de N" fica à
 *  vista para uma nota só não se passar por consenso. */
function MediasDasNotas({ ativas }: { ativas: Observacao[] }) {
  const medias = NOTAS.map(([chave, rotulo]) => ({ rotulo, m: mediaDaNota(ativas, chave) })).filter(
    (x) => x.m != null,
  )
  if (!medias.length) return null
  return (
    <div style={{ display: 'grid', gridTemplateColumns: `repeat(${medias.length}, 1fr)`, gap: 8, marginTop: 8 }}>
      {medias.map(({ rotulo, m }) => (
        <Kpi
          key={rotulo}
          valor={`${estrelas(m!.media)} ${m!.media.toLocaleString('pt-BR', { minimumFractionDigits: 1, maximumFractionDigits: 1 })}`}
          rotulo={`${rotulo} · média de ${m!.n}`}
        />
      ))}
    </div>
  )
}

function Kpi({ valor, rotulo }: { valor: string; rotulo: string }) {
  return (
    <div
      style={{
        background: 'var(--surf-raised)',
        border: '1px solid var(--line)',
        borderRadius: 'var(--r-md)',
        padding: '10px 12px',
      }}
    >
      <div style={{ font: '600 20px/1.1 var(--f-titulo)', color: 'var(--tx-max)' }}>{valor}</div>
      <div style={{ color: 'var(--tx-sub)', font: '400 11.5px/1.35 var(--f-ui)', marginTop: 3 }}>
        {rotulo}
      </div>
    </div>
  )
}

function FormularioObservacao({
  form,
  setForm,
  erro,
  salvando,
  rotulo,
  onSalvar,
  onCancelar,
}: {
  form: Formulario
  setForm: (f: Formulario) => void
  erro: string | null
  salvando: boolean
  rotulo: string
  onSalvar: () => void
  onCancelar: () => void
}) {
  const label: React.CSSProperties = {
    display: 'block',
    color: 'var(--tx-label)',
    font: '500 11.5px/1.2 var(--f-ui)',
    marginBottom: 4,
  }
  return (
    <div
      style={{
        background: 'var(--surf-raised)',
        border: '1px solid var(--ac-a24)',
        borderRadius: 'var(--r-md)',
        padding: 12,
        marginBottom: 9,
      }}
    >
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 8, marginBottom: 10 }}>
        <label style={{ display: 'block' }}>
          <span style={label}>Metragem (m²)</span>
          <input
            inputMode="numeric"
            maxLength={DIGITOS_MAXIMOS}
            placeholder="Ex.: 1500"
            value={form.metragem_m2}
            onChange={(e) => setForm({ ...form, metragem_m2: apenasDigitos(e.target.value) })}
          />
        </label>
        <label style={{ display: 'block' }}>
          <span style={label}>Vagas</span>
          <input
            inputMode="numeric"
            maxLength={DIGITOS_MAXIMOS}
            placeholder="Estacionamento"
            value={form.vagas}
            onChange={(e) => setForm({ ...form, vagas: apenasDigitos(e.target.value) })}
          />
        </label>
        <label style={{ display: 'block' }}>
          <span style={label}>Alunos estimados</span>
          <input
            inputMode="numeric"
            maxLength={DIGITOS_MAXIMOS}
            placeholder="Se souber"
            value={form.alunos_estimados}
            onChange={(e) => setForm({ ...form, alunos_estimados: apenasDigitos(e.target.value) })}
          />
        </label>
      </div>
      {NOTAS.map(([chave, rotuloNota]) => (
        <SeletorNota
          key={chave}
          rotulo={rotuloNota}
          valor={form[chave]}
          onMudar={(v) => setForm({ ...form, [chave]: v } as Formulario)}
        />
      ))}
      <p style={{ margin: '0 0 10px', color: 'var(--tx-off)', font: '400 11px/1.3 var(--f-ui)' }}>
        Tocar de novo na mesma estrela apaga a nota.
      </p>
      <label style={{ display: 'block', marginBottom: 10, marginTop: 2 }}>
        <span style={label}>Equipamentos</span>
        <textarea
          rows={2}
          maxLength={TEXTO_MAXIMO}
          placeholder="Marca, quantidade, estado de conservação…"
          value={form.equipamentos}
          onChange={(e) => setForm({ ...form, equipamentos: e.target.value })}
          style={{ resize: 'vertical' }}
        />
      </label>
      <label style={{ display: 'block', marginBottom: 10 }}>
        <span style={label}>Comodidades e aulas coletivas</span>
        <textarea
          rows={2}
          maxLength={TEXTO_MAXIMO}
          placeholder="Vestiário, sauna, piscina, spinning, pilates, grade de aulas…"
          value={form.comodidades}
          onChange={(e) => setForm({ ...form, comodidades: e.target.value })}
          style={{ resize: 'vertical' }}
        />
      </label>
      <label style={{ display: 'block', marginBottom: 10 }}>
        <span style={label}>Comentário</span>
        <textarea
          rows={3}
          maxLength={TEXTO_MAXIMO}
          placeholder="O que você viu ou ouviu sobre esta unidade"
          value={form.comentario}
          onChange={(e) => setForm({ ...form, comentario: e.target.value })}
          style={{ resize: 'vertical' }}
        />
      </label>
      <div
        style={{
          display: 'flex',
          gap: 8,
          font: '400 11.5px/1.4 var(--f-ui)',
          color: 'var(--warn-text)',
          background: 'color-mix(in srgb, var(--warn) 12%, transparent)',
          borderRadius: 'var(--r-sm)',
          padding: '7px 9px',
          marginBottom: 10,
        }}
      >
        <span aria-hidden>⚠</span>
        <span>
          Não escreva nome, telefone ou e-mail de pessoas. A anotação fica visível para todos os
          perfis e não se apaga do histórico.
        </span>
      </div>
      {erro && (
        <p role="alert" style={{ color: 'var(--neg)', font: '500 11.5px/1.4 var(--f-ui)', margin: '0 0 10px' }}>
          {erro}
        </p>
      )}
      <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8 }}>
        <Botao variante="ghost" onClick={onCancelar} disabled={salvando}>
          Cancelar
        </Botao>
        <Botao onClick={onSalvar} disabled={salvando}>
          {salvando ? 'Salvando…' : rotulo}
        </Botao>
      </div>
    </div>
  )
}

/** Nota em estrelas, de 1 a NOTA_MAXIMA: um toque, sem digitar, e sem valor fora da faixa por
 *  construção. Tocar de novo na estrela escolhida apaga a nota (nota é opcional). */
function SeletorNota({
  rotulo,
  valor,
  onMudar,
}: {
  rotulo: string
  valor: number | null
  onMudar: (v: number | null) => void
}) {
  return (
    <div
      style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 6 }}
      role="group"
      aria-label={`${rotulo}, de 1 a ${NOTA_MAXIMA} estrelas`}
    >
      <span style={{ flex: '0 0 92px', color: 'var(--tx-label)', font: '500 11.5px/1.2 var(--f-ui)' }}>
        {rotulo}
      </span>
      <div style={{ display: 'flex', gap: 2 }}>
        {Array.from({ length: NOTA_MAXIMA }, (_, i) => i + 1).map((n) => {
          const cheia = valor != null && n <= valor
          return (
            <button
              key={n}
              type="button"
              aria-pressed={valor === n}
              aria-label={`${n} de ${NOTA_MAXIMA}`}
              title={valor === n ? 'Tocar de novo apaga a nota' : `${n} de ${NOTA_MAXIMA}`}
              onClick={() => onMudar(valor === n ? null : n)}
              style={{
                padding: '0 2px',
                border: 'none',
                background: 'transparent',
                cursor: 'pointer',
                font: '400 22px/1 var(--f-ui)',
                color: cheia ? 'var(--ac)' : 'var(--line-strong)',
              }}
            >
              {cheia ? '★' : '☆'}
            </button>
          )
        })}
      </div>
      <span
        style={{
          font: '500 11.5px/1.2 var(--f-ui)',
          color: valor != null ? 'var(--ac-text)' : 'var(--tx-off)',
        }}
      >
        {valor != null ? `${valor} de ${NOTA_MAXIMA}` : 'sem nota'}
      </span>
    </div>
  )
}

function CartaoObservacao({
  o,
  moderador,
  confirmando,
  salvando,
  historicoAberto,
  onEditar,
  onPedirApagar,
  onCancelarApagar,
  onApagar,
  onHistorico,
}: {
  o: Observacao
  moderador: boolean
  confirmando: boolean
  salvando: boolean
  historicoAberto: boolean
  onEditar?: () => void
  onPedirApagar?: () => void
  onCancelarApagar?: () => void
  onApagar?: () => void
  onHistorico: () => void
}) {
  const n = numeroDoRotulo(o.autor_rotulo)
  const cor = CORES_AVATAR[(n - 1 + CORES_AVATAR.length) % CORES_AVATAR.length]
  const avatar = o.autor_nome
    ? o.autor_nome
        .split(' ')
        .map((p) => p[0])
        .slice(0, 2)
        .join('')
    : String(n)
  const linhas = linhasDaObservacao(o)
  const botaoMini: React.CSSProperties = {
    borderRadius: 'var(--r-sm)',
    padding: '4px 9px',
    font: '500 11.5px/1.2 var(--f-ui)',
    cursor: 'pointer',
    border: '1px solid var(--line-strong)',
    background: 'var(--surf-raised)',
    color: 'var(--tx-soft)',
  }
  const perigo: React.CSSProperties = {
    ...botaoMini,
    color: 'var(--neg)',
    border: '1px solid color-mix(in srgb, var(--neg) 40%, transparent)',
    background: 'color-mix(in srgb, var(--neg) 10%, transparent)',
  }

  return (
    <div
      style={{
        background: 'var(--surf-card)',
        border: `1px ${o.apagada ? 'dashed' : 'solid'} ${o.minha ? 'var(--ac-a24)' : 'var(--line)'}`,
        borderRadius: 'var(--r-md)',
        padding: '11px 12px',
        marginBottom: 9,
        opacity: o.apagada ? 0.65 : 1,
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: 9 }}>
        <div
          aria-hidden
          style={{
            width: 26,
            height: 26,
            borderRadius: '50%',
            display: 'grid',
            placeItems: 'center',
            flex: 'none',
            background: cor,
            color: '#0b1016',
            font: '700 11px/1 var(--f-ui)',
          }}
        >
          {avatar}
        </div>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ font: '600 12.5px/1.25 var(--f-ui)', color: 'var(--tx-max)' }}>
            {o.autor_nome ? (
              <>
                {o.autor_nome}{' '}
                <span style={{ color: 'var(--tx-sub)', fontWeight: 400 }}>· {o.autor_rotulo}</span>
              </>
            ) : (
              o.autor_rotulo
            )}
            {o.minha && <span style={{ color: 'var(--ac-text)', fontWeight: 500 }}> (você)</span>}
          </div>
          <div style={{ color: 'var(--tx-sub)', font: '400 11px/1.3 var(--f-ui)' }}>
            {dataHora(o.criada_em)}
            {o.editada && ` · editada em ${dataHora(o.atualizada_em)}`}
          </div>
        </div>
        {o.apagada && (
          <span
            style={{
              font: '600 10px/1 var(--f-ui)',
              padding: '3px 6px',
              borderRadius: 999,
              color: 'var(--neg)',
              border: '1px solid color-mix(in srgb, var(--neg) 40%, transparent)',
            }}
          >
            apagada
          </span>
        )}
      </div>
      <div style={{ marginTop: 8, display: 'grid', gap: 6 }}>
        {linhas.map(([k, v, destaque]) => (
          <div key={k} style={{ display: 'grid', gridTemplateColumns: '92px 1fr', gap: 8, font: '400 12.5px/1.4 var(--f-ui)' }}>
            <span style={{ color: 'var(--tx-label)' }}>{k}</span>
            <span
              style={{
                color: destaque ? 'var(--tx-max)' : 'var(--tx-soft)',
                fontWeight: destaque ? 600 : 400,
                whiteSpace: 'pre-wrap',
                wordBreak: 'break-word',
              }}
            >
              {v}
            </span>
          </div>
        ))}
      </div>
      {(o.pode_editar || o.pode_apagar || o.historico) && (
        <div style={{ display: 'flex', gap: 6, marginTop: 10, alignItems: 'center', flexWrap: 'wrap' }}>
          {o.pode_editar && onEditar && (
            <button type="button" style={botaoMini} onClick={onEditar}>
              Editar
            </button>
          )}
          {o.pode_apagar && onPedirApagar && (
            <button type="button" style={perigo} onClick={onPedirApagar}>
              {o.minha ? 'Apagar' : 'Apagar (moderação)'}
            </button>
          )}
          <span style={{ flex: 1 }} />
          {o.historico && (
            <button
              type="button"
              onClick={onHistorico}
              style={{
                background: 'none',
                border: 'none',
                padding: 0,
                color: 'var(--ops-text)',
                cursor: 'pointer',
                font: '500 12px/1.3 var(--f-ui)',
                textDecoration: 'underline',
                textUnderlineOffset: 3,
              }}
            >
              {historicoAberto
                ? 'Ocultar histórico'
                : `Histórico (${o.historico.length} ${o.historico.length === 1 ? 'registro' : 'registros'})`}
            </button>
          )}
        </div>
      )}
      {confirmando && (
        <div
          style={{
            marginTop: 10,
            padding: '9px 10px',
            borderRadius: 'var(--r-sm)',
            background: 'color-mix(in srgb, var(--neg) 10%, transparent)',
            border: '1px solid color-mix(in srgb, var(--neg) 30%, transparent)',
            font: '400 12px/1.4 var(--f-ui)',
            color: 'var(--tx-soft)',
          }}
        >
          {o.minha
            ? 'Apagar esta anotação? Ela some para todos, mas continua guardada no histórico.'
            : 'Apagar a anotação de outra pessoa? Ela some para todos, e o histórico registra que foi moderação sua.'}
          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8, marginTop: 8 }}>
            <button type="button" style={botaoMini} onClick={onCancelarApagar} disabled={salvando}>
              Cancelar
            </button>
            <button type="button" style={perigo} onClick={onApagar} disabled={salvando}>
              Apagar
            </button>
          </div>
        </div>
      )}
      {o.apagada && moderador && (
        <div style={{ color: 'var(--ops-text)', font: '400 11.5px/1.4 var(--f-ui)', marginTop: 8 }}>
          Apagada por {o.apagada.por} em {dataHora(o.apagada.em)}
          {o.apagada.moderacao ? ' (moderação)' : ''}.
        </div>
      )}
      {historicoAberto && o.historico && (
        <div
          style={{
            marginTop: 10,
            borderLeft: '2px solid var(--line-strong)',
            paddingLeft: 10,
            display: 'grid',
            gap: 8,
          }}
        >
          {[...o.historico].reverse().map((h, i) => {
            const ant = h.versao_anterior
            const antes = ant
              ? linhasDaObservacao(ant)
                  .map(([k, v]) => `${k}: ${v}`)
                  .join(' · ') || '(vazio)'
              : null
            const verbo = { criada: 'Criada', editada: 'Editada', apagada: 'Apagada' }[h.acao]
            return (
              <div key={i} style={{ font: '400 11.5px/1.4 var(--f-ui)', color: 'var(--tx-sub)' }}>
                <b style={{ color: 'var(--tx-soft)', fontWeight: 600 }}>{verbo}</b> por {h.por}
                {h.moderacao ? ' (moderação)' : ''} · {dataHora(h.em)}
                {antes && (
                  <div style={{ color: 'var(--tx-label)', marginTop: 2, whiteSpace: 'pre-wrap' }}>
                    Antes: {antes}
                  </div>
                )}
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
