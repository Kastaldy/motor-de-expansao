-- ARQUIVO GERADO -- nao editar a mao.
-- Origem: banco-de-reservas/sql/012-seed-rbac-real.md (primeiro bloco ```sql).
-- sha256 do bloco extraido: 9de851bcc309c22461f4bf6fec34e6518e20c5d45efb811888834adef061cfd2
-- Regenerar: python scripts/extrair_migracoes.py --origem <.../banco-de-reservas/sql>
--
-- O `banco-de-reservas` e' a fonte da verdade do DESENHO (convencoes §7): mudanca de
-- modelo entra la' primeiro e so' depois vira migration aqui. Editar este arquivo
-- direto quebra essa ordem e o teste de manifesto acusa.

BEGIN;

-- ---------------------------------------------------------------------------------------------
-- 1) Sai o seed sugerido da 010
--
-- O DELETE dos perfis leva junto, por ON DELETE CASCADE, as 18 linhas de `perfil_permissoes` da
-- matriz 8/7/3 -- e a trigger de auditoria do D19 registra as 18 como 'revogada'. Isso e' o
-- comportamento CERTO e a prova de que a auditoria funciona: o historico e' append-only e guarda
-- que aqueles perfis existiram e o que tinham.
--
-- `usuarios.id_perfil` e' NOT NULL com ON DELETE RESTRICT: se alguem ja' estiver apontando para
-- 'admin'/'analista'/'leitor', este DELETE FALHA -- de proposito. Reatribuir pessoa em silencio
-- durante uma migration seria pior que parar e pedir decisao.
-- ---------------------------------------------------------------------------------------------
DELETE FROM perfis WHERE nome_perfil IN ('admin', 'analista', 'leitor');

-- ---------------------------------------------------------------------------------------------
-- 2) Os quatro perfis reais
--
-- Identificadores sem acento (convencoes §6); a descricao e' texto de TELA e vai acentuada.
-- ---------------------------------------------------------------------------------------------
INSERT INTO perfis (nome_perfil, descricao_perfil) VALUES
  ('expansao',    'Prospecção territorial: mapa, funil de oportunidades, imóveis e viabilidade'),
  ('consultoria', 'Carteira da rede: acompanha unidades e mantém consultor e master franquia'),
  ('lideres',     'Expansão e Consultoria juntas: território, viabilidade, imóveis e carteira'),
  ('growth',      'Tudo de Líderes, mais o painel de acessos (quem usou o quê)');

-- ---------------------------------------------------------------------------------------------
-- 3) As catorze capacidades do piloto, derivadas das 19 regras de rota
--
-- A rota de cada uma esta no comentario: e' o que amarra a permissao ao codigo, e o que permite
-- conferir se uma rota nova nasceu sem permissao correspondente.
-- ---------------------------------------------------------------------------------------------
INSERT INTO permissoes (chave, descricao_permissao) VALUES
  ('territorio.explorar',         'Explorar UF e município no Mapa Territorial'),          -- /api/uf/ /api/municipio/ /api/municipios/
  ('territorio.ranking_nacional', 'Ver o ranking nacional por estado'),                    -- /api/estados
  ('ponto.analisar',              'Analisar um ponto ou endereço e seu entorno'),          -- /api/geocode /api/resolver-ponto /api/ponto /api/cobertura/
  ('relatorio.comparacao',        'Gerar o deck de comparação entre pontos ou hexágonos'), -- /api/relatorio/comparacao
  ('relatorio.municipal',         'Gerar o Relatório Municipal'),                          -- /api/relatorio/municipal
  ('relatorio.pontual',           'Gerar o Relatório Pontual Censitário'),                 -- /api/relatorio/pontual
  ('viabilidade.calcular',        'Calcular a viabilidade de um imóvel candidato'),        -- /api/viabilidade
  ('viabilidade.simular',         'Usar o simulador financeiro e a faixa de alunos'),      -- /api/simulador/ /api/faixa-alunos
  ('imovel.listar',               'Ver a lista de imóveis disponíveis (agregada)'),        -- /api/oportunidades
  ('imovel.dossie_ver',           'Abrir o dossiê do imóvel, que traz contato de corretor'),-- /api/oportunidades/{id}/dossie
  ('imovel.registrar_gesto',      'Registrar visita e demais gestos na ficha do imóvel'),  -- /api/imobiliaria/evento/
  ('rede.ver',                    'Ver a carteira da rede e a ficha de cada unidade'),     -- GET /api/rede/ /api/executiva/
  ('rede.cadastro_editar',        'Atribuir consultor e master franquia às unidades'),     -- PUT /api/rede/cadastro/
  ('acesso.painel_ver',           'Ver o painel de acessos (quem usou o quê, com retenção de 90 dias)'); -- /api/acessos/

-- ---------------------------------------------------------------------------------------------
-- 4) A matriz perfil x permissao -- 11 / 2 / 13 / 14
--
-- Escrita como consulta, e nao com ids literais: `id_perfil`/`id_permissao` sao BIGSERIAL e
-- dependem da ordem de insercao, que muda se esta migration rodar num banco que ja' teve outras.
-- ---------------------------------------------------------------------------------------------
INSERT INTO perfil_permissoes (id_perfil, id_permissao)
SELECT p.id_perfil, pe.id_permissao
FROM perfis p
JOIN permissoes pe ON TRUE
WHERE (p.nome_perfil, pe.chave) IN (
  -- Expansao (11): territorio, ponto, relatorios, viabilidade e imoveis. Sem a carteira.
  ('expansao', 'territorio.explorar'),         ('expansao', 'territorio.ranking_nacional'),
  ('expansao', 'ponto.analisar'),              ('expansao', 'relatorio.comparacao'),
  ('expansao', 'relatorio.municipal'),         ('expansao', 'relatorio.pontual'),
  ('expansao', 'viabilidade.calcular'),        ('expansao', 'viabilidade.simular'),
  ('expansao', 'imovel.listar'),               ('expansao', 'imovel.dossie_ver'),
  ('expansao', 'imovel.registrar_gesto'),

  -- Consultoria (2): so' a carteira -- e com direito de edicao do cadastro.
  ('consultoria', 'rede.ver'),                 ('consultoria', 'rede.cadastro_editar'),

  -- Lideres (13): a uniao das duas acima.
  ('lideres', 'territorio.explorar'),          ('lideres', 'territorio.ranking_nacional'),
  ('lideres', 'ponto.analisar'),               ('lideres', 'relatorio.comparacao'),
  ('lideres', 'relatorio.municipal'),          ('lideres', 'relatorio.pontual'),
  ('lideres', 'viabilidade.calcular'),         ('lideres', 'viabilidade.simular'),
  ('lideres', 'imovel.listar'),                ('lideres', 'imovel.dossie_ver'),
  ('lideres', 'imovel.registrar_gesto'),       ('lideres', 'rede.ver'),
  ('lideres', 'rede.cadastro_editar'),

  -- Growth (14): Lideres mais o painel de acessos.
  ('growth', 'territorio.explorar'),           ('growth', 'territorio.ranking_nacional'),
  ('growth', 'ponto.analisar'),                ('growth', 'relatorio.comparacao'),
  ('growth', 'relatorio.municipal'),           ('growth', 'relatorio.pontual'),
  ('growth', 'viabilidade.calcular'),          ('growth', 'viabilidade.simular'),
  ('growth', 'imovel.listar'),                 ('growth', 'imovel.dossie_ver'),
  ('growth', 'imovel.registrar_gesto'),        ('growth', 'rede.ver'),
  ('growth', 'rede.cadastro_editar'),          ('growth', 'acesso.painel_ver')
);

COMMIT;
