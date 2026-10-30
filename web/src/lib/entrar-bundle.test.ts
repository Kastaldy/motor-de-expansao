import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

import { describe, expect, it } from 'vitest'

/**
 * Guardas do BUNDLE da tela de entrar.
 *
 * Ela é servida na raiz de `auth.ultra-expansao.tech`, um host que ela DIVIDE com o
 * portal do Authelia: o Caddy manda para o nosso container só a página e o prefixo
 * `entrar-assets/`; todo o resto daquele host vai para o Authelia.
 *
 * Isso cria duas formas de quebrar que **não aparecem em desenvolvimento** — no piloto
 * tudo é servido pelo mesmo backend, então qualquer caminho funciona lá. Só em produção,
 * e só naquele host, o erro aparece. Estes testes olham o FONTE, que é onde o defeito
 * seria introduzido.
 *
 * A TOPOLOGIA MUDA NO CORTE DO P19 (DEC-067): a partir dele esta pagina e' servida pelo
 * host do PILOTO (`deploy/caddy/piloto-br.Caddyfile.template`), e nao pela raiz de
 * `auth.`. O `auth.` continua existindo -- a instancia AR depende dele --, e o cookie
 * continua saindo com `Domain=<apex>`, entao o mecanismo descrito acima segue valendo
 * nos dois casos.
 */

const RAIZ = resolve(import.meta.dirname, '..')

/* Lê o fonte SEM comentários. Sem isto, a própria explicação de por que o caminho
   absoluto é proibido — que cita `src="/logo-ultra.png"` — faria a guarda reprovar o
   arquivo que ela protege. Documentar o defeito não pode acusar o defeito. */
