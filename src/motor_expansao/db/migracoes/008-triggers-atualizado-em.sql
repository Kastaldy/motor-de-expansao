-- ARQUIVO GERADO -- nao editar a mao.
-- Origem: banco-de-reservas/sql/008-triggers-atualizado-em.md (primeiro bloco ```sql).
-- sha256 do bloco extraido: 9f22f59ecbd44a1eae05d43858566a56824ca7b55cc3aec29de4ca67cf4aa657
-- Regenerar: python scripts/extrair_migracoes.py --origem <.../banco-de-reservas/sql>
--
-- O `banco-de-reservas` e' a fonte da verdade do DESENHO (convencoes §7): mudanca de
-- modelo entra la' primeiro e so' depois vira migration aqui. Editar este arquivo
-- direto quebra essa ordem e o teste de manifesto acusa.

BEGIN;

CREATE OR REPLACE FUNCTION set_atualizado_em_usuario() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN NEW.atualizado_em_usuario = now(); RETURN NEW; END;
$$;

CREATE OR REPLACE FUNCTION set_atualizado_em_area_estudo() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN NEW.atualizado_em_area_estudo = now(); RETURN NEW; END;
$$;

CREATE OR REPLACE FUNCTION set_atualizado_em_contrato() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN NEW.atualizado_em_contrato = now(); RETURN NEW; END;
$$;

CREATE TRIGGER trg_usuarios_upd BEFORE UPDATE ON usuarios
  FOR EACH ROW EXECUTE FUNCTION set_atualizado_em_usuario();

CREATE TRIGGER trg_areas_estudo_upd BEFORE UPDATE ON areas_estudo
  FOR EACH ROW EXECUTE FUNCTION set_atualizado_em_area_estudo();

CREATE TRIGGER trg_contratos_upd BEFORE UPDATE ON contratos
  FOR EACH ROW EXECUTE FUNCTION set_atualizado_em_contrato();

COMMIT;
