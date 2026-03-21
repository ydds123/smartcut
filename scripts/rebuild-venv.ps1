[CmdletBinding(SupportsShouldProcess = $true, ConfirmImpact = 'Medium')]
param(
    [string]$Python = "python",
    [string]$VenvPath = ".venv",
    [string[]]$Extras = @("dev", "web", "refine"),
    [int]$PipTimeout = 300,
    [switch]$SkipTests
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectRoot

function Write-Step {
    param([string]$Message)

    Write-Host ""
    Write-Host "==> $Message" -ForegroundColor Cyan
}

function Resolve-CommandPath {
    param([string]$CommandName)

    $command = Get-Command $CommandName -ErrorAction Stop | Select-Object -First 1
    return $command.Source
}

# Resolve the venv path against the repo root so the script is stable from any cwd.
if ([System.IO.Path]::IsPathRooted($VenvPath)) {
    $ResolvedVenvPath = [System.IO.Path]::GetFullPath($VenvPath)
} else {
    $ResolvedVenvPath = [System.IO.Path]::GetFullPath((Join-Path $ProjectRoot $VenvPath))
}

$PythonPath = Resolve-CommandPath -CommandName $Python
$EditableSpec = if ($Extras.Count -gt 0) {
    ".[{0}]" -f ($Extras -join ",")
} else {
    "."
}

if (-not $PSCmdlet.ShouldProcess($ResolvedVenvPath, "Rebuild virtual environment and install $EditableSpec")) {
    return
}

Write-Step "Rebuild $ResolvedVenvPath with $PythonPath"
& $PythonPath -m venv --clear $ResolvedVenvPath

$VenvPython = Join-Path $ResolvedVenvPath "Scripts\python.exe"
if (-not (Test-Path $VenvPython)) {
    throw "Virtual environment interpreter not found: $VenvPython"
}

Write-Step "Install dependencies $EditableSpec"
& $VenvPython -m pip install --default-timeout=$PipTimeout -e $EditableSpec

if (-not $SkipTests) {
    # Run a quick regression by default so dependency issues surface immediately.
    Write-Step "Run tests .\.venv\Scripts\python -m pytest -q"
    & $VenvPython -m pytest -q
}

Write-Host ""
Write-Host "Environment rebuild complete." -ForegroundColor Green
Write-Host "  Activate: .\.venv\Scripts\Activate.ps1"
Write-Host "  Python:   $VenvPython"
