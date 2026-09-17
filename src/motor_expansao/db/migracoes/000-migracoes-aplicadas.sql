-- Migration NATIVA do motor -- NAO vem do `banco-de-reservas` e nao e' gerada pelo
-- extrator (`scripts/extrair_migracoes.py` preserva arquivos sem documento de origem).
--
-- Por que ela nao esta la': o `banco-de-reservas` e' a fonte da verdade do MODELO DE
-- DOMINIO (usuarios, RBAC, eventos, regioes, bases de referencia). Esta tabela nao e'
-- dominio: e' o controle de aplicacao das proprias migrations, infraestrutura do motor.
-- Por isso ela tambem fica FORA das 11 tabelas que a §0 da `verificacao.md` conta -- e o
-- filtro por lista nominal daquela consulta ja' a ignora por construcao.
--
-- Roda ANTES de todas, incluindo a 001: sem ela nao ha onde registrar que as outras
-- foram aplicadas. Num banco que ja' rodou 001->010 a mao, aplicar esta e depois inserir
-- as ONZE linhas correspondentes (as dez mais a propria 000) deixa o registro em dia sem
-- reprocessar nada -- e o script de conferencia emite esse INSERT a partir do manifesto.

BEGIN;

CREATE TABLE migracoes_aplicadas (
  -- Chave natural, como nas bases de referencia (`bairros.cod_bairro`): a versao E' a
  -- identidade da migration. `TEXT` e nao `INTEGER` para preservar o zero a esquerda,
  -- que e' o que faz a ordenacao alfabetica coincidir com a numerica ate' a 999.
  versao_migracao      TEXT PRIMARY KEY CHECK (versao_migracao ~ '^[0-9]{3}$'),
  -- Amarrado a versao: sem isto da' para registrar a '003' apontando para
  -- '007-regioes.sql', ou o mesmo arquivo em duas versoes, e o registro passaria a
  -- mentir sobre o que foi aplicado.
  arquivo_migracao     TEXT NOT NULL CHECK (arquivo_migracao ~ ('^' || versao_migracao || '-')),
  -- sha256 do arquivo aplicado, em hex minusculo (o que `sha256sum` e `hashlib` produzem;
  -- o `certutil` do Windows devolve MAIUSCULAS com espacos e seria recusado aqui).
  -- E' a EVIDENCIA de qual conteudo entrou. A conferencia -- recalcular e comparar contra
  -- o arquivo em disco -- e' do script de conferencia, nao do banco: guardar o hash nao
  -- detecta nada sozinho, so' torna a deteccao possivel.
  hash_migracao        TEXT NOT NULL CHECK (hash_migracao ~ '^[0-9a-f]{64}$'),
  -- `now()` e nao `clock_timestamp()`: aqui a coerencia com a TRANSACAO e' o que importa
  -- (a linha e' gravada junto da migration que ela registra). O caso oposto e' o
  -- `perfil_permissoes_historico` do D19, log append-only, onde a ordem REAL e' o dado.
  aplicada_em_migracao TIMESTAMPTZ NOT NULL DEFAULT now()
);

COMMIT;
