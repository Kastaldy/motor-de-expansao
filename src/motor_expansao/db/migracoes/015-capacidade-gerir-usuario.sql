-- ARQUIVO GERADO -- nao editar a mao.
-- Origem: banco-de-reservas/sql/015-capacidade-gerir-usuario.md (primeiro bloco ```sql).
-- sha256 do bloco extraido: af7e24c9e754574f2008c62443688bc94fe8a78ec4139e12f215da8e3c7dd1da
-- Regenerar: python scripts/extrair_migracoes.py --origem <.../banco-de-reservas/sql>
--
-- O `banco-de-reservas` e' a fonte da verdade do DESENHO (convencoes §7): mudanca de
-- modelo entra la' primeiro e so' depois vira migration aqui. Editar este arquivo
-- direto quebra essa ordem e o teste de manifesto acusa.

BEGIN;

-- A capacidade nova. Descricao com o mesmo cuidado das outras: ela vira ROTULO DE TELA, e a
-- verificacao mede char_length/octet_length para pegar duplo-encoding (convencoes §5).
INSERT INTO permissoes (chave, descricao_permissao) VALUES
  ('acesso.usuario_gerir', 'Criar, desativar e trocar o perfil de usuários');  -- POST/PATCH /api/acessos/usuarios

-- So' Growth, que e' quem ja' tem o painel. Escrito como consulta, e nao com id literal, pelo
-- mesmo motivo da 012: `id_perfil`/`id_permissao` sao BIGSERIAL e dependem da ordem de insercao.
--
-- Este INSERT dispara a trigger de auditoria do D19 e gravara' `registrado_por` NULO -- migration
-- nao tem `app.id_usuario`. E' o comportamento previsto pelo D19 ("sem ela, a acao e' registrada
-- com autoria nula") e o mesmo que a 010 e a 012 ja' produziram.
INSERT INTO perfil_permissoes (id_perfil, id_permissao)
SELECT p.id_perfil, pe.id_permissao
FROM perfis p
JOIN permissoes pe ON TRUE
WHERE (p.nome_perfil, pe.chave) IN (
  ('growth', 'acesso.usuario_gerir')
);

COMMIT;
