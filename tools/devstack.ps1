[CmdletBinding()]
param(
  [Parameter(ValueFromRemainingArguments = $true)]
  [string[]]$ArgsList
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RootDir = Split-Path -Parent $ScriptDir

$pythonCmd = Get-Command py -ErrorAction SilentlyContinue
if ($pythonCmd) {
  Set-Location $RootDir
  & py -3 "$RootDir\tools\devstack.py" @ArgsList
  exit $LASTEXITCODE
}

$pythonCmd = Get-Command python -ErrorAction SilentlyContinue
if ($pythonCmd) {
  Set-Location $RootDir
  & python "$RootDir\tools\devstack.py" @ArgsList
  exit $LASTEXITCODE
}

Write-Error "Python is required but not found in PATH."
