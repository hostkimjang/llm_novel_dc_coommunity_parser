[CmdletBinding()]
param(
    [ValidateSet('Release', 'Debug')]
    [string]$Configuration = 'Release',
    [switch]$SkipBuild
)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
if (-not $SkipBuild) {
    & (Join-Path $root 'build.ps1') -Configuration $Configuration
}

$output = Join-Path (Join-Path $root 'build') $Configuration
$diagnostic = Join-Path $output 'p0_windows_owner_observer_diagnostic.exe'
$service = Join-Path $output 'llm-novel-dc-owner-verifier.exe'
foreach ($binary in @($diagnostic, $service)) {
    if (-not (Test-Path -LiteralPath $binary)) {
        throw "Expected binary is missing: $binary"
    }
}

$raw = & $diagnostic
if ($LASTEXITCODE -ne 0) {
    throw "Diagnostic execution failed with exit code $LASTEXITCODE"
}
$receipt = $raw | ConvertFrom-Json -Depth 20

function Assert-True([bool]$Condition, [string]$Message) {
    if (-not $Condition) { throw $Message }
}

Assert-True ($receipt.schema_version -eq 'p0_windows_owner_observer_diagnostic_v1') 'diagnostic schema mismatch'
Assert-True ($receipt.gate_status -eq 'BOUNDED_NATIVE_OBSERVER_CANDIDATE_NO_GO') 'diagnostic gate mismatch'
Assert-True ($receipt.decision -eq 'NO_GO') 'diagnostic must stay NO_GO'
Assert-True ($receipt.candidate_only -eq $true) 'diagnostic must stay candidate_only'
Assert-True ($receipt.production_binary -eq $false) 'diagnostic must identify itself as non-production'
Assert-True ($receipt.operational_effect -eq 'NONE_READ_ONLY_DIAGNOSTIC') 'diagnostic operational effect mismatch'
Assert-True ($receipt.observation_completed -eq $true) 'bounded observation did not complete'
Assert-True ($receipt.process_id -eq $PID -or $receipt.process_id -gt 0) 'observer process ID is invalid'
Assert-True ($receipt.process_creation_time_stable -eq $true) 'observer process creation time changed during observation'
Assert-True ($receipt.bounded_qpc_interval_observed -eq $true) 'bounded QPC interval was not observed'
Assert-True ($receipt.self_image.observed -eq $true) 'held self-image identity/hash observation failed'
Assert-True ($receipt.self_image.identity_stable -eq $true) 'self-image identity was not stable'
Assert-True ($receipt.self_image.sha256 -match '^[0-9a-f]{64}$') 'self-image SHA-256 is invalid'
Assert-True ($receipt.production_service_image_candidate.observed -eq $true) 'fixed sibling service image candidate was not observed'
Assert-True ($receipt.production_service_image_candidate.sha256 -match '^[0-9a-f]{64}$') 'service image candidate SHA-256 is invalid'
Assert-True ($receipt.bootstrap_resource_exact -eq $true) 'embedded bootstrap resource is not exact'
Assert-True ($receipt.bootstrap_resource_sha256 -match '^[0-9a-f]{64}$') 'resource SHA-256 is invalid'
Assert-True ($receipt.loaded_modules.Count -eq 2) 'exact bcrypt module count mismatch'
foreach ($module in $receipt.loaded_modules) {
    Assert-True ($module.loaded -eq $true) "module not loaded: $($module.role)"
    Assert-True ($module.system32_path -eq $true) "module not loaded from System32: $($module.role)"
    Assert-True ($module.file.observed -eq $true) "module file identity/hash failed: $($module.role)"
}
Assert-True ($receipt.wldp_query_succeeded -eq $true) 'WLDP read-only query failed'
Assert-True ($receipt.diagnostic_errors.Count -eq 0) 'diagnostic emitted internal observation errors'

$diagnosticDiskSha = (Get-FileHash -Algorithm SHA256 -LiteralPath $diagnostic).Hash.ToLowerInvariant()
$serviceDiskSha = (Get-FileHash -Algorithm SHA256 -LiteralPath $service).Hash.ToLowerInvariant()
$resourceSourceSha = (Get-FileHash -Algorithm SHA256 -LiteralPath (Join-Path $root 'bootstrap_candidate.bin')).Hash.ToLowerInvariant()
Assert-True ($receipt.self_image.sha256 -eq $diagnosticDiskSha) 'diagnostic held-image SHA does not match disk hash'
Assert-True ($receipt.production_service_image_candidate.sha256 -eq $serviceDiskSha) 'service candidate held-image SHA does not match disk hash'
Assert-True ($receipt.bootstrap_resource_sha256 -eq $resourceSourceSha) 'embedded service resource SHA does not match source bytes'

