-- ARQUIVO GERADO -- nao editar a mao.
-- Origem: banco-de-reservas/sql/010-seed-rbac.md (primeiro bloco ```sql).
-- sha256 do bloco extraido: 085060ee2e18920cbf2da765873b748640b1d35cfa85a1d5eccecf938d583066
-- Regenerar: python scripts/extrair_migracoes.py --origem <.../banco-de-reservas/sql>
--
-- O `banco-de-reservas` e' a fonte da verdade do DESENHO (convencoes §7): mudanca de
-- modelo entra la' primeiro e so' depois vira migration aqui. Editar este arquivo
-- direto quebra essa ordem e o teste de manifesto acusa.

BEGIN;

INSERT INTO perfis (nome_perfil, descricao_perfil) VALUES
  ('admin',    'Acesso total, incluindo gestão de usuários'),
  ('analista', 'Cria e analisa regiões; edita apenas o que criou'),
  ('leitor',   'Somente leitura e geração de relatórios')
ON CONFLICT (nome_perfil) DO NOTHING;

INSERT INTO permissoes (chave, descricao_permissao) VALUES
  ('contrato.ver',              'Visualizar contratos'),
  ('contrato.criar',            'Criar contratos'),
  ('contrato.editar',           'Editar qualquer contrato'),
  ('contrato.editar_proprio',   'Editar apenas contratos que criou'),
  ('area_estudo.ver',           'Visualizar áreas de estudo'),
  ('area_estudo.criar',         'Criar áreas de estudo'),
  ('area_estudo.editar',        'Editar qualquer área de estudo'),
  ('area_estudo.editar_proprio','Editar apenas áreas de estudo que criou'),
  ('relatorio.gerar',           'Gerar relatórios'),
  ('usuario.gerenciar',         'Gerenciar usuários e perfis')
ON CONFLICT (chave) DO NOTHING;

-- matriz perfil x permissao (esquema 3.5); concedido_por fica NULL: seed nao tem autor
INSERT INTO perfil_permissoes (id_perfil, id_permissao)
SELECT p.id_perfil, pe.id_permissao
FROM perfis p
JOIN permissoes pe ON (p.nome_perfil, pe.chave) IN (
  ('admin','contrato.ver'), ('admin','contrato.criar'), ('admin','contrato.editar'),
  ('admin','area_estudo.ver'), ('admin','area_estudo.criar'), ('admin','area_estudo.editar'),
  ('admin','relatorio.gerar'), ('admin','usuario.gerenciar'),

  ('analista','contrato.ver'), ('analista','contrato.criar'), ('analista','contrato.editar_proprio'),
  ('analista','area_estudo.ver'), ('analista','area_estudo.criar'), ('analista','area_estudo.editar_proprio'),
  ('analista','relatorio.gerar'),

  ('leitor','contrato.ver'), ('leitor','area_estudo.ver'), ('leitor','relatorio.gerar')
)
ON CONFLICT DO NOTHING;

COMMIT;
