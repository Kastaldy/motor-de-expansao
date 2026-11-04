-- ARQUIVO GERADO -- nao editar a mao.
-- Origem: banco-de-reservas/sql/021-usuario-paises.md (primeiro bloco ```sql).
-- sha256 do bloco extraido: 280da9ec44a2f89df0c19330ea48eb616863c6a946947fbca5770edcf18b4a2e
-- Regenerar: python scripts/extrair_migracoes.py --origem <.../banco-de-reservas/sql>
--
-- O `banco-de-reservas` e' a fonte da verdade do DESENHO (convencoes §7): mudanca de
-- modelo entra la' primeiro e so' depois vira migration aqui. Editar este arquivo
-- direto quebra essa ordem e o teste de manifesto acusa.

BEGIN;

CREATE TABLE usuario_paises (
  id_usuario BIGINT NOT NULL REFERENCES usuarios(id_usuario) ON DELETE CASCADE,
  -- Sigla ISO de 2 letras MAIUSCULAS -- o MESMO tipo/regra do UF do schema (convencoes 2) e do
  -- _RE_PAIS do perfil.py. E' VALOR controlado, nao FK: o gate compara PERFIL.pais `in` estes
  -- valores. `pais` fica SEM sufixo de tabela por ser valor universal cujo nome ja' e' unico --
  -- excecao DECLARADA em convencoes.md 1 (sem a declaracao, leria como defeito, nao estilo).
  pais       CHAR(2) NOT NULL,
  CONSTRAINT chk_usuario_paises_sigla CHECK (pais ~ '^[A-Z]{2}$'),
  -- PK composta: uma pessoa nao pode ter o mesmo pais duas vezes. Serve tambem "os paises de uma
  -- pessoa" (prefixo id_usuario), que e' a consulta QUENTE do gate (uma ida indexada por login).
  PRIMARY KEY (id_usuario, pais)
);

-- Backfill: toda pessoa que ja' existe e' BR, porque este e' o banco de producao do Brasil (a AR
-- ainda nao tem banco -- entra no Estagio 2 da DEC-081 com o seed 'AR'). Sem este backfill, o gate
-- fail-closed (`BR not in {}`) negaria a REDE INTEIRA no primeiro deploy -- o defeito P4 da
-- verificacao. ON CONFLICT DO NOTHING torna o backfill idempotente (molde do seed 010/012). Sem
-- filtro de `ativo`: pessoa reativada depois nao pode nascer sem pais.
INSERT INTO usuario_paises (id_usuario, pais)
SELECT id_usuario, 'BR' FROM usuarios
ON CONFLICT (id_usuario, pais) DO NOTHING;

COMMIT;
