#requires -Version 5.1
<#
.SYNOPSIS
Starts Epic UE5.6 Pixel Streaming locally. Keep this terminal open; Q or Ctrl+C stops owned processes.
#>
[CmdletBinding()]
param(
    [string]$ExecutablePath,
    [string]$ProjectPath,
    [string]$EditorPath,
    [ValidateSet('Low','Balanced','Original')][string]$Quality = 'Low',
    [ValidateSet('Economy','Clear','Sharp')][string]$VRClarity = 'Clear',
    [ValidateRange(1,65535)][int]$HttpPort = 80,
    [ValidateRange(1,65535)][int]$StreamerPort = 8888,
    [ValidateRange(1,65535)][int]$SfuPort = 8889,
    [ValidateRange(1,900)][int]$TimeoutSeconds = 180,
    [ValidateRange(0,86400)][int]$RunSeconds = 0,
    [ValidateRange(1,60)][int]$DisconnectGraceSeconds = 5,
    [switch]$Development,
    [switch]$Hmd,
    [switch]$DesktopOnly,
    [switch]$SetupOnly,
    [switch]$ServerOnly,
    [switch]$KeepAlive,
    [switch]$NoBrowser
)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$repo = Split-Path $PSScriptRoot -Parent
$localRoot = Join-Path $repo '.pixelstream'
$infra = Join-Path $localRoot 'Infrastructure'
$revision = '3082a5f2faa2a6d2e57606180d34f1539abc9925'
$owned = [System.Collections.Generic.List[System.Diagnostics.Process]]::new()

