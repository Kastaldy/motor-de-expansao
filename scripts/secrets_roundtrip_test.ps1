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

    # Encriptar (stdout do sops vai direto para arquivo via redirecionamento)
    $EncContent = & sops --age $DummyRecipient -e $Fixture 2>$null
    if ($LASTEXITCODE -ne 0) {
        Write-Host 'ROUNDTRIP FAIL: sops -e falhou.'
        exit 1
    }
    $EncContent | Out-File -FilePath $Enc -Encoding utf8

    # Desencriptar
    $DecContent = & sops -d $Enc 2>$null
    if ($LASTEXITCODE -ne 0) {
        Write-Host 'ROUNDTRIP FAIL: sops -d falhou.'
        exit 1
    }
    $DecContent | Out-File -FilePath $Round -Encoding utf8

    # Comparar por hash (insensivel a encoding/newline normalization de Out-File:
    # comparamos via bytes do conteudo logico apos re-leitura como texto)
    $OrigText  = (Get-Content $Fixture -Raw) -replace "`r`n", "`n"
    $RoundText = (Get-Content $Round   -Raw) -replace "`r`n", "`n"

    if ($OrigText -eq $RoundText) {
        Write-Host 'ROUNDTRIP OK'
        $ExitCode = 0
    } else {
        Write-Host 'ROUNDTRIP FAIL: diff entre original e roundtrip nao bate.'
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
