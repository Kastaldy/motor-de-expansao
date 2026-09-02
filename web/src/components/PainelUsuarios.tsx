import { useCallback, useEffect, useState } from 'react'

import { api, ApiError } from '../lib/api'
import type { AdminPerfil, AdminUsuario, AdminUsuariosPayload } from '../lib/types'
import { Aviso, Botao, Chip, Spinner } from './primitives'

/* ---------------------------------------------------------------------------
   Administração de usuários (D25) — quem entra, com que perfil.

   POR QUE ESTA TELA EXISTE. Antes do banco, mudar o acesso de alguém era editar o
   `acesso_abas.json` no volume `:rw` — sem rebuild e sem deploy. Com o RBAC no
   banco, a mesma mudança viraria `UPDATE` manual na VPS. Isto desfaz essa regressão.

   O QUE ELA NÃO FAZ, e a tela diz isso em voz alta: criar pessoa. Enquanto o
   Authelia autenticar (P19 decidido, não executado), quem entra no sistema nasce no
   `users_database.yml` do servidor. Uma linha em `usuarios` sem a entrada de lá não
   deixa ninguém entrar — e `senha_hash` é `NOT NULL` sem consumidor, então não há o
   que gravar ali que signifique alguma coisa hoje.

   CADA MUDANÇA É UM EVENTO. O backend grava `usuario.perfil_alterado`,
   `usuario.desativado` e `usuario.reativado` na MESMA transação da mudança, com
   `id_usuario` = quem fez e `entidade_id` = quem sofreu (D24). A tela não precisa
   fazer nada para isso acontecer — mas precisa não mentir sobre o que aconteceu, e é
   por isso que ela recarrega do servidor depois de cada ação em vez de adivinhar o
   novo estado localmente.
   --------------------------------------------------------------------------- */

/** Tom do chip por perfil. Segue a hierarquia da D22: quanto mais alcance, mais quente. */
const TOM_DO_PERFIL: Record<string, 'blue' | 'green' | 'amber' | 'gray'> = {
  consultoria: 'gray',
  expansao: 'blue',
  lideres: 'green',
  growth: 'amber',
}

function rotuloPerfil(perfil: string): string {
  const nomes: Record<string, string> = {
    consultoria: 'Consultoria',
    expansao: 'Expansão',
    lideres: 'Líderes',
    growth: 'Growth',
  }
  return nomes[perfil] ?? perfil
}

/** Mensagem por status. O backend já manda texto útil; aqui só os casos que a tela
 *  precisa enquadrar de outro jeito. */
function mensagemDeErro(e: ApiError): string {
  if (e.status === 404) return 'O painel de acessos não está habilitado para este usuário.'
  if (e.status === 503) return `Banco indisponível — nada foi alterado. ${e.message}`
  return e.message
}