foreach ($field in @(
    'external_owner_key_verified',
    'observer_receipt_signature_verified',
    'trusted_time_verified',
    'revocation_current_verified',
    'durable_nonce_verified',
    'owner_authority_verified',
    'actual_authority_granted',
    'production_approval',
    'full_scan_approval',
    'p0_phase_exit',
    'action_applied'
)) {
    Assert-True ($receipt.$field -eq $false) "authority/action field must be false: $field"
}
foreach ($blocker in @(
    'AUTHENTICODE_NOT_VERIFIED',
    'EXTERNAL_OWNER_KEY_NOT_VERIFIED',
    'TRUSTED_TIME_REVOCATION_NOT_VERIFIED',
    'DURABLE_NONCE_NOT_VERIFIED',
    'SIGNED_NATIVE_OBSERVER_NOT_VERIFIED'
)) {
    Assert-True ($receipt.blocker_codes -contains $blocker) "required blocker missing: $blocker"
}

$vswhere = 'C:\Program Files (x86)\Microsoft Visual Studio\Installer\vswhere.exe'
$vs = (& $vswhere -latest -products * -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath).Trim()
$dumpbin = Get-ChildItem -LiteralPath (Join-Path $vs 'VC\Tools\MSVC') -Filter dumpbin.exe -Recurse |
    Where-Object { $_.FullName -match '\\Hostx64\\x64\\dumpbin\.exe$' } |
    Sort-Object FullName -Descending |
    Select-Object -First 1 -ExpandProperty FullName
if (-not $dumpbin) { throw 'dumpbin.exe was not found in the installed x64 MSVC toolchain' }

foreach ($binary in @($diagnostic, $service)) {
    $headers = (& $dumpbin /headers $binary 2>&1) -join "`n"
    $dependents = (& $dumpbin /dependents $binary 2>&1) -join "`n"
    $imports = (& $dumpbin /imports $binary 2>&1) -join "`n"
    $loadConfig = (& $dumpbin /loadconfig $binary 2>&1) -join "`n"
    Assert-True ($headers -match '8664 machine \(x64\)') "binary is not AMD64: $binary"
    Assert-True ($headers -match '(?m)^\s*0 \[\s*0\] RVA \[size\] of COM Descriptor Directory\s*$') "CLR/COM descriptor must be zero: $binary"
    foreach ($flag in @('High Entropy Virtual Addresses', 'Dynamic base', 'NX compatible', 'Control Flow Guard', 'CET Compat')) {
        Assert-True ($headers -match [regex]::Escape($flag)) "PE hardening flag missing ($flag): $binary"
    }
    foreach ($loadConfigFlag in @('0800 Dependent Load Flag', 'CF instrumented', 'FID table present', 'EH Continuation table present')) {
        Assert-True ($loadConfig -match [regex]::Escape($loadConfigFlag)) "PE load-config hardening missing ($loadConfigFlag): $binary"
    }
    $dependencyNames = [regex]::Matches($dependents, '(?im)^\s+([A-Za-z0-9._-]+\.dll)\s*$') |
        ForEach-Object { $_.Groups[1].Value.ToLowerInvariant() } |
        Sort-Object -Unique
    $expectedDependencies = @('advapi32.dll', 'bcrypt.dll', 'kernel32.dll')
    Assert-True (($dependencyNames -join ',') -eq ($expectedDependencies -join ',')) "unexpected PE dependency set ($($dependencyNames -join ',')): $binary"
    foreach ($forbidden in @('mscoree.dll', 'coreclr.dll', 'hostfxr.dll', 'hostpolicy.dll', 'clrjit.dll', 'vcruntime140.dll', 'msvcp140.dll', 'ucrtbase.dll', 'winhttp.dll', 'wininet.dll', 'urlmon.dll', 'ws2_32.dll')) {
        Assert-True ($dependents -notmatch [regex]::Escape($forbidden)) "forbidden dynamic dependency ($forbidden): $binary"
    }
    foreach ($forbiddenApi in @('CreateServiceW', 'ChangeServiceConfigW', 'ChangeServiceConfig2W', 'DeleteService', 'ControlService')) {
        Assert-True ($imports -notmatch "\b$forbiddenApi\b") "forbidden SCM mutation API ($forbiddenApi): $binary"
    }
}

$argProbe = Start-Process -FilePath $diagnostic -ArgumentList 'unexpected-selector' -Wait -PassThru -WindowStyle Hidden
Assert-True ($argProbe.ExitCode -ne 0) 'diagnostic accepted an unexpected public selector argument'

[pscustomobject]@{
    Gate = $receipt.gate_status
    Decision = $receipt.decision
    CandidateOnly = $receipt.candidate_only
    SelfImageSha256 = $receipt.self_image.sha256
    ServiceImageSha256 = $receipt.production_service_image_candidate.sha256
    ResourceSha256 = $receipt.bootstrap_resource_sha256
    LoadedModuleCount = $receipt.loaded_modules.Count
    WldpLockdownState = $receipt.wldp_lockdown_state
    UmciEnforced = $receipt.wdac_umci_enforced
    ServicePresent = $receipt.service_present
    PeSmoke = 'AMD64_STATIC_CRT_CFG_CET_ASLR_NX_NO_MANAGED_OR_NETWORK_IMPORTS_PASS'
    ServiceExecuted = $false
    ServiceInstalledOrStarted = $false
    ScmOrWdacConfigurationWritten = $false
} | ConvertTo-Json -Compress
