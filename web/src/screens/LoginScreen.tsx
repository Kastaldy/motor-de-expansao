import { useEffect, useId, useRef, useState } from 'react'

import MalhaBrasil from '../components/login/MalhaBrasil'
/* O logo entra por IMPORT, e não pelo caminho `/logo-ultra.png` que o Dock usa.

   MUDA NO CORTE DO P19 (DEC-067): a partir dele esta tela é servida pelo host do PILOTO
   (`deploy/caddy/piloto-br.Caddyfile.template`) e fala com o NOSSO backend. O `auth.`
   continua existindo — a instância AR depende dele. O parágrafo abaixo descreve o estado
   de ANTES do corte, e o que ele diz sobre origem/cookie segue valendo nos dois.

   Esta tela é servida na raiz de `auth.ultra-expansao.tech`, onde só a página e o
   prefixo `entrar-assets/` vêm do nosso container — a raiz do host pertence ao
   Authelia. Um `src="/logo-ultra.png"` cairia lá e o logo sumiria EM PRODUÇÃO, sem
   nada quebrar em desenvolvimento. Resolvido no build, o caminho não tem como estar
   errado no ar sem antes quebrar o build.

   O arquivo é uma CÓPIA de `public/logo-ultra.png` com a extensão que o conteúdo pede
   (é AVIF por dentro — a mesma armadilha que o `portal/index.html` documenta). São
   7 KB duplicados para que o piloto não precise mudar de caminho por causa desta tela. */
import logoUltra from '../assets/logo-ultra.avif'
import {
  MENSAGEM_FALHA,
  normalizarUsuario,
  podeEnviar,
  type EstadoEnvio,
  type FalhaLogin,
} from '../lib/login'
import { censoDaBase, procedenciaCurta } from '../lib/rodape-base'
import { useUfsDaBase } from '../lib/base-contexto'

/**
 * Tela de ENTRAR do piloto — o cartão flutuante do mockup "Login · cartão flutuante".
 *
 * O QUE ELA AINDA NÃO É. Ela não autentica ninguém. Quem autentica hoje é o Authelia,
 * na borda, com a própria tela dele; esta aqui existe pronta para o momento em que essa
 * decisão for tomada — seja apontando o `submit` para a API do Authelia, seja para o
 * motor depois do corte do P19. O `onEntrar` chega por prop exatamente por isso: é o
 * único ponto que muda entre os dois destinos.
 *
 * As decisões de segurança que a tela já respeita, e que não são pintura:
 *
 *  - a mensagem de credencial é AMBÍGUA entre usuário e senha, de propósito;
 *  - o bloqueio por tentativas tem mensagem PRÓPRIA: traduzi-lo como "senha errada"
 *    deixaria a pessoa repetindo a senha certa enquanto a trava dura. A régua é a do
 *    NOSSO servidor desde 25/09/2026 — `MAX_TENTATIVAS` recusas numa janela MÓVEL de
 *    `JANELA_TENTATIVAS_MIN` minutos (`lib/login-motor.ts`, espelhando `db/sessoes.py`).
 *    Até essa data este comentário descrevia o `regulation` do Authelia (4 erros em
 *    2 min, banimento de 10 min), que deixa de existir no corte;
 *  - campo vazio não vai ao servidor, para não gastar uma das tentativas da trava;
 *  - o `<form>` é `<form>` de verdade, com `type="submit"`: o Enter no campo de senha
 *    precisa entrar, e gerenciador de senha precisa reconhecer o par.
 *
 * "Esqueci minha senha" ficou FORA (Felipe, 2026-09-22): não há autoatendimento — o
 * time é pequeno e ele redefine. Um link para uma rota que não existe seria pior que a
 * ausência dele.
 */
