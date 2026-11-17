-- ARQUIVO GERADO -- nao editar a mao.
-- Origem: banco-de-reservas/sql/025-perfil-master.md (primeiro bloco ```sql).
-- sha256 do bloco extraido: 8edccc88f02e830436c1e9bdc74b86a57dd0bf189db66220c083542cdb519aec
-- Regenerar: python scripts/extrair_migracoes.py --origem <.../banco-de-reservas/sql>
--
-- O `banco-de-reservas` e' a fonte da verdade do DESENHO (convencoes §7): mudanca de
-- modelo entra la' primeiro e so' depois vira migration aqui. Editar este arquivo
-- direto quebra essa ordem e o teste de manifesto acusa.

BEGIN;

-- A TABELA VEM PRIMEIRO (revisao de 17/11/2026): o `db aplicar` reconhece a janela
-- "aplicada mas nao registrada" pelo erro de objeto que ja' existe (42P07) no PRIMEIRO comando.
-- Abrindo com o INSERT do perfil, a reexecucao cairia num 23505 cru, que o runner nao trata.
-- ---------------------------------------------------------------------------------------------
-- O vinculo pessoa -> master franquia
-- ---------------------------------------------------------------------------------------------
CREATE TABLE usuario_masters (
  id_usuario      BIGINT NOT NULL REFERENCES usuarios(id_usuario) ON DELETE CASCADE,
  -- O MESMO texto do campo `master_franquia` do cadastro da rede, que nao e' entidade do banco:
  -- por isso valor, e nao FK. Sem espaco nas pontas, para o vinculo nao falhar por um espaco que
  -- ninguem ve; a comparacao com o cadastro e' do piloto. `master_franquia` sem sufixo de tabela
  -- porque e' o nome do campo de onde o valor vem (mesma excecao declarada do `pais` da 021).
  master_franquia TEXT NOT NULL,
  CONSTRAINT chk_usuario_masters_nome CHECK (
    master_franquia = btrim(master_franquia) AND char_length(master_franquia) BETWEEN 2 AND 120
  ),
  -- PK composta: a mesma pessoa nao tem o mesmo master duas vezes. Serve tambem "os masters de
  -- uma pessoa" (prefixo id_usuario), a consulta QUENTE do recorte, e cobre o indice da FK.
  PRIMARY KEY (id_usuario, master_franquia)
);

-- ---------------------------------------------------------------------------------------------
-- O perfil novo
--
-- Identificador sem acento (convencoes §6); a descricao e' texto de TELA e vai acentuada.
-- ---------------------------------------------------------------------------------------------
INSERT INTO perfis (nome_perfil, descricao_perfil) VALUES
  ('master', 'Master franqueado: Visão Executiva só das próprias unidades');

-- ---------------------------------------------------------------------------------------------
-- A capacidade nova
--
-- Descricao com o mesmo cuidado das outras: ela vira ROTULO DE TELA (convencoes §5). O gate a
-- aceita so' numa allowlist FECHADA de leituras de `/api/rede/` (`acesso.rota_da_rede_propria`):
-- filtros, carteira (sem os exports), inteligencia e a ficha, a inteligencia e os setores de uma
-- unidade. O recorte as unidades do master e' aplicado pela rota.
-- ---------------------------------------------------------------------------------------------
INSERT INTO permissoes (chave, descricao_permissao) VALUES
  ('rede.ver_propria', 'Ver a carteira e a ficha só das unidades do próprio master franquia'); -- GET /api/rede/ (allowlist)

-- So' o master, e so' esta (decisao de produto de 17/11/2026, DEC-087): sem `rede.ver`, sem
-- `rede.cadastro_editar`, sem `concorrente.anotar`. Escrito como consulta, e nao com id literal,
-- pelo mesmo motivo da 012. A trigger de auditoria do D19 grava `registrado_por` NULO, como na 015.
INSERT INTO perfil_permissoes (id_perfil, id_permissao)
SELECT p.id_perfil, pe.id_permissao
FROM perfis p
JOIN permissoes pe ON TRUE
WHERE (p.nome_perfil, pe.chave) IN (
  ('master', 'rede.ver_propria')
);

COMMIT;
