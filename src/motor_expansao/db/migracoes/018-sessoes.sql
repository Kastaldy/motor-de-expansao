-- ARQUIVO GERADO -- nao editar a mao.
-- Origem: banco-de-reservas/sql/018-sessoes.md (primeiro bloco ```sql).
-- sha256 do bloco extraido: a411ab6fc6b51e6bf9c2bf4c90083f5767d45a7471c52c2b208aa614a49dd18a
-- Regenerar: python scripts/extrair_migracoes.py --origem <.../banco-de-reservas/sql>
--
-- O `banco-de-reservas` e' a fonte da verdade do DESENHO (convencoes §7): mudanca de
-- modelo entra la' primeiro e so' depois vira migration aqui. Editar este arquivo
-- direto quebra essa ordem e o teste de manifesto acusa.

BEGIN;

CREATE TABLE sessoes (
  id_sessao               BIGSERIAL PRIMARY KEY,
  id_usuario              BIGINT NOT NULL REFERENCES usuarios(id_usuario) ON DELETE CASCADE,
  -- NUNCA o token em claro. O que a aplicacao manda no cookie e' o segredo; aqui fica so' o
  -- hash dele, pelo mesmo raciocinio de `senha_hash`: um dump do banco nao pode permitir que
  -- alguem se passe por uma sessao viva. Hash rapido (SHA-256) e' suficiente e CORRETO aqui --
  -- diferente de senha, o token e' aleatorio de alta entropia, entao nao ha ataque de
  -- dicionario a encarecer, e Argon2 por requisicao custaria CPU sem comprar nada.
  token_hash_sessao       TEXT NOT NULL,
  criado_em_sessao        TIMESTAMPTZ NOT NULL DEFAULT now(),
  -- Teto ABSOLUTO da sessao. A decisao 2 da epic (duracao e inatividade) escolhe o numero; a
  -- coluna existe para que ele seja POLITICA e nao constante de codigo.
  expira_em_sessao        TIMESTAMPTZ NOT NULL,
  -- Ultimo uso, para a regra de INATIVIDADE (o Authelia usa `inactivity: 30m` hoje, e o
  -- `AvisoSessao` do front nasceu dessa realidade). Escrito pela APLICACAO, nao por trigger --
  -- ver a nota "por que nao ha trigger aqui".
  ultimo_acesso_em_sessao TIMESTAMPTZ NOT NULL DEFAULT now(),
  -- Revogacao explicita: logout, troca de senha, admin expulsando alguem. NULO = sessao viva.
  -- Coluna, e nao DELETE, porque "esta sessao foi encerrada, quando e por que" e' informacao de
  -- auditoria; apagar a linha responderia "nunca existiu", que e' outra coisa.
  revogada_em_sessao      TIMESTAMPTZ,
  -- Guarda de absurdo: sessao que nasce ja' vencida e' defeito de quem a criou, e sem este
  -- CHECK ela entraria em silencio e seria negada no primeiro uso -- com a pessoa vendo
  -- "sessao expirada" logo apos digitar a senha certa, que e' o pior diagnostico possivel.
  CONSTRAINT chk_sessao_expira_apos_criacao CHECK (expira_em_sessao > criado_em_sessao)
);

-- A consulta QUENTE: uma sessao e' procurada pelo hash do token, em toda requisicao guardada.
-- UNIQUE porque dois registros com o mesmo token seriam ambiguidade sobre QUEM esta' logado.
CREATE UNIQUE INDEX IF NOT EXISTS idx_sessoes_token_hash ON sessoes (token_hash_sessao);

-- toda FK ganha indice B-tree (convencoes 1)
CREATE INDEX IF NOT EXISTS idx_sessoes_id_usuario ON sessoes (id_usuario);

COMMIT;
