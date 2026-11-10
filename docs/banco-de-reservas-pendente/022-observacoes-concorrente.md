# 022 — Anotações de campo nas academias concorrentes

> **Rascunho para o `banco-de-reservas`.** O desenho do esquema mora lá (convenções §7), e este
> arquivo existe no motor só porque aquele repositório não estava ao alcance de quem escreveu a
> mudança. O primeiro bloco ```sql abaixo é, byte a byte, o que `scripts/extrair_migracoes.py`
> extraiu para `src/motor_expansao/db/migracoes/022-observacoes-concorrente.sql` — quem trouxer
> este documento para `banco-de-reservas/sql/` deve conferir com
> `python scripts/extrair_migracoes.py --origem <.../banco-de-reservas/sql> --conferir` e então
> apagar esta cópia.

## O que a migration cria

O piloto passa a aceitar uma ESCRITA de qualquer perfil: ao clicar no pino de uma academia
concorrente, a pessoa registra o que viu em campo — metragem, equipamentos, vagas de
estacionamento, comodidades e aulas coletivas, três notas de 1 a 10 (conservação, fachada e
atendimento), alunos estimados quando houver, e um comentário livre.

| Objeto | Para quê |
|---|---|
| `observacoes_concorrente` | O estado atual de cada anotação. Uma linha por anotação, nunca removida. |
| `observacoes_concorrente_historico` | Uma cópia completa por criação, edição e remoção, escrita SÓ pela trigger. |
| `registra_observacao_concorrente()` | Trigger `SECURITY DEFINER` que alimenta o histórico com o autor do `app.id_usuario` (D19/D28). |
| `guarda_observacao_concorrente()` | Trigger `BEFORE UPDATE`: fixa o que não pode mudar e numera a versão. |
| `recusa_remover_observacao()` | Recusa `DELETE`/`TRUNCATE` nas duas tabelas e `UPDATE` no histórico. |
| `concorrente.anotar` | Capacidade nova, concedida a TODOS os perfis. |
| `concorrente.ver_autor` | Capacidade nova, só `growth`: ver o nome do autor, o histórico e as apagadas, e apagar a anotação de outra pessoa (moderação). |

## Decisões de desenho

- **Apagar é marcar.** `apagada_em_observacao`/`apagada_por` substituem o `DELETE`, pelo mesmo
  raciocínio da `revogada_em_sessao` (018): "esta anotação foi apagada, quando e por quem" é dado
  de auditoria, e apagar a linha responderia "nunca existiu". A trigger recusa `DELETE` e
  `TRUNCATE` — inclusive do dono — e o papel `app` não recebe `DELETE` (o D20 já não o concede por
  padrão).
- **Editar não reescreve o passado.** Toda mudança de conteúdo grava uma linha nova no histórico
  com o estado resultante; a versão anterior é a linha de antes. O histórico é append-only pelo
  mesmo contrato da `perfil_permissoes_historico` (009): sem `INSERT`, `UPDATE` nem `DELETE` para o
  `app`, e com trigger que recusa `UPDATE`/`DELETE`/`TRUNCATE`.
- **A âncora da academia é dupla.** `chave_concorrente` é um sha1 de `rede | nome-base | célula H3
  res-5`, estável a re-geocodificação dentro da célula (mesmo raciocínio da chave de churn da
  DEC-063). A foto da academia (`rede`, `nome`, `lat`, `lng`) viaja junto para a leitura achar a
  anotação também quando a chave muda (nome ajustado pela coleta, célula cruzada): mesma rede num
  raio de ~150 m. Por isso o índice `(pais, rede_concorrente, lat_concorrente)`.
- **`pais` na linha.** O cadastro é único entre BR e AR (DEC-081) e o banco também; a anotação é
  do país do deploy que a recebeu (`PERFIL.pais`), e a leitura filtra por ele. Mesma regra e mesma
  exceção de sufixo da `usuario_paises` (021, convenções 1).
- **Texto livre com teto.** `equipamentos` e `comodidades` até 1.000 caracteres e `comentario` até
  2.000; metragem inteira de 50 a 20.000 m², vagas de 0 a 5.000, notas de 1 a 10 e alunos
  estimados de 1 a 50.000. Ao menos um dos campos preenchido.
- **Notas e alunos estimados são opinião de campo, não medida.** A tela mostra a média das notas
  das anotações vivas; nada disso entra em score, ranking ou na capacidade do residual (DEC-057) —
  `alunos_estimados` não se confunde com o `alunos_reais` das planilhas das redes.
- **O nome do autor não sai do banco para quem não é Growth.** Isso é regra da aplicação (a API só
  devolve `nome_usuario` a quem tem `concorrente.ver_autor`), registrada aqui porque explica por que
  a tabela guarda `id_usuario_autor` e não um apelido: o pseudônimo ("Pessoa 1, Pessoa 2…",
  numerado por academia) é calculado na leitura.
- **Dívida declarada (LGPD).** Como nada se apaga, um telefone escrito por engano num comentário
  continua no histórico depois da moderação. A tela avisa para não escrever dado pessoal; o expurgo
  de um pedido do titular é ato do DONO, com a trigger desligada na mesma transação e a decisão
  registrada — fora do alcance do papel `app` por desenho.

## GRANT do papel `app` (levar às seções 3 e 4 do `papeis-e-privilegios.md`)

Numa instalação do zero o D20 roda depois das migrations e o default privilege não alcança estas
tabelas; em produção, o `ALTER DEFAULT PRIVILEGES FOR ROLE reservas_owner` concede `SELECT`,
`INSERT` e `UPDATE` + `USAGE` da sequence — e é preciso REVOGAR o que o histórico não pode ter.

```text
GRANT SELECT, INSERT, UPDATE ON observacoes_concorrente TO app;
GRANT USAGE ON SEQUENCE observacoes_concorrente_id_observacao_seq TO app;
GRANT SELECT ON observacoes_concorrente_historico TO app;
REVOKE INSERT, UPDATE, DELETE, TRUNCATE ON observacoes_concorrente_historico FROM app;
REVOKE USAGE ON SEQUENCE observacoes_concorrente_historico_id_observacao_historico_seq FROM app;

