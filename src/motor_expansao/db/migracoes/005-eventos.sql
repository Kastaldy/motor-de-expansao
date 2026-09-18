-- ARQUIVO GERADO -- nao editar a mao.
-- Origem: banco-de-reservas/sql/005-eventos.md (primeiro bloco ```sql).
-- sha256 do bloco extraido: 813aab1bdc77b87321ff624fcd26e65aa418b2bafbd45f7d701529c0c8c987c6
-- Regenerar: python scripts/extrair_migracoes.py --origem <.../banco-de-reservas/sql>
--
-- O `banco-de-reservas` e' a fonte da verdade do DESENHO (convencoes §7): mudanca de
-- modelo entra la' primeiro e so' depois vira migration aqui. Editar este arquivo
-- direto quebra essa ordem e o teste de manifesto acusa.

BEGIN;

CREATE TABLE eventos (
  id_evento        BIGSERIAL PRIMARY KEY,
  id_usuario       BIGINT REFERENCES usuarios(id_usuario) ON DELETE SET NULL,  -- NULL = evento de sistema
  tipo             TEXT NOT NULL,          -- ex.: login, relatorio.gerado, contrato.criado
  entidade         TEXT,                   -- area_estudo | contrato | NULL
  entidade_id      BIGINT,                 -- PK da tabela indicada por 'entidade' (ref. polimorfica, sem FK)
  metadados        JSONB,                  -- payload tecnico do evento (sem PII)
  ip               INET,
  criado_em_evento TIMESTAMPTZ NOT NULL DEFAULT now(),
  -- o par polimorfico anda junto: ambos nulos (sistema) ou ambos preenchidos (objeto)
  CONSTRAINT chk_evento_entidade CHECK ((entidade IS NULL) = (entidade_id IS NULL)),
  -- D11: valores de 'entidade' travados; 'tipo' segue livre
  CONSTRAINT chk_evento_entidade_valor CHECK (entidade IS NULL OR entidade IN ('area_estudo','contrato'))
);

CREATE INDEX IF NOT EXISTS idx_eventos_tipo_criado_em       ON eventos (tipo, criado_em_evento);
CREATE INDEX IF NOT EXISTS idx_eventos_id_usuario_criado_em ON eventos (id_usuario, criado_em_evento);
CREATE INDEX IF NOT EXISTS idx_eventos_entidade_entidade_id ON eventos (entidade, entidade_id);

-- D17: lookup do relatorio vazado pelo report_id embutido no PDF
CREATE INDEX IF NOT EXISTS idx_eventos_metadados_report_id
  ON eventos ((metadados->>'report_id')) WHERE tipo = 'relatorio.gerado';

COMMIT;
