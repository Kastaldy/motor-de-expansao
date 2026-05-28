# Roundtrip dummy de SOPS+age. NAO usa segredo real.
# Gera chave dummy temporaria, encripta tests/fixtures/dummy_secret.yaml,
# desencripta, compara e limpa. Imprime ROUNDTRIP OK / ROUNDTRIP FAIL.
#
# Exit code 0 em sucesso, 1 em falha.
# Sempre limpa temporarios, inclusive em caso de falha.
# Compativel com PowerShell 5.1 e 7+.

$ErrorActionPreference = 'Stop'

$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot '..')
$Fixture  = Join-Path $RepoRoot 'tests\fixtures\dummy_secret.yaml'
$Enc      = Join-Path $RepoRoot 'tests\fixtures\dummy_secret.enc.yaml'
$Round    = Join-Path $RepoRoot 'tests\fixtures\dummy_secret.roundtrip.yaml'
$KeyFile  = Join-Path $env:USERPROFILE '.sops\age\dummy-test-key.txt'

$ExitCode = 1

function Cleanup {
    Remove-Item -Force -ErrorAction SilentlyContinue $script:Enc, $script:Round, $script:KeyFile
}

try {
    # Pre-checks
    if (-not (Get-Command sops -ErrorAction SilentlyContinue)) {
        Write-Host 'ROUNDTRIP FAIL: sops nao instalado.'
        exit 1
    }
    if (-not (Get-Command age-keygen -ErrorAction SilentlyContinue)) {
        Write-Host 'ROUNDTRIP FAIL: age-keygen nao instalado.'
        exit 1
    }
    if (-not (Test-Path $Fixture)) {
        Write-Host "ROUNDTRIP FAIL: fixture ausente em $Fixture."
        exit 1
    }

    # Estado limpo
    $KeyDir = Split-Path $KeyFile
    if (-not (Test-Path $KeyDir)) {
        New-Item -ItemType Directory -Force $KeyDir | Out-Null
    }
    if (Test-Path $KeyFile) {
        Remove-Item $KeyFile -Force
    }

    # Gerar chave dummy
    & age-keygen -o $KeyFile 2>$null | Out-Null
    if ($LASTEXITCODE -ne 0 -or -not (Test-Path $KeyFile)) {
        Write-Host 'ROUNDTRIP FAIL: age-keygen falhou.'
        exit 1
    }

    $env:SOPS_AGE_KEY_FILE = $KeyFile

    # Extrair recipient publico
    $KeyContent = Get-Content $KeyFile
    $RecipientLine = $KeyContent | Where-Object { $_ -match '^# public key:' } | Select-Object -First 1
    if (-not $RecipientLine) {
        Write-Host 'ROUNDTRIP FAIL: nao consegui extrair recipient publico.'
        exit 1
    }
    $DummyRecipient = ($RecipientLine -split ':', 2)[1].Trim()

    # Encriptar (--config NUL: ignora .sops.yaml do projeto, cujas creation_rules
    # casam apenas com secrets/**; o teste vive em tests/fixtures/).
    $NullCfg = if ($IsWindows -or $PSVersionTable.PSEdition -eq 'Desktop') { 'NUL' } else { '/dev/null' }
    $EncContent = & sops --config $NullCfg --age $DummyRecipient -e $Fixture 2>$null
    if ($LASTEXITCODE -ne 0) {
        Write-Host 'ROUNDTRIP FAIL: sops -e falhou.'
        exit 1
    }
    $EncContent | Out-File -FilePath $Enc -Encoding utf8

    # Desencriptar
    $DecContent = & sops --config $NullCfg -d $Enc 2>$null
    if ($LASTEXITCODE -ne 0) {
        Write-Host 'ROUNDTRIP FAIL: sops -d falhou.'
        exit 1
    }
    $DecContent | Out-File -FilePath $Round -Encoding utf8

    # Comparar via parse YAML semantico (sops normaliza aspas/indentacao na
    # desencriptacao; conteudo logico e identico, byte-a-byte nao). Usa PyYAML.
    if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
        Write-Host 'ROUNDTRIP FAIL: python ausente para comparacao YAML.'
        exit 1
    }
    $PyCode = @'
import sys, yaml
with open(sys.argv[1], encoding="utf-8") as fa, open(sys.argv[2], encoding="utf-8") as fb:
    sys.exit(0 if yaml.safe_load(fa) == yaml.safe_load(fb) else 1)
'@
    & python -c $PyCode $Fixture $Round
    if ($LASTEXITCODE -eq 0) {
        Write-Host 'ROUNDTRIP OK'
        $ExitCode = 0
    } else {
        Write-Host 'ROUNDTRIP FAIL: estrutura YAML do roundtrip diverge do original.'
        $ExitCode = 1
    }
}
catch {
    Write-Host "ROUNDTRIP FAIL: excecao $($_.Exception.Message)"
    $ExitCode = 1
}
finally {
    Cleanup
}

exit $ExitCode