-- Seção 2 (molde das funções da 009): a gravadora SECURITY DEFINER não é chamável à mão.
REVOKE EXECUTE ON FUNCTION registra_observacao_concorrente() FROM PUBLIC;

-- Seção 7 (molde da `trg_perfil_permissoes_auditoria`): com session_replication_role=replica,
-- trigger fora de 'A' deixa de disparar — e a edição sairia sem histórico.
ALTER TABLE observacoes_concorrente ENABLE ALWAYS TRIGGER trg_observacoes_concorrente_guarda;
ALTER TABLE observacoes_concorrente ENABLE ALWAYS TRIGGER trg_observacoes_concorrente_historico;
ALTER TABLE observacoes_concorrente ENABLE ALWAYS TRIGGER trg_observacoes_concorrente_sem_delete;
ALTER TABLE observacoes_concorrente ENABLE ALWAYS TRIGGER trg_observacoes_concorrente_sem_truncate;
ALTER TABLE observacoes_concorrente_historico ENABLE ALWAYS TRIGGER trg_observacoes_concorrente_historico_imutavel;
ALTER TABLE observacoes_concorrente_historico ENABLE ALWAYS TRIGGER trg_observacoes_concorrente_historico_sem_truncate;
```

> O `db privilegios` ganhou as checagens de `INSERT`/`UPDATE`/`DELETE` destas duas tabelas; o
> `ENABLE ALWAYS` e o `REVOKE EXECUTE` acima ainda são conferidos só para `perfil_permissoes`
> (`postgres.TABELA_AUDITADA`) — estender aquelas duas camadas a uma segunda tabela auditada é
> follow-up declarado.

## Migration

```sql
BEGIN;

