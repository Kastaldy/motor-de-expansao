-- ARQUIVO GERADO -- nao editar a mao.
-- Origem: banco-de-reservas/sql/013-login-do-usuario.md (primeiro bloco ```sql).
-- sha256 do bloco extraido: 40c5e9c7c551a8b7e6309417817eb1ddd22ecf28bdab1e9f55716154e70aad9b
-- Regenerar: python scripts/extrair_migracoes.py --origem <.../banco-de-reservas/sql>
--
-- O `banco-de-reservas` e' a fonte da verdade do DESENHO (convencoes §7): mudanca de
-- modelo entra la' primeiro e so' depois vira migration aqui. Editar este arquivo
-- direto quebra essa ordem e o teste de manifesto acusa.

BEGIN;

-- `CITEXT` pelo mesmo motivo do `email` (§3.1 / convencoes §2): identidade nao pode depender de
-- caixa. `Felipe` e `felipe` sao a mesma pessoa, e o proprio motor ja' trata assim -- a allowlist
-- do painel de acessos compara com `casefold()`.
--
-- `NOT NULL` sem DEFAULT: so' passa em tabela VAZIA, que e' o estado de `usuarios` depois do
-- roteiro 001->012 (nenhuma migration insere pessoa). Se houver linhas, esta migration FALHA -- e
-- deve falhar: inventar um login para quem ja' existe e' decisao de quem conhece as pessoas, nao
-- de um DEFAULT.
ALTER TABLE usuarios ADD COLUMN login_usuario CITEXT NOT NULL;

-- Unico entre ATIVOS, espelhando o D9 do e-mail: desativar alguem libera o login para reuso, e
-- logins de inativos podem coexistir. Sem isto, dois ativos com o mesmo `Remote-User` fariam a
-- resolucao de identidade devolver a linha errada -- em silencio.
CREATE UNIQUE INDEX IF NOT EXISTS idx_usuarios_login_ativo ON usuarios (login_usuario) WHERE ativo;

COMMIT;
