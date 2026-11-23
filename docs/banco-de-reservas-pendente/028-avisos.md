# 028 — Avisos no piloto: o sino dos pedidos dos masters

> **Rascunho para o `banco-de-reservas`.** O desenho do esquema mora lá (convenções §7), e este
> arquivo existe no motor só porque aquele repositório não estava ao alcance de quem escreveu a
> mudança. O primeiro bloco ```sql abaixo é, byte a byte, o que vai em
> `src/motor_expansao/db/migracoes/028-avisos.sql` — quem trouxer este documento
> para `banco-de-reservas/sql/` deve conferir com
> `python scripts/extrair_migracoes.py --origem <.../banco-de-reservas/sql> --conferir` e então
> apagar esta cópia.

## O que a migration cria

Pedido de 19/11/2026 (DEC-090): um sistema de avisos dentro do motor, começando pelos masters.
Quando um master pede um estudo pelo Início, o aviso chega ao time do Growth (a hora, quem pediu e
de onde); quando pede um imóvel, chega à pessoa que cuida dos imóveis. O aviso aparece num sino na
barra lateral, com o número de não lidos.

| Objeto | Para quê |
|---|---|
| `usuario_avisos` | Os avisos que uma pessoa recebe além dos do perfil dela, marcados na aba Acessos. |
| `avisos_lidos` | Até que evento da trilha a pessoa já viu os avisos (o sino conta os de depois). |
| `avisos.estudos_masters` | Capacidade nova: receber o aviso de estudo pedido por um master. |
| `masters.inicio_testar` | Capacidade nova: ver e testar o Início do master (a trilha "Meu território") sem ser master. |

## Decisões de desenho

- **O aviso é o EVENTO, e não uma tabela de avisos.** A trilha (`eventos`, 005) já guarda o gesto
  do master com quem, quando e o quê (`estudo.solicitado`, `imovel.solicitado`). O sino lê essas
  linhas; uma tabela de avisos copiaria a trilha e poderia divergir dela.
- **Quem recebe: o perfil OU a pessoa.** O estudo vai para o perfil `growth` inteiro (Juan,
  19/11/2026: "o time todo da Growth"), inclusive quem entrar no Growth depois — por isso
  capacidade de perfil. O imóvel vai para uma pessoa (a Priscila), que não é um perfil inteiro —
  por isso a lista por pessoa, no molde da `usuario_paises` (021) e da `usuario_masters` (025),
  editada na aba Acessos. A lista também serve para dar o aviso de estudo a alguém de fora do
  Growth.
- **O Growth avalia o Início do master** (Juan, 22/11/2026: "seria bom a growth terem essa nova
  vista, para testes ou avaliar"). Capacidade, e não nome de perfil, como todo o RBAC: Líderes
  entram com uma linha em `perfil_permissoes`. Ela só liga a trilha na tela (`/api/me`); as rotas
  dos dois pedidos já aceitam quem tem `masters.ver`. O pedido de quem vê todos os masters é
  teste: não vira aviso.
- **`aviso` é valor controlado, e não FK.** A lista é curta e fechada e cresce por migration: o
  CHECK `chk_usuario_avisos_tipo` recusa o que o piloto não sabe mostrar.
- **"Lido até" em vez de "lido um a um".** Abrir o sino marca tudo o que estava na lista; uma linha
  por pessoa com o maior `id_evento` visto basta, e a contagem é `id_evento >` esse valor.
- **`ON DELETE CASCADE` nas duas, como a 021.** Sem a pessoa, nenhuma das duas decide nada.
- **Sem trigger de histórico.** `usuario_avisos` é configuração mudada à mão pelo dono, com o evento
  `usuario.avisos_alterados` na trilha da administração; `avisos_lidos` é estado de tela.

## GRANT do papel `app` (levar às seções 3 e 4 do `papeis-e-privilegios.md`)

Numa instalação do zero o D20 roda depois das migrations e o default privilege não alcança estas
tabelas; em produção, o `ALTER DEFAULT PRIVILEGES FOR ROLE reservas_owner` concede `SELECT`,
`INSERT` e `UPDATE`. O `DELETE` de `usuario_avisos` vem explícito, como o da `usuario_masters`:
desmarcar um aviso é apagar a linha. `avisos_lidos` não precisa de `DELETE` (é gravada por
`INSERT ... ON CONFLICT DO UPDATE`). Sem sequence: as PKs não são `BIGSERIAL`.

```text
GRANT SELECT, INSERT, UPDATE, DELETE ON usuario_avisos TO app;
GRANT SELECT, INSERT, UPDATE ON avisos_lidos TO app;
```

## Migration

```sql
BEGIN;