CREATE TABLE observacoes_concorrente (
  id_observacao              BIGSERIAL PRIMARY KEY,
  -- Pais do DEPLOY que recebeu a anotacao (PERFIL.pais). Mesma regra e mesma excecao de sufixo da
  -- `usuario_paises` (021): sigla ISO de 2 letras maiusculas, valor controlado e nao FK.
  pais                       CHAR(2) NOT NULL,
  -- Ancora estavel da academia: sha1 de `rede | nome-base | celula H3 res-5`, calculado pelo
  -- motor (`motor_expansao.db.observacoes.chave_concorrente`). Opaca aqui de proposito.
  chave_concorrente          TEXT NOT NULL,
  -- Foto da academia no momento da anotacao. Serve a leitura por proximidade (a chave muda se a
  -- coleta ajustar o nome) e responde "de qual academia era" mesmo depois que ela sumir do feed.
  rede_concorrente           TEXT NOT NULL,
  nome_concorrente           TEXT NOT NULL,
  lat_concorrente            DOUBLE PRECISION NOT NULL,
  lng_concorrente            DOUBLE PRECISION NOT NULL,
  -- Sem ON DELETE: usuario nao se apaga (desativa-se), e a anotacao precisa do autor para sempre.
  id_usuario_autor           BIGINT NOT NULL REFERENCES usuarios(id_usuario),
  metragem_m2                INTEGER,
  equipamentos_observacao    TEXT,
  vagas_estacionamento       INTEGER,
  -- Comodidades e aulas coletivas, em texto livre (decisao de produto: sem lista fixa).
  comodidades_observacao     TEXT,
  -- Tres notas de 1 a 10 de quem visitou. OPINIAO de campo, nao medida: a tela as mostra como
  -- media das anotacoes vivas e nada as leva a score, ranking ou residual.
  nota_conservacao           SMALLINT,
  nota_fachada               SMALLINT,
  nota_atendimento           SMALLINT,
  -- Estimativa de alunos de quem visitou, quando houver. NAO e' o `alunos_reais` (planilha que a
  -- rede entregou) e NAO entra na capacidade do residual (DEC-057): so' exibicao.
  alunos_estimados           INTEGER,
  comentario_observacao      TEXT,
  -- Numerada pela trigger de guarda a cada mudanca de conteudo. E' o que a aplicacao compara no
  -- UPDATE para recusar a edicao feita em cima de uma versao velha (409).
  versao_observacao          INTEGER NOT NULL DEFAULT 1,
  criada_em_observacao       TIMESTAMPTZ NOT NULL DEFAULT now(),
  atualizada_em_observacao   TIMESTAMPTZ NOT NULL DEFAULT now(),
  -- Apagar e' MARCAR, nunca DELETE (mesmo raciocinio da `revogada_em_sessao`, 018).
  apagada_em_observacao      TIMESTAMPTZ,
  apagada_por                BIGINT REFERENCES usuarios(id_usuario),
  CONSTRAINT chk_observacao_pais_sigla CHECK (pais ~ '^[A-Z]{2}$'),
  CONSTRAINT chk_observacao_coordenada CHECK (
    lat_concorrente BETWEEN -90 AND 90 AND lng_concorrente BETWEEN -180 AND 180
  ),
  CONSTRAINT chk_observacao_metragem CHECK (metragem_m2 IS NULL OR metragem_m2 BETWEEN 50 AND 20000),
  CONSTRAINT chk_observacao_vagas CHECK (
    vagas_estacionamento IS NULL OR vagas_estacionamento BETWEEN 0 AND 5000
  ),
  CONSTRAINT chk_observacao_notas CHECK (
    (nota_conservacao IS NULL OR nota_conservacao BETWEEN 1 AND 10)
    AND (nota_fachada IS NULL OR nota_fachada BETWEEN 1 AND 10)
    AND (nota_atendimento IS NULL OR nota_atendimento BETWEEN 1 AND 10)
  ),
  CONSTRAINT chk_observacao_alunos CHECK (
    alunos_estimados IS NULL OR alunos_estimados BETWEEN 1 AND 50000
  ),
  CONSTRAINT chk_observacao_tamanho_texto CHECK (
    char_length(coalesce(equipamentos_observacao, '')) <= 1000
    AND char_length(coalesce(comodidades_observacao, '')) <= 1000
    AND char_length(coalesce(comentario_observacao, '')) <= 2000
  ),
  -- Anotacao vazia nao informa nada e so' poluiria o historico.
  CONSTRAINT chk_observacao_algum_campo CHECK (
    metragem_m2 IS NOT NULL
    OR vagas_estacionamento IS NOT NULL
    OR nota_conservacao IS NOT NULL
    OR nota_fachada IS NOT NULL
    OR nota_atendimento IS NOT NULL
    OR alunos_estimados IS NOT NULL
    OR nullif(btrim(equipamentos_observacao), '') IS NOT NULL
    OR nullif(btrim(comodidades_observacao), '') IS NOT NULL
    OR nullif(btrim(comentario_observacao), '') IS NOT NULL
  ),
  -- O par anda junto: ou a anotacao esta' viva (os dois nulos) ou foi apagada por alguem.
  CONSTRAINT chk_observacao_apagada_par CHECK (
    (apagada_em_observacao IS NULL) = (apagada_por IS NULL)
  )
);

