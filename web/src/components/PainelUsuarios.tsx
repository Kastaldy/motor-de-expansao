import { type CSSProperties, useCallback, useEffect, useState } from 'react'

import { api, ApiError } from '../lib/api'
import type {
  AdminPerfil,
  AdminUsuario,
  AdminUsuarioNovo,
  AdminUsuariosPayload,
} from '../lib/types'
import { Aviso, Botao, Chip, Spinner } from './primitives'

/* ---------------------------------------------------------------------------
   Administração de usuários (D25, criação na D26) — quem entra, com que perfil.

   POR QUE ESTA TELA EXISTE. Antes do banco, mudar o acesso de alguém era editar o
   `acesso_abas.json` no volume `:rw` — sem rebuild e sem deploy. Com o RBAC no
   banco, a mesma mudança viraria `UPDATE` manual na VPS. Isto desfaz essa regressão.

   CRIAR PESSOA JÁ É FEITO AQUI (D26), e o que a tela precisa dizer mudou de lugar.
   Quem nasce aqui recebe a SENHA INICIAL COMPARTILHADA (`MOTOR_SENHA_INICIAL` no
   servidor) e é marcado para trocá-la. Não há campo de senha no formulário de
   propósito: o admin não deve conhecer a senha de outra pessoa, senão qualquer ação
   daquela conta fica contestável — o oposto do que o D17 sustenta.

   O QUE AINDA NÃO ESTÁ RESOLVIDO, e a tela diz em voz alta DEPOIS DE CRIAR: enquanto
   o Authelia autenticar (P19 decidido, não executado), a pessoa também precisa nascer
   no `users_database.yml` do servidor. Uma linha em `usuarios` sem a entrada de lá não
   deixa ninguém entrar. Sem esse recado, criar usuário seria uma armadilha silenciosa
   — a pessoa apareceria na lista e não entraria, sem pista do porquê.

   CADA MUDANÇA É UM EVENTO. O backend grava `usuario.criado`,
   `usuario.perfil_alterado`, `usuario.desativado`, `usuario.reativado` e
   `usuario.senha_definida` na MESMA transação da mudança, com `id_usuario` = quem fez
   e `entidade_id` = quem sofreu (D24). A tela não precisa fazer nada para isso
   acontecer — mas precisa não mentir sobre o que aconteceu, e é por isso que ela
   recarrega do servidor depois de cada ação em vez de adivinhar o novo estado.

   A COLUNA SENHA mostra `senha_propria`, não hash nenhum: o payload nunca carrega
   `senha_hash`, nem mascarado. O que a tela precisa saber é se a pessoa já saiu da
   senha inicial, e isso é um booleano.
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
  if (e.status === 503) return `Indisponível — nada foi alterado. ${e.message}`
  return e.message
}

/** Campos vazios do formulário de criação. Fica fora do componente para o
 *  `Cancelar` e o `criar` bem-sucedido zerarem pelo MESMO objeto. */
const NOVO_VAZIO: AdminUsuarioNovo = { login: '', nome: '', email: '', perfil: '' }

const ESTILO_CAMPO: CSSProperties = {
  padding: '6px 9px',
  borderRadius: 'var(--r-sm)',
  border: '1px solid var(--line-strong)',
  background: 'var(--surf-chrome)',
  color: 'var(--tx-max)',
  font: '400 11.5px/1.3 var(--f-ui)',
  width: '100%',
  minWidth: 0,
}

const ESTILO_ROTULO: CSSProperties = {
  font: '600 9.5px/1 var(--f-ui)',
  letterSpacing: '.07em',
  textTransform: 'uppercase',
  color: 'var(--tx-muted)',
  marginBottom: 4,
  display: 'block',
}

