-- ARQUIVO GERADO -- nao editar a mao.
-- Origem: banco-de-reservas/sql/014-indices-de-metadados.md (primeiro bloco ```sql).
-- sha256 do bloco extraido: be4e5129252ff33ac10de26acd342a612f5e46a406319a8fd057e14f6c06fb2c
-- Regenerar: python scripts/extrair_migracoes.py --origem <.../banco-de-reservas/sql>
--
-- O `banco-de-reservas` e' a fonte da verdade do DESENHO (convencoes §7): mudanca de
-- modelo entra la' primeiro e so' depois vira migration aqui. Editar este arquivo
-- direto quebra essa ordem e o teste de manifesto acusa.

BEGIN;

-- Tres indices de expressao, um por entidade do motor, no molde do
-- `idx_eventos_metadados_report_id` que ja' existe (D17).
--
-- COMPOSTOS com `criado_em_evento` porque a pergunta e' "o historico deste objeto, do mais
-- recente para o mais antigo" -- o mesmo motivo que fez `idx_eventos_tipo_criado_em` e
-- `idx_eventos_id_usuario_criado_em` serem compostos.
--
-- PARCIAIS pelo predicado `IS NOT NULL` sobre a propria chave: sem ele, o btree indexaria um
-- NULL por linha que nao tem a chave, e cada indice ficaria do tamanho da tabela inteira.
-- O predicado por PRESENCA (e nao por lista de `tipo`, como o do report_id) se mantem sozinho
-- quando o vocabulario de `tipo` crescer -- e ele vai crescer.
--
-- AGORA, e nao quando a camada de gravacao existir: `eventos` e' append-only, e acrescentar
-- indice a uma tabela ja' povoada exige `CREATE INDEX CONCURRENTLY`, que NAO roda dentro de
-- bloco de transacao. Todas as migrations sao `BEGIN; ... COMMIT;`. Numa tabela vazia, custa zero.

CREATE INDEX IF NOT EXISTS idx_eventos_metadados_imovel_id
  ON eventos ((metadados->>'imovel_id'), criado_em_evento)
  WHERE (metadados->>'imovel_id') IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_eventos_metadados_unidade_id
  ON eventos ((metadados->>'unidade_id'), criado_em_evento)
  WHERE (metadados->>'unidade_id') IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_eventos_metadados_hex_id
  ON eventos ((metadados->>'hex_id'), criado_em_evento)
  WHERE (metadados->>'hex_id') IS NOT NULL;

COMMIT;
