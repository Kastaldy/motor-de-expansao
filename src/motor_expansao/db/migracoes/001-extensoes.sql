-- ARQUIVO GERADO -- nao editar a mao.
-- Origem: banco-de-reservas/sql/001-extensoes.md (primeiro bloco ```sql).
-- sha256 do bloco extraido: 4213e537ea97f9ca011acf10f59fcdbb5d31b54bcac5c63d40bed3b01bf85a76
-- Regenerar: python scripts/extrair_migracoes.py --origem <.../banco-de-reservas/sql>
--
-- O `banco-de-reservas` e' a fonte da verdade do DESENHO (convencoes §7): mudanca de
-- modelo entra la' primeiro e so' depois vira migration aqui. Editar este arquivo
-- direto quebra essa ordem e o teste de manifesto acusa.

CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS citext;

-- conferencia
SELECT postgis_full_version();
SELECT extname, extversion FROM pg_extension ORDER BY extname;