export default function PainelUsuarios() {
  const [dados, setDados] = useState<AdminUsuariosPayload | null>(null)
  const [carregando, setCarregando] = useState(true)
  const [erro, setErro] = useState<string | null>(null)
  /** `id_usuario` em trânsito: desabilita só a linha que está sendo salva. */
  const [salvando, setSalvando] = useState<number | null>(null)
  const [recado, setRecado] = useState<string | null>(null)

  const carregar = useCallback(() => {
    setCarregando(true)
    return api
      .adminUsuarios()
      .then((d) => {
        setDados(d)
        setErro(null)
      })
      .catch((e: ApiError) => {
        setErro(mensagemDeErro(e))
        setDados(null)
      })
      .finally(() => setCarregando(false))
  }, [])

  useEffect(() => {
    void carregar()
  }, [carregar])

  /**
   * Aplica a mudança e RECARREGA do servidor.
   *
   * Não atualiza o estado local por conta própria de propósito. Esta tela decide quem
   * entra onde; mostrar um estado otimista que o banco recusou seria pior que esperar
   * meio segundo — alguém sairia daqui achando que desativou quem continua entrando.
   */
  const aplicar = useCallback(
    async (alvo: AdminUsuario, mudanca: { perfil?: string; ativo?: boolean }) => {
      setSalvando(alvo.id_usuario)
      setRecado(null)
      try {
        const r = await api.adminAlterarUsuario(alvo.id_usuario, mudanca)
        await carregar()
        const trocou = r.perfil?.mudou
        const mudouStatus = r.status?.mudou
        if (trocou) {
          setRecado(
            `${alvo.login}: ${rotuloPerfil(r.perfil!.de)} → ${rotuloPerfil(r.perfil!.para)}.`,
          )
        } else if (mudouStatus) {
          setRecado(`${alvo.login} foi ${r.status!.ativo ? 'reativado' : 'desativado'}.`)
        } else {
          // `mudou: false` = já estava assim. Sucesso sem evento gravado, e a tela
          // não pode chamar isso de alteração.
          setRecado(`${alvo.login} já estava assim — nada foi alterado.`)
        }
      } catch (e) {
        setErro(e instanceof ApiError ? mensagemDeErro(e) : String(e))
      } finally {
        setSalvando(null)
      }
    },
    [carregar],
  )

  if (carregando && !dados) {
    return (
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 8,
          color: 'var(--tx-muted)',
          font: '400 12px/1 var(--f-ui)',
          padding: 18,
        }}
      >
        <Spinner /> Lendo o cadastro de usuários…
      </div>
    )
  }

  if (erro && !dados) {
    return (
      <Aviso
        titulo="Cadastro indisponível"
        corpo={erro}
        acao={
          <Botao variante="ghost" onClick={() => void carregar()}>
            Tentar de novo
          </Botao>
        }
      />
    )
  }

  if (!dados) return null

  const { usuarios, perfis, eu } = dados

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
      {erro && (
        <div
          style={{
            font: '500 11.5px/1.4 var(--f-ui)',
            color: 'var(--tx-max)',
            background: 'rgba(255,90,110,.12)',
            border: '1px solid rgba(255,90,110,.3)',
            borderRadius: 'var(--r-md)',
            padding: '8px 11px',
          }}
        >
          {erro}
        </div>
      )}
      {recado && (
        <div
          style={{
            font: '400 11.5px/1.4 var(--f-ui)',
            color: 'var(--tx-soft)',
            background: 'rgba(60,200,120,.10)',
            border: '1px solid rgba(60,200,120,.25)',
            borderRadius: 'var(--r-md)',
            padding: '8px 11px',
          }}
        >
          {recado}
        </div>
      )}

      <div style={{ overflowX: 'auto' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', minWidth: 620 }}>
          <thead>
            <tr>
              {['Pessoa', 'Login', 'Perfil', 'Situação', ''].map((h) => (
                <th
                  key={h}
                  style={{
                    textAlign: 'left',
                    padding: '0 10px 8px',
                    font: '600 10px/1 var(--f-ui)',
                    letterSpacing: '.08em',
                    textTransform: 'uppercase',
                    color: 'var(--tx-muted)',
                    borderBottom: '1px solid var(--line-soft)',
                    whiteSpace: 'nowrap',
                  }}
                >
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {usuarios.map((u) => {
              const souEu = u.id_usuario === eu
              const travado = souEu || salvando === u.id_usuario
              return (
                <tr
                  key={u.id_usuario}
                  style={{
                    borderBottom: '1px solid var(--line-soft)',
                    // Inativo fica visível, mas apagado: ele existe para ser reativado.
                    opacity: u.ativo ? 1 : 0.55,
                  }}
                >
                  <td style={{ padding: '9px 10px', minWidth: 0 }}>
                    <div
                      style={{
                        font: '600 12px/1.3 var(--f-ui)',
                        color: 'var(--tx-max)',
                        overflow: 'hidden',
                        textOverflow: 'ellipsis',
                      }}
                    >
                      {u.nome}
                      {souEu && (
                        <span
                          style={{
                            marginLeft: 7,
                            font: '500 10px/1 var(--f-ui)',
                            color: 'var(--tx-muted)',
                          }}
                        >
                          você
                        </span>
                      )}
                    </div>
                    <div style={{ font: '400 10.5px/1.3 var(--f-ui)', color: 'var(--tx-muted)' }}>
                      {u.email}
                    </div>
                  </td>
                  <td
                    style={{
                      padding: '9px 10px',
                      font: '500 11.5px/1 var(--f-num)',
                      color: 'var(--tx-soft)',
                      whiteSpace: 'nowrap',
                    }}
                  >
                    {u.login}
                  </td>
                  <td style={{ padding: '9px 10px' }}>
                    <select
                      value={u.perfil}
                      disabled={travado}
                      aria-label={`Perfil de ${u.nome}`}
                      onChange={(ev) => void aplicar(u, { perfil: ev.target.value })}
                      style={{
                        padding: '5px 8px',
                        borderRadius: 'var(--r-sm)',
                        border: '1px solid var(--line-strong)',
                        background: 'var(--surf-chrome)',
                        color: 'var(--tx-max)',
                        font: '500 11.5px/1 var(--f-ui)',
                        cursor: travado ? 'not-allowed' : 'pointer',
                      }}
                    >
                      {perfis.map((p: AdminPerfil) => (
                        <option key={p.perfil} value={p.perfil}>
                          {rotuloPerfil(p.perfil)} ({p.capacidades})
                        </option>
                      ))}
                    </select>
                  </td>
                  <td style={{ padding: '9px 10px', whiteSpace: 'nowrap' }}>
                    <Chip tom={u.ativo ? TOM_DO_PERFIL[u.perfil] ?? 'gray' : 'gray'}>
                      {u.ativo ? 'ativo' : 'inativo'}
                    </Chip>
                  </td>
                  <td style={{ padding: '9px 10px', textAlign: 'right', whiteSpace: 'nowrap' }}>
                    <Botao
                      variante="ghost"
                      disabled={travado}
                      title={
                        souEu
                          ? 'Você não pode alterar o seu próprio acesso por aqui.'
                          : u.ativo
                            ? 'Tira o acesso, preservando o histórico da pessoa.'
                            : 'Devolve o acesso com o perfil que estiver selecionado.'
                      }
                      onClick={() => void aplicar(u, { ativo: !u.ativo })}
                    >
                      {salvando === u.id_usuario ? '…' : u.ativo ? 'Desativar' : 'Reativar'}
                    </Botao>
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>

      <div style={{ font: '400 10.5px/1.5 var(--f-ui)', color: 'var(--tx-muted)' }}>
        Toda mudança aqui fica registrada com autor, data e o de-para — desativar é{' '}
        <strong>reversível</strong> e preserva o histórico da pessoa; nada é apagado.{' '}
        <strong>Criar usuário não é feito por aqui:</strong> quem entra no sistema nasce no
        Authelia, no servidor, e só depois ganha a linha de perfil no banco. O número ao lado
        de cada perfil é quantas coisas ele libera.
      </div>
    </div>
  )
}
