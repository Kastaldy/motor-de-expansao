# 024 — Unidades Ultra incluídas pelo site

> **Rascunho para o `banco-de-reservas`.** O desenho do esquema mora lá (convenções §7), e este
> arquivo existe no motor só porque aquele repositório não estava ao alcance de quem escreveu a
> mudança. O primeiro bloco ```sql abaixo é, byte a byte, o que vai em
> `src/motor_expansao/db/migracoes/024-unidades-ultra-site.sql` — quem trouxer este documento
> para `banco-de-reservas/sql/` deve conferir com
> `python scripts/extrair_migracoes.py --origem <.../banco-de-reservas/sql> --conferir` e então
> apagar esta cópia.

## O que a migration cria

Hoje uma unidade Ultra nova só entra no cadastro (`unidades_ultra_mapeadas.parquet`) pela conta
`deploy`, à mão (`scripts/incluir_unidade_ultra.py`). Com a DEC-085, quem tem o perfil `growth` ou
`lideres` inclui pelo Mapa do piloto: digita nome e coordenadas, revisa numa tela de confirmação e
só então grava. A unidade aparece na hora no pino, na busca e na ficha; pode ser alterada ou
removida por 1 dia; depois disso a linha congela, e o cron de mercado de domingo a acrescenta ao
parquet — de onde ela chega ao mercado residual e ao PDF da API.

| Objeto | Para quê |
|---|---|
| `unidades_ultra_site` | Uma linha por unidade incluída pelo site, no país do deploy. Nunca removida: remover é marcar. |
| `guarda_unidade_ultra_site()` | Trigger `BEFORE UPDATE`: recusa mexer em unidade removida ou com mais de 1 dia, e fixa país, autor e data de inclusão. |
| `recusa_remover_unidade_ultra_site()` | Recusa `DELETE` e `TRUNCATE`, inclusive do dono. |
| `rede.unidade_incluir` | Capacidade nova, de `growth` e `lideres`: incluir, alterar e remover no primeiro dia. |

## Decisões de desenho

- **O prazo de 1 dia mora no banco, não só na tela.** A trigger de guarda recusa o `UPDATE` de uma
  linha criada há 24 h ou mais — a mesma regra que o piloto confere antes (`PRAZO_ALTERACAO` em
  `motor_expansao.cadastro_ultra`). É ela que deixa o cron de domingo levar a unidade ao parquet
  sem medo: a linha consolidada não muda mais por caminho nenhum do `app`. Corrigir depois disso é
  por PR (uma migration do dono, que desliga a guarda dentro da própria transação, e o
  `scripts/incluir_unidade_ultra.py mover` para o parquet).
- **Remover é marcar.** `removida_em_unidade_site`/`removida_por` no lugar do `DELETE`, pelo mesmo
  raciocínio da `revogada_em_sessao` (018) e das anotações (023): "esta unidade foi incluída e
  tirada, quando e por quem" é dado de auditoria.
- **Sem tabela de histórico.** Diferente da 023, aqui não há moderação nem texto de outra pessoa
  para preservar, e a janela de edição é de um dia: `alterada_em`/`alterada_por` dizem quem mexeu
  por último. Se a auditoria pedir a versão anterior da coordenada, o histórico entra numa
  migration própria, no molde da 023.
- **País do deploy em toda linha.** O banco é um só para BR e AR (`docker-compose.ar.yml`); a
  unidade é do país do deploy que a recebeu (`PERFIL.pais`), e cada site lê só as do seu país.
- **Nome único entre as vivas do país.** O índice único parcial é a última linha contra o duplo
  clique: o piloto já recusa nome repetido contra o cadastro inteiro (parquet + site), mas duas
  requisições simultâneas passariam as duas pela conferência.
- **O hexágono é gravado.** `hex_id_res7` sai do `h3` no piloto, na inclusão, e viaja igual para o
  parquet: o cron de domingo não recalcula nada.

## GRANT do papel `app` (levar às seções 3 e 4 do `papeis-e-privilegios.md`)

Numa instalação do zero o D20 roda depois das migrations e o default privilege não alcança esta
tabela; em produção, o `ALTER DEFAULT PRIVILEGES FOR ROLE reservas_owner` concede `SELECT`,
`INSERT` e `UPDATE` + `USAGE` da sequence.

```text
GRANT SELECT, INSERT, UPDATE ON unidades_ultra_site TO app;
GRANT USAGE ON SEQUENCE unidades_ultra_site_id_unidade_site_seq TO app;
REVOKE DELETE, TRUNCATE ON unidades_ultra_site FROM app;

