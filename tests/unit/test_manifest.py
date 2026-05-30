"""Testes do manifesto de proveniencia dos outputs (BLK-OPS-03).

Cobrem presenca/tipo das 9 chaves, valores canonicos lidos de
``settings``/``PESOS_HEX_SCORE_ESTRUTURAL``, hash sha256 dos BYTES BRUTOS
(presente/ausente), campos volateis (timestamp/commit) e a gravacao do JSON
em UTF-8 puro (sem BOM). Nao roda o pipeline pesado nem toca artefatos M1.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime

from motor_expansao.pipelines.m1.provenance import build_manifest, write_manifest

_REQUIRED_KEYS = {
    "schema_version",
    "ibge_vintage",
    "ultra_csv_sha256",
    "code_commit",
    "generated_at",
    "h3_resolution",
    "pesos",
    "dist_min_ultra_km",
    "renda_min",
}

_COMMIT_RE = re.compile(r"^[0-9a-f]{7,40}$")


def test_build_manifest_has_all_required_keys() -> None:
    m = build_manifest()
    assert set(m.keys()) == _REQUIRED_KEYS
    assert isinstance(m["schema_version"], int)
    assert isinstance(m["ibge_vintage"], str)
    assert isinstance(m["h3_resolution"], int)
    assert isinstance(m["pesos"], dict)
    assert set(m["pesos"].keys()) == {"renda", "pop"}
    assert isinstance(m["dist_min_ultra_km"], float)
    assert isinstance(m["renda_min"], float)


def test_canonical_values() -> None:
    m = build_manifest()
    assert m["h3_resolution"] == 7
    assert m["pesos"] == {"renda": 0.40, "pop": 0.60}
    assert m["dist_min_ultra_km"] == 1.0
    assert m["renda_min"] == 4500.0
    assert m["ibge_vintage"] == "censo_2022"


def test_sha256_present_with_file(tmp_path) -> None:
    # bytes nao-UTF8 (byte 0xff sozinho nao e UTF-8 valido) — hasheia BYTES BRUTOS
    raw = b"\xff\xfe metadado;col1;col2\nlatin-1 \xe9\xe7\xe3\n"
    csv_path = tmp_path / "Ultra.csv"
    csv_path.write_bytes(raw)
    expected = hashlib.sha256(raw).hexdigest()
    m = build_manifest(ultra_csv_path=csv_path)
    assert m["ultra_csv_sha256"] == expected


def test_sha256_none_when_file_absent(tmp_path) -> None:
    m = build_manifest(ultra_csv_path=tmp_path / "nao_existe.csv")
    assert m["ultra_csv_sha256"] is None


def test_volatile_fields_present_and_typed() -> None:
    m = build_manifest()
    assert isinstance(m["generated_at"], str)
    parsed = datetime.fromisoformat(m["generated_at"])
    assert parsed.utcoffset() is not None
    assert parsed.utcoffset().total_seconds() == 0
    commit = m["code_commit"]
    assert commit is None or bool(_COMMIT_RE.match(commit))


def test_write_manifest_creates_utf8_json(tmp_path) -> None:
    out_path = tmp_path / "_manifest.json"
    out = write_manifest(out_path, ultra_csv_path=tmp_path / "u.csv")
    assert out == out_path
    assert out.exists()
    data = json.loads(out.read_text(encoding="utf-8"))
    assert set(data.keys()) == _REQUIRED_KEYS
    # JSON em UTF-8 puro: nao pode ter BOM utf-8-sig
    assert out.read_bytes()[:3] != b"\xef\xbb\xbf"
