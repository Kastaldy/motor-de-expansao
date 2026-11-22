-- ARQUIVO GERADO -- nao editar a mao.
-- Origem: banco-de-reservas/sql/026-permissao-masters.md (primeiro bloco ```sql).
-- sha256 do bloco extraido: c49c952bbd89cd3939beb531ed5ddc92df1a17b2b7993b5202884d5bf72d09d5
-- Regenerar: python scripts/extrair_migracoes.py --origem <.../banco-de-reservas/sql>
--
-- O `banco-de-reservas` e' a fonte da verdade do DESENHO (convencoes §7): mudanca de
-- modelo entra la' primeiro e so' depois vira migration aqui. Editar este arquivo
-- direto quebra essa ordem e o teste de manifesto acusa.

BEGIN;

-- A capacidade nova. Descricao com o mesmo cuidado das outras: ela vira ROTULO DE TELA, e a
-- verificacao mede char_length/octet_length para pegar duplo-encoding (convencoes §5).
INSERT INTO permissoes (chave, descricao_permissao) VALUES
  ('masters.ver', 'Ver a tela Masters: contratos, metas e unidades de cada master'); -- GET /api/masters

-- Growth e lideres (decisao de produto de 18/11/2026, DEC-089). Escrito como consulta, e nao com
-- id literal, pelo mesmo motivo da 012: `id_perfil`/`id_permissao` sao BIGSERIAL e dependem da
-- ordem de insercao. A trigger de auditoria do D19 grava `registrado_por` NULO, como na 015.
INSERT INTO perfil_permissoes (id_perfil, id_permissao)
SELECT p.id_perfil, pe.id_permissao
FROM perfis p
JOIN permissoes pe ON TRUE
WHERE (p.nome_perfil, pe.chave) IN (
  ('growth', 'masters.ver'),
  ('lideres', 'masters.ver')
);

COMMIT;
