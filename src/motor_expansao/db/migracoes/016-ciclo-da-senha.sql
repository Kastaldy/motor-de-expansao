-- ARQUIVO GERADO -- nao editar a mao.
-- Origem: banco-de-reservas/sql/016-ciclo-da-senha.md (primeiro bloco ```sql).
-- sha256 do bloco extraido: 35289d2ff0aa9b3333dbd9e18da85ef3af27c419ea743d0468b96c735dcb2e63
-- Regenerar: python scripts/extrair_migracoes.py --origem <.../banco-de-reservas/sql>
--
-- O `banco-de-reservas` e' a fonte da verdade do DESENHO (convencoes §7): mudanca de
-- modelo entra la' primeiro e so' depois vira migration aqui. Editar este arquivo
-- direto quebra essa ordem e o teste de manifesto acusa.

BEGIN;

-- Quando a PESSOA definiu a senha dela. NULO significa "ainda na senha inicial", e essa e' a
-- pergunta que a conversao precisa responder: quem ainda nao trocou.
--
-- SEM default, de proposito. As quatro linhas que existem hoje tem `hash_de_teste_*`, que nao e'
-- hash de senha nenhuma (dados-ficticios.md §2) -- carimba-las com now() afirmaria uma falsidade
-- justamente na coluna criada para nao afirmar falsidades.
ALTER TABLE usuarios ADD COLUMN senha_definida_em_usuario TIMESTAMPTZ;

-- Se a proxima entrada deve pedir troca de senha.
--
-- `DEFAULT TRUE` para que as linhas existentes nascam marcadas: os hashes delas sao ficticios,
-- entao "deve trocar" e' a verdade sobre elas -- e vale igual para quem for criado pela tela, que
-- nasce com a senha inicial compartilhada.
--
-- NAO e' derivavel da coluna acima. Um admin pode forcar troca de quem JA' definiu a propria
-- senha (suspeita de vazamento, desligamento de terceiro), e nesse caso
-- `senha_definida_em_usuario` continua preenchida e este booleano volta a TRUE. Sao duas
-- perguntas diferentes: "ja' definiu alguma vez?" e "precisa definir agora?".
ALTER TABLE usuarios ADD COLUMN deve_trocar_senha_usuario BOOLEAN NOT NULL DEFAULT TRUE;

COMMIT;
