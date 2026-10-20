"""Invariantes do serviço de rotas (Valhalla, DEC-074) na infraestrutura.

O serviço é OPCIONAL por construção e mora numa stack separada (`valhalla-infra/`). O que
este arquivo trava são as coisas que só se descobrem quebradas na VPS:

1. `MOTOR_ROTAS_URL` fora do `environment:` do `web`. O compose de produção NÃO tem
   `env_file`: sem a linha, preencher o `.env` não tem efeito nenhum e a opção "10 min de
   carro" nunca aparece — falha muda, o operador conclui que a função não funciona.
2. A mesma variável com `:?` em vez de `:-`. Ela é opcional: com `:?` o `docker compose up`
   do motor inteiro ABORTARIA numa VPS onde o Valhalla nem foi instalado.
3. O Valhalla publicando porta no host. Ele não tem autenticação; `ports:` o poria na
   internet. Quem chama é o servidor do piloto, pela `app_net`.
4. O healthcheck dando FAIL eterno onde a stack não foi instalada (ou, ao contrário, não
   vigiando o container quando a função está ligada).
5. O smoke do build aprovando resposta que não é isócrona.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest

yaml = pytest.importorskip("yaml", reason="pyyaml nao instalado neste ambiente")

RAIZ = Path(__file__).resolve().parents[2]
COMPOSE_PROD = RAIZ / "docker-compose.prod.yml"
ENV_EXEMPLO = RAIZ / ".env.example"
STACK = RAIZ / "valhalla-infra"
COMPOSE_ROTAS = STACK / "docker-compose.yml"
BUILD = STACK / "scripts" / "build-brazil.sh"
HEALTHCHECK = RAIZ / "scripts" / "healthcheck_vps.sh"

CONTAINER = "motor_expansao_valhalla"


def _valhalla() -> dict:
    return yaml.safe_load(COMPOSE_ROTAS.read_text(encoding="utf-8"))["services"]["valhalla"]


# --------------------------------------------------------------------------- compose do motor


def test_web_recebe_motor_rotas_url_opcional() -> None:
    web = yaml.safe_load(COMPOSE_PROD.read_text(encoding="utf-8"))["services"]["web"]
    env = web.get("environment") or {}
    assert "MOTOR_ROTAS_URL" in env, (
        "o `web` perdeu `MOTOR_ROTAS_URL` no `environment:` — sem `env_file`, o valor do .env "
        "nunca chega ao container e a opção de 10 min de carro some em silêncio"
    )
    assert env["MOTOR_ROTAS_URL"] == "${MOTOR_ROTAS_URL:-}", (
        "a variável tem de ser `${MOTOR_ROTAS_URL:-}`: opcional. Com `:?` o compose do motor "
        "inteiro aborta numa VPS sem o Valhalla."
    )


def test_motor_rotas_url_documentada_no_env_exemplo() -> None:
    texto = ENV_EXEMPLO.read_text(encoding="utf-8")
    declaradas = set(re.findall(r"^\s*#?\s*([A-Z0-9_]+)=", texto, re.MULTILINE))
    assert "MOTOR_ROTAS_URL" in declaradas
    # Documentada com o valor INTERNO de exemplo: a rota pública atrás do login daria 302
    # para um fetch do servidor (a mesma armadilha do basemap).
    assert "http://motor_expansao_valhalla:8002" in texto


# --------------------------------------------------------------------------- stack valhalla-infra


def test_valhalla_nao_publica_porta_no_host() -> None:
    servico = _valhalla()
    assert "ports" not in servico, (
        "o Valhalla ganhou `ports:` — ele não tem autenticação e ficaria aberto na internet. "
        "Use `expose:` (só a app_net) e chame pelo nome do container."
    )
    assert servico.get("expose") == ["8002"]


def test_valhalla_na_rede_externa_do_motor() -> None:
    dados = yaml.safe_load(COMPOSE_ROTAS.read_text(encoding="utf-8"))
    assert dados["services"]["valhalla"]["networks"] == ["app_net"]
    # `external` faz o `up` FALHAR sem a rede, em vez de criar uma isolada do `web`.
    assert dados["networks"]["app_net"] == {"external": True, "name": "app_app_net"}


def test_valhalla_nome_do_container_e_o_que_o_monitor_e_a_env_usam() -> None:
    assert _valhalla()["container_name"] == CONTAINER
    assert CONTAINER in HEALTHCHECK.read_text(encoding="utf-8")


def test_valhalla_so_serve_e_tem_teto_de_memoria_obrigatorio() -> None:
    servico = _valhalla()
    env = servico["environment"]
    # Nunca rebuildar o Brasil dentro da caixa de produção.
    assert env["use_tiles_ignore_pbf"] == "True"
    assert env["force_rebuild"] == "False"
    # Teto MEDIDO e fail-closed: sem o valor no .env da stack, o `up` aborta.
    assert str(servico["mem_limit"]).startswith("${VALHALLA_MEM_LIMIT:?")
    assert "no-new-privileges:true" in servico["security_opt"]


def test_imagem_pinada_por_digest_e_igual_no_build() -> None:
    imagem = _valhalla()["image"]
    assert re.fullmatch(r"ghcr\.io/valhalla/valhalla-scripted:3\.9\.0@sha256:[0-9a-f]{64}", imagem)
    m = re.search(r'^IMAGEM="([^"]+)"', BUILD.read_text(encoding="utf-8"), re.MULTILINE)
    assert m and m.group(1) == imagem, (
        "o build e o compose usam imagens diferentes — tiles gerados por uma versão e servidos "
        "por outra quebram o serviço"
    )


def test_tiles_e_extrato_fora_do_git() -> None:
    linhas = (STACK / ".gitignore").read_text(encoding="utf-8").splitlines()
    assert "custom_files/" in linhas
    assert "*.pbf" in linhas


def test_build_nao_alcanca_a_vps_de_fora() -> None:
    """CLAUDE.md §6: cada comando na VPS é confirmado um a um; o script só imprime o passo."""
    executavel = [
        linha
        for linha in BUILD.read_text(encoding="utf-8").splitlines()
        if not linha.lstrip().startswith(("#", "echo"))
    ]
    for proibido in ("ssh ", "scp ", "rsync "):
        assert not any(proibido in linha for linha in executavel), proibido


# --------------------------------------------------------------------------- smoke do build


def _smoke_py() -> str:
    """O Python do smoke, RECORTADO do script de produção (nunca uma cópia)."""
    texto = BUILD.read_text(encoding="utf-8")
    i = texto.index("SMOKE_PY='") + len("SMOKE_PY='")
    j = texto.index("\n'\n", i)
    return texto[i:j]


def _servidor(resposta_isocrona: dict) -> tuple[HTTPServer, str]:
    class _H(BaseHTTPRequestHandler):
        def _json(self, corpo: dict) -> None:
            dados = json.dumps(corpo).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(dados)))
            self.end_headers()
            self.wfile.write(dados)

        def do_POST(self) -> None:  # noqa: N802
            pedido = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            # O smoke pede exatamente o que o motor pede: carro, 10 min, polígono.
            assert pedido["costing"] == "auto" and pedido["contours"] == [{"time": 10}]
            self._json(resposta_isocrona)

        def do_GET(self) -> None:  # noqa: N802
            self._json({"version": "3.9.0", "tileset_last_modified": 1760000000})

        def log_message(self, *args: object) -> None:
            pass

    srv = HTTPServer(("127.0.0.1", 0), _H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, f"http://127.0.0.1:{srv.server_address[1]}"


def _rodar_smoke(resposta: dict) -> subprocess.CompletedProcess[str]:
    srv, url = _servidor(resposta)
    try:
        return subprocess.run(
            [sys.executable, "-c", _smoke_py(), url],
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
    finally:
        srv.shutdown()


def test_smoke_aprova_isocrona_e_imprime_a_versao() -> None:
    lat, lng, d = -23.5614, -46.6559, 0.02
    anel = [
        [lng - d, lat - d],
        [lng + d, lat - d],
        [lng + d, lat + d],
        [lng - d, lat + d],
        [lng - d, lat - d],
    ]
    saida = _rodar_smoke({"features": [{"geometry": {"type": "Polygon", "coordinates": [anel]}}]})
    assert saida.returncode == 0, saida.stderr
    assert "smoke OK: Polygon" in saida.stdout
    assert "versao=3.9.0" in saida.stdout


def test_smoke_reprova_resposta_sem_poligono() -> None:
    saida = _rodar_smoke({"features": [{"geometry": {"type": "LineString", "coordinates": []}}]})
    assert saida.returncode != 0
    assert "REPROVADO" in saida.stderr


# --------------------------------------------------------------------------- healthcheck


def _healthcheck(tmp_path: Path, env_motor: str) -> dict[str, str]:
    """Roda o `containers` de verdade, com `docker`/`curl` falsos, e devolve os estados.

    Caminhos RELATIVOS ao `cwd` (lição de `test_wrapper_cron_weekly_90`): interpolar caminho
    absoluto do Windows no Git Bash dá um verde que não prova nada.
    """
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    # O Valhalla NÃO existe nesta "VPS"; todo o resto está de pé.
    falsos = {
        "docker": (
            '#!/usr/bin/env bash\ncase "$*" in\n'
            f"  *{CONTAINER}*) exit 1 ;;\n"
            "  *Health*) echo n/a ;;\n"
            "  *) echo running ;;\nesac\n"
        ),
        "curl": "#!/usr/bin/env bash\necho 401\n",
    }
    for nome, corpo in falsos.items():
        alvo = bin_dir / nome
        alvo.write_text(corpo, encoding="utf-8", newline="\n")
        os.chmod(alvo, 0o755)
    shutil.copy(HEALTHCHECK, tmp_path / "healthcheck_vps.sh")
    (tmp_path / "env").write_text(env_motor, encoding="utf-8", newline="\n")
    script = (
        'PATH="$PWD/bin:$PATH" MONITOR_ENV_FILE=env MONITOR_STATE_DIR=estado '
        "MONITOR_LOG_FILE=log/hc.log bash ./healthcheck_vps.sh containers"
    )
    saida = subprocess.run(
        ["bash", "-c", script],
        cwd=tmp_path,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    assert saida.returncode == 0, saida.stderr
    estados = {
        p.stem: p.read_text(encoding="utf-8").split()[0]
        for p in (tmp_path / "estado").glob("*.state")
    }
    # Prova de execução: o laço passou pelos containers fixos (senão "nada de valhalla" seria vazio).
    assert estados.get("container_motor_expansao_web") == "OK", estados
    return estados


@pytest.mark.skipif(shutil.which("bash") is None, reason="precisa de bash (Git Bash no Windows)")
def test_healthcheck_ignora_valhalla_quando_a_funcao_esta_desligada(tmp_path: Path) -> None:
    estados = _healthcheck(tmp_path, "API_TELEGRAM_TOKEN=\nMOTOR_ROTAS_URL=\n")
    assert f"container_{CONTAINER}" not in estados, (
        "stack não instalada e função desligada tem de ser estado CORRETO, não FAIL eterno"
    )


@pytest.mark.skipif(shutil.which("bash") is None, reason="precisa de bash (Git Bash no Windows)")
def test_healthcheck_acusa_valhalla_ausente_com_a_funcao_ligada(tmp_path: Path) -> None:
    estados = _healthcheck(
        tmp_path, f"API_TELEGRAM_TOKEN=\nMOTOR_ROTAS_URL=http://{CONTAINER}:8002\n"
    )
    assert estados.get(f"container_{CONTAINER}") == "FAIL", (
        "com MOTOR_ROTAS_URL preenchida a opção aparece na tela; container ausente é falha real"
    )
