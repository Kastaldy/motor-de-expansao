-- ARQUIVO GERADO -- nao editar a mao.
-- Origem: banco-de-reservas/sql/028-avisos.md (primeiro bloco ```sql).
-- sha256 do bloco extraido: 636a3c368bad64ba01c3834ffc00e98295f3d9f3d93f803f934520dde393a53b
-- Regenerar: python scripts/extrair_migracoes.py --origem <.../banco-de-reservas/sql>
--
-- O `banco-de-reservas` e' a fonte da verdade do DESENHO (convencoes §7): mudanca de
-- modelo entra la' primeiro e so' depois vira migration aqui. Editar este arquivo
-- direto quebra essa ordem e o teste de manifesto acusa.

BEGIN;

-- AS TABELAS VEM PRIMEIRO (mesma razao da 025): o `db aplicar` reconhece a janela "aplicada mas
-- nao registrada" pelo erro de objeto que ja' existe (42P07) no PRIMEIRO comando.
-- ---------------------------------------------------------------------------------------------
-- Os avisos que uma pessoa recebe alem dos do perfil
-- ---------------------------------------------------------------------------------------------
CREATE TABLE usuario_avisos (
  id_usuario BIGINT NOT NULL REFERENCES usuarios(id_usuario) ON DELETE CASCADE,
  -- Valor controlado, e nao FK: a lista e' curta, fechada e cresce por migration. Sem sufixo de
  -- tabela pela mesma excecao declarada do `pais` da 021 (nome universal e unico).
  aviso      TEXT NOT NULL,
  CONSTRAINT chk_usuario_avisos_tipo CHECK (aviso IN ('estudo_master', 'imovel_master')),
  -- PK composta: a mesma pessoa nao tem o mesmo aviso duas vezes. Serve "os avisos de uma pessoa"
  -- (prefixo id_usuario), a consulta do sino, e cobre o indice da FK.
  PRIMARY KEY (id_usuario, aviso)
);

-- ---------------------------------------------------------------------------------------------
-- Ate' onde a pessoa ja' viu os avisos
-- ---------------------------------------------------------------------------------------------
CREATE TABLE avisos_lidos (
  id_usuario       BIGINT PRIMARY KEY REFERENCES usuarios(id_usuario) ON DELETE CASCADE,
  -- O maior `eventos.id_evento` que estava no sino quando a pessoa o abriu. Sem FK de proposito:
  -- e' um marco de posicao na trilha, nao uma referencia a um evento que precise existir.
  ultimo_id_evento BIGINT NOT NULL,
  lido_em          TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT chk_avisos_lidos_evento CHECK (ultimo_id_evento >= 0)
);

-- ---------------------------------------------------------------------------------------------
-- A capacidade do aviso de estudo, e o perfil que a recebe
--
-- Descricao com o mesmo cuidado das outras: ela vira ROTULO DE TELA (convencoes §5).
-- ---------------------------------------------------------------------------------------------
INSERT INTO permissoes (chave, descricao_permissao) VALUES
  ('avisos.estudos_masters', 'Receber o aviso de estudo pedido por um master'), -- GET /api/avisos
  -- So' liga a trilha "Meu territorio" no Inicio (`trilha_do_master` do /api/me); os pedidos
  -- seguem o gate de sempre (`masters.ver`). Juan, 22/11/2026: o Growth testa e avalia.
  ('masters.inicio_testar', 'Ver e testar o Início do master');

-- O perfil `growth` inteiro (decisao de produto de 19/11/2026, DEC-090). Escrito como consulta, e
-- nao com id literal, pelo mesmo motivo da 012. A trigger de auditoria do D19 grava
-- `registrado_por` NULO, como na 015.
INSERT INTO perfil_permissoes (id_perfil, id_permissao)
SELECT p.id_perfil, pe.id_permissao
FROM perfis p
JOIN permissoes pe ON TRUE
WHERE (p.nome_perfil, pe.chave) IN (
  ('growth', 'avisos.estudos_masters'),
  ('growth', 'masters.inicio_testar')
);

COMMIT;
