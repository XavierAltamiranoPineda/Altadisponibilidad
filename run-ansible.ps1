[CmdletBinding()]
param(
    [Parameter(Mandatory = $true, Position = 0)]
    [string]$Playbook,

    [Parameter(Position = 1, ValueFromRemainingArguments = $true)]
    [string[]]$Arguments
)

$ErrorActionPreference = "Stop"

$altadisponibilidad = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectRoot = Split-Path -Parent $altadisponibilidad
$playbookBase = if ($Playbook -like 'Altadisponibilidad-main/*') { $projectRoot } else { $altadisponibilidad }
$playbookPath = Join-Path $playbookBase $Playbook

if (-not (Test-Path $playbookPath)) {
    throw "No existe el playbook: $playbookPath"
}

$wsl = Get-Command wsl.exe -ErrorAction SilentlyContinue
if ($null -eq $wsl) {
    throw "WSL no esta instalado. Instala WSL2 y una distribucion Linux, por ejemplo Ubuntu."
}

$distribution = "Ubuntu"
$installedDistributions = @(wsl.exe --list --quiet | ForEach-Object { $_.Trim().TrimStart('*').Trim() })
if ($distribution -notin $installedDistributions) {
    throw "No existe la distribucion WSL '$distribution'. Instalala con: wsl --install -d Ubuntu"
}

function Convert-ToWslPath([string]$windowsPath) {
    $resolvedPath = (Resolve-Path $windowsPath).Path
    $drive = $resolvedPath.Substring(0, 1).ToLowerInvariant()
    $rest = $resolvedPath.Substring(2).Replace('\', '/')
    return "/mnt/$drive$rest"
}

$wslProjectRoot = Convert-ToWslPath $projectRoot
$windowsWorkingDirectory = if ($Playbook -like 'Altadisponibilidad-main/*') { $projectRoot } else { $altadisponibilidad }
$wslWorkingDirectory = if ($Playbook -like 'Altadisponibilidad-main/*') { $wslProjectRoot } else { "$wslProjectRoot/Altadisponibilidad" }
$wslPlaybook = (Resolve-Path $playbookPath).Path.Substring($windowsWorkingDirectory.Length + 1).Replace('\', '/')
$wslArguments = @('bash', '-lc', "cd '$wslWorkingDirectory' && ansible-playbook '$wslPlaybook'")

foreach ($argument in $Arguments) {
    $escapedArgument = $argument.Replace("'", "'\\''")
    $wslArguments[-1] += " '$escapedArgument'"
}

& wsl.exe -d $distribution @wslArguments
exit $LASTEXITCODE
