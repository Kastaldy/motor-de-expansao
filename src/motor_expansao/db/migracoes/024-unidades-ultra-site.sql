-- ARQUIVO GERADO -- nao editar a mao.
-- Origem: banco-de-reservas/sql/024-unidades-ultra-site.md (primeiro bloco ```sql).
-- sha256 do bloco extraido: 58ca9d9fa5fef4921e8610c521466b3f6b7133c89e72a4fa367f502ccf378b41
-- Regenerar: python scripts/extrair_migracoes.py --origem <.../banco-de-reservas/sql>
--
-- O `banco-de-reservas` e' a fonte da verdade do DESENHO (convencoes §7): mudanca de
-- modelo entra la' primeiro e so' depois vira migration aqui. Editar este arquivo
-- direto quebra essa ordem e o teste de manifesto acusa.

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