-- A consulta QUENTE: as anotacoes de UMA academia, no pais do deploy.
CREATE INDEX IF NOT EXISTS idx_observacoes_concorrente_chave
  ON observacoes_concorrente (pais, chave_concorrente);
-- A leitura por proximidade (mesma rede a ~150 m) quando a chave mudou.
CREATE INDEX IF NOT EXISTS idx_observacoes_concorrente_rede_lat
  ON observacoes_concorrente (pais, rede_concorrente, lat_concorrente);
-- toda FK ganha indice B-tree (convencoes 1)
CREATE INDEX IF NOT EXISTS idx_observacoes_concorrente_autor
  ON observacoes_concorrente (id_usuario_autor);
CREATE INDEX IF NOT EXISTS idx_observacoes_concorrente_apagada_por
  ON observacoes_concorrente (apagada_por);

CREATE TABLE observacoes_concorrente_historico (
  id_observacao_historico    BIGSERIAL PRIMARY KEY,
  -- SEM FK de proposito (mesmo racional do D8 na 009): o historico nao pode depender da linha viva.
  id_observacao              BIGINT NOT NULL,
  acao_observacao            TEXT NOT NULL,
  -- O ESTADO RESULTANTE da acao. A versao anterior de uma edicao e' a linha anterior desta tabela.
  versao_observacao          INTEGER NOT NULL,
  metragem_m2                INTEGER,
  equipamentos_observacao    TEXT,
  vagas_estacionamento       INTEGER,
  comodidades_observacao     TEXT,
  nota_conservacao           SMALLINT,
  nota_fachada               SMALLINT,
  nota_atendimento           SMALLINT,
  alunos_estimados           INTEGER,
  comentario_observacao      TEXT,
  -- clock_timestamp() e nao now(): num log append-only a ordem REAL e' o dado (ver a 009).
  registrado_em              TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
  -- Do `app.id_usuario` (D19/D28). Sem FK pelo mesmo motivo do `id_observacao`.
  registrado_por             BIGINT,
  CONSTRAINT chk_observacao_historico_acao CHECK (
    acao_observacao IN ('criada', 'editada', 'apagada')
  )
);

CREATE INDEX IF NOT EXISTS idx_observacoes_concorrente_historico_id_observacao
  ON observacoes_concorrente_historico (id_observacao);

-- ---------------------------------------------------------------------------------------------
-- Guarda: o que nao muda, e a versao
--
-- NAO e' SECURITY DEFINER: so' levanta excecao e ajusta NEW, nao escreve em lugar nenhum.
-- ---------------------------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION guarda_observacao_concorrente() RETURNS trigger
LANGUAGE plpgsql
SET search_path = pg_catalog, pg_temp AS $$
DECLARE
  conteudo_mudou boolean :=
    (OLD.metragem_m2, OLD.equipamentos_observacao, OLD.vagas_estacionamento,
     OLD.comodidades_observacao, OLD.nota_conservacao, OLD.nota_fachada, OLD.nota_atendimento,
     OLD.alunos_estimados, OLD.comentario_observacao)
    IS DISTINCT FROM
    (NEW.metragem_m2, NEW.equipamentos_observacao, NEW.vagas_estacionamento,
     NEW.comodidades_observacao, NEW.nota_conservacao, NEW.nota_fachada, NEW.nota_atendimento,
     NEW.alunos_estimados, NEW.comentario_observacao);