const ler = (p: string) =>
  readFileSync(resolve(RAIZ, p), 'utf-8')
    .replace(/\/\*[\s\S]*?\*\//g, '')
    .replace(/^\s*\/\/.*$/gm, '')

describe('tela de entrar: caminhos de asset', () => {
  it('nao referencia asset por caminho ABSOLUTO', () => {
    /* `src="/logo-ultra.png"` funciona no piloto e cai no Authelia em `auth.` — o logo
       sumiria em produção sem nada quebrar antes. Resolvido por import, o caminho não
       tem como estar errado no ar sem primeiro quebrar o build. */
    const fontes = [
      'screens/LoginScreen.tsx',
      'components/login/MalhaBrasil.tsx',
      'entrar.tsx',
    ]
    for (const f of fontes) {
      const texto = ler(f)
      expect(texto, `${f}: asset por caminho absoluto`).not.toMatch(/(?:src|href)=["']\//)
      expect(texto, `${f}: url() absoluta no CSS em linha`).not.toMatch(/url\(\s*["']?\//)
    }
  })

  it('a entrada da tela NAO arrasta o app do piloto', () => {
    /* Importar `App` (ou o `main`) traria a SPA inteira para o bundle servido ANTES do
       login — as rotas internas da API viajam nela. O bundle tem de ser só a tela. */
    const entrada = ler('entrar.tsx')
    expect(entrada).not.toMatch(/from\s+["']\.\/App["']/)
    expect(entrada).not.toMatch(/from\s+["']\.\/main["']/)
  })

  it('a tela fala com o NOSSO backend, e por caminho RELATIVO', () => {
    /* Até 25/09/2026 esta guarda exigia `fetch('/api/firstfactor')` — o Authelia. A
       DEC-067 foi assinada nos quatro itens e a tela passou a usar `api.entrar()`, que
       fala com o nosso `POST /api/login`.

       A PROPRIEDADE que a guarda protege não mudou: origem RELATIVA. Uma origem absoluta
       (`https://auth...`) quebraria o que sustenta o desenho — o pedido é de mesma
       origem, e é isso que faz o cookie de sessão ser aceito sem CORS. Cravar o host
       também impediria o mesmo binário de servir outra instância (DEC-047: um país por
       processo, nenhum host no código). */
    const entrada = ler('entrar.tsx')
    expect(entrada).toMatch(/\bapi\.entrar\(/)
    expect(entrada).not.toMatch(/https?:\/\//)
  })

  it('não há reserva do Authelia: só o nosso backend autentica', () => {
    /* ESTA GUARDA JÁ EXISTIU AO CONTRÁRIO, e a inversão custou uma queda de produção. Até
       28/09/2026 ela exigia que `entrar.tsx` NÃO mencionasse `firstfactor`, "porque depois
       do corte o Authelia não existe" — e estava no tempo errado: o corte NÃO tinha sido
       virado, e a tela que só falava com o nosso backend tirou todo mundo do ar. A DEC-081
       virou o corte: o login próprio vale em todas as origens, o Authelia foi aposentado, e
       agora a premissa É verdadeira — a tela fala com UM backend só.

       Medido na FONTE sem comentários: o docstring conta a história e cita o Authelia por
       escrito, muito antes da primeira linha executável; medir a fonte crua mediria a
       PROSA. Mesma lição que `tema-claro-ultra.test.ts` registra para o CSS. */
    const codigo = ler('entrar.tsx')
      .replace(/\/\*[\s\S]*?\*\//g, '')
      .replace(/^\s*\/\/.*$/gm, '')

    // Entra pelo nosso backend...
    expect(codigo).toMatch(/\bapi\.entrar\(/)
    // ...e não há mais reserva do Authelia: nem a chamada de rede, nem a função.
    expect(codigo, 'o firstfactor do Authelia voltou').not.toMatch(/firstfactor/)
    expect(codigo, 'a função de reserva do Authelia voltou').not.toMatch(/entrarPeloAuthelia/)

    /* O 404 deixou de ser sinal especial: antes desviava para a reserva, agora é erro de
       servidor como outro qualquer (`falhaDoStatus`), sem ramo próprio nenhum. */
    expect(codigo, 'o 404 voltou a ter tratamento próprio na tela').not.toMatch(/404/)
  })

  it('o aviso de autofill existe no CSS com o nome que o TS compara', () => {
    /* Relato do Vinicius (2026-09-24): com os campos autopreenchidos, o botao de
       entrar nascia desabilitado — o navegador escreve no DOM sem disparar o evento
       que o React escuta, entao o estado ficava vazio.

       A correcao depende de um acoplamento POR NOME entre dois arquivos: a animacao
       `aviso-autofill` no `global.css` e a comparacao `e.animationName === '...'` no
       `LoginScreen`. Renomear de um lado so' devolve o defeito EM SILENCIO — nada
       quebra, nada fica vermelho, o botao so' volta a mentir. Este teste e' o que
       torna essa quebra visivel. */
    const css = readFileSync(resolve(RAIZ, 'styles/global.css'), 'utf8')
    const tela = ler('screens/LoginScreen.tsx')

    expect(css).toMatch(/@keyframes\s+aviso-autofill\b/)
    expect(css).toMatch(/input:-webkit-autofill\s*\{[^}]*animation-name:\s*aviso-autofill/)
    expect(tela).toMatch(/animationName\s*!==\s*'aviso-autofill'/)
    // E os dois campos precisam ESCUTAR o evento — sem o handler, a animacao dispara
    // para ninguem.
    expect(tela.match(/onAnimationStart=\{aoAutoPreencher\}/g)).toHaveLength(2)
  })

  it('a habilitacao NAO depende de ler o valor autopreenchido', () => {
    /* O defeito voltou uma vez por isto (relato de 25/09: "o botao so' fica azul
       depois que eu clico na tela, independente de onde seja o clique").

       O Chrome preenche os campos na carga mas SEGURA o valor da senha ate' haver um
       gesto do usuario — `input.value` devolve vazio antes disso, e o clique em
       qualquer lugar e' o gesto que libera. Uma correcao que sincronize o estado
       lendo o DOM le' VAZIO e conclui "campo vazio": foi a 1a tentativa, e ela nao
       resolveu.

       O que sustenta o botao e' a PRESENCA do autofill (`auto`), nao o valor. E o
       envio le' o DOM, porque ali o gesto ja' aconteceu. Estas duas travas sao o que
       impede a regressao. */
    const tela = ler('screens/LoginScreen.tsx')
    expect(tela).toMatch(/podeEnviar\(usuario,\s*senha,\s*estado,\s*auto\)/)
    expect(tela).toMatch(/matches\(':-webkit-autofill'\)/)
    expect(tela).toMatch(/refUsuario\.current\?\.value\s*\|\|\s*usuario/)
    expect(tela).toMatch(/refSenha\.current\?\.value\s*\|\|\s*senha/)
  })
})

describe('tela de entrar: o destino pos-login nao pode ser ela mesma', () => {
  /* O laco de 29/09/2026, medido no access log do Caddy: `/entrar.html` esta' ATRAS do
     `forward_auth`, entao o `rd` que o Caddy carimba e' a propria tela de entrar, e
     obedecer a ele devolve a pessoa ao formulario -- autenticada, com o cookie gravado,
     mas no host onde ninguem autentica. A regra de desembrulho vive em `destinoSeguro` e
     tem teste proprio; o que se guarda AQUI e' a CHAMADA, porque e' por ela que o
     conserto pode desaparecer em silencio: a funcao continuaria existindo, os testes dela
     continuariam verdes, e so' a producao saberia. */

  it('passa a pagina atual a `destinoSeguro` -- senao a raiz do host de auth passa batido', () => {
    /* O 3o argumento e' o que ensina a funcao a reconhecer a tela de entrar quando ela
       NAO se chama `entrar.html`: na raiz do host de auth ela se chama `/`. */
    expect(ler('entrar.tsx')).toMatch(
      /destinoSeguro\(\s*rd,\s*window\.location\.hostname,\s*window\.location\.href\s*\)/,
    )
  })
})
