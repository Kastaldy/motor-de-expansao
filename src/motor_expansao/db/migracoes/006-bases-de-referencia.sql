-- ARQUIVO GERADO -- nao editar a mao.
-- Origem: banco-de-reservas/sql/006-bases-de-referencia.md (primeiro bloco ```sql).
-- sha256 do bloco extraido: 2db928b2544a6200a7f79e528f7546bb25367ab3ca959e1fee4d7daba46368ca
-- Regenerar: python scripts/extrair_migracoes.py --origem <.../banco-de-reservas/sql>
--
-- O `banco-de-reservas` e' a fonte da verdade do DESENHO (convencoes §7): mudanca de
-- modelo entra la' primeiro e so' depois vira migration aqui. Editar este arquivo
-- direto quebra essa ordem e o teste de manifesto acusa.

BEGIN;

CREATE TABLE municipios (
  cod_municipio  TEXT PRIMARY KEY,                                  -- CD_MUN (7 digitos)
  nome_municipio TEXT,
  uf_municipio   CHAR(2) CHECK (uf_municipio ~ '^[A-Z]{2}$'),
  geom_municipio geometry(MultiPolygon, 4674) NOT NULL,
  vintage        SMALLINT NOT NULL,                                 -- ano da malha IBGE (D13)
  carregado_em   TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_municipios_geom ON municipios USING GIST (geom_municipio);

CREATE TABLE distritos (
  cod_distrito  TEXT PRIMARY KEY,                                   -- CD_DIST (9 digitos)
  nome_distrito TEXT,
  cod_municipio TEXT NOT NULL REFERENCES municipios(cod_municipio) ON DELETE RESTRICT,
  uf_distrito   CHAR(2) CHECK (uf_distrito ~ '^[A-Z]{2}$'),
  geom_distrito geometry(MultiPolygon, 4674) NOT NULL,
  vintage       SMALLINT NOT NULL,
  carregado_em  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_distritos_geom          ON distritos USING GIST (geom_distrito);
CREATE INDEX IF NOT EXISTS idx_distritos_cod_municipio ON distritos (cod_municipio);

CREATE TABLE bairros (
  cod_bairro    TEXT PRIMARY KEY,                                   -- CD_BAIRRO (13 digitos, embute o municipio) D14
  nome_bairro   TEXT,
  cod_distrito  TEXT NOT NULL REFERENCES distritos(cod_distrito)  ON DELETE RESTRICT,
  nome_distrito TEXT,
  cod_municipio TEXT NOT NULL REFERENCES municipios(cod_municipio) ON DELETE RESTRICT,
  uf_bairro     CHAR(2) CHECK (uf_bairro ~ '^[A-Z]{2}$'),
  geom_bairro   geometry(MultiPolygon, 4674) NOT NULL,
  vintage       SMALLINT NOT NULL,
  carregado_em  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_bairros_geom          ON bairros USING GIST (geom_bairro);
CREATE INDEX IF NOT EXISTS idx_bairros_cod_distrito  ON bairros (cod_distrito);
CREATE INDEX IF NOT EXISTS idx_bairros_cod_municipio ON bairros (cod_municipio);

COMMIT;
