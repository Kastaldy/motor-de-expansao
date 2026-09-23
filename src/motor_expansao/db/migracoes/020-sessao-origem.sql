-- ARQUIVO GERADO -- nao editar a mao.
-- Origem: banco-de-reservas/sql/020-sessao-origem.md (primeiro bloco ```sql).
-- sha256 do bloco extraido: 7f9eedff035402edfb5c030bea9978d36e14de7d8628c052e46f3fe8b67a58f1
-- Regenerar: python scripts/extrair_migracoes.py --origem <.../banco-de-reservas/sql>
--
-- O `banco-de-reservas` e' a fonte da verdade do DESENHO (convencoes §7): mudanca de
-- modelo entra la' primeiro e so' depois vira migration aqui. Editar este arquivo
-- direto quebra essa ordem e o teste de manifesto acusa.

BEGIN;

-- IP de origem, tipo INET e nao TEXT: o Postgres valida o formato na escrita, entao uma
-- string qualquer nao entra fingindo ser endereco. Nulo = origem desconhecida, que e' o
-- estado de toda sessao aberta antes desta migration e o de qualquer chamada que nao
-- consiga resolver o peer.
--
-- O VALOR GRAVADO E' O ULTIMO TOKEN DO `X-Forwarded-For`, nunca o primeiro. O Caddy ANEXA
-- o peer real ao fim; os tokens a' esquerda sao do CLIENTE e forjaveis. Isso ja' foi
-- vulnerabilidade real no motor (pentest de 19/08/2026: `X-Forwarded-For: 8.8.8.8` fazia a
-- acao constar de um IP arbitrario na aba Acessos), e a resolucao correta ja' existe em
-- `web/server/app.py::_ip_real_do_xff` -- que e' quem esta coluna consome. Nao ha' segunda
-- redacao da regra.
ALTER TABLE sessoes ADD COLUMN ip_sessao INET;

-- Navegador/dispositivo de origem. TEXT sem `CHECK` de tamanho, e isso e' DECIDIDO, nao
-- esquecido: o valor vem de um header que o CLIENTE controla, entao um `CHECK` de
-- comprimento transformaria um `User-Agent` gigante em ERRO DE ESCRITA -- ou seja, em
-- login que falha. Seria negacao de servico por cabecalho, de graca. O teto e' aplicado
-- por quem escreve (`db/sessoes.py`, mesmo teto de 200 da trilha da DEC-027), onde o
-- excesso vira TRUNCAGEM em vez de recusa.
ALTER TABLE sessoes ADD COLUMN user_agent_sessao TEXT;

COMMIT;
