-- ARQUIVO GERADO -- nao editar a mao.
-- Origem: banco-de-reservas/sql/004-perfil-permissoes.md (primeiro bloco ```sql).
-- sha256 do bloco extraido: 56f7b9038e16be7c64ab6ac859b01d0d8bdab00f17254f3e5b2a53bce3823997
-- Regenerar: python scripts/extrair_migracoes.py --origem <.../banco-de-reservas/sql>
--
-- O `banco-de-reservas` e' a fonte da verdade do DESENHO (convencoes §7): mudanca de
-- modelo entra la' primeiro e so' depois vira migration aqui. Editar este arquivo
-- direto quebra essa ordem e o teste de manifesto acusa.

BEGIN;

CREATE TABLE perfil_permissoes (
  id_perfil     BIGINT NOT NULL REFERENCES perfis(id_perfil) ON DELETE CASCADE,
  id_permissao  BIGINT NOT NULL REFERENCES permissoes(id_permissao) ON DELETE CASCADE,
  concedido_em  TIMESTAMPTZ NOT NULL DEFAULT now(),                        -- auditoria (D12)
  concedido_por BIGINT REFERENCES usuarios(id_usuario) ON DELETE SET NULL, -- NULL = seed/sistema
  PRIMARY KEY (id_perfil, id_permissao)
);

-- a PK (id_perfil, id_permissao) ja serve "permissoes de um perfil";
-- o indice reverso serve "quais perfis tem a permissao X" (auditoria)
CREATE INDEX IF NOT EXISTS idx_perfil_permissoes_id_permissao  ON perfil_permissoes (id_permissao);
CREATE INDEX IF NOT EXISTS idx_perfil_permissoes_concedido_por ON perfil_permissoes (concedido_por);

COMMIT;
