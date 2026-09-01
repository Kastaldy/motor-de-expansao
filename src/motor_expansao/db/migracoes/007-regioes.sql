-- ARQUIVO GERADO -- nao editar a mao.
-- Origem: banco-de-reservas/sql/007-regioes.md (primeiro bloco ```sql).
-- sha256 do bloco extraido: bb68805dd6b7355fdb8c015bbb2cfdcd2334aa78755a9317ac6f0d589ca7c411
-- Regenerar: python scripts/extrair_migracoes.py --origem <.../banco-de-reservas/sql>
--
-- O `banco-de-reservas` e' a fonte da verdade do DESENHO (convencoes §7): mudanca de
-- modelo entra la' primeiro e so' depois vira migration aqui. Editar este arquivo
-- direto quebra essa ordem e o teste de manifesto acusa.

BEGIN;

CREATE TABLE areas_estudo (
  id_area_estudo            BIGSERIAL PRIMARY KEY,
  nome_area_estudo          TEXT NOT NULL,
  status_area_estudo        TEXT NOT NULL CHECK (status_area_estudo IN ('em_observacao','analisada','descartada')),
  metodo_area_estudo        TEXT NOT NULL CHECK (metodo_area_estudo IN ('raio','isocrona','bairro','distrito','municipio','poligono_livre')),
  ponto_area_estudo         geometry(Point, 4674) NOT NULL,
  parametros_area_estudo    JSONB,
  geom_area_estudo          geometry(MultiPolygon, 4674) NOT NULL,
  criado_por_area_estudo    BIGINT NOT NULL REFERENCES usuarios(id_usuario) ON DELETE RESTRICT,
  criado_em_area_estudo     TIMESTAMPTZ NOT NULL DEFAULT now(),
  atualizado_em_area_estudo TIMESTAMPTZ NOT NULL DEFAULT now(),
  -- D15: coerencia metodo <-> parametros; cada metodo exige suas chaves
  CONSTRAINT chk_ae_metodo_parametros CHECK (
    (metodo_area_estudo <> 'raio'     OR COALESCE(parametros_area_estudo ? 'raio_m', false)) AND
    (metodo_area_estudo <> 'isocrona' OR COALESCE(parametros_area_estudo ? 'minutos', false)) AND
    (metodo_area_estudo NOT IN ('bairro','distrito','municipio') OR COALESCE(parametros_area_estudo ? 'cod', false))
  )
);

CREATE INDEX IF NOT EXISTS idx_areas_estudo_geom       ON areas_estudo USING GIST (geom_area_estudo);
CREATE INDEX IF NOT EXISTS idx_areas_estudo_ponto      ON areas_estudo USING GIST (ponto_area_estudo);
CREATE INDEX IF NOT EXISTS idx_areas_estudo_criado_por ON areas_estudo (criado_por_area_estudo);
CREATE INDEX IF NOT EXISTS idx_areas_estudo_status     ON areas_estudo (status_area_estudo);
-- indice funcional: e este (nao o GiST da geometria pura) que serve ST_DWithin em geography
CREATE INDEX IF NOT EXISTS idx_areas_estudo_geom_geography ON areas_estudo USING GIST ((geom_area_estudo::geography));

CREATE TABLE contratos (
  id_contrato            BIGSERIAL PRIMARY KEY,
  nome_contrato          TEXT NOT NULL,
  status_contrato        TEXT NOT NULL CHECK (status_contrato IN ('em_desenvolvimento','ativo','encerrado')),
  ponto_contrato         geometry(Point, 4674) NOT NULL,
  metodo_contrato        TEXT NOT NULL CHECK (metodo_contrato IN ('raio','isocrona','bairro','distrito','municipio','poligono_livre')),
  parametros_contrato    JSONB,
  area_influencia        geometry(MultiPolygon, 4674) NOT NULL,
  id_area_estudo         BIGINT REFERENCES areas_estudo(id_area_estudo) ON DELETE SET NULL,
  criado_por_contrato    BIGINT NOT NULL REFERENCES usuarios(id_usuario) ON DELETE RESTRICT,
  criado_em_contrato     TIMESTAMPTZ NOT NULL DEFAULT now(),
  atualizado_em_contrato TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT chk_ct_metodo_parametros CHECK (        -- D15
    (metodo_contrato <> 'raio'     OR COALESCE(parametros_contrato ? 'raio_m', false)) AND
    (metodo_contrato <> 'isocrona' OR COALESCE(parametros_contrato ? 'minutos', false)) AND
    (metodo_contrato NOT IN ('bairro','distrito','municipio') OR COALESCE(parametros_contrato ? 'cod', false))
  )
);

CREATE INDEX IF NOT EXISTS idx_contratos_area_influencia           ON contratos USING GIST (area_influencia);
CREATE INDEX IF NOT EXISTS idx_contratos_ponto                     ON contratos USING GIST (ponto_contrato);
CREATE INDEX IF NOT EXISTS idx_contratos_id_area_estudo            ON contratos (id_area_estudo);
CREATE INDEX IF NOT EXISTS idx_contratos_criado_por                ON contratos (criado_por_contrato);
CREATE INDEX IF NOT EXISTS idx_contratos_status                    ON contratos (status_contrato);
CREATE INDEX IF NOT EXISTS idx_contratos_area_influencia_geography ON contratos USING GIST ((area_influencia::geography));

-- D16: no maximo UM contrato nao-encerrado por area de estudo; repromocao so apos encerrar
CREATE UNIQUE INDEX IF NOT EXISTS idx_contratos_id_area_estudo_nao_encerrado ON contratos (id_area_estudo)
  WHERE id_area_estudo IS NOT NULL AND status_contrato <> 'encerrado';

COMMIT;