-- Seção 7 (molde da `trg_perfil_permissoes_auditoria`): com session_replication_role=replica,
-- trigger fora de 'A' deixa de disparar — e o prazo de 1 dia deixaria de valer.
ALTER TABLE unidades_ultra_site ENABLE ALWAYS TRIGGER trg_unidades_ultra_site_guarda;
ALTER TABLE unidades_ultra_site ENABLE ALWAYS TRIGGER trg_unidades_ultra_site_sem_delete;
ALTER TABLE unidades_ultra_site ENABLE ALWAYS TRIGGER trg_unidades_ultra_site_sem_truncate;
```

## Migration

```sql
BEGIN;

CREATE TABLE unidades_ultra_site (
  id_unidade_site            BIGSERIAL PRIMARY KEY,
  -- Pais do DEPLOY que recebeu a unidade (PERFIL.pais). Mesma regra da `usuario_paises` (021):
  -- sigla ISO de 2 letras maiusculas, valor controlado e nao FK.
  pais                       CHAR(2) NOT NULL,
  nome_unidade_site          TEXT NOT NULL,
  -- UF no Brasil; provincia na Argentina. Texto curto, conferido pelo piloto.
  uf_unidade_site            TEXT NOT NULL,
  cidade_unidade_site        TEXT NOT NULL,
  lat_unidade_site           DOUBLE PRECISION NOT NULL,
  lng_unidade_site           DOUBLE PRECISION NOT NULL,
  -- Celula H3 res-7 do ponto, calculada pelo piloto na inclusao e levada igual ao parquet.
  hex_id_res7                TEXT NOT NULL,
  -- Sem ON DELETE: usuario nao se apaga (desativa-se), e a unidade precisa de quem a incluiu.
  id_usuario_criou           BIGINT NOT NULL REFERENCES usuarios(id_usuario),
  criada_em_unidade_site     TIMESTAMPTZ NOT NULL DEFAULT now(),
  alterada_em_unidade_site   TIMESTAMPTZ,
  alterada_por               BIGINT REFERENCES usuarios(id_usuario),
  -- Remover e' MARCAR, nunca DELETE (mesmo raciocinio da `revogada_em_sessao`, 018).
  removida_em_unidade_site   TIMESTAMPTZ,
  removida_por               BIGINT REFERENCES usuarios(id_usuario),
  CONSTRAINT chk_unidade_site_pais_sigla CHECK (pais ~ '^[A-Z]{2}$'),
  CONSTRAINT chk_unidade_site_coordenada CHECK (
    lat_unidade_site BETWEEN -90 AND 90 AND lng_unidade_site BETWEEN -180 AND 180
  ),
  CONSTRAINT chk_unidade_site_textos CHECK (
    char_length(btrim(nome_unidade_site)) BETWEEN 2 AND 120
    AND char_length(btrim(uf_unidade_site)) BETWEEN 1 AND 40
    AND char_length(btrim(cidade_unidade_site)) BETWEEN 1 AND 120
  ),
  CONSTRAINT chk_unidade_site_hexagono CHECK (hex_id_res7 ~ '^[0-9a-f]{15}$'),
  -- Os pares andam juntos: ou nao houve a acao, ou ela tem data e autor.
  CONSTRAINT chk_unidade_site_alterada_par CHECK (
    (alterada_em_unidade_site IS NULL) = (alterada_por IS NULL)
  ),
  CONSTRAINT chk_unidade_site_removida_par CHECK (
    (removida_em_unidade_site IS NULL) = (removida_por IS NULL)
  )
);

-- A consulta QUENTE: as unidades vivas do pais do deploy, em ordem de inclusao.
CREATE INDEX IF NOT EXISTS idx_unidades_ultra_site_pais
  ON unidades_ultra_site (pais, criada_em_unidade_site);
-- Ultima linha contra o duplo clique: duas unidades VIVAS com o mesmo nome no mesmo pais.
CREATE UNIQUE INDEX IF NOT EXISTS uq_unidades_ultra_site_nome_vivo
  ON unidades_ultra_site (pais, lower(btrim(nome_unidade_site)))
  WHERE removida_em_unidade_site IS NULL;
-- toda FK ganha indice B-tree (convencoes 1)
CREATE INDEX IF NOT EXISTS idx_unidades_ultra_site_criou
  ON unidades_ultra_site (id_usuario_criou);
CREATE INDEX IF NOT EXISTS idx_unidades_ultra_site_alterada_por
  ON unidades_ultra_site (alterada_por);
CREATE INDEX IF NOT EXISTS idx_unidades_ultra_site_removida_por
  ON unidades_ultra_site (removida_por);

