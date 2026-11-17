# 025 — Perfil `master`: a Visão Executiva só das próprias unidades

> **Rascunho para o `banco-de-reservas`.** O desenho do esquema mora lá (convenções §7), e este
> arquivo existe no motor só porque aquele repositório não estava ao alcance de quem escreveu a
> mudança. O primeiro bloco ```sql abaixo é, byte a byte, o que vai em
> `src/motor_expansao/db/migracoes/025-perfil-master.sql` — quem trouxer este documento
> para `banco-de-reservas/sql/` deve conferir com
> `python scripts/extrair_migracoes.py --origem <.../banco-de-reservas/sql> --conferir` e então
> apagar esta cópia.

## O que a migration cria

Pedido de 17/11/2026 (DEC-087): o master franqueado entra no piloto e vê a Visão Executiva **só das
unidades dele** — a carteira, a ficha, a inteligência e os setores das unidades cujo
`master_franquia` no cadastro da rede é o dele. Pode comparar com os agregados da rede (média,
total, posição, faixas de coorte), mas não vê dado individual de unidade de outro master, não
exporta (CSV, XLSX, PDF) e não edita o cadastro.

| Objeto | Para quê |
|---|---|
| perfil `master` | O perfil novo. Só tem `rede.ver_propria`. |
| `rede.ver_propria` | Capacidade nova: a Visão Executiva recortada às unidades do próprio master. |
| `usuario_masters` | Vínculo pessoa → master franquia (N:N), no molde da `usuario_paises` (021). |

## Decisões de desenho

- **Uma capacidade nova, e não `rede.ver` com filtro.** `rede.ver` é a carteira da rede INTEIRA, e
  quem a tem (consultoria, líderes, growth) continua com ela, intocada. Reaproveitá-la para o
  master faria o recorte depender de o perfil ser `master` — um `if perfil == ...` que o gate não
  enxerga. Com a chave própria, quem decide o alcance é a capacidade: o gate só abre para
  `rede.ver_propria` uma allowlist FECHADA de leituras (`acesso.rota_da_rede_propria`), e a rota
  aplica o recorte (`_recorte_da_rede` no piloto).
- **O master não ganha `rede.cadastro_editar` nem `concorrente.anotar`.** A 023 deu `anotar` a todos
  os perfis que existiam em 05/11/2026; o `master` nasce depois e de propósito fica de fora: ele não
  alcança o Mapa.
- **O vínculo é por TEXTO, e não por FK.** O master franquia não é entidade do banco: é um campo do
  cadastro da rede (`cadastro_unidades.json`, editado pela Consultoria). O vínculo guarda o mesmo
  texto, e o piloto compara os dois. Um master renomeado no cadastro deixa o vínculo sem unidade —
  e o piloto mostra a carteira VAZIA, nunca a rede (fail-closed).
- **N:N, e não uma coluna em `usuarios`.** Um master pode aparecer no cadastro com mais de uma
  grafia, e uma pessoa pode responder por mais de um master; a PK composta impede o mesmo vínculo
  duas vezes e serve a consulta quente ("os masters desta pessoa", prefixo `id_usuario`).
- **`ON DELETE CASCADE`, como a 021.** O vínculo não é registro a preservar: sem a pessoa, ele
  não decide mais nada. Desativar a pessoa (o caminho normal) já a tira do piloto.
- **Sem trigger de histórico.** O vínculo é dado de configuração, mudado à mão pelo dono, e o
  evento de quem mudou fica na trilha da administração quando houver tela para isso.

## GRANT do papel `app` (levar às seções 3 e 4 do `papeis-e-privilegios.md`)

Numa instalação do zero o D20 roda depois das migrations e o default privilege não alcança esta
tabela; em produção, o `ALTER DEFAULT PRIVILEGES FOR ROLE reservas_owner` concede `SELECT`,
`INSERT` e `UPDATE`. O `DELETE` vem explícito, como o da `usuario_paises`: desvincular é apagar a
linha (não há histórico a preservar). Sem sequence: a PK é composta e não há `BIGSERIAL`.

```text
GRANT SELECT, INSERT, UPDATE, DELETE ON usuario_masters TO app;
```

## Migration

```sql
BEGIN;

