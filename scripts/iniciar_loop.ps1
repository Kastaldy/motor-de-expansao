# iniciar_loop.ps1 — lancador de 1 clique do loop autonomo (ralph) do Motor de Expansao.
# Le SO o token do Claude do .env, mascara o .env dentro do container (creds Growth/UX nunca
# entram), cria um branch de trabalho se voce estiver na main, builda a imagem se faltar, e roda
# o loop. O container escreve SO neste repo; nunca faz merge/push/deploy.
$ErrorActionPreference = 'Stop'

# Raiz do repo = pasta-pai de scripts/
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
# Caminho com barras normais (Docker Desktop lida melhor com C:/... do que C:\...)
$rootFwd = $root -replace '\\', '/'

Write-Host "== Loop autonomo (ralph) - Motor de Expansao ==" -ForegroundColor Cyan

# 1. Docker rodando?
docker info *> $null
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERRO: Docker nao esta rodando. Abra o Docker Desktop e tente de novo." -ForegroundColor Red
    Read-Host "Enter para fechar"; exit 1
}

# 2. Token do Claude no .env (lemos SO esta variavel; o resto do .env nao entra no container)
if (-not (Test-Path ".env")) {
    Write-Host "ERRO: nao existe .env na raiz. Crie-o e adicione a linha:" -ForegroundColor Red
    Write-Host "  CLAUDE_CODE_OAUTH_TOKEN=<token de 'claude setup-token'>" -ForegroundColor Yellow
    Read-Host "Enter para fechar"; exit 1
}
$line = Select-String -Path ".env" -Pattern '^\s*CLAUDE_CODE_OAUTH_TOKEN\s*=' | Select-Object -First 1
if (-not $line) {
    Write-Host "ERRO: o .env nao tem CLAUDE_CODE_OAUTH_TOKEN." -ForegroundColor Red
    Write-Host "Gere um token no host com:  claude setup-token" -ForegroundColor Yellow
    Write-Host "e adicione ao .env a linha:  CLAUDE_CODE_OAUTH_TOKEN=<token>" -ForegroundColor Yellow
    Read-Host "Enter para fechar"; exit 1
}
$token = ($line.Line -replace '^\s*CLAUDE_CODE_OAUTH_TOKEN\s*=\s*', '').Trim().Trim('"').Trim("'")
if (-not $token) {
    Write-Host "ERRO: CLAUDE_CODE_OAUTH_TOKEN esta vazio no .env." -ForegroundColor Red
    Read-Host "Enter para fechar"; exit 1
}

# 3. Nao rodar na main: cria um branch de trabalho (o loop commita aqui; voce revisa/mergeia depois)
$branch = (git rev-parse --abbrev-ref HEAD).Trim()
if ($branch -eq 'main') {
    $stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
    $branch = "ciclo/loop-$stamp"
    git switch -c $branch | Out-Null
    Write-Host "Branch de trabalho criado: $branch" -ForegroundColor Yellow
}
else {
    Write-Host "Rodando no branch atual: $branch" -ForegroundColor Yellow
}

# 4. Quantas iteracoes (default 10; sobrescreva com  $env:MAX_ITERS = 20  antes de rodar)
if ($env:MAX_ITERS) { $maxIters = $env:MAX_ITERS } else { $maxIters = '10' }

# 5. Imagem existe? senao builda (primeira vez demora alguns minutos)
docker image inspect motor-loop *> $null
if ($LASTEXITCODE -ne 0) {
    Write-Host "Construindo a imagem 'motor-loop' (primeira vez; alguns minutos)..." -ForegroundColor Yellow
    docker build -t motor-loop -f Dockerfile.loop .
    if ($LASTEXITCODE -ne 0) {
        Write-Host "ERRO: falha no build da imagem." -ForegroundColor Red
        Read-Host "Enter para fechar"; exit 1
    }
}

# 6. Arquivo de mascara do .env (container credential-free)
if (-not (Test-Path ".loop")) { New-Item -ItemType Directory ".loop" | Out-Null }
"# mascarado pelo launcher (container credential-free)" | Out-File -Encoding ascii ".loop/empty.env"

# 7. Roda o loop. Monta o repo + mascara o .env; passa SO o token do Claude.
Write-Host "Iniciando o loop (MAX_ITERS=$maxIters) no branch $branch. Ctrl+C interrompe." -ForegroundColor Cyan
docker run --rm -it `
    -e CLAUDE_CODE_OAUTH_TOKEN="$token" `
    -e MAX_ITERS="$maxIters" `
    -v "${rootFwd}:/repo" `
    -v "${rootFwd}/.loop/empty.env:/repo/.env:ro" `
    motor-loop

# 8. Pos-loop: orientar a revisao (passo humano)
Write-Host ""
Write-Host "Loop encerrado no branch $branch." -ForegroundColor Green
if (Test-Path "RELATORIO-BLOQUEIO.md") {
    Write-Host "ATENCAO: RELATORIO-BLOQUEIO.md presente - o loop travou (erro 3x ou guard). Leia-o." -ForegroundColor Red
}
if (Test-Path "LOOP_DONE") {
    Write-Host "LOOP_DONE presente - todos os blocos loop-safe fecharam." -ForegroundColor Green
}
Write-Host "Revise antes de mergear:" -ForegroundColor Cyan
Write-Host "  git log --oneline -20"
Write-Host "  git diff main...$branch"
Read-Host "Enter para fechar"