export default function LoginScreen({
  onEntrar,
}: {
  /**
   * Executa a tentativa. Devolve a falha a exibir, ou `null` quando entrou — quem
   * navega depois é quem passou a função, porque o destino depende de quem autentica.
   */
  onEntrar: (usuario: string, senha: string, manterConectado: boolean) => Promise<FalhaLogin | null>
}) {
  const ufs = useUfsDaBase()
  const [usuario, setUsuario] = useState('')
  const [senha, setSenha] = useState('')
  const [manter, setManter] = useState(false)
  const [verSenha, setVerSenha] = useState(false)
  const [estado, setEstado] = useState<EstadoEnvio>('parado')
  const [falha, setFalha] = useState<FalhaLogin | null>(null)

  const idUsuario = useId()
  const idSenha = useId()
  const idErro = useId()
  /*
   * AUTOFILL x ESTADO DO REACT (relato do Vinicius, 2026-09-24: "ao recarregar a
   * sessão, quando os dados já estão preenchidos automaticamente, o botão de entrar
   * aparece como não-clicável").
   *
   * O navegador (e o gerenciador de senhas) escreve o valor DIRETO no DOM e NÃO
   * dispara o `change` que o React escuta. Então `usuario`/`senha` continuavam `''`,
   * `podeEnviar` devolvia falso e o botão nascia `disabled` e apagado — sobre campos
   * visivelmente preenchidos. O botão estava mentindo sobre o próprio formulário.
   *
   * A 1ª tentativa (24/09) lia o DOM e sincronizava o estado. NÃO RESOLVEU, e o
   * relato seguinte explicou por quê: "o botão só fica azul depois que eu clico na
   * tela, independente de onde seja o clique". O Chrome preenche os campos na carga,
   * mas SEGURA o valor da senha até haver um GESTO do usuário — antes disso
   * `input.value` devolve string vazia. Ler o DOM lia vazio; ler mais vezes leria
   * vazio mais vezes. E o clique em qualquer lugar é justamente o gesto que libera.
   *
   * A correção certa NÃO DEPENDE DO VALOR. Ela detecta que o campo ESTÁ
   * autopreenchido e trata isso como "tem conteúdo":
   *
   *  1. `animationstart` — o Chrome aplica `:-webkit-autofill` ao preencher, e o
   *     `global.css` pendura ali uma animação sem efeito visual só para virar evento.
   *     É o aviso que funciona mesmo com o valor ainda ilegível.
   *  2. `matches(':-webkit-autofill')` na montagem e em alguns quadros seguintes —
   *     rede de segurança para quando o preenchimento acontece antes de a tela montar
   *     e o evento se perde.
   *
   * O valor de verdade é lido no ENVIO, direto do DOM: lá o clique já aconteceu e o
   * navegador o entrega. Por isso `enviar` não usa o estado do React.
   *
   * A trava "campo vazio não vai ao servidor" fica de pé: sem autofill nada muda, e
   * ela existe para não gastar uma das tentativas da trava do servidor (`MAX_TENTATIVAS`,
   * em `lib/login-motor.ts`) antes de
   * barrar a conta ate' a tentativa mais antiga envelhecer na janela.
   */
  const refUsuario = useRef<HTMLInputElement>(null)
  const refSenha = useRef<HTMLInputElement>(null)
  const [auto, setAuto] = useState<{ usuario?: boolean; senha?: boolean }>({})

  useEffect(() => {
    const olhar = () => {
      const marcado = (el: HTMLInputElement | null) => {
        // O seletor é específico do WebKit/Blink: em navegador que não o conhece o
        // `matches` LANÇA, e sem o try o efeito derrubaria a tela inteira.
        try {
          return el?.matches(':-webkit-autofill') ?? false
        } catch {
          return false
        }
      }
      const u = marcado(refUsuario.current)
      const p = marcado(refSenha.current)
      // Só sobe: o autofill não se desfaz sozinho, e um `false` tardio apagaria um
      // `true` legítimo vindo do `animationstart`.
      if (u || p) setAuto((a) => ({ usuario: a.usuario || u, senha: a.senha || p }))
      // Quando o valor JÁ é legível (depois do gesto, ou em navegador sem a trava),
      // aproveita e sincroniza — mantém o estado fiel para quem depois edita o campo.
      const vu = refUsuario.current?.value ?? ''
      const vs = refSenha.current?.value ?? ''
      if (vu) setUsuario((atual) => (atual === vu ? atual : vu))
      if (vs) setSenha((atual) => (atual === vs ? atual : vs))
    }
    olhar()
    const timers = [60, 150, 300, 600, 1000].map((ms) => window.setTimeout(olhar, ms))
    return () => timers.forEach(window.clearTimeout)
  }, [])

  const aoAutoPreencher = (e: React.AnimationEvent<HTMLInputElement>) => {
    if (e.animationName !== 'aviso-autofill') return
    const alvo = e.currentTarget
    if (alvo === refUsuario.current) setAuto((a) => ({ ...a, usuario: true }))
    if (alvo === refSenha.current) setAuto((a) => ({ ...a, senha: true }))
    // Se o valor já vier legível, guarda; se vier vazio, o `auto` acima já sustenta
    // o botão e o envio lê o DOM.
    if (alvo.value) {
      if (alvo === refUsuario.current) setUsuario(alvo.value)
      if (alvo === refSenha.current) setSenha(alvo.value)
    }
  }

  const habilitado = podeEnviar(usuario, senha, estado, auto)
  const selo = procedenciaCurta(ufs) ?? censoDaBase()

  async function enviar(e: React.FormEvent) {
    e.preventDefault()
    if (!habilitado) return
    /* Lê do DOM, não do estado. Com autofill o estado pode estar VAZIO — o navegador
       só entrega o valor depois de um gesto, e o clique que disparou este envio é
       exatamente esse gesto. Cai no estado quando o ref não existe (teste/SSR). */
    const usuarioEnviado = refUsuario.current?.value || usuario
    const senhaEnviada = refSenha.current?.value || senha
    if (!usuarioEnviado.trim() || !senhaEnviada) {
      // O autofill prometeu conteúdo e o DOM não entregou: não gasta uma das
      // tentativas da trava do servidor (`MAX_TENTATIVAS`, em `lib/login-motor.ts`).
      setFalha('credencial')
      return
    }
    setEstado('enviando')
    setFalha(null)
    try {
      setFalha(await onEntrar(normalizarUsuario(usuarioEnviado), senhaEnviada, manter))
    } catch {
      // Exceção não tratada é INDISPONÍVEL, nunca credencial — ver `falhaDoStatus`.
      setFalha('indisponivel')
    } finally {
      setEstado('parado')
    }
  }

  return (
    <div
      style={{
        position: 'absolute',
        inset: 0,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        overflow: 'auto',
        padding: 24,
        boxSizing: 'border-box',
        background:
          'radial-gradient(ellipse at 50% 40%, var(--bg-lift) 0%, var(--bg-base) 62%)',
      }}
    >
      {/* Malha esvaecida ao fundo, sangrando para fora da tela — a mesma arte do painel,
          com id de gradiente próprio (ver `MalhaBrasil`). */}
      <div
        aria-hidden
        style={{ position: 'absolute', inset: -70, opacity: 0.11, pointerEvents: 'none' }}
      >
        <MalhaBrasil idBrilho="brilho-fundo" />
      </div>

      <div
        style={{
          position: 'relative',
          display: 'grid',
          /* Duas colunas enquanto couberem; abaixo disso o painel some (ver a regra no
             fim do arquivo) e sobra o formulário, que é o que a tela precisa entregar. */
          gridTemplateColumns: 'minmax(0, 620px) minmax(0, 540px)',
          width: 'min(1160px, 100%)',
          borderRadius: 24,
          border: '1px solid var(--line)',
          background: 'var(--surf-panel)',
          boxShadow: 'var(--sh-frame)',
          overflow: 'hidden',
          backdropFilter: 'blur(14px)',
        }}
        className="cartao-entrar"
      >
        {/* ---------------- Formulário ---------------- */}
        <section
          style={{
            boxSizing: 'border-box',
            /* 56 em cima e embaixo contra 60 nas laterais: o mockup usava 44, e com o
               conteúdo real (logo + hero + dois campos + caixa + botão + rodapé) ele
               encostava nas duas bordas. Quase quadrado no respiro é o que faz o cartão
               ler como proporcional. */
            padding: '56px 60px',
            display: 'flex',
            flexDirection: 'column',
            gap: 28,
          }}
        >
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
              {/* O logo REAL, o mesmo arquivo que o Dock serve (`Dock.tsx`). O mockup
                  desenhava um quadrado turquesa escrito "ultra" porque era mockup.

                  Fundo BRANCO e `objectFit: cover`, como no Dock: a arte tem fundo
                  próprio, e deixá-la sobre a superfície do cartão a faria sumir no tema
                  claro. (O arquivo chama-se `.png` e é AVIF por dentro — o navegador
                  resolve pelo conteúdo; é assim que o Dock já o serve.) */}
              <span
                style={{
                  width: 44,
                  height: 44,
                  borderRadius: 13,
                  overflow: 'hidden',
                  background: '#fff',
                  display: 'grid',
                  placeItems: 'center',
                  flexShrink: 0,
                }}
              >
                <img
                  src={logoUltra}
                  alt="Ultra Academia"
                  style={{ width: '100%', height: '100%', objectFit: 'cover' }}
                />
              </span>
              <span
                style={{
                  font: '700 20px/1 var(--f-ui)',
                  letterSpacing: '-.01em',
                  color: 'var(--tx-max)',
                }}
              >
                Ultra Academia
              </span>
            </div>
            <p
              style={{
                margin: '10px 0 0',
                font: '400 13px/1.4 var(--f-ui)',
                letterSpacing: '.02em',
                color: 'var(--tx-narrative)',
              }}
            >
              Motor de Expansão
            </p>
          </div>

          <form onSubmit={enviar} style={{ display: 'flex', flexDirection: 'column', gap: 22 }}>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
              <span
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: 8,
                  font: '600 11px/1 var(--f-num)',
                  letterSpacing: '.12em',
                  textTransform: 'uppercase',
                  color: 'var(--ac-text)',
                }}
              >
                <span
                  aria-hidden
                  style={{ width: 6, height: 6, borderRadius: '50%', background: 'var(--ac)' }}
                />
                Acesso restrito
              </span>
              <h1
                className="story"
                style={{
                  margin: 0,
                  font: '400 32px/1.15 var(--f-story)',
                  color: 'var(--tx-max)',
                }}
              >
                Entrar no sistema
              </h1>
              <p
                style={{
                  margin: 0,
                  font: '400 15px/1.55 var(--f-ui)',
                  color: 'var(--tx-narrative)',
                }}
              >
                Use o usuário e a senha da sua conta Ultra.
              </p>
            </div>

            <Campo rotulo="Usuário" id={idUsuario}>
              <IconeUsuario />
              <input
                id={idUsuario}
                ref={refUsuario}
                onAnimationStart={aoAutoPreencher}
                name="username"
                type="text"
                value={usuario}
                onChange={(e) => setUsuario(e.target.value)}
                placeholder="nome.sobrenome"
                autoComplete="username"
                autoCapitalize="none"
                autoCorrect="off"
                spellCheck={false}
                required
                aria-invalid={falha === 'credencial'}
                aria-describedby={falha ? idErro : undefined}
                style={ENTRADA}
              />
            </Campo>

            <Campo rotulo="Senha" id={idSenha}>
              <IconeCadeado />
              <input
                id={idSenha}
                ref={refSenha}
                onAnimationStart={aoAutoPreencher}
                name="password"
                type={verSenha ? 'text' : 'password'}
                value={senha}
                onChange={(e) => setSenha(e.target.value)}
                placeholder="••••••••"
                autoComplete="current-password"
                required
                aria-invalid={falha === 'credencial'}
                aria-describedby={falha ? idErro : undefined}
                style={ENTRADA}
              />
              <button
                type="button"
                onClick={() => setVerSenha((v) => !v)}
                aria-label={verSenha ? 'Ocultar senha' : 'Mostrar senha'}
                aria-pressed={verSenha}
                style={{
                  width: 44,
                  height: 44,
                  border: 0,
                  background: 'transparent',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  borderRadius: 10,
                  cursor: 'pointer',
                  color: 'var(--tx-narrative)',
                  flexShrink: 0,
                }}
              >
                <IconeOlho cortado={verSenha} />
              </button>
            </Campo>

            {/* O erro fica ENTRE os campos e o botão, e é `role="alert"`: quem usa leitor
                de tela precisa ouvi-lo sem ir procurar, e quem não usa precisa vê-lo sem
                rolar. `aria-describedby` amarra os dois campos a ele. */}
            {falha && (
              <p
                id={idErro}
                role="alert"
                style={{
                  margin: 0,
                  padding: '10px 12px',
                  borderRadius: 'var(--r-md)',
                  border: '1px solid var(--neg)',
                  background: 'var(--surf-raised)',
                  font: '500 13px/1.5 var(--f-ui)',
                  color: 'var(--neg)',
                }}
              >
                {MENSAGEM_FALHA[falha]}
              </p>
            )}

            <label
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 10,
                minHeight: 44,
                font: '400 14px/1.3 var(--f-ui)',
                color: 'var(--tx-narrative)',
                cursor: 'pointer',
                width: 'fit-content',
              }}
            >
              <input
                type="checkbox"
                checked={manter}
                onChange={(e) => setManter(e.target.checked)}
                style={{
                  appearance: 'none',
                  WebkitAppearance: 'none',
                  width: 18,
                  height: 18,
                  margin: 0,
                  background: manter ? 'var(--ac)' : 'var(--surf-input)',
                  border: `1px solid ${manter ? 'var(--ac)' : 'var(--line-strong)'}`,
                  borderRadius: 5,
                  cursor: 'pointer',
                }}
              />
              Manter conectado
            </label>

            <button
              type="submit"
              disabled={!habilitado}
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                gap: 8,
                height: 52,
                border: 0,
                borderRadius: 12,
                background: habilitado ? 'var(--ac)' : 'var(--surf-pending)',
                color: habilitado ? 'var(--ac-on)' : 'var(--tx-off)',
                font: '800 15px/1 var(--f-ui)',
                cursor: habilitado ? 'pointer' : 'default',
                transition: 'background .15s ease',
              }}
            >
              {estado === 'enviando' ? 'Entrando…' : 'Entrar'}
              {estado === 'parado' && (
                <svg
                  width="18"
                  height="18"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="1.8"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  aria-hidden
                >
                  <path d="M5 12h14" />
                  <path d="M13 6l6 6-6 6" />
                </svg>
              )}
            </button>
          </form>

          <p
            style={{
              margin: 'auto 0 0',
              font: '400 13px/1.5 var(--f-ui)',
              color: 'var(--tx-sub)',
            }}
          >
            Problemas para acessar? Fale com o time de Estratégia &amp; Growth.
          </p>
        </section>

        {/* ---------------- Painel ---------------- */}
        <section
          className="painel-entrar"
          style={{
            position: 'relative',
            overflow: 'hidden',
            background: 'var(--bg-lift)',
            borderLeft: '1px solid var(--line)',
            minHeight: 600,
          }}
        >
          <div style={{ position: 'absolute', top: 26, right: 30, bottom: 178, left: 30 }}>
            <MalhaBrasil idBrilho="brilho-painel" />
          </div>

          {/* SELO de procedência. Servida em `auth.`, a tela não fala com o nosso
              backend — quem está aqui ainda não entrou, e `/api/ufs` está atrás do
              login. Sem a lista, a contagem de estados não existe e o selo cai no
              crédito do censo sozinho, que é fato do PERFIL e não da base. Some por
              inteiro se nem isso for conhecido, em vez de anunciar "0 estados". */}
          {selo && (
            <div
              style={{
                position: 'absolute',
                top: 22,
                right: 22,
                display: 'flex',
                alignItems: 'center',
                gap: 8,
                padding: '8px 14px',
                border: '1px solid var(--line)',
                borderRadius: 999,
                background: 'var(--surf-card)',
                font: '400 12px/1 var(--f-ui)',
                color: 'var(--tx-narrative)',
              }}
            >
              <span
                aria-hidden
                style={{ width: 6, height: 6, borderRadius: 3, background: 'var(--ac)' }}
              />
              {selo}
            </div>
          )}

          <div
            style={{
              position: 'absolute',
              left: 44,
              right: 32,
              bottom: 44,
              display: 'flex',
              flexDirection: 'column',
              gap: 10,
            }}
          >
            <h2
              className="story"
              style={{ margin: 0, font: '400 34px/1.08 var(--f-story)', color: 'var(--tx-max)' }}
            >
              Motor de Expansão
            </h2>
            <p
              style={{
                margin: 0,
                font: '400 14px/1.55 var(--f-ui)',
                color: 'var(--tx-narrative)',
              }}
            >
              Território, mercado e rede lidos sobre a mesma base, do Brasil inteiro até um
              endereço.
            </p>
          </div>
        </section>
      </div>
    </div>
  )
}

