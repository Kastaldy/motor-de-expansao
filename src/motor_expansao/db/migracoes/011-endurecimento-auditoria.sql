-- ARQUIVO GERADO -- nao editar a mao.
-- Origem: banco-de-reservas/sql/011-endurecimento-auditoria.md (primeiro bloco ```sql).
-- sha256 do bloco extraido: b66c3603b9aafca8f9ebff5ce4c5d9762d69222c9fabbbea1f206e69352db313
-- Regenerar: python scripts/extrair_migracoes.py --origem <.../banco-de-reservas/sql>
--
-- O `banco-de-reservas` e' a fonte da verdade do DESENHO (convencoes §7): mudanca de
-- modelo entra la' primeiro e so' depois vira migration aqui. Editar este arquivo
-- direto quebra essa ordem e o teste de manifesto acusa.

BEGIN;

-- ---------------------------------------------------------------------------------------------
-- 1) Guarda de alvo nas duas funcoes SECURITY DEFINER da 009
--
-- TG_RELID e o OID da tabela que disparou a trigger. Amarrar a funcao a UMA tabela e a defesa que
-- nao depende de GRANT nenhum: mesmo que alguem consiga instalar a trigger noutro lugar, ela
-- recusa. O REVOKE EXECUTE fica no papeis-e-privilegios.md (e GRANT, nao DDL) e e complementar --
-- as duas juntas sao cinto e suspensorio.
--
-- O corpo abaixo e IDENTICO ao da 009, com o bloco de guarda acrescentado logo apos o BEGIN.
-- ---------------------------------------------------------------------------------------------

CREATE OR REPLACE FUNCTION registra_perfil_permissoes_historico() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER
SET search_path = pg_catalog, public, pg_temp AS $$
DECLARE
  autor_texto text := current_setting('app.id_usuario', true);
  autor bigint := CASE WHEN autor_texto ~ '^[0-9]{1,18}$' THEN autor_texto::bigint END;
BEGIN
  -- Sem esta guarda, uma trigger instalada numa TEMP TABLE chama esta funcao SECURITY DEFINER e
  -- grava no historico com o privilegio do dono -- forjando concessao e revogacao.
  IF TG_RELID <> 'public.perfil_permissoes'::regclass THEN
    RAISE EXCEPTION 'registra_perfil_permissoes_historico so pode ser instalada em perfil_permissoes'
      USING ERRCODE = 'insufficient_privilege';
  END IF;

  IF TG_OP = 'INSERT' THEN
    INSERT INTO perfil_permissoes_historico
      (acao, id_perfil, id_permissao, nome_perfil, chave_permissao,
       concedido_em, concedido_por, registrado_por)
    VALUES ('concedida', NEW.id_perfil, NEW.id_permissao,
            rotulo_perfil(NEW.id_perfil), rotulo_permissao(NEW.id_permissao),
            NEW.concedido_em, NEW.concedido_por, autor);
    RETURN NEW;

  ELSIF TG_OP = 'DELETE' THEN
    INSERT INTO perfil_permissoes_historico
      (acao, id_perfil, id_permissao, nome_perfil, chave_permissao,
       concedido_em, concedido_por, registrado_por)
    VALUES ('revogada', OLD.id_perfil, OLD.id_permissao,
            rotulo_perfil(OLD.id_perfil), rotulo_permissao(OLD.id_permissao),
            OLD.concedido_em, OLD.concedido_por, autor);
    RETURN OLD;

  ELSE  -- UPDATE
    IF (OLD.id_perfil, OLD.id_permissao) IS DISTINCT FROM (NEW.id_perfil, NEW.id_permissao) THEN
      INSERT INTO perfil_permissoes_historico
        (acao, id_perfil, id_permissao, nome_perfil, chave_permissao,
         concedido_em, concedido_por, registrado_por)
      VALUES ('revogada', OLD.id_perfil, OLD.id_permissao,
              rotulo_perfil(OLD.id_perfil), rotulo_permissao(OLD.id_permissao),
              OLD.concedido_em, OLD.concedido_por, autor);
      INSERT INTO perfil_permissoes_historico
        (acao, id_perfil, id_permissao, nome_perfil, chave_permissao,
         concedido_em, concedido_por, registrado_por)
      VALUES ('concedida', NEW.id_perfil, NEW.id_permissao,
              rotulo_perfil(NEW.id_perfil), rotulo_permissao(NEW.id_permissao),
              NEW.concedido_em, NEW.concedido_por, autor);
    ELSE
      INSERT INTO perfil_permissoes_historico
        (acao, id_perfil, id_permissao, nome_perfil, chave_permissao,
         concedido_em, concedido_por, registrado_por)
      VALUES ('alterada', NEW.id_perfil, NEW.id_permissao,
              rotulo_perfil(NEW.id_perfil), rotulo_permissao(NEW.id_permissao),
              NEW.concedido_em, NEW.concedido_por, autor);
    END IF;
    RETURN NEW;
  END IF;
END;
$$;

CREATE OR REPLACE FUNCTION registra_perfil_permissoes_truncate() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER
SET search_path = pg_catalog, public, pg_temp AS $$
DECLARE
  autor_texto text := current_setting('app.id_usuario', true);
  autor bigint := CASE WHEN autor_texto ~ '^[0-9]{1,18}$' THEN autor_texto::bigint END;
BEGIN
  -- Mesma guarda. Esta e a mais barata de abusar sem ela: um TRUNCATE numa temp table VAZIA ja
  -- grava o marcador, sem precisar de coluna nenhuma que case com a juncao.
  IF TG_RELID <> 'public.perfil_permissoes'::regclass THEN
    RAISE EXCEPTION 'registra_perfil_permissoes_truncate so pode ser instalada em perfil_permissoes'
      USING ERRCODE = 'insufficient_privilege';
  END IF;

  INSERT INTO perfil_permissoes_historico (acao, id_perfil, id_permissao, registrado_por)
  VALUES ('truncada', 0, 0, autor);
  RETURN NULL;
END;
$$;

-- ---------------------------------------------------------------------------------------------
-- 2) search_path fixo nas tres funcoes de `atualizado_em` (008)
--
-- `pg_catalog, pg_temp` e o suficiente: elas nao referenciam objeto do schema `public`, so' now().
-- O `pg_temp` vai LISTADO e no FIM pelo mesmo motivo da 009 -- quando ele nao aparece, o Postgres
-- o pesquisa PRIMEIRO, que e exatamente o que se quer evitar.
-- ---------------------------------------------------------------------------------------------

CREATE OR REPLACE FUNCTION set_atualizado_em_usuario() RETURNS trigger
LANGUAGE plpgsql
SET search_path = pg_catalog, pg_temp AS $$
BEGIN NEW.atualizado_em_usuario = now(); RETURN NEW; END;
$$;

CREATE OR REPLACE FUNCTION set_atualizado_em_area_estudo() RETURNS trigger
LANGUAGE plpgsql
SET search_path = pg_catalog, pg_temp AS $$
BEGIN NEW.atualizado_em_area_estudo = now(); RETURN NEW; END;
$$;

CREATE OR REPLACE FUNCTION set_atualizado_em_contrato() RETURNS trigger
LANGUAGE plpgsql
SET search_path = pg_catalog, pg_temp AS $$
BEGIN NEW.atualizado_em_contrato = now(); RETURN NEW; END;
$$;

COMMIT;
