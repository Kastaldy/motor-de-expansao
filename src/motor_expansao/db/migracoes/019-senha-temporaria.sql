-- ARQUIVO GERADO -- nao editar a mao.
-- Origem: banco-de-reservas/sql/019-senha-temporaria.md (primeiro bloco ```sql).
-- sha256 do bloco extraido: 4e13b274f0ac60f5e047239d19999b0f3d20fead5c0ae8f69c0233316b17e394
-- Regenerar: python scripts/extrair_migracoes.py --origem <.../banco-de-reservas/sql>
--
-- O `banco-de-reservas` e' a fonte da verdade do DESENHO (convencoes §7): mudanca de
-- modelo entra la' primeiro e so' depois vira migration aqui. Editar este arquivo
-- direto quebra essa ordem e o teste de manifesto acusa.

BEGIN;

-- Ate' quando a senha guardada vale. NULO significa "nao expira", que e' o estado de toda senha
-- que a PESSOA escolheu -- e e' o estado de todas as linhas de hoje, por isso o CHECK abaixo
-- valida sem `NOT VALID`.
--
-- Nao e' derivavel de `senha_definida_em_usuario`: aquela coluna diz quando a pessoa definiu a
-- senha DELA, e fica NULA exatamente no caso que esta coluna precisa datar -- o da senha que a
-- pessoa nao escolheu. Sao os dois lados da mesma moeda, e nenhum substitui o outro.
ALTER TABLE usuarios ADD COLUMN senha_expira_em_usuario TIMESTAMPTZ;

-- Quando foi a ultima redefinicao por administrador. NULO = nunca houve.
--
-- Existe para a TRAVA DE TENTATIVAS, nao para auditoria (quem audita le o evento
-- `usuario.senha_redefinida`, que tem os dois nomes). A trava conta os `login.recusado` da conta
-- numa janela movel, e o caso tipico e' este: a pessoa esqueceu a senha, errou cinco vezes, so'
-- ENTAO ligou para o administrador. Sem esta coluna ela receberia a senha nova e continuaria
-- barrada por ate' 15 minutos, com a mesma mensagem de senha errada -- sem ter como entender.
-- Com ela, a contagem passa a considerar so' o que aconteceu DEPOIS da redefinicao.
--
-- Por que coluna, e nao subconsulta no proprio `eventos`: a alternativa era derivar o piso do
-- ultimo evento `usuario.senha_redefinida` por `entidade_id`, e nao existe indice por
-- `(tipo, entidade_id)` -- seria varredura no caminho quente do login para poupar uma coluna. A
-- credencial ja' e' lida nesse ponto, entao aqui o custo de consulta e' zero.
ALTER TABLE usuarios ADD COLUMN senha_redefinida_em_usuario TIMESTAMPTZ;

-- O unico estado incoerente possivel entre as duas colunas da senha, barrado na escrita.
--
-- Uma senha com prazo e' sempre uma senha que a pessoa ainda precisa trocar. O inverso nao vale
-- (um admin pode exigir troca de quem tem senha propria -- `usuario.troca_exigida` --, e ai' ha'
-- marca sem prazo), por isso o CHECK e' de uma perna so'.
--
-- O QUE ELE IMPEDE, em concreto: quando a pessoa troca a temporaria pela dela,
-- `deve_trocar_senha_usuario` vai a FALSE e alguem precisa zerar `senha_expira_em_usuario` na
-- MESMA escrita. Esquecer disso nao daria erro nenhum -- daria uma pessoa com senha PROPRIA que
-- expira, barrada com a senha certa, recebendo "Login ou senha incorretos". E' defeito silencioso
-- e de diagnostico caro; aqui ele vira erro de escrita, no momento em que e' cometido.
ALTER TABLE usuarios ADD CONSTRAINT ck_usuarios_prazo_exige_troca
  CHECK (deve_trocar_senha_usuario OR senha_expira_em_usuario IS NULL);

COMMIT;
