import { describe, expect, it } from 'vitest'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'

/* O que a tela faz com o login próprio desligado — e com o 503 do `/api/me` —, guardado no
   TEXTO-FONTE, como em `aviso-sessao.test.ts`: o Vitest daqui roda sem DOM, então não há como
   montar o React e olhar a tela. Os textos têm teste próprio em `lib/`; aqui se guarda que são
   ELES que chegam à tela, e que os botões, o cadeado e a nova tentativa estão ligados.

   Decisão do dono (24/10/2026): até o corte do P19, o cadeado "Trocar a minha senha", o
   "Redefinir senha" e o "Exigir troca" só aparecem — e só funcionam — com o login próprio
   (`MOTOR_AUTENTICACAO_PROPRIA`) LIGADO. */

const ler = (rel: string) => readFileSync(fileURLToPath(new URL(rel, import.meta.url)), 'utf-8')
const painel = ler('./PainelUsuarios.tsx')
const troca = ler('./TrocaDeSenha.tsx')
const app = ler('../App.tsx')

describe('o painel de usuários com a chave do login próprio', () => {
  it('Redefinir senha e Exigir troca só aparecem com o login próprio ligado', () => {
    expect(painel).toContain('{u.ativo && loginProprio && (')
    expect(painel).toContain('const loginProprio = loginProprioDoPayload(dados)')
  })

  it('a coluna é a "Senha (banco)" e o selo leva a dica da senha do banco', () => {
    expect(painel).toContain("['Pessoa', 'Login', 'Perfil', 'Situação', COLUNA_SENHA, '']")
    expect(painel).toContain('title={tituloDoSeloDaSenha(u.senha_propria, loginProprio)}')
  })

  it('os recados de criação, o formulário e o rodapé saem da lib, com a chave', () => {
    expect(painel).toContain('recadoDaCriacao(criado.login, criado.loginProprio)')
    expect(painel).toContain('rodapeDoPainel(loginProprio)')
    expect(painel).toContain('{dicaDoFormulario(loginProprio)}')
    expect(painel).toContain('title={tituloDoBotaoCriar(loginProprio)}')
    // A confirmação de criar também precisa saber a chave.
    expect(painel).toMatch(/capacidades: capacidadesDe\(novo\.perfil\),\s+loginProprio,/)
  })

  it('o erro de escrita passa pela régua que não afirma "nada foi alterado"', () => {
    expect(painel).toContain('mensagemDeErroDoPainel(e.status, e.message, { escrita })')
    expect(painel.match(/setErro\(mensagemDeErro\(e, true\)\)/g)).toHaveLength(3)
    expect(painel).toContain('Recarregar a lista')
  })

  it('as frases que mentiam com a chave desligada não voltam ao componente', () => {
    expect(painel).not.toContain('obriga a criar uma senha nova')
    expect(painel).not.toContain('Indisponível — nada foi alterado')
    expect(painel).not.toContain('é o Authelia que autentica hoje. A senha inicial')
  })
})

describe('a troca da própria senha com o login próprio ligado', () => {
  it('o fim da troca manda entrar de novo, e não voltar ao piloto', () => {
    expect(troca).toContain('{TEXTO_SENHA_DEFINIDA}')
    expect(troca).toContain('<Botao onClick={onEntrarDeNovo}>{ROTULO_ENTRAR_DE_NOVO}</Botao>')
    expect(troca).not.toContain('Voltar ao piloto')
  })

  it('o App liga o "entrar de novo" à tela de entrar de verdade', () => {
    expect(app).toContain('onEntrarDeNovo={entrarNovamente}')
  })

  it('pelo convite, o sucesso NÃO desmonta o pop-up antes da tela de "entre de novo"', () => {
    /* O pop-up monta com `senhaAberta || deveOferecerTroca(...)`. Aberto pelo CONVITE,
       `senhaAberta` é falso — e o `setEstadoSenha({ deveTrocar: false, ... })` do sucesso
       tornava o segundo termo falso no mesmo render: o pop-up sumia sem a pessoa ler que a
       sessão caiu, e ela descobria no clique seguinte, pelo "Sessão encerrada". O sucesso
       passa a manter o pop-up montado (`setSenhaAberta(true)`) até ela sair por ele. */
    expect(app).toContain('(senhaAberta || deveOferecerTroca(estadoSenha, senhaDispensada))')
    expect(app).toMatch(
      /setEstadoSenha\(\{ deveTrocar: false, propria: true \}\)[\s\S]{0,1200}?setSenhaAberta\(true\)\s*\n\s*return null/,
    )
  })

  it('sem estado da senha não há cadeado — e o estado só vem com a chave ligada', () => {
    expect(app).toContain('onSenha={estadoSenha ? () => setSenhaAberta(true) : undefined}')
  })
})

describe('o /api/me com 503 (#463, follow-up A)', () => {
  it('o App repete o /api/me em 503 em vez de pedir uma vez só', () => {
    expect(app).toContain('repetirEm503(() => api.me(), { vivo: () => vivo })')
  })

  it('quando a nova tentativa acerta, os alcances do ponto voltam — e o país NÃO', () => {
    /* Um 503 no `/api/me` do `main.tsx` deixava o seletor de alcance só com o raio de 1 km
       até recarregar, mesmo depois de a nova tentativa do App acertar. Os alcances não são
       do país (DEC-074: dependem do serviço de rotas), então podem ser instalados depois;
       perfil, aviso e moeda da viabilidade são, e só valem no bootstrap. */
    expect(app).toMatch(/if \(!vivo\) return[\s\S]{0,1200}?definirAlcances\(r\.alcances\)/)
    for (const doPais of ['definirPerfil(', 'definirAvisoDeViabilidade(', 'definirMoedaDeViabilidade(']) {
      expect(app).not.toContain(doPais)
    }
  })

  it('a nova tentativa para quando o App desmonta, e a resposta tardia não escreve no estado', () => {
    expect(app).toMatch(/return \(\) => \{\s+vivo = false\s+\}/)
    expect(app).toContain('if (!vivo) return')
  })
})
