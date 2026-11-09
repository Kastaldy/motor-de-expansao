-- ARQUIVO GERADO -- nao editar a mao.
-- Origem: banco-de-reservas/sql/022-sso-tickets.md (primeiro bloco ```sql).
-- sha256 do bloco extraido: 1f9451927659914410117186913b92fdd9295aaadb14457deebd2f195463852f
-- Regenerar: python scripts/extrair_migracoes.py --origem <.../banco-de-reservas/sql>
--
-- O `banco-de-reservas` e' a fonte da verdade do DESENHO (convencoes §7): mudanca de
-- modelo entra la' primeiro e so' depois vira migration aqui. Editar este arquivo
-- direto quebra essa ordem e o teste de manifesto acusa.

BEGIN;

CREATE TABLE sso_tickets (
  id_ticket            BIGSERIAL PRIMARY KEY,
  id_usuario           BIGINT NOT NULL REFERENCES usuarios(id_usuario) ON DELETE CASCADE,
  -- NUNCA o ticket em claro -- so' o SHA-256, MESMA razao de sessoes.token_hash_sessao: um dump
  -- do banco nao pode permitir forjar um handoff vivo. Token aleatorio de alta entropia
  -- (secrets.token_urlsafe), entao hash rapido e' o certo -- Argon2 nao compra defesa aqui.
  token_hash_ticket    TEXT NOT NULL,
  -- O pais do HOST de destino. O ticket vale para UM host so': consumi-lo noutro pais e' negado
  -- (o consumo reexige pais_destino == PERFIL.pais, defesa em profundidade). MESMO tipo/regra de
  -- usuario_paises.pais -- sigla ISO de 2 letras MAIUSCULAS (convencoes 2, _RE_PAIS do perfil.py).
  pais_destino         CHAR(2) NOT NULL,
  criado_em_ticket     TIMESTAMPTZ NOT NULL DEFAULT now(),
  -- TTL CURTO (a aplicacao poe ~60s). Coluna e nao constante de codigo, como expira_em_sessao: a
  -- politica de janela muda sem migration.
  expira_em_ticket     TIMESTAMPTZ NOT NULL,
  -- USO UNICO: NULL = ainda nao consumido. O consumo e' `UPDATE ... SET consumido_em_ticket = now()
  -- WHERE token_hash = %s AND consumido_em_ticket IS NULL AND expira_em_ticket > now() RETURNING`,
  -- atomico: replay concorrente so' acha a linha uma vez. NAO e' DELETE para o expurgo poder
  -- distinguir "consumido" de "expirado sem uso" por uma janela curta de auditoria.
  consumido_em_ticket  TIMESTAMPTZ,
  -- Auditoria: de qual sessao (host de origem) o ticket nasceu. SET NULL e nao CASCADE porque a
  -- origem some por expurgo/anonimizacao sem precisar apagar o rastro do handoff.
  id_sessao_origem     BIGINT REFERENCES sessoes(id_sessao) ON DELETE SET NULL,
  -- Mesma sigla controlada da usuario_paises.
  CONSTRAINT chk_sso_ticket_sigla CHECK (pais_destino ~ '^[A-Z]{2}$'),
  -- Guarda de absurdo, molde do chk_sessao_expira_apos_criacao: ticket que nasce vencido e' defeito
  -- de quem o criou, e sem o CHECK entraria em silencio e seria negado no consumo.
  CONSTRAINT chk_sso_ticket_expira_apos_criacao CHECK (expira_em_ticket > criado_em_ticket)
);

-- A consulta QUENTE do consumo: achar o ticket pelo hash do token. UNIQUE porque dois tickets com
-- o mesmo token seriam ambiguidade sobre QUEM esta' entrando.
CREATE UNIQUE INDEX IF NOT EXISTS idx_sso_tickets_token_hash ON sso_tickets (token_hash_ticket);

-- toda FK ganha indice B-tree (convencoes 1)
CREATE INDEX IF NOT EXISTS idx_sso_tickets_id_usuario ON sso_tickets (id_usuario);

COMMIT;
