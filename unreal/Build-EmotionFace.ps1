param([string]$EngineRoot = 'C:/Program Files/Epic Games/UE_5.6')
$ErrorActionPreference = 'Stop'
$project = Join-Path $PSScriptRoot 'ResonanceVR/ResonanceVR.uproject'
uv run python (Join-Path $PSScriptRoot 'patch_ace_emotion_transport.py')
if ($LASTEXITCODE -ne 0) { throw 'ACE transport patch failed' }
& (Join-Path $EngineRoot 'Engine/Build/BatchFiles/Build.bat') ResonanceVREditor Win64 Development $project -NoHotReloadFromIDE '-CompilerVersion=14.38.33130' -Module=ResonanceFace -Module=ResonanceFaceEditor -Module=ACECore -Module=A2FCommon -Module=ACERuntime -Module=AnimStream -Module=LegacyA2FRemote -NoUBA
if ($LASTEXITCODE -ne 0) { throw 'Native face build failed' }
# A module-only UBT build does not run target metadata generation. Use the
# installed engine's ID for this plugin, leaving every other plugin manifest alone.
$engineManifest = Get-Content -Raw (Join-Path $EngineRoot 'Engine/Binaries/Win64/UnrealEditor.modules') | ConvertFrom-Json
$output = Join-Path $PSScriptRoot 'ResonanceVR/Plugins/ResonanceFace/Binaries/Win64/UnrealEditor.modules'
$manifest = [ordered]@{
    BuildId = $engineManifest.BuildId
    Modules = [ordered]@{
        ResonanceFace = 'UnrealEditor-ResonanceFace.dll'
        ResonanceFaceEditor = 'UnrealEditor-ResonanceFaceEditor.dll'
    }
} | ConvertTo-Json -Depth 4
[System.IO.File]::WriteAllText($output, $manifest, [System.Text.UTF8Encoding]::new($false))
Write-Output 'Native emotion transport and face fusion ready. Reopen the editor.'