-- A TABELA VEM PRIMEIRO (revisao de 17/11/2026): o `db aplicar` reconhece a janela
-- "aplicada mas nao registrada" pelo erro de objeto que ja' existe (42P07) no PRIMEIRO comando.
-- Abrindo com o INSERT do perfil, a reexecucao cairia num 23505 cru, que o runner nao trata.
-- ---------------------------------------------------------------------------------------------
-- O vinculo pessoa -> master franquia
-- ---------------------------------------------------------------------------------------------
CREATE TABLE usuario_masters (
  id_usuario      BIGINT NOT NULL REFERENCES usuarios(id_usuario) ON DELETE CASCADE,
  -- O MESMO texto do campo `master_franquia` do cadastro da rede, que nao e' entidade do banco:
  -- por isso valor, e nao FK. Sem espaco nas pontas, para o vinculo nao falhar por um espaco que
  -- ninguem ve; a comparacao com o cadastro e' do piloto. `master_franquia` sem sufixo de tabela
  -- porque e' o nome do campo de onde o valor vem (mesma excecao declarada do `pais` da 021).
  master_franquia TEXT NOT NULL,
  CONSTRAINT chk_usuario_masters_nome CHECK (
    master_franquia = btrim(master_franquia) AND char_length(master_franquia) BETWEEN 2 AND 120
  ),
  -- PK composta: a mesma pessoa nao tem o mesmo master duas vezes. Serve tambem "os masters de
  -- uma pessoa" (prefixo id_usuario), a consulta QUENTE do recorte, e cobre o indice da FK.
  PRIMARY KEY (id_usuario, master_franquia)
);

-- ---------------------------------------------------------------------------------------------
-- O perfil novo
--
-- Identificador sem acento (convencoes §6); a descricao e' texto de TELA e vai acentuada.
-- ---------------------------------------------------------------------------------------------
INSERT INTO perfis (nome_perfil, descricao_perfil) VALUES
  ('master', 'Master franqueado: Visão Executiva só das próprias unidades');

-- ---------------------------------------------------------------------------------------------
-- A capacidade nova
--
-- Descricao com o mesmo cuidado das outras: ela vira ROTULO DE TELA (convencoes §5). O gate a
-- aceita so' numa allowlist FECHADA de leituras de `/api/rede/` (`acesso.rota_da_rede_propria`):
-- filtros, carteira (sem os exports), inteligencia e a ficha, a inteligencia e os setores de uma
-- unidade. O recorte as unidades do master e' aplicado pela rota.
-- ---------------------------------------------------------------------------------------------
INSERT INTO permissoes (chave, descricao_permissao) VALUES
  ('rede.ver_propria', 'Ver a carteira e a ficha só das unidades do próprio master franquia'); -- GET /api/rede/ (allowlist)

-- So' o master, e so' esta (decisao de produto de 17/11/2026, DEC-087): sem `rede.ver`, sem
-- `rede.cadastro_editar`, sem `concorrente.anotar`. Escrito como consulta, e nao com id literal,
-- pelo mesmo motivo da 012. A trigger de auditoria do D19 grava `registrado_por` NULO, como na 015.
INSERT INTO perfil_permissoes (id_perfil, id_permissao)
SELECT p.id_perfil, pe.id_permissao
FROM perfis p
JOIN permissoes pe ON TRUE
WHERE (p.nome_perfil, pe.chave) IN (
  ('master', 'rede.ver_propria')
);

COMMIT;
```

## Verificação (não vai para a migration)

```sql
-- 1. O master tem só `rede.ver_propria`.
SELECT pe.chave
FROM perfil_permissoes pp
JOIN perfis p ON p.id_perfil = pp.id_perfil
JOIN permissoes pe ON pe.id_permissao = pp.id_permissao
WHERE p.nome_perfil = 'master';

-- 2. Espaço nas pontas é recusado: deve FALHAR com check_violation.
INSERT INTO usuario_masters (id_usuario, master_franquia)
SELECT id_usuario, ' Exemplo ' FROM usuarios LIMIT 1;
```

## Vincular uma pessoa (operação, não vai para a migration)

Desde 17/11/2026 (emenda 1 da DEC-087) a pessoa é criada **e vinculada** pela aba Acessos: com o
perfil `master`, o campo "Master franquia" oferece os nomes do cadastro e grava a grafia de lá.
O SQL abaixo fica só como contingência (tela fora do ar), com o texto EXATO do `master_franquia`
do cadastro — e ele não deixa o evento `usuario.masters_alterados` que a tela grava:

```text
INSERT INTO usuario_masters (id_usuario, master_franquia)
SELECT id_usuario, '<master como está no cadastro>' FROM usuarios
WHERE login_usuario = '<login>' AND ativo;
```