BEGIN
  IF OLD.apagada_em_observacao IS NOT NULL THEN
    RAISE EXCEPTION 'anotacao % ja foi apagada e nao muda mais', OLD.id_observacao
      USING ERRCODE = 'check_violation';
  END IF;
  IF (OLD.id_observacao, OLD.pais, OLD.chave_concorrente, OLD.rede_concorrente,
      OLD.nome_concorrente, OLD.lat_concorrente, OLD.lng_concorrente, OLD.id_usuario_autor,
      OLD.criada_em_observacao)
     IS DISTINCT FROM
     (NEW.id_observacao, NEW.pais, NEW.chave_concorrente, NEW.rede_concorrente,
      NEW.nome_concorrente, NEW.lat_concorrente, NEW.lng_concorrente, NEW.id_usuario_autor,
      NEW.criada_em_observacao) THEN
    RAISE EXCEPTION 'a academia, o autor e a data de uma anotacao nao mudam'
      USING ERRCODE = 'check_violation';
  END IF;
  -- Uma acao por UPDATE: editar e apagar juntos deixariam o historico sem dizer qual foi.
  IF conteudo_mudou AND NEW.apagada_em_observacao IS NOT NULL THEN
    RAISE EXCEPTION 'editar e apagar uma anotacao sao acoes separadas'
      USING ERRCODE = 'check_violation';
  END IF;
  IF conteudo_mudou THEN
    NEW.versao_observacao := OLD.versao_observacao + 1;
    NEW.atualizada_em_observacao := now();
  ELSE
    NEW.versao_observacao := OLD.versao_observacao;
    NEW.atualizada_em_observacao := OLD.atualizada_em_observacao;
  END IF;
  RETURN NEW;
END;
$$;

-- ---------------------------------------------------------------------------------------------
-- Historico: escrito SO' por esta funcao, com o privilegio do dono
-- ---------------------------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION registra_observacao_concorrente() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER
SET search_path = pg_catalog, public, pg_temp AS $$
DECLARE
  autor_texto text := current_setting('app.id_usuario', true);
  autor bigint := CASE WHEN autor_texto ~ '^[0-9]{1,18}$' THEN autor_texto::bigint END;
  acao text;
BEGIN
  -- Guarda de alvo (D21, molde da 011): instalada noutra tabela, esta funcao SECURITY DEFINER
  -- forjaria linha de historico com o privilegio do dono.
  IF TG_RELID <> 'public.observacoes_concorrente'::regclass THEN
    RAISE EXCEPTION 'registra_observacao_concorrente so pode ser instalada em observacoes_concorrente'
      USING ERRCODE = 'insufficient_privilege';
  END IF;

  IF TG_OP = 'INSERT' THEN
    acao := 'criada';
  ELSIF OLD.apagada_em_observacao IS NULL AND NEW.apagada_em_observacao IS NOT NULL THEN
    acao := 'apagada';
  ELSIF NEW.versao_observacao <> OLD.versao_observacao THEN
    acao := 'editada';
  ELSE
    RETURN NULL;  -- UPDATE sem mudanca de conteudo nem de estado: nada a registrar
  END IF;

  INSERT INTO observacoes_concorrente_historico
    (id_observacao, acao_observacao, versao_observacao, metragem_m2,
     equipamentos_observacao, vagas_estacionamento, comodidades_observacao, nota_conservacao,
     nota_fachada, nota_atendimento, alunos_estimados, comentario_observacao, registrado_por)
  VALUES (NEW.id_observacao, acao, NEW.versao_observacao, NEW.metragem_m2,
          NEW.equipamentos_observacao, NEW.vagas_estacionamento, NEW.comodidades_observacao,
          NEW.nota_conservacao, NEW.nota_fachada, NEW.nota_atendimento, NEW.alunos_estimados,
          NEW.comentario_observacao, autor);
  RETURN NULL;
