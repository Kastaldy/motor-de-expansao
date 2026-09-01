-- ARQUIVO GERADO -- nao editar a mao.
-- Origem: banco-de-reservas/sql/003-usuarios.md (primeiro bloco ```sql).
-- sha256 do bloco extraido: d1c182e8cc805febc63e45d3a7765949f273d6e0fa6961b4f11ad9eb121e93c2
-- Regenerar: python scripts/extrair_migracoes.py --origem <.../banco-de-reservas/sql>
--
-- O `banco-de-reservas` e' a fonte da verdade do DESENHO (convencoes §7): mudanca de
-- modelo entra la' primeiro e so' depois vira migration aqui. Editar este arquivo
-- direto quebra essa ordem e o teste de manifesto acusa.

BEGIN;

CREATE TABLE usuarios (
  id_usuario            BIGSERIAL PRIMARY KEY,
  nome_usuario          TEXT NOT NULL,
  email                 CITEXT NOT NULL,
  senha_hash            TEXT NOT NULL,
  id_perfil             BIGINT NOT NULL REFERENCES perfis(id_perfil) ON DELETE RESTRICT,
  ativo                 BOOLEAN NOT NULL DEFAULT TRUE,
  criado_em_usuario     TIMESTAMPTZ NOT NULL DEFAULT now(),
  atualizado_em_usuario TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- toda FK ganha indice B-tree (convencoes 1)
CREATE INDEX IF NOT EXISTS idx_usuarios_id_perfil ON usuarios (id_perfil);

-- D9: e-mail unico apenas entre usuarios ATIVOS -> libera reuso do e-mail de um desativado
CREATE UNIQUE INDEX IF NOT EXISTS idx_usuarios_email_ativo ON usuarios (email) WHERE ativo;

COMMIT;