/* ---------------------------------------------------------------------------
   Peças
   --------------------------------------------------------------------------- */

/* O campo é só o texto: quem desenha a caixa é o `Campo` em volta dele.

   `padding` e `borderRadius` ZERADOS de propósito. A regra global de `input`
   (`styles/global.css`) dá recheio e raio a todo campo do app, e aqui isso desenhava
   um retângulo arredondado DENTRO da caixa — invisível enquanto o fundo é
   transparente, e escancarado no instante em que o navegador pinta o autopreenchimento.
   Era a "cor diferente da própria caixa" que apareceu na revisão de 2026-09-22. */
const ENTRADA: React.CSSProperties = {
  flexGrow: 1,
  minWidth: 0,
  height: 44,
  padding: 0,
  background: 'transparent',
  border: 0,
  borderRadius: 0,
  outline: 'none',
  font: '400 15px/1 var(--f-ui)',
  color: 'var(--tx-max)',
}

/** Rótulo + a caixa que envolve ícone, campo e (na senha) o botão de mostrar. */
function Campo({
  rotulo,
  id,
  children,
}: {
  rotulo: string
  id: string
  children: React.ReactNode
}) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
      <label htmlFor={id} style={{ font: '600 13px/1 var(--f-ui)', color: 'var(--tx-max)' }}>
        {rotulo}
      </label>
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 12,
          height: 52,
          padding: '0 8px 0 16px',
          background: 'var(--surf-input)',
          border: '1px solid var(--line-strong)',
          borderRadius: 12,
          boxSizing: 'border-box',
        }}
      >
        {children}
      </div>
    </div>
  )
}

function IconeUsuario() {
  return (
    <svg
      width="18"
      height="18"
      viewBox="0 0 24 24"
      fill="none"
      stroke="var(--tx-narrative)"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden
      style={{ flexShrink: 0 }}
    >
      <circle cx="12" cy="8" r="4" />
      <path d="M4 21a8 8 0 0116 0" />
    </svg>
  )
}

function IconeCadeado() {
  return (
    <svg
      width="18"
      height="18"
      viewBox="0 0 24 24"
      fill="none"
      stroke="var(--tx-narrative)"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden
      style={{ flexShrink: 0 }}
    >
      <rect x="5" y="11" width="14" height="9" rx="2" />
      <path d="M8 11V8a4 4 0 018 0v3" />
    </svg>
  )
}

/** O olho ganha a barra quando a senha está VISÍVEL — o ícone mostra o estado atual,
 *  não a ação. Sem a barra, os dois estados desenham igual. */
function IconeOlho({ cortado }: { cortado: boolean }) {
  return (
    <svg
      width="18"
      height="18"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden
    >
      <path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12z" />
      <circle cx="12" cy="12" r="3" />
      {cortado && <path d="M3 3l18 18" />}
    </svg>
  )
}