END;
$$;

-- ---------------------------------------------------------------------------------------------
-- Nada se apaga: DELETE e TRUNCATE nas duas tabelas, e UPDATE no historico
-- ---------------------------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION recusa_remover_observacao() RETURNS trigger
LANGUAGE plpgsql
SET search_path = pg_catalog, pg_temp AS $$
BEGIN
  RAISE EXCEPTION '% em %: anotacoes de concorrente nao se apagam nem se reescrevem (apagar e marcar apagada_em_observacao)',
    TG_OP, TG_TABLE_NAME
    USING ERRCODE = 'insufficient_privilege';
END;
$$;

CREATE TRIGGER trg_observacoes_concorrente_guarda
  BEFORE UPDATE ON observacoes_concorrente
  FOR EACH ROW EXECUTE FUNCTION guarda_observacao_concorrente();

CREATE TRIGGER trg_observacoes_concorrente_historico
  AFTER INSERT OR UPDATE ON observacoes_concorrente
  FOR EACH ROW EXECUTE FUNCTION registra_observacao_concorrente();

CREATE TRIGGER trg_observacoes_concorrente_sem_delete
  BEFORE DELETE ON observacoes_concorrente
  FOR EACH ROW EXECUTE FUNCTION recusa_remover_observacao();

CREATE TRIGGER trg_observacoes_concorrente_sem_truncate
  BEFORE TRUNCATE ON observacoes_concorrente
  FOR EACH STATEMENT EXECUTE FUNCTION recusa_remover_observacao();

CREATE TRIGGER trg_observacoes_concorrente_historico_imutavel
  BEFORE UPDATE OR DELETE ON observacoes_concorrente_historico
  FOR EACH ROW EXECUTE FUNCTION recusa_remover_observacao();

CREATE TRIGGER trg_observacoes_concorrente_historico_sem_truncate
  BEFORE TRUNCATE ON observacoes_concorrente_historico
  FOR EACH STATEMENT EXECUTE FUNCTION recusa_remover_observacao();

-- ---------------------------------------------------------------------------------------------
-- As duas capacidades novas
--
-- Descricao com o mesmo cuidado das outras: ela vira ROTULO DE TELA (convencoes §5).
-- ---------------------------------------------------------------------------------------------
INSERT INTO permissoes (chave, descricao_permissao) VALUES
  ('concorrente.anotar',    'Anotar metragem, equipamentos e comentários nas academias concorrentes'), -- /api/concorrente/observacoes
  ('concorrente.ver_autor', 'Ver quem escreveu cada anotação de concorrente e moderar as dos outros');  -- dentro de /api/concorrente/observacoes

-- `anotar` para TODOS os perfis que existem (decisao de produto de 05/11/2026); `ver_autor` so'
-- para Growth. Escrito como consulta, e nao com id literal, pelo mesmo motivo da 012.
INSERT INTO perfil_permissoes (id_perfil, id_permissao)
SELECT p.id_perfil, pe.id_permissao
FROM perfis p
JOIN permissoes pe ON pe.chave = 'concorrente.anotar';

INSERT INTO perfil_permissoes (id_perfil, id_permissao)
SELECT p.id_perfil, pe.id_permissao
FROM perfis p
JOIN permissoes pe ON TRUE
WHERE (p.nome_perfil, pe.chave) IN (
  ('growth', 'concorrente.ver_autor')
);

COMMIT;
```

## Verificação (não vai para a migration)

```sql
-- 1. Nada se apaga: as duas devem FALHAR com insufficient_privilege.
DELETE FROM observacoes_concorrente;
TRUNCATE observacoes_concorrente_historico;

-- 2. Os quatro perfis têm `concorrente.anotar`; só Growth tem `concorrente.ver_autor`.
SELECT p.nome_perfil, pe.chave
FROM perfil_permissoes pp
JOIN perfis p ON p.id_perfil = pp.id_perfil
JOIN permissoes pe ON pe.id_permissao = pp.id_permissao
WHERE pe.chave LIKE 'concorrente.%'
ORDER BY 2, 1;
```