-- AS TABELAS VEM PRIMEIRO (mesma razao da 025): o `db aplicar` reconhece a janela "aplicada mas
-- nao registrada" pelo erro de objeto que ja' existe (42P07) no PRIMEIRO comando.
-- ---------------------------------------------------------------------------------------------
-- Os avisos que uma pessoa recebe alem dos do perfil
-- ---------------------------------------------------------------------------------------------
CREATE TABLE usuario_avisos (
  id_usuario BIGINT NOT NULL REFERENCES usuarios(id_usuario) ON DELETE CASCADE,
  -- Valor controlado, e nao FK: a lista e' curta, fechada e cresce por migration. Sem sufixo de
  -- tabela pela mesma excecao declarada do `pais` da 021 (nome universal e unico).
  aviso      TEXT NOT NULL,
  CONSTRAINT chk_usuario_avisos_tipo CHECK (aviso IN ('estudo_master', 'imovel_master')),
  -- PK composta: a mesma pessoa nao tem o mesmo aviso duas vezes. Serve "os avisos de uma pessoa"
  -- (prefixo id_usuario), a consulta do sino, e cobre o indice da FK.
  PRIMARY KEY (id_usuario, aviso)
);

-- ---------------------------------------------------------------------------------------------
-- Ate' onde a pessoa ja' viu os avisos
-- ---------------------------------------------------------------------------------------------
CREATE TABLE avisos_lidos (
  id_usuario       BIGINT PRIMARY KEY REFERENCES usuarios(id_usuario) ON DELETE CASCADE,
  -- O maior `eventos.id_evento` que estava no sino quando a pessoa o abriu. Sem FK de proposito:
  -- e' um marco de posicao na trilha, nao uma referencia a um evento que precise existir.
  ultimo_id_evento BIGINT NOT NULL,
  lido_em          TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT chk_avisos_lidos_evento CHECK (ultimo_id_evento >= 0)
);

-- ---------------------------------------------------------------------------------------------
-- A capacidade do aviso de estudo, e o perfil que a recebe
--
-- Descricao com o mesmo cuidado das outras: ela vira ROTULO DE TELA (convencoes §5).
-- ---------------------------------------------------------------------------------------------
INSERT INTO permissoes (chave, descricao_permissao) VALUES
  ('avisos.estudos_masters', 'Receber o aviso de estudo pedido por um master'), -- GET /api/avisos
  -- So' liga a trilha "Meu territorio" no Inicio (`trilha_do_master` do /api/me); os pedidos
  -- seguem o gate de sempre (`masters.ver`). Juan, 22/11/2026: o Growth testa e avalia.
  ('masters.inicio_testar', 'Ver e testar o Início do master');

-- O perfil `growth` inteiro (decisao de produto de 19/11/2026, DEC-090). Escrito como consulta, e
-- nao com id literal, pelo mesmo motivo da 012. A trigger de auditoria do D19 grava
-- `registrado_por` NULO, como na 015.
INSERT INTO perfil_permissoes (id_perfil, id_permissao)
SELECT p.id_perfil, pe.id_permissao
FROM perfis p
JOIN permissoes pe ON TRUE
WHERE (p.nome_perfil, pe.chave) IN (
  ('growth', 'avisos.estudos_masters'),
  ('growth', 'masters.inicio_testar')
);

COMMIT;
```

## Verificação (não vai para a migration)

```sql
-- 1. Só o perfil growth tem as duas capacidades novas.
SELECT p.nome_perfil, pe.chave
FROM perfil_permissoes pp
JOIN perfis p ON p.id_perfil = pp.id_perfil
JOIN permissoes pe ON pe.id_permissao = pp.id_permissao
WHERE pe.chave IN ('avisos.estudos_masters', 'masters.inicio_testar')
ORDER BY 1;

-- 2. Aviso fora da lista é recusado: deve FALHAR com check_violation.
INSERT INTO usuario_avisos (id_usuario, aviso)
SELECT id_usuario, 'qualquer_coisa' FROM usuarios LIMIT 1;
```

## Dar o aviso de imóvel a uma pessoa (operação, não vai para a migration)

Pela aba Acessos: no usuário, o campo "Avisos" marca "Imóvel pedido por um master". O SQL abaixo
fica só como contingência (tela fora do ar), e ele não deixa o evento `usuario.avisos_alterados`
que a tela grava:

```text
INSERT INTO usuario_avisos (id_usuario, aviso)
SELECT id_usuario, 'imovel_master' FROM usuarios
WHERE login_usuario = '<login>' AND ativo;
```
