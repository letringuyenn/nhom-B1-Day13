param(
    [string]$BaseUrl = $(if ($env:LAB_BASE_URL) {
        $env:LAB_BASE_URL
    } elseif ($env:BASE_URL) {
        $env:BASE_URL
    } else {
        "http://127.0.0.1:8013"
    }),
    [switch]$SkipTests
)

$ErrorActionPreference = "Stop"
$baseUrl = $BaseUrl.TrimEnd("/")
$baseUri = [System.Uri]$baseUrl
$serverHost = $baseUri.Host
$serverPort = $baseUri.Port
$python = Join-Path $PSScriptRoot "..\.venv\Scripts\python.exe"
$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")

function Invoke-Checked {
    param(
        [string]$FilePath,
        [string[]]$Arguments
    )

    & $FilePath @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Command failed with exit code $LASTEXITCODE`: $FilePath $Arguments"
    }
}

Push-Location $repoRoot
try {
    if (Test-Path "data\logs.jsonl") {
        Clear-Content "data\logs.jsonl"
    }

    $server = Start-Process `
        -FilePath $python `
        -ArgumentList "-m", "uvicorn", "app.main:app", "--host", $serverHost, "--port", $serverPort, "--env-file", ".env" `
        -WorkingDirectory $repoRoot `
        -WindowStyle Hidden `
        -PassThru

    try {
        Start-Sleep -Seconds 2
        Invoke-Checked $python @("-c", "import httpx; response=httpx.get('$baseUrl/health'); response.raise_for_status(); print(response.json())")
        Invoke-Checked $python @("scripts\load_test.py", "--concurrency", "5", "--base-url", $baseUrl)
        Invoke-Checked $python @("scripts\eval_quality.py", "--base-url", $baseUrl)
        Invoke-Checked $python @("scripts\collect_evidence.py", "--base-url", $baseUrl)
        Invoke-Checked $python @("scripts\build_dashboard.py")
        Invoke-Checked $python @("scripts\check_alerts.py")
        Start-Sleep -Seconds 3
        Invoke-Checked $python @("scripts\export_langfuse_evidence.py")
        Invoke-Checked $python @("scripts\validate_logs.py")
        if (-not $SkipTests) {
            $pytestTemp = "data\pytest-verify-$PID"
            Invoke-Checked $python @(
                "-m", "pytest", "tests", "-v",
                "--basetemp=$pytestTemp"
            )
        }
    }
    finally {
        if ($server -and -not $server.HasExited) {
            Stop-Process -Id $server.Id
        }
    }
}
finally {
    Pop-Location
}
