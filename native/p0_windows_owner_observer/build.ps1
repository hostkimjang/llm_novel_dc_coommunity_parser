[CmdletBinding()]
param(
    [ValidateSet('Release', 'Debug')]
    [string]$Configuration = 'Release',
    [switch]$Clean
)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$build = Join-Path $root 'build'
$vswhere = 'C:\Program Files (x86)\Microsoft Visual Studio\Installer\vswhere.exe'

if (-not (Test-Path -LiteralPath $vswhere)) {
    throw 'Visual Studio locator is missing; no fallback download is permitted.'
}

$vs = (& $vswhere -latest -products * -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath).Trim()
if (-not $vs) {
    throw 'The installed MSVC x64 toolchain was not found.'
}

$cmake = Join-Path $vs 'Common7\IDE\CommonExtensions\Microsoft\CMake\CMake\bin\cmake.exe'
if (-not (Test-Path -LiteralPath $cmake)) {
    throw 'The Visual Studio bundled CMake executable was not found.'
}

if ($Clean -and (Test-Path -LiteralPath $build)) {
    $resolvedRoot = [IO.Path]::GetFullPath($root)
    $resolvedBuild = [IO.Path]::GetFullPath($build)
    if (-not $resolvedBuild.StartsWith($resolvedRoot + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) {
        throw 'Refusing to clean a build directory outside the observer source directory.'
    }
    Remove-Item -LiteralPath $resolvedBuild -Recurse -Force
}

& $cmake -S $root -B $build -G 'Visual Studio 17 2022' -A x64 '-DCMAKE_SYSTEM_VERSION=10.0.26100.0'
if ($LASTEXITCODE -ne 0) {
    throw "CMake configure failed with exit code $LASTEXITCODE"
}

& $cmake --build $build --config $Configuration --parallel 16
if ($LASTEXITCODE -ne 0) {
    throw "MSVC build failed with exit code $LASTEXITCODE"
}

$output = Join-Path $build $Configuration
[pscustomobject]@{
    Configuration = $Configuration
    BuildDirectory = $build
    ServiceBinary = Join-Path $output 'llm-novel-dc-owner-verifier.exe'
    DiagnosticBinary = Join-Path $output 'p0_windows_owner_observer_diagnostic.exe'
    NetworkUsed = $false
    RestoreUsed = $false
    ServiceInstalledOrStarted = $false
    ScmOrWdacConfigurationWritten = $false
} | ConvertTo-Json -Compress
