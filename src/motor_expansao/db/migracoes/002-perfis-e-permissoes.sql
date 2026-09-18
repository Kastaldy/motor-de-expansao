-- ARQUIVO GERADO -- nao editar a mao.
-- Origem: banco-de-reservas/sql/002-perfis-e-permissoes.md (primeiro bloco ```sql).
-- sha256 do bloco extraido: 7c8ed3ed674bb19c1aca676aff5019bb20e051edd9edfb6ee5f7c0ee854efc8d
-- Regenerar: python scripts/extrair_migracoes.py --origem <.../banco-de-reservas/sql>
--
-- O `banco-de-reservas` e' a fonte da verdade do DESENHO (convencoes §7): mudanca de
-- modelo entra la' primeiro e so' depois vira migration aqui. Editar este arquivo
-- direto quebra essa ordem e o teste de manifesto acusa.

BEGIN;

CREATE TABLE perfis (
  id_perfil        BIGSERIAL PRIMARY KEY,
  nome_perfil      TEXT NOT NULL UNIQUE,
  descricao_perfil TEXT
);

CREATE TABLE permissoes (
  id_permissao        BIGSERIAL PRIMARY KEY,
  chave               TEXT NOT NULL UNIQUE,   -- padrao recurso.acao (ex.: contrato.criar)
  descricao_permissao TEXT
);

COMMIT;
