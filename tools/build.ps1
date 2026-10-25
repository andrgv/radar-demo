param(
    [ValidateSet('build', 'getlibs', 'program')][string]$Action = 'build',
    [switch]$ConfirmFlash,
    [ValidateSet('working','hpf350','hpf100','scope')][string]$Variant = 'working',
    [string]$ToolsDir = "$env:USERPROFILE\ModusToolbox\tools_3.9"
)
$ErrorActionPreference = 'Stop'
if ($Action -eq 'program' -and -not $ConfirmFlash) {
    throw 'Flashing requires explicit confirmation: -Action program -ConfirmFlash'
}
$projectRoot = Split-Path -Parent $PSScriptRoot
$bash = Join-Path $ToolsDir 'modus-shell\bin\bash.exe'
if (-not (Test-Path -LiteralPath $bash)) { throw "ModusToolbox shell missing: $bash" }
Push-Location $projectRoot
try {
    $variantArguments = ''
    $buildLocation = 'build'
    if ($Variant -ne 'working') {
        & python tools/prepare_qualification.py
        if ($LASTEXITCODE -ne 0) { throw 'Qualification source generation failed' }
        $hpfKhz = if ($Variant -eq 'hpf100') { '100' } else { '350' }
        $variantArguments = "RADAR_QUALIFICATION=1 RADAR_HPF_KHZ=$hpfKhz"
        $buildLocation = "build/qualification-$hpfKhz"
        if ($Variant -eq 'scope') {
            $variantArguments += ' RADAR_SCOPE_OUTPUT=1'
            $buildLocation = 'build/scope-timing'
        }
    }
    & $bash -c "export PATH=/usr/bin:`$PATH; make $Action -j8 CY_BUILD_LOCATION=$buildLocation $variantArguments"
    if ($LASTEXITCODE -ne 0) { throw "ModusToolbox $Action failed with exit code $LASTEXITCODE" }
} finally {
    Pop-Location
}
