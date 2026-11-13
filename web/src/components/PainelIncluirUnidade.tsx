import { useState, type CSSProperties } from 'react'

import { ApiError, api } from '../lib/api'
import {
  FORMULARIO_VAZIO,
  avisoDoPrazo,
  coordenadaTexto,
  formularioDaPrevia,
  formularioDaUnidade,
  lerFormulario,
  prazoTexto,
  rotuloMaisPerto,
  unidadesNoPrazo,
  type CamposUnidade,
  type FormularioUnidade,
} from '../lib/inclusao-unidade'
import type { PreviaUnidadeSite, UnidadeSite, UnidadesSitePayload } from '../lib/types'
import { Botao } from './primitives'

/**
 * Incluir unidade Ultra pelo Mapa (DEC-085) — o painel da janela aberta pelo botão "+" do
 * seletor UNIDADES. Só aparece para Growth e Líderes (`pode_incluir`, decidido no servidor).
 *
 * Três passos, e nada é gravado antes do terceiro: o FORMULÁRIO (nome e coordenadas; UF e
 * cidade opcionais), a REVISÃO (o servidor confere e mostra o que vai entrar, sem gravar) e a
 * CONFIRMAÇÃO. Embaixo, as unidades incluídas no último dia, que ainda dá para alterar ou
 * remover; depois do prazo, a correção é por PR. A lógica sem tela está em
 * `lib/inclusao-unidade.ts`.
 */

function mensagem(e: unknown): string {
  if (e instanceof ApiError) {
    if (e.status === 403) return e.message || 'Você não tem permissão para incluir unidades.'
    if (e.status === 503) return 'O banco do piloto não respondeu. Tente novamente em instantes.'
    return e.message
  }
  return 'Não foi possível concluir. Tente novamente.'
}

const rotuloSecao: CSSProperties = {
  font: '600 10.5px/1 var(--f-ui)',
  letterSpacing: '.08em',
  textTransform: 'uppercase',
  color: 'var(--tx-label)',
  margin: '16px 0 8px',
}

const rotuloCampo: CSSProperties = {
  display: 'block',
  color: 'var(--tx-label)',
  font: '500 11.5px/1.2 var(--f-ui)',
  marginBottom: 4,
}

const cartao: CSSProperties = {
  background: 'var(--surf-raised)',
  border: '1px solid var(--ac-a24)',
  borderRadius: 'var(--r-md)',
  padding: 12,
  marginBottom: 9,
}

const dica: CSSProperties = { margin: '4px 0 0', color: 'var(--tx-off)', font: '400 11px/1.35 var(--f-ui)' }

const erroEstilo: CSSProperties = { color: 'var(--neg)', font: '500 12px/1.4 var(--f-ui)', margin: '0 0 10px' }

type Etapa = { tipo: 'formulario' } | { tipo: 'revisao'; campos: CamposUnidade; previa: PreviaUnidadeSite }

