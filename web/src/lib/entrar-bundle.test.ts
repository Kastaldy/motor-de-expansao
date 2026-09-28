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

  it('o Authelia é RESERVA, e só o 404 cai nele', () => {
    /* ESTA GUARDA JÁ EXISTIU AO CONTRÁRIO, e a inversão custou uma queda de produção.
       Até 28/09/2026 ela exigia que `entrar.tsx` NÃO mencionasse `firstfactor`, com a
       justificativa "depois do corte o Authelia não existe". A premissa é verdadeira e
       estava no tempo errado: o corte NÃO foi virado, e a tela que só falava com o nosso
       backend tirou todo mundo do ar — `/api/login` responde 404 com
       `MOTOR_AUTENTICACAO_PROPRIA` desligada, e da borda do host de auth o pedido nem
       chega ao nosso backend.

       O invariante que vale nos DOIS mundos, e é o que se mede aqui:
         1. o NOSSO backend é tentado PRIMEIRO (depois do corte, é o único que responde);
         2. o Authelia é alcançável, mas só como RESERVA;
         3. a queda para a reserva é no 404 e em MAIS NADA — 401 é credencial recusada e
            429 é trava; cair no Authelia neles gastaria uma tentativa da trava DELE com
            uma senha que o nosso servidor já recusou;
         4. o 404 não conta como tentativa, senão a pessoa vê "muitas tentativas" no
            primeiro envio por causa de uma porta fechada que ela não escolheu. */
    /* O CÓDIGO, sem os comentários. Medir a fonte crua mediria a PROSA: o docstring desta
       tela explica a ordem das duas tentativas e cita `/api/firstfactor` por escrito, muito
       antes da primeira linha executável. A 1a versão desta guarda caiu nisso e acusou "o
       Authelia virou a primeira tentativa" apontando para um parágrafo. Mesma lição que
       `tema-claro-ultra.test.ts` já registra para o CSS: comentário sai ANTES do parse. */
    const codigo = ler('entrar.tsx')
      .replace(/\/\*[\s\S]*?\*\//g, '')
      .replace(/^\s*\/\/.*$/gm, '')
    const entrada = codigo

    /* POSIÇÃO DE TEXTO NÃO MEDE ORDEM DE CHAMADA, e a 1a versão desta guarda errou por
       isso: `entrarPeloAuthelia` é declarada ACIMA de `Entrada`, então o `firstfactor` do
       corpo dela aparece antes do `api.entrar(` — e a asserção acusou inversão onde não
       havia. O que se mede aqui é ESTRUTURA: o POST ao Authelia existe SÓ dentro da
       função de reserva, e o nosso backend é chamado SÓ fora dela. Quem amarra as duas na
       ordem certa é a asserção do 404, abaixo. */
    const iDef = entrada.search(/async function entrarPeloAuthelia\b/)
    expect(iDef, 'a função de reserva desapareceu — quem entra hoje fica fora').toBeGreaterThan(-1)
    const fimDef = entrada.indexOf('\nfunction Entrada(', iDef)
    expect(fimDef, 'não achei o fim da função de reserva').toBeGreaterThan(iDef)
    const reserva = entrada.slice(iDef, fimDef)
    const resto = entrada.slice(0, iDef) + entrada.slice(fimDef)

    expect(reserva, 'a reserva não chama o primeiro fator').toMatch(/fetch\('\/api\/firstfactor'/)
    expect(resto, 'o Authelia é chamado FORA da reserva — virou primeira tentativa').not.toMatch(
      /firstfactor/,
    )
    expect(resto, 'a tela não chama o nosso backend').toMatch(/\bapi\.entrar\(/)
    expect(reserva, 'o nosso backend é chamado DENTRO da reserva').not.toMatch(/\bapi\.entrar\(/)

    // 3. a queda é no 404...
    expect(entrada).toMatch(/erro\.status === 404[\s\S]{0,800}?entrarPeloAuthelia\(/)
    // ...e em mais nada: nenhum outro status leva à reserva.
    for (const status of [401, 403, 429, 500]) {
      expect(
        entrada,
        `${status} não pode cair no Authelia`,
      ).not.toMatch(new RegExp(`erro\\.status === ${status}[\\s\\S]{0,200}?entrarPeloAuthelia\\(`))
    }

    /* 4. o ramo do 404 vem ANTES de contar a tentativa — medido em `resto`, e não na fonte
       inteira, porque a função de RESERVA também conta tentativa (as recusas do Authelia
       contam, e devem contar). Medir tudo junto pegaria aquele `falhas.current += 1`, que
       está acima no arquivo, e a guarda reprovaria um código correto. */
    const iQuatroCentoQuatro = resto.search(/erro\.status === 404/)
    const iConta = resto.search(/falhas\.current \+= 1/)
    expect(iQuatroCentoQuatro, 'o 404 saiu do caminho próprio').toBeGreaterThan(-1)
    expect(iConta, 'o caminho próprio parou de contar tentativa').toBeGreaterThan(-1)
    expect(iQuatroCentoQuatro, 'o 404 passou a contar como tentativa').toBeLessThan(iConta)
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