function Resolve-RepoPath([string]$Value) {
    if ([IO.Path]::IsPathRooted($Value)) { return [IO.Path]::GetFullPath($Value) }
    return [IO.Path]::GetFullPath((Join-Path $repo $Value))
}
function Invoke-Checked([string]$Command, [string[]]$Arguments) {
    & $Command @Arguments
    if ($LASTEXITCODE -ne 0) { throw "$Command failed with exit code $LASTEXITCODE" }
}
function Test-FreePort([int]$Port) {
    $listener = [Net.Sockets.TcpListener]::new([Net.IPAddress]::Loopback, $Port)
    try { $listener.Start(); return $true } catch { return $false } finally { $listener.Stop() }
}
function Start-Owned([string]$File, [string[]]$Arguments, [string]$WorkingDirectory, [string]$Name) {
    # Windows PowerShell joins ArgumentList without quoting. Quote each argument
    # explicitly; reject embedded quotes rather than interpreting shell text.
    $quoted = foreach ($argument in $Arguments) {
        if ($argument.Contains('"') -or $argument.EndsWith('\')) { throw "Invalid process argument: $argument" }
        '"' + $argument + '"'
    }
    $process = Start-Process -FilePath $File -ArgumentList $quoted -WorkingDirectory $WorkingDirectory `
        -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $run "$Name.stdout.log") `
        -RedirectStandardError (Join-Path $run "$Name.stderr.log")
    $owned.Add($process)
    return $process
}
function Wait-Local([string]$Url, [scriptblock]$Accept, [System.Diagnostics.Process]$Process, [string]$Description) {
    $deadline = [DateTime]::UtcNow.AddSeconds($TimeoutSeconds)
    do {
        if ($Process.HasExited) { throw "$Description failed: process exited ($($Process.ExitCode)). See $run" }
        try {
            $response = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 2
            if (& $Accept $response) { return }
        } catch { Write-Verbose $_ }
        Start-Sleep -Milliseconds 500
    } while ([DateTime]::UtcNow -lt $deadline)
    throw "Timed out waiting for $Description. See $run"
}

$configPath = Join-Path $PSScriptRoot 'pixelstream.local.json'
if (Test-Path -LiteralPath $configPath) {
    $config = Get-Content -LiteralPath $configPath -Raw | ConvertFrom-Json
    foreach ($key in @('ExecutablePath','ProjectPath','EditorPath','HttpPort','Development','Quality','VRClarity')) {
        if (-not $PSBoundParameters.ContainsKey($key) -and $config.PSObject.Properties[$key]) {
            Set-Variable -Name $key -Value $config.$key
        }
    }
}
if ($PSBoundParameters.ContainsKey('ExecutablePath') -and -not $PSBoundParameters.ContainsKey('Development')) {
    $Development = [switch]$false
}
if (-not $ProjectPath) { $ProjectPath = 'unreal/ResonanceVR/ResonanceVR.uproject' }
if (-not $ExecutablePath) { $ExecutablePath = '.pixelstream/Build/Windows/ResonanceVR.exe' }
$presets = @{
    Low = @{ ScalabilityLevel=0; Fps=30; ScreenPercentage=70; XrFrameRate=72; ShadowBias=2; TexturePoolMB=768; TextureMipBias=1 }
    Balanced = @{ ScalabilityLevel=1; Fps=45; ScreenPercentage=85; XrFrameRate=72; ShadowBias=1; TexturePoolMB=1024; TextureMipBias=0 }
    Original = @{ ScalabilityLevel=3; Fps=60; ScreenPercentage=100; XrFrameRate=90; ShadowBias=0; TexturePoolMB=0; TextureMipBias=0 }
}
if (-not $presets.ContainsKey($Quality)) { throw 'Quality must be Low, Balanced or Original.' }
$imagePresets = @{
    Economy = @{ Height=480; VRScreenPercentage=70; MaxWidth=1920; XrScale=0.5; MinBitrate=1000000; Bitrate=6000000 }
    Clear = @{ Height=1080; VRScreenPercentage=100; MaxWidth=4096; XrScale=1.0; MinBitrate=12000000; Bitrate=24000000 }
    Sharp = @{ Height=1440; VRScreenPercentage=100; MaxWidth=4096; XrScale=1.0; MinBitrate=16000000; Bitrate=32000000 }
}
if (-not $imagePresets.ContainsKey($VRClarity)) { throw 'VRClarity must be Economy, Clear or Sharp.' }
$preset = $presets[$Quality].Clone()
foreach ($key in $imagePresets[$VRClarity].Keys) { $preset[$key] = $imagePresets[$VRClarity][$key] }
$preset.Clarity = $VRClarity
if ($HttpPort -lt 1 -or $HttpPort -gt 65535) { throw 'HttpPort must be 1..65535.' }
if (@($HttpPort,$StreamerPort,$SfuPort | Select-Object -Unique).Count -ne 3) { throw 'Ports must be distinct.' }

foreach ($command in @('git.exe','node.exe','npm.cmd')) { Get-Command $command -ErrorAction Stop | Out-Null }
$nodeMajor = [int]((& node.exe --version).TrimStart('v').Split('.')[0])
if ($nodeMajor -notin @(22,24)) { throw 'Use Node 22 (upstream NODE_VERSION: 22.14.0) or locally tested Node 24. No system software is installed by this script.' }

# Fail before installing anything if an application launch cannot succeed.
if (-not $SetupOnly -and -not $ServerOnly) {
    if ($Development) {
        $ProjectPath = Resolve-RepoPath $ProjectPath
        if (-not (Test-Path -LiteralPath $ProjectPath -PathType Leaf)) { throw "Missing project: $ProjectPath" }
        if (-not $EditorPath) {
            $installation = Get-ItemProperty 'HKLM:\SOFTWARE\EpicGames\Unreal Engine\5.6' -ErrorAction SilentlyContinue
            $engine = if ($installation) { $installation.InstalledDirectory } else { $null }
            if ($engine) { $EditorPath = Join-Path $engine 'Engine/Binaries/Win64/UnrealEditor.exe' }
        }
        if (-not $EditorPath -or -not (Test-Path -LiteralPath $EditorPath -PathType Leaf)) { throw 'Supply -EditorPath for UE5.6.1; see docs/PIXEL_STREAMING_SETUP.md.' }
        $app = Resolve-RepoPath $EditorPath
        $descriptor = Get-Content -LiteralPath $ProjectPath -Raw | ConvertFrom-Json
        if (-not ($descriptor.Plugins | Where-Object { $_.Name -eq 'PixelStreaming2' -and $_.Enabled })) { throw 'This project does not explicitly enable PixelStreaming2.' }
        if ($descriptor.Plugins | Where-Object { $_.Name -eq 'PixelStreaming' -and $_.Enabled }) { throw 'Disable legacy PixelStreaming for this workflow.' }
        if (-not $DesktopOnly -and ($descriptor.Plugins | Where-Object { $_.Name -match '^OpenXR' -and $_.Enabled })) { throw 'This project still enables OpenXR plugins; use the streaming configuration described in the guide.' }
        if (-not $DesktopOnly -and -not ($descriptor.Plugins | Where-Object { $_.Name -eq 'ResonanceWebXR' -and $_.Enabled })) { throw 'Enable/build the ResonanceWebXR plugin in this project, or use -DesktopOnly. See docs/PIXEL_STREAMING_SETUP.md.' }
    } else {
        $app = Resolve-RepoPath $ExecutablePath
        if (-not (Test-Path -LiteralPath $app -PathType Leaf)) { throw "No packaged application at $app. Package first, set scripts/pixelstream.local.json, or use -Development -EditorPath <UE5.6.1 editor>. See docs/PIXEL_STREAMING_SETUP.md." }
    }
}

if (-not (Test-Path -LiteralPath $infra)) {
    New-Item -ItemType Directory -Force -Path $localRoot | Out-Null
    Invoke-Checked 'git.exe' @('clone','--branch','UE5.6','--single-branch','https://github.com/EpicGames/PixelStreamingInfrastructure.git',$infra)
    Invoke-Checked 'git.exe' @('-C',$infra,'checkout','--detach',$revision)
}
$actualRevision = & git.exe -C $infra rev-parse HEAD
if ($LASTEXITCODE -ne 0 -or $actualRevision -ne $revision) { throw "Infrastructure must be the pinned UE5.6 revision $revision. Existing checkout was left unchanged." }
$entry = Join-Path $infra 'SignallingWebServer/dist/index.js'
$page = Join-Path $infra 'SignallingWebServer/www/player.html'
$stamp = Join-Path $localRoot 'built-revision.txt'
if (-not (Test-Path $stamp) -or (Get-Content $stamp -Raw).Trim() -ne $revision -or -not (Test-Path $entry) -or -not (Test-Path $page)) {
    Push-Location $infra
    try {
        Invoke-Checked 'npm.cmd' @('ci','--workspace','Common','--workspace','Signalling','--workspace','SignallingWebServer','--workspace','Frontend/library','--workspace','Frontend/ui-library','--workspace','Frontend/implementations/typescript','--include-workspace-root','--ignore-scripts','--no-audit','--no-fund')
        Invoke-Checked 'npm.cmd' @('run','build:all:cjs')
        Set-Content -LiteralPath $stamp -Value $revision -Encoding Ascii
    } finally { Pop-Location }
}
# Express sendFile rejects absolute paths containing dot directories such as
# hidden parent directories. Its static middleware serves index.html from
# an explicit root. Use an identical copy of Epic's page as the root index.
Copy-Item -LiteralPath $page -Destination (Join-Path (Split-Path $page -Parent) 'index.html') -Force
if (-not $DesktopOnly) {
    Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'pixelstream-webxr.js') -Destination (Join-Path (Split-Path $page -Parent) 'resonance-webxr.js') -Force
    $html = [IO.File]::ReadAllText($page)
    $browserPreset = @{ name="$Quality graphics / $VRClarity image"; framebufferScale=$preset.XrScale; refreshRate=$preset.XrFrameRate } | ConvertTo-Json -Compress
    $html = $html.Replace('</body>', "<script>window.ResonanceStreamingPreset=$browserPreset;</script>" + '<script src="resonance-webxr.js"></script></body>')
    [IO.File]::WriteAllText((Join-Path (Split-Path $page -Parent) 'index.html'), $html)
}
if ($SetupOnly) { Write-Host "UE5.6 infrastructure ready: $infra"; return }

if (-not (Test-FreePort $HttpPort)) {
    if ($HttpPort -eq 80 -and -not $PSBoundParameters.ContainsKey('HttpPort') -and (Test-FreePort 8080)) {
        $HttpPort = 8080
        Write-Warning 'Port 80 is occupied; using localhost:8080.'
    } else { throw "HTTP port $HttpPort is occupied; use -HttpPort <free port>." }
}
foreach ($port in @($StreamerPort,$SfuPort)) { if (-not (Test-FreePort $port)) { throw "Port $port is occupied. No existing process was stopped." } }
$run = Join-Path $localRoot ('logs/' + [DateTime]::Now.ToString('yyyyMMdd-HHmmss-fff'))
New-Item -ItemType Directory -Force -Path $run | Out-Null
$baseUrl = if ($HttpPort -eq 80) { 'http://localhost' } else { "http://localhost:$HttpPort" }
$probeUrl = "http://127.0.0.1:$HttpPort"
try {
    $serverArgs = @('--require',(Join-Path $PSScriptRoot 'pixelstream-loopback.cjs'),$entry,'--no_config','--serve','--rest_api','--player_port',"$HttpPort",'--streamer_port',"$StreamerPort",'--sfu_port',"$SfuPort",'--max_players','1','--http_root',(Join-Path $infra 'SignallingWebServer/www'),'--log_folder',$run)
    $server = Start-Owned (Get-Command node.exe).Source $serverArgs (Join-Path $infra 'SignallingWebServer') 'server'
    Wait-Local "$probeUrl/" { param($r) $r.StatusCode -eq 200 } $server 'reference frontend'
    Write-Host "Reference frontend ready at $baseUrl (loopback only). Logs: $run"
    Write-Host "Graphics: $Quality; VR image: $VRClarity ($($preset.Height)p, $($preset.VRScreenPercentage)% render scale, $($preset.Fps) FPS target, browser scale $($preset.XrScale))."
    Set-Content -LiteralPath (Join-Path $run 'quality-preset.json') -Value ($preset | ConvertTo-Json) -Encoding UTF8
    if ($Development -and @(Get-Process UnrealEditor -ErrorAction SilentlyContinue).Count -gt 0) {
        Write-Warning 'An Unreal Editor is already running. Close it manually before streaming to avoid keeping a second scene/assets in GPU memory.'
    }
    if (-not $ServerOnly) {
        # Select actual Unreal graphics quality BEFORE startup, for desktop and
        # VR alike. Isolate generated/saved settings from normal editor/game use.
        $scalabilityGroups = @('ViewDistanceQuality','AntiAliasingQuality','ShadowQuality',
            'GlobalIlluminationQuality','ReflectionQuality','PostProcessQuality',
            'TextureQuality','EffectsQuality','FoliageQuality','ShadingQuality','LandscapeQuality')
        $userSettingsPath = Join-Path $run 'GameUserSettings.ini'
        $settings = @('[ScalabilityGroups]',"sg.ResolutionQuality=$($preset.ScreenPercentage)")
        $settings += foreach ($group in $scalabilityGroups) { "sg.$group=$($preset.ScalabilityLevel)" }
        $settings += @('', '[/Script/Engine.GameUserSettings]', 'Version=5',
            'ResolutionSizeX=1280','ResolutionSizeY=720','LastUserConfirmedResolutionSizeX=1280',
            'LastUserConfirmedResolutionSizeY=720','FullscreenMode=2','LastConfirmedFullscreenMode=2',
            'PreferredFullscreenMode=2','bUseVSync=False','bUseDynamicResolution=False','FrameRateLimit=30.0')
        Set-Content -LiteralPath $userSettingsPath -Value $settings -Encoding Ascii
        Write-Host "Unreal graphics scalability: $($preset.ScalabilityLevel) (Low=0, Medium=1, Epic=3). Session settings: $userSettingsPath"
        $appArgs = @()
        if ($Development) { $appArgs += @($ProjectPath,'-game') }
        # UE5.6.1 mutes hardware output AFTER submix listeners capture audio.
        # This preserves Pixel Streaming speech while preventing a local echo.
        # Engine implementation supports this in editor/Development, not Shipping.
        $appArgs += @("-PixelStreamingURL=ws://127.0.0.1:$StreamerPort",'-AudioMixer','-muteaudio','-RenderOffscreen','-ForceRes','-ResY=720','-PixelStreamingEncoderCodec=H264',"-PixelStreamingWebRTCMinBitrate=$($preset.MinBitrate)","-PixelStreamingWebRTCMaxBitrate=$($preset.Bitrate)","-abslog=$(Join-Path $run 'Unreal.log')")
        if (-not $DesktopOnly) {
            # Load the XR driver now; the bridge starts in mono and switches only
            # after the browser successfully creates an immersive session.
            $appArgs += @('-PixelStreamingEnableHMD','-PixelStreamingHMDEnable=true','-ResonanceWebXR')
            $appArgs += @("-ResonanceVRHeight=$($preset.Height)","-ResonanceVRFPS=$($preset.Fps)","-ResonanceVRScreenPercentage=$($preset.VRScreenPercentage)","-ResonanceVRMaxWidth=$($preset.MaxWidth)","-ResonanceVRShadowBias=$($preset.ShadowBias)")
            $appArgs += @("-ResonanceVRTexturePoolMB=$($preset.TexturePoolMB)","-ResonanceVRTextureMipBias=$($preset.TextureMipBias)")
        } else {
            $appArgs += @('-PixelStreamingHMDEnable=false')
        }
        $qualityQueries = ($scalabilityGroups | ForEach-Object { "sg.$_" }) -join ','
        $appArgs += @('-ResX=1280','-PixelStreamingWebRTCFps=30',"-GameUserSettingsINI=$userSettingsPath","-ExecCmds=t.MaxFPS 30,$qualityQueries,r.ScreenPercentage,r.MaterialQualityLevel,r.ShadowQuality")
        Set-Content -LiteralPath (Join-Path $run 'launch-arguments.json') -Value (ConvertTo-Json -InputObject $appArgs) -Encoding UTF8
        $application = Start-Owned $app $appArgs (Split-Path $app -Parent) 'application'
        Wait-Local "$probeUrl/api/streamers" { param($r) @($r.Content | ConvertFrom-Json | Where-Object { $_.streaming }).Count -gt 0 } $application 'Unreal streamer connection'
        # Check the values actually reported by the running engine, not just the
        # preset label/config file. Refuse to continue if Low remained Epic.
        $graphicsState = @{}
        $graphicsDeadline = [DateTime]::UtcNow.AddSeconds(10)
        do {
            $engineLog = Get-Content -LiteralPath (Join-Path $run 'Unreal.log') -Raw -ErrorAction SilentlyContinue
            foreach ($group in $scalabilityGroups) {
                $pattern = 'sg\.' + [regex]::Escape($group) + '\s*=\s*"(\d+)"'
                $reported = [regex]::Matches([string]$engineLog, $pattern)
                if ($reported.Count -gt 0) { $graphicsState[$group] = [int]$reported[$reported.Count - 1].Groups[1].Value }
            }
            if ($graphicsState.Count -eq $scalabilityGroups.Count) { break }
            Start-Sleep -Milliseconds 500
        } while ([DateTime]::UtcNow -lt $graphicsDeadline)
        $graphicsState | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $run 'graphics-verification.json') -Encoding UTF8
        if ($graphicsState.Count -ne $scalabilityGroups.Count -or
            @($graphicsState.Values | Where-Object { $_ -ne $preset.ScalabilityLevel }).Count -gt 0) {
            throw "Unreal did not confirm graphics scalability $($preset.ScalabilityLevel) for every group. See graphics-verification.json and Unreal.log in $run."
        }
        Write-Host "Verified all $($scalabilityGroups.Count) Unreal graphics groups at level $($preset.ScalabilityLevel)."
        Write-Host 'Unreal streamer registered. Video, audio, and XR still require browser verification.'
    }
    $maxKbps = [int]($preset.Bitrate / 1000)
    $minKbps = [int]($preset.MinBitrate / 1000)
    $playerUrl = "$baseUrl/?UseMic=false&MatchViewportRes=false&WebRTCMinBitrate=$minKbps&WebRTCMaxBitrate=$maxKbps&HoveringMouse=true&AutoEnterVR=false"
    if ($Hmd) { Write-Host '-Hmd now uses the same desktop-first session. Click Open in VR in the player.' }
    if (-not $NoBrowser) {
        $browser = @(
            (Join-Path ${env:ProgramFiles(x86)} 'Microsoft/Edge/Application/msedge.exe'),
            (Join-Path $env:ProgramFiles 'Google/Chrome/Application/chrome.exe'),
            (Join-Path $env:LOCALAPPDATA 'Google/Chrome/Application/chrome.exe')
        ) | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
        if (-not $browser) { throw 'Install Chrome/Edge manually, or use -NoBrowser and open the printed URL.' }
        # Browser may reuse a personal session. It is intentionally not owned/stopped.
        # The requested browser is the visible, interactive player UI.
        Start-Process -FilePath $browser -ArgumentList $playerUrl -WindowStyle Normal | Out-Null
    }
    Write-Host "Player: $playerUrl"
    Write-Host 'Keep this terminal open. Press Q or Ctrl+C to stop the server and application started here.'
    $watchPlayer = -not $ServerOnly -and -not $KeepAlive
    if ($watchPlayer) { Write-Host "Closing the player stops this session after $DisconnectGraceSeconds seconds. Refreshing within that time keeps it running." }
    $playerSeen = $false
    $playerMissingSince = $null
    $nextPlayerCheck = [DateTime]::MinValue
    $playerDeadline = [DateTime]::UtcNow.AddSeconds($TimeoutSeconds)
    $stopAt = if ($RunSeconds) { [DateTime]::UtcNow.AddSeconds($RunSeconds) } else { [DateTime]::MaxValue }
    while (-not $server.HasExited) {
        if ([DateTime]::UtcNow -ge $stopAt) { break }
        if (-not $ServerOnly -and $application.HasExited) { throw 'Unreal application exited; inspect Unreal.log.' }
        if ($watchPlayer -and [DateTime]::UtcNow -ge $nextPlayerCheck) {
            $nextPlayerCheck = [DateTime]::UtcNow.AddSeconds(1)
            try {
                $response = Invoke-WebRequest -Uri "$probeUrl/api/players" -UseBasicParsing -TimeoutSec 2
                # Windows PowerShell can emit a JSON array as one pipeline item,
                # including []. Enumerate it explicitly to count actual players.
                $playerCount = 0
                foreach ($player in (ConvertFrom-Json -InputObject $response.Content)) {
                    if ($null -ne $player) { $playerCount++ }
                }
                if ($playerCount -gt 0) {
                    $playerSeen = $true
                    $playerMissingSince = $null
                } elseif ($playerSeen) {
                    if ($null -eq $playerMissingSince) { $playerMissingSince = [DateTime]::UtcNow }
                    if (([DateTime]::UtcNow - $playerMissingSince).TotalSeconds -ge $DisconnectGraceSeconds) {
                        Write-Host 'Player closed or disconnected. Stopping this session.'
                        break
                    }
                } elseif ([DateTime]::UtcNow -ge $playerDeadline) {
                    Write-Host 'No browser player connected before the timeout. Stopping this session.'
                    break
                }
            } catch {
                # An API failure is not evidence that the browser has closed.
                # Reset the grace period rather than shutting down on stale data.
                $playerMissingSince = $null
                Write-Verbose "Could not check browser connection: $_"
            }
        }
        try {
            if (-not [Console]::IsInputRedirected -and [Console]::KeyAvailable -and [Console]::ReadKey($true).Key -eq 'Q') { break }
        } catch [InvalidOperationException] { Write-Verbose 'No interactive console; use Ctrl+C or -RunSeconds.' }
        Start-Sleep -Milliseconds 300
    }
    if ($server.HasExited) { throw 'Signalling server exited; inspect server.stderr.log.' }
} finally {
    # Kill only owned process objects and their descendants (packaged UE uses a bootstrap child).
    foreach ($process in $owned) {
        $process.Refresh()
        if (-not $process.HasExited) { & taskkill.exe /PID $process.Id /T /F 2>$null | Out-Null }
    }
    Write-Host 'Local Pixel Streaming stopped. Browser and pre-existing processes were left running.'
}