-- ---------------------------------------------------------------------------------------------
-- Guarda: o prazo de 1 dia e o que nao muda
--
-- NAO e' SECURITY DEFINER: so' levanta excecao, nao escreve em lugar nenhum.
-- ---------------------------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION guarda_unidade_ultra_site() RETURNS trigger
LANGUAGE plpgsql
SET search_path = pg_catalog, pg_temp AS $$
BEGIN
  IF OLD.removida_em_unidade_site IS NOT NULL THEN
    RAISE EXCEPTION 'unidade % foi removida e nao muda mais', OLD.id_unidade_site
      USING ERRCODE = 'check_violation';
  END IF;
  -- O prazo de alteracao (DEC-085): depois de 1 dia a linha congela e o cron de domingo a leva
  -- ao parquet. Corrigir depois disso e' por PR.
  IF OLD.criada_em_unidade_site <= now() - interval '24 hours' THEN
    RAISE EXCEPTION 'unidade %: passou o prazo de 1 dia para alterar ou remover pelo site',
      OLD.id_unidade_site
      USING ERRCODE = 'check_violation';
  END IF;
  IF (OLD.id_unidade_site, OLD.pais, OLD.id_usuario_criou, OLD.criada_em_unidade_site)
     IS DISTINCT FROM
     (NEW.id_unidade_site, NEW.pais, NEW.id_usuario_criou, NEW.criada_em_unidade_site) THEN
    RAISE EXCEPTION 'o pais, quem incluiu e a data de inclusao de uma unidade nao mudam'
      USING ERRCODE = 'check_violation';
  END IF;
  RETURN NEW;
END;
$$;

-- ---------------------------------------------------------------------------------------------
-- Nada se apaga: DELETE e TRUNCATE
-- ---------------------------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION recusa_remover_unidade_ultra_site() RETURNS trigger
LANGUAGE plpgsql
SET search_path = pg_catalog, pg_temp AS $$
BEGIN
  RAISE EXCEPTION '% em %: unidades incluidas pelo site nao se apagam (remover e marcar removida_em_unidade_site)',
    TG_OP, TG_TABLE_NAME
    USING ERRCODE = 'insufficient_privilege';
END;
$$;

CREATE TRIGGER trg_unidades_ultra_site_guarda
  BEFORE UPDATE ON unidades_ultra_site
  FOR EACH ROW EXECUTE FUNCTION guarda_unidade_ultra_site();

CREATE TRIGGER trg_unidades_ultra_site_sem_delete
  BEFORE DELETE ON unidades_ultra_site
  FOR EACH ROW EXECUTE FUNCTION recusa_remover_unidade_ultra_site();

CREATE TRIGGER trg_unidades_ultra_site_sem_truncate
  BEFORE TRUNCATE ON unidades_ultra_site
  FOR EACH STATEMENT EXECUTE FUNCTION recusa_remover_unidade_ultra_site();

-- ---------------------------------------------------------------------------------------------
-- A capacidade nova
--
-- Descricao com o mesmo cuidado das outras: ela vira ROTULO DE TELA (convencoes §5).
-- ---------------------------------------------------------------------------------------------
INSERT INTO permissoes (chave, descricao_permissao) VALUES
  ('rede.unidade_incluir', 'Incluir unidades Ultra novas no mapa e corrigi-las no primeiro dia'); -- POST/PATCH/DELETE /api/mapa/unidades-site

-- Growth e lideres (decisao de produto de 13/11/2026). Escrito como consulta, e nao com id
-- literal, pelo mesmo motivo da 012.
INSERT INTO perfil_permissoes (id_perfil, id_permissao)
SELECT p.id_perfil, pe.id_permissao
FROM perfis p
JOIN permissoes pe ON pe.chave = 'rede.unidade_incluir'
WHERE p.nome_perfil IN ('growth', 'lideres');

COMMIT;
```

## Verificação (não vai para a migration)

```sql
-- 1. Nada se apaga: as duas devem FALHAR com insufficient_privilege.
DELETE FROM unidades_ultra_site;
TRUNCATE unidades_ultra_site;

-- 2. Só growth e lideres têm `rede.unidade_incluir`.
SELECT p.nome_perfil, pe.chave
FROM perfil_permissoes pp
JOIN perfis p ON p.id_perfil = pp.id_perfil
JOIN permissoes pe ON pe.id_permissao = pp.id_permissao
WHERE pe.chave = 'rede.unidade_incluir'
ORDER BY 1;

-- 3. Unidade com mais de 1 dia não muda: deve FALHAR com check_violation.
UPDATE unidades_ultra_site SET cidade_unidade_site = cidade_unidade_site
WHERE criada_em_unidade_site <= now() - interval '24 hours';
```
