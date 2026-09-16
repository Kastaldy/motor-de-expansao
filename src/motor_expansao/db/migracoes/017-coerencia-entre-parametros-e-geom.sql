-- ARQUIVO GERADO -- nao editar a mao.
-- Origem: banco-de-reservas/sql/017-coerencia-entre-parametros-e-geom.md (primeiro bloco ```sql).
-- sha256 do bloco extraido: e5f12fd040e8f2dc89defe912070c3b2fb2113bf7cb9c986552cdaee10c88aea
-- Regenerar: python scripts/extrair_migracoes.py --origem <.../banco-de-reservas/sql>
--
-- O `banco-de-reservas` e' a fonte da verdade do DESENHO (convencoes §7): mudanca de
-- modelo entra la' primeiro e so' depois vira migration aqui. Editar este arquivo
-- direto quebra essa ordem e o teste de manifesto acusa.

BEGIN;

-- Funcao UNICA para as duas tabelas: os nomes das colunas chegam por TG_ARGV, porque a mesma
-- ideia tem nomes diferentes em cada uma -- `geom_area_estudo` numa, `area_influencia` na outra
-- (§5 do esquema). Duas funcoes gemeas divergiriam no primeiro conserto feito so' numa delas.
--
-- NAO e' SECURITY DEFINER: ela nao escreve nada e nao precisa de privilegio de dono. So' recusa.
CREATE OR REPLACE FUNCTION exige_geom_coerente() RETURNS trigger
LANGUAGE plpgsql
SET search_path = pg_catalog, pg_temp AS $$
DECLARE
  col_geom   text := TG_ARGV[0];
  col_param  text := TG_ARGV[1];
  col_metodo text := TG_ARGV[2];
  col_ponto  text := TG_ARGV[3];
  -- `to_jsonb` da linha inteira evita SQL dinamico para ler uma coluna cujo nome e' variavel.
  antes  jsonb := to_jsonb(OLD);
  depois jsonb := to_jsonb(NEW);
BEGIN
  -- A definicao mudou? Qualquer um dos tres que produzem a forma conta.
  IF     antes -> col_param  IS NOT DISTINCT FROM depois -> col_param
     AND antes -> col_metodo IS NOT DISTINCT FROM depois -> col_metodo
     AND antes -> col_ponto  IS NOT DISTINCT FROM depois -> col_ponto THEN
    RETURN NEW;   -- nada que produza a forma se mexeu: segue o baile
  END IF;

  -- Mudou a definicao. Entao a forma TEM de vir junta, no mesmo UPDATE.
  IF antes -> col_geom IS NOT DISTINCT FROM depois -> col_geom THEN
    RAISE EXCEPTION
      'a definicao da regiao mudou e % continuou igual: grave a forma nova no mesmo UPDATE',
      col_geom
      USING ERRCODE = 'integrity_constraint_violation',
            DETAIL  = format('tabela %s, colunas %s/%s/%s', TG_TABLE_NAME,
                             col_metodo, col_ponto, col_param),
            HINT    = 'o banco nao recalcula por voce: `isocrona` depende de servico externo e '
                      '`bairro`/`distrito`/`municipio` guardam SNAPSHOT com vintage, que '
                      'recalcular apagaria. Ver a 017 e o D29.';
  END IF;

  RETURN NEW;
END;
$$;

-- Os nomes comecam com `trg_<tabela>_c` DE PROPOSITO: trigger de mesmo tipo dispara em ordem
-- ALFABETICA, e `..._coerencia` vem antes de `..._upd` (a do `atualizado_em`, migration 008).
-- Assim a recusa acontece ANTES de o carimbo de tempo ser mexido -- uma linha recusada nao deve
-- deixar rastro de ter sido cuidada.
CREATE TRIGGER trg_areas_estudo_coerencia
  BEFORE UPDATE ON areas_estudo
  FOR EACH ROW
  EXECUTE FUNCTION exige_geom_coerente(
    'geom_area_estudo', 'parametros_area_estudo', 'metodo_area_estudo', 'ponto_area_estudo');

CREATE TRIGGER trg_contratos_coerencia
  BEFORE UPDATE ON contratos
  FOR EACH ROW
  EXECUTE FUNCTION exige_geom_coerente(
    'area_influencia', 'parametros_contrato', 'metodo_contrato', 'ponto_contrato');

COMMIT;
