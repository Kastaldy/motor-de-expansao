"""Checagem de subida da renda: falha explicita em vez do fallback silencioso de antes da E0."""

from __future__ import annotations

import logging
import os
from pathlib import Path

from motor_expansao.renda.carregador import FatoresRenda, carregar_fatores
from motor_expansao.renda.hex import InsumoRendaInvalido, k_calibracao_renda
from motor_expansao.renda.insumos import conferir_leitura
from motor_expansao.renda.insumos import staging_dir as _staging_padrao

_LOG = logging.getLogger("motor_expansao.renda")


def validar_na_subida(staging_dir: Path | str | None = None) -> FatoresRenda:
    """Carrega os fatores vigentes e confere os insumos de staging. Chamar no boot.

    - Fatores invalidos -> `FatoresRendaInvalidos` SEMPRE (a configuracao vai na imagem).
    - Com `MOTOR_DATA_DIR` setado (producao): cada `artefatos_obrigatorios` tem de existir e,
      se a versao exige, o carimbo k tem de ser legivel e plausivel -> senao
      `InsumoRendaInvalido`. Presente mas ilegivel (coluna faltando, parquet corrompido) tambem.
    - Sem `MOTOR_DATA_DIR` (dev/teste): artefato ausente so loga WARNING; a leitura cai na
      cascata nacional como antes.
    """
    fatores = carregar_fatores()
    base = Path(staging_dir) if staging_dir is not None else _staging_padrao()
    producao = bool(os.environ.get("MOTOR_DATA_DIR"))
    faltando = [nome for nome in fatores.artefatos_obrigatorios if not (base / nome).is_file()]
    if faltando:
        if producao:
            raise InsumoRendaInvalido(
                f"renda ({fatores.pais}, fatores {fatores.versao}): artefato(s) obrigatorio(s) "
                f"ausente(s) em {base}: {', '.join(faltando)}"
            )
        _LOG.warning(
            "renda (%s, fatores %s): artefato(s) ausente(s) em %s: %s -- dev/teste, "
            "seguindo pela cascata nacional",
            fatores.pais, fatores.versao, base, ", ".join(faltando),
        )
    if fatores.artefato_k_obrigatorio:
        # Em producao levanta se o carimbo for ilegivel; em dev cai no fallback com WARNING.
        k_calibracao_renda(base)
    # Existir nao basta: o hexagono le estes insumos SEM rede de seguranca (`fator_hex` deixa
    # o erro subir), entao um artefato presente mas sem coluna/corrompido derrubaria cada rota
    # com 500. Le aqui, uma vez, para a falha aparecer no boot.
    presentes = [n for n in fatores.artefatos_obrigatorios if n not in faltando]
    ilegiveis = conferir_leitura(base, presentes)
    if ilegiveis:
        if producao:
            raise InsumoRendaInvalido(
                f"renda ({fatores.pais}, fatores {fatores.versao}): artefato(s) obrigatorio(s) "
                f"ilegivel(is) em {base}: {'; '.join(ilegiveis)}"
            )
        _LOG.warning(
            "renda (%s, fatores %s): %s -- dev/teste, a leitura vai falhar nas rotas do hex",
            fatores.pais, fatores.versao, "; ".join(ilegiveis),
        )
    if fatores.fixada_por_env:
        _LOG.warning(
            "renda (%s): subindo com a versao FIXADA por env %s (rollback ativo)",
            fatores.pais, fatores.versao,
        )
    return fatores