export default function PainelIncluirUnidade({
  dados,
  onMudou,
  onIncluida,
}: {
  dados: UnidadesSitePayload
  /** a lista do servidor mudou (incluiu, alterou, removeu): o Mapa refaz o seletor */
  onMudou: (payload: UnidadesSitePayload) => void
  /** a unidade recém-incluída: o Mapa a abre e leva a câmera até ela */
  onIncluida?: (u: UnidadeSite) => void
}) {
  const [form, setForm] = useState<FormularioUnidade>(FORMULARIO_VAZIO)
  const [etapa, setEtapa] = useState<Etapa>({ tipo: 'formulario' })
  const [editando, setEditando] = useState<UnidadeSite | null>(null)
  const [removendo, setRemovendo] = useState<UnidadeSite | null>(null)
  const [erro, setErro] = useState<string | null>(null)
  const [ocupado, setOcupado] = useState(false)
  const [salva, setSalva] = useState<string | null>(null)

  const noPrazo = unidadesNoPrazo(dados.unidades)

  const recomecar = () => {
    setForm(FORMULARIO_VAZIO)
    setEtapa({ tipo: 'formulario' })
    setEditando(null)
    setErro(null)
  }

  const revisar = async () => {
    setSalva(null)
    const leitura = lerFormulario(form)
    if (!leitura.ok) {
      setErro(leitura.erro)
      return
    }
    setOcupado(true)
    setErro(null)
    try {
      const previa = await api.unidadeSitePrevia(leitura.campos)
      // O que vai para a gravação é o que a pessoa VIU na revisão. UF e cidade, o servidor tira
      // do ponto de novo ao gravar.
      setEtapa({ tipo: 'revisao', previa, campos: { unidade: previa.unidade, lat: previa.lat, lng: previa.lng } })
    } catch (e) {
      setErro(mensagem(e))
    } finally {
      setOcupado(false)
    }
  }

  const confirmar = async () => {
    if (etapa.tipo !== 'revisao') return
    setOcupado(true)
    setErro(null)
    try {
      if (editando) {
        const payload = await api.unidadeSiteAlterar(editando.id, etapa.campos)
        onMudou(payload)
        setSalva(`${etapa.campos.unidade}: alteração salva.`)
      } else {
        const payload = await api.unidadeSiteIncluir(etapa.campos)
        onMudou(payload)
        setSalva(`${etapa.campos.unidade} entrou no mapa.`)
        if (payload.incluida) onIncluida?.(payload.incluida)
      }
      recomecar()
    } catch (e) {
      setErro(mensagem(e))
    } finally {
      setOcupado(false)
    }
  }

  const remover = async (u: UnidadeSite) => {
    setOcupado(true)
    setErro(null)
    setSalva(null)
    try {
      onMudou(await api.unidadeSiteRemover(u.id))
      setSalva(`${u.unidade} saiu do mapa.`)
      setRemovendo(null)
      if (editando?.id === u.id) recomecar()
    } catch (e) {
      setErro(mensagem(e))
    } finally {
      setOcupado(false)
    }
  }

  const alterar = (u: UnidadeSite) => {
    setEditando(u)
    setForm(formularioDaUnidade(u))
    setEtapa({ tipo: 'formulario' })
    setErro(null)
    setSalva(null)
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', paddingBottom: 12 }}>
      <div style={{ ...rotuloSecao, marginTop: 2 }}>
        {editando ? `Alterar ${editando.unidade}` : 'Nova unidade'}
      </div>

      {salva && (
        <p role="status" style={{ color: 'var(--pos)', font: '500 12px/1.4 var(--f-ui)', margin: '0 0 10px' }}>
          {salva}
        </p>
      )}

      {etapa.tipo === 'formulario' ? (
        <div style={cartao}>
          <label style={{ display: 'block', marginBottom: 10 }}>
            <span style={rotuloCampo}>Nome da unidade</span>
            <input
              maxLength={120}
              placeholder="Como vai aparecer no pino (ex.: Teresópolis)"
              value={form.unidade}
              onChange={(e) => setForm({ ...form, unidade: e.target.value })}
            />
          </label>
          <label style={{ display: 'block', marginBottom: 10 }}>
            <span style={rotuloCampo}>Coordenadas</span>
            <input
              placeholder="-22.407291, -42.965760"
              value={form.coordenadas}
              onChange={(e) => setForm({ ...form, coordenadas: e.target.value })}
            />
            <p style={{ ...dica, marginBottom: 12 }}>
              Latitude e longitude, como o Google Maps copia ao clicar com o botão direito no ponto. O link
              do mapa também serve. O estado e a cidade saem do ponto, e você confere na revisão.
            </p>
          </label>
          {erro && (
            <p role="alert" style={erroEstilo}>
              {erro}
            </p>
          )}
          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8 }}>
            {editando && (
              <Botao variante="ghost" onClick={recomecar} disabled={ocupado}>
                Cancelar
              </Botao>
            )}
            <Botao onClick={() => void revisar()} disabled={ocupado}>
              {ocupado ? 'Conferindo…' : 'Revisar →'}
            </Botao>
          </div>
        </div>
      ) : (
        <div style={{ ...cartao, border: '1px solid var(--ac)' }}>
          <div style={{ font: '600 12px/1.2 var(--f-ui)', color: 'var(--tx-label)', marginBottom: 8 }}>
            {editando ? 'Confirme a alteração' : 'Confirme a inclusão'} — nada foi gravado ainda
          </div>
          <div style={{ font: '600 15px/1.25 var(--f-ui)', color: 'var(--tx-strong)' }}>{etapa.previa.unidade}</div>
          <div style={{ color: 'var(--tx-sub)', font: '400 12.5px/1.4 var(--f-ui)', marginBottom: 8 }}>
            {etapa.previa.cidade}/{etapa.previa.uf}
          </div>
          <div className="num" style={{ color: 'var(--tx-sub)', font: '400 12px/1.4 var(--f-num)', marginBottom: 8 }}>
            {coordenadaTexto(etapa.previa.lat, etapa.previa.lng)}
          </div>
          <div style={{ color: 'var(--tx-sub)', font: '400 12.5px/1.4 var(--f-ui)', marginBottom: 10 }}>
            {etapa.previa.mais_perto
              ? `Unidade Ultra mais perto: ${rotuloMaisPerto(etapa.previa.mais_perto)}.`
              : 'Nenhuma outra unidade Ultra no cadastro deste país.'}
          </div>
          <p style={{ ...dica, margin: '0 0 12px' }}>{avisoDoPrazo(etapa.previa.prazo_horas)}</p>
          {erro && (
            <p role="alert" style={erroEstilo}>
              {erro}
            </p>
          )}
          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8 }}>
            <Botao
              variante="ghost"
              onClick={() => {
                setForm(formularioDaPrevia(etapa.previa))
                setEtapa({ tipo: 'formulario' })
                setErro(null)
              }}
              disabled={ocupado}
            >
              ← Corrigir
            </Botao>
            <Botao onClick={() => void confirmar()} disabled={ocupado}>
              {ocupado ? 'Salvando…' : editando ? 'Confirmar alteração' : 'Confirmar inclusão'}
            </Botao>
          </div>
        </div>
      )}

      <div style={rotuloSecao}>Incluídas pelo site (podem mudar por {dados.prazo_horas === 24 ? '1 dia' : `${dados.prazo_horas} h`})</div>
      {noPrazo.length === 0 ? (
        <p style={{ ...dica, marginTop: 0 }}>Nenhuma unidade incluída pelo site ainda está no prazo de alteração.</p>
      ) : (
        noPrazo.map((u) => (
          <div key={u.id} style={{ ...cartao, padding: 10 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8, alignItems: 'baseline' }}>
              <div>
                <div style={{ font: '600 13px/1.25 var(--f-ui)', color: 'var(--tx-strong)' }}>{u.unidade}</div>
                <div style={{ color: 'var(--tx-sub)', font: '400 12px/1.35 var(--f-ui)' }}>
                  {u.cidade}/{u.uf}
                </div>
              </div>
              <div style={{ color: 'var(--tx-off)', font: '400 11px/1.3 var(--f-ui)', textAlign: 'right' }}>
                {u.incluida_por ? `por ${u.incluida_por}` : null}
                <br />
                {prazoTexto(u.prazo_ate)}
              </div>
            </div>
            {removendo?.id === u.id ? (
              <div style={{ marginTop: 8 }}>
                <p style={{ ...dica, margin: '0 0 8px', color: 'var(--tx-sub)' }}>
                  Remover {u.unidade}? A unidade sai do mapa e da busca. Fica registrado quem removeu.
                </p>
                <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8 }}>
                  <Botao variante="ghost" onClick={() => setRemovendo(null)} disabled={ocupado}>
                    Cancelar
                  </Botao>
                  <Botao onClick={() => void remover(u)} disabled={ocupado}>
                    {ocupado ? 'Removendo…' : 'Remover'}
                  </Botao>
                </div>
              </div>
            ) : (
              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8, marginTop: 8 }}>
                <Botao variante="ghost" onClick={() => alterar(u)} disabled={ocupado}>
                  Alterar
                </Botao>
                <Botao variante="ghost" onClick={() => setRemovendo(u)} disabled={ocupado}>
                  Remover
                </Botao>
              </div>
            )}
          </div>
        ))
      )}
    </div>
  )
}
