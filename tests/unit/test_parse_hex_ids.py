"""Reancoragem do parser de hex_ids colados (DEC-022).

Estes invariantes viviam em tests/integration/test_streamlit_app.py (Bloco 16.2:
Facilitar Copia e Inclusao de hex_id), que sera deletado no corte do Streamlit.
parse_hex_ids_from_text e' motor compartilhado (o fluxo "colar lista" do cenario
multi-hex depende dele em qualquer UI), entao os cenarios sao reescritos aqui
contra a funcao pura em motor_expansao.dashboard.data — sem streamlit.
"""

from __future__ import annotations

from motor_expansao.dashboard.data import parse_hex_ids_from_text


def test_aceita_separadores_variados():
    # O usuario cola listas vindas de Excel, CSV ou chat: quebra de linha,
    # virgula, ponto-e-virgula e espaco precisam funcionar igualmente.
    assert parse_hex_ids_from_text("87abc\n87xyz") == ["87abc", "87xyz"]
    assert parse_hex_ids_from_text("87abc,87xyz") == ["87abc", "87xyz"]
    assert parse_hex_ids_from_text("87abc;87xyz") == ["87abc", "87xyz"]
    assert parse_hex_ids_from_text("87abc 87xyz") == ["87abc", "87xyz"]


def test_aceita_separadores_misturados_na_mesma_colagem():
    # Colagens reais misturam separadores (linha + virgula + espaco): o parser
    # nao pode exigir um formato unico.
    result = parse_hex_ids_from_text("87abc\n87xyz, 87def;87ghi 87jkl")
    assert result == ["87abc", "87xyz", "87def", "87ghi", "87jkl"]


def test_texto_vazio_ou_so_whitespace_retorna_lista_vazia():
    # Colar nada (ou so espacos/linhas em branco) nao pode virar um id fantasma
    # "" adicionado ao cenario.
    assert parse_hex_ids_from_text("") == []
    assert parse_hex_ids_from_text("   ") == []
    assert parse_hex_ids_from_text("\n\n") == []


def test_crlf_de_colagem_windows_nao_gera_tokens_vazios():
    # Listas copiadas no Windows chegam com \r\n: o \r precisa ser tratado como
    # separador, nunca grudado no fim do hex_id (um "87abc\r" jamais casaria
    # com o hex_id real do DataFrame).
    assert parse_hex_ids_from_text("87abc\r\n87xyz\r\n") == ["87abc", "87xyz"]


def test_separadores_consecutivos_e_bordas_nao_geram_tokens_vazios():
    # Linhas em branco no meio, virgulas duplicadas e separadores nas pontas
    # sao ruido comum de colagem: nada disso pode virar item vazio na lista.
    assert parse_hex_ids_from_text("\n87abc\n\n,,87xyz;; ") == ["87abc", "87xyz"]


def test_preserva_ordem_de_colagem():
    # A ordem colada e' a ordem de exibicao no cenario: o parser nao pode
    # ordenar nem embaralhar.
    raw = "87hex_c\n87hex_a\n87hex_b"
    assert parse_hex_ids_from_text(raw) == ["87hex_c", "87hex_a", "87hex_b"]


def test_nao_deduplica_para_permitir_contagem_de_duplicados():
    # O parser devolve TODAS as ocorrencias: a deduplicacao e' responsabilidade
    # do caller, que usa a diferenca de tamanhos para avisar "N duplicado(s)
    # ignorado(s)" ao usuario.
    parsed = parse_hex_ids_from_text("hex_b\nhex_c\nhex_b")
    assert parsed == ["hex_b", "hex_c", "hex_b"]


def test_logica_de_duplicados_do_caller_detecta_repetidos():
    # Reproduz o invariante do fluxo "Adicionar lista": ids ja no cenario e
    # repetidos na propria colagem contam como duplicados; so o inedito entra.
    existing = {"hex_a", "hex_b"}
    parsed = parse_hex_ids_from_text("hex_b\nhex_c\nhex_b")
    new_ids = [h for h in parsed if h not in existing]
    dupes = len(parsed) - len(new_ids)
    assert new_ids == ["hex_c"]
    assert dupes == 2


def test_nao_valida_formato_h3_apenas_tokeniza():
    # Decisao de contrato: o parser so tokeniza; um token que nao e' hex H3
    # passa adiante e a resolucao contra o universo (df) e' quem o rejeita.
    # Assim o aviso ao usuario distingue "duplicado" de "nao encontrado".
    assert parse_hex_ids_from_text("nao_e_hex 87abc") == ["nao_e_hex", "87abc"]


def test_resolucao_contra_universo_descarta_ids_desconhecidos():
    # Simula o passo seguinte do fluxo multi-hex: so ids presentes no universo
    # sinteticamente conhecido sobrevivem; o id errado nao entra no cenario.
    universo = {"87hex_a", "87hex_b"}
    parsed = parse_hex_ids_from_text("87hex_a, 87hex_errado")
    conhecidos = [h for h in parsed if h in universo]
    assert conhecidos == ["87hex_a"]


def test_colagem_multilinha_simulando_colar_do_usuario():
    # Cenario fim-a-fim do expander "Adicionar hexes por ID": uma lista com um
    # id por linha vira exatamente N itens na mesma ordem.
    raw = "87hex_a\n87hex_b\n87hex_c"
    result = parse_hex_ids_from_text(raw)
    assert len(result) == 3
    assert result == ["87hex_a", "87hex_b", "87hex_c"]