export default function PainelUsuarios() {
  const [dados, setDados] = useState<AdminUsuariosPayload | null>(null)
  const [carregando, setCarregando] = useState(true)
  const [erro, setErro] = useState<string | null>(null)
  /** `id_usuario` em trânsito: desabilita só a linha que está sendo salva. */
  const [salvando, setSalvando] = useState<number | null>(null)
  const [recado, setRecado] = useState<string | null>(null)
  /** `null` = formulário fechado. Aberto começa com os quatro campos vazios. */
  const [novo, setNovo] = useState<AdminUsuarioNovo | null>(null)
  const [criando, setCriando] = useState(false)
  /** Login de quem acabou de ser criado, para o recado do Authelia ficar na tela até
   *  ser fechado à mão. Some junto com um novo `criar`, não com o próximo clique. */
  const [criado, setCriado] = useState<string | null>(null)

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

  /**
   * Cria a pessoa e RECARREGA, como o `aplicar`.
   *
   * O recado de sucesso não é decorativo: ele diz o passo que a tela não fez — cadastrar
   * a pessoa no Authelia. Sem isso, criar usuário aqui é uma armadilha silenciosa.
   *
   * Em caso de erro o formulário fica ABERTO com o que foi digitado. Um 409 de login em
   * uso costuma se resolver mudando uma letra, e limpar os campos obrigaria a redigitar
   * tudo para consertar um caractere.
   */
  const criar = useCallback(async () => {
    if (!novo) return
    setCriando(true)
    setRecado(null)
    setCriado(null)
    setErro(null)
    try {
      const r = await api.adminCriarUsuario({
        login: novo.login.trim(),
        nome: novo.nome.trim(),
        email: novo.email.trim(),
        perfil: novo.perfil,
      })
      await carregar()
      setNovo(null)
      setCriado(r.login)
    } catch (e) {
      setErro(e instanceof ApiError ? mensagemDeErro(e) : String(e))
    } finally {
      setCriando(false)
    }
  }, [novo, carregar])

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

      {criado && (
        <div
          style={{
            font: '400 11.5px/1.5 var(--f-ui)',
            color: 'var(--tx-max)',
            background: 'rgba(255,190,60,.12)',
            border: '1px solid rgba(255,190,60,.35)',
            borderRadius: 'var(--r-md)',
            padding: '10px 12px',
            display: 'flex',
            gap: 10,
            alignItems: 'flex-start',
          }}
        >
          <div style={{ flex: 1, minWidth: 0 }}>
            <strong>{criado} foi criado no banco, mas ainda não consegue entrar.</strong>
            <br />
            Falta cadastrar o login <strong>{criado}</strong> no{' '}
            <code style={{ font: '500 11px var(--f-num)' }}>authelia/users_database.yml</code> do
            servidor — é o Authelia que autentica hoje. A senha inicial é a compartilhada do
            piloto, e a pessoa será levada a trocá-la no primeiro acesso.
          </div>
          <Botao variante="ghost" onClick={() => setCriado(null)}>
            Ok
          </Botao>
        </div>
      )}

      {novo === null ? (
        <div>
          <Botao variante="ghost" onClick={() => setNovo({ ...NOVO_VAZIO })}>
            + Novo usuário
          </Botao>
        </div>
      ) : (
        <div
          style={{
            border: '1px solid var(--line-strong)',
            borderRadius: 'var(--r-md)',
            padding: 12,
            display: 'flex',
            flexDirection: 'column',
            gap: 10,
            background: 'var(--surf-sunken, transparent)',
          }}
        >
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))',
              gap: 10,
            }}
          >
            <div>
              <label style={ESTILO_ROTULO} htmlFor="novo-nome">
                Nome
              </label>
              <input
                id="novo-nome"
                style={ESTILO_CAMPO}
                value={novo.nome}
                autoComplete="off"
                onChange={(ev) => setNovo({ ...novo, nome: ev.target.value })}
              />
            </div>
            <div>
              <label style={ESTILO_ROTULO} htmlFor="novo-login">
                Login
              </label>
              <input
                id="novo-login"
                style={ESTILO_CAMPO}
                value={novo.login}
                autoComplete="off"
                spellCheck={false}
                placeholder="igual ao do Authelia"
                onChange={(ev) => setNovo({ ...novo, login: ev.target.value })}
              />
            </div>
            <div>
              <label style={ESTILO_ROTULO} htmlFor="novo-email">
                E-mail
              </label>
              <input
                id="novo-email"
                type="email"
                style={ESTILO_CAMPO}
                value={novo.email}
                autoComplete="off"
                spellCheck={false}
                onChange={(ev) => setNovo({ ...novo, email: ev.target.value })}
              />
            </div>
            <div>
              <label style={ESTILO_ROTULO} htmlFor="novo-perfil">
                Perfil
              </label>
              <select
                id="novo-perfil"
                style={{ ...ESTILO_CAMPO, cursor: 'pointer' }}
                value={novo.perfil}
                onChange={(ev) => setNovo({ ...novo, perfil: ev.target.value })}
              >
                <option value="">Escolha…</option>
                {perfis.map((p: AdminPerfil) => (
                  <option key={p.perfil} value={p.perfil}>
                    {rotuloPerfil(p.perfil)} ({p.capacidades})
                  </option>
                ))}
              </select>
            </div>
          </div>

          <div
            style={{
              display: 'flex',
              gap: 8,
              alignItems: 'center',
              flexWrap: 'wrap',
            }}
          >
            <Botao
              onClick={() => void criar()}
              disabled={
                criando ||
                !novo.nome.trim() ||
                !novo.login.trim() ||
                !novo.email.trim() ||
                !novo.perfil
              }
              title="Cria a pessoa com a senha inicial do piloto, marcada para troca."
            >
              {criando ? 'Criando…' : 'Criar usuário'}
            </Botao>
            <Botao variante="ghost" disabled={criando} onClick={() => setNovo(null)}>
              Cancelar
            </Botao>
            <span style={{ font: '400 10.5px/1.4 var(--f-ui)', color: 'var(--tx-muted)' }}>
              Sem campo de senha de propósito — a pessoa recebe a senha inicial do piloto e
              troca no primeiro acesso.
            </span>
          </div>
        </div>
      )}

      <div style={{ overflowX: 'auto' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', minWidth: 700 }}>
          <thead>
            <tr>
              {['Pessoa', 'Login', 'Perfil', 'Situação', 'Senha', ''].map((h) => (
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
                  <td style={{ padding: '9px 10px', whiteSpace: 'nowrap' }}>
                    {/* `senha_propria`, nunca hash: o payload não carrega `senha_hash`.
                        "inicial" é informação de operação — é quem ainda não saiu da
                        senha compartilhada, e é a fila que a virada do P19 precisa zerar. */}
                    <Chip tom={u.senha_propria ? 'green' : 'amber'}>
                      {u.senha_propria ? 'própria' : 'inicial'}
                    </Chip>
                    {u.senha_propria && u.deve_trocar_senha && (
                      <span
                        style={{
                          marginLeft: 6,
                          font: '500 10px/1 var(--f-ui)',
                          color: 'var(--tx-muted)',
                        }}
                        title="Já definiu uma senha própria, mas está marcada para trocar de novo."
                      >
                        trocar
                      </span>
                    )}
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
        <strong>Criar usuário grava só no banco:</strong> a pessoa também precisa ser cadastrada
        no Authelia, no servidor, senão ela aparece nesta lista e não consegue entrar. A coluna{' '}
        <strong>Senha</strong> diz quem já saiu da senha inicial compartilhada — nenhum hash sai
        do banco para esta tela. O número ao lado de cada perfil é quantas coisas ele libera.
      </div>
    </div>
  )
}
