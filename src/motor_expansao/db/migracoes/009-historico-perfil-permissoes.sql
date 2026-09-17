-- ARQUIVO GERADO -- nao editar a mao.
-- Origem: banco-de-reservas/sql/009-historico-perfil-permissoes.md (primeiro bloco ```sql).
-- sha256 do bloco extraido: 89b46c7ea710ebe6070407291f5674347e0e76d789f6f44e812de027d775b86e
-- Regenerar: python scripts/extrair_migracoes.py --origem <.../banco-de-reservas/sql>
--
-- O `banco-de-reservas` e' a fonte da verdade do DESENHO (convencoes §7): mudanca de
-- modelo entra la' primeiro e so' depois vira migration aqui. Editar este arquivo
-- direto quebra essa ordem e o teste de manifesto acusa.

BEGIN;

CREATE TABLE perfil_permissoes_historico (
  id_perfil_permissoes_historico BIGSERIAL PRIMARY KEY,
  acao            TEXT NOT NULL CHECK (acao IN ('concedida','revogada','alterada','truncada')),
  -- SEM FK de proposito (mesmo racional do D8): o historico precisa sobreviver ao perfil ou a
  -- permissao apagados. Com CASCADE seria apagado junto; com RESTRICT travaria a exclusao.
  id_perfil       BIGINT NOT NULL,
  id_permissao    BIGINT NOT NULL,
  -- snapshot dos rotulos (mesmo racional do D4): sem eles, o id de uma permissao apagada vira
  -- orfao ilegivel e o historico perde o dado que a auditoria procura ("qual permissao era?")
  nome_perfil     TEXT,
  chave_permissao TEXT,
  concedido_em    TIMESTAMPTZ,   -- da linha original, preservados na revogacao
  concedido_por   BIGINT,
  -- clock_timestamp() e nao now(): num log append-only a ordem REAL dos eventos e o dado. now()
  -- devolve o inicio da TRANSACAO, entao duas acoes na mesma transacao sairiam com o mesmo
  -- instante, e duas sessoes concorrentes podem sair fora de ordem (ver "Por que clock_timestamp").
  registrado_em   TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),   -- desta acao
  registrado_por  BIGINT
);

CREATE INDEX IF NOT EXISTS idx_perfil_permissoes_historico_id_perfil     ON perfil_permissoes_historico (id_perfil);
CREATE INDEX IF NOT EXISTS idx_perfil_permissoes_historico_id_permissao  ON perfil_permissoes_historico (id_permissao);
CREATE INDEX IF NOT EXISTS idx_perfil_permissoes_historico_registrado_em ON perfil_permissoes_historico (registrado_em);

-- Rotulos legiveis, com fallback ao proprio historico.
-- Numa revogacao por ON DELETE CASCADE a linha-pai JA foi removida quando a trigger da juncao
-- dispara (o cascade e um AFTER trigger na tabela pai), entao o SELECT direto devolveria NULL --
-- justo no caso em que o rotulo mais importa. A concessao original gravou o rotulo enquanto o
-- objeto existia; e de la que ele e recuperado.
-- O SET search_path e obrigatorio, e o pg_temp precisa aparecer NELE, no fim: quando pg_temp nao
-- e listado, o Postgres o pesquisa PRIMEIRO -- entao qualquer papel cria uma tabela temporaria de
-- mesmo nome e sequestra a leitura e a escrita da auditoria (ver "Notas").
CREATE OR REPLACE FUNCTION rotulo_perfil(p_id_perfil bigint) RETURNS text
LANGUAGE sql STABLE
SET search_path = pg_catalog, public, pg_temp AS $$
  SELECT COALESCE(
    (SELECT p.nome_perfil FROM perfis p WHERE p.id_perfil = p_id_perfil),
    (SELECT h.nome_perfil FROM perfil_permissoes_historico h
      WHERE h.id_perfil = p_id_perfil AND h.nome_perfil IS NOT NULL
      ORDER BY h.id_perfil_permissoes_historico DESC LIMIT 1)
  );
$$;

CREATE OR REPLACE FUNCTION rotulo_permissao(p_id_permissao bigint) RETURNS text
LANGUAGE sql STABLE
SET search_path = pg_catalog, public, pg_temp AS $$
  SELECT COALESCE(
    (SELECT pe.chave FROM permissoes pe WHERE pe.id_permissao = p_id_permissao),
    (SELECT h.chave_permissao FROM perfil_permissoes_historico h
      WHERE h.id_permissao = p_id_permissao AND h.chave_permissao IS NOT NULL
      ORDER BY h.id_perfil_permissoes_historico DESC LIMIT 1)
  );
$$;

-- SECURITY DEFINER: a trigger grava com o privilegio do DONO, entao o papel da aplicacao nao
-- precisa de nenhum privilegio no historico -- e por isso nao consegue forjar nem apagar linha
-- nenhuma la. Com SECURITY INVOKER (o padrao) seria o oposto: para a trigger funcionar seria
-- preciso dar SELECT+INSERT no historico ao mesmo papel que a auditoria existe para vigiar.
CREATE OR REPLACE FUNCTION registra_perfil_permissoes_historico() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER
SET search_path = pg_catalog, public, pg_temp AS $$
DECLARE
  -- quem esta agindo: a aplicacao declara com SET LOCAL app.id_usuario = '<id>' na transacao.
  -- O 'true' e missing_ok: sem a variavel definida, devolve NULL em vez de estourar. Nao da para
  -- trocar por IS NULL depois: RESET app.id_usuario deixa a GUC como string VAZIA, nao NULL.
  autor_texto text := current_setting('app.id_usuario', true);
  -- valida ANTES do cast. Identidade nao-numerica (UUID, login, 'null', um espaco) derrubaria a
  -- transacao inteira com 22P02 -- inclusive o que veio antes dela. Aqui vira NULL: a acao fica
  -- registrada sem autoria, que e o mesmo caso do SQL manual. Ate 18 digitos cabe em bigint.
  autor bigint := CASE WHEN autor_texto ~ '^[0-9]{1,18}$' THEN autor_texto::bigint END;
BEGIN
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
      -- o par mudou: na pratica o antigo deixou de valer e o novo passou a valer
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
      -- mesmo par, mudou so a auditoria da concessao: NAO houve interrupcao de acesso, e
      -- registrar 'revogada'+'concedida' aqui mentiria sobre uma janela sem acesso
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

-- TRUNCATE nao passa por trigger de linha: apagaria a juncao inteira sem uma linha de historico.
-- Uma trigger de statement nao enxerga as linhas apagadas, entao grava um MARCADOR -- que e a
-- diferenca entre "nao sabemos que houve" e "sabemos quando e por quem".
CREATE OR REPLACE FUNCTION registra_perfil_permissoes_truncate() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER
SET search_path = pg_catalog, public, pg_temp AS $$
DECLARE
  autor_texto text := current_setting('app.id_usuario', true);
  autor bigint := CASE WHEN autor_texto ~ '^[0-9]{1,18}$' THEN autor_texto::bigint END;
BEGIN
  -- id_perfil/id_permissao sao NOT NULL e o marcador nao se refere a um par especifico: vao com 0,
  -- valor que nenhuma BIGSERIAL gera. Os rotulos ficam NULL pelo mesmo motivo.
  INSERT INTO perfil_permissoes_historico (acao, id_perfil, id_permissao, registrado_por)
  VALUES ('truncada', 0, 0, autor);
  RETURN NULL;   -- statement-level AFTER: o valor de retorno e ignorado
END;
$$;

CREATE TRIGGER trg_perfil_permissoes_auditoria
  AFTER INSERT OR UPDATE OR DELETE ON perfil_permissoes
  FOR EACH ROW EXECUTE FUNCTION registra_perfil_permissoes_historico();

CREATE TRIGGER trg_perfil_permissoes_auditoria_truncate
  AFTER TRUNCATE ON perfil_permissoes
  FOR EACH STATEMENT EXECUTE FUNCTION registra_perfil_permissoes_truncate();

COMMIT;
