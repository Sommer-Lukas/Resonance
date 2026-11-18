param(
    [string]$Frames = "$PSScriptRoot/ResonanceVR/Saved/ResonanceTrailer/Frames4K",
    [string]$Output = "$PSScriptRoot/ResonanceVR/Saved/ResonanceTrailer/Resonance-Trailer-4K.mp4"
)
$ErrorActionPreference = 'Stop'
$trailerFiles = @(Get-ChildItem -LiteralPath $Frames -Filter 'Resonance.*.png' |
    Where-Object { $_.Name -match '^Resonance\.\d{4}\.png$' })
if ($trailerFiles.Count -ne 336) { throw "Expected 336 frames, found $($trailerFiles.Count)." }
for ($trailerIndex = 0; $trailerIndex -lt 336; $trailerIndex++) {
    if (-not (Test-Path -LiteralPath (Join-Path $Frames ('Resonance.{0:D4}.png' -f $trailerIndex)))) {
        throw "Missing frame $trailerIndex"
    }
}
$trailerVoice = "$PSScriptRoot/ResonanceVR/Content/Resonance/Audio/voice_test.wav"
# The source WAV is untouched. Pad it with exactly two seconds of leading
# silence and three seconds afterward, matching the baked Sequencer timing.
& ffmpeg -hide_banner -loglevel warning -n -framerate 24 -start_number 0 `
    -i "$Frames/Resonance.%04d.png" -i $trailerVoice `
    -vf 'fade=t=in:st=0:d=0.5,fade=t=out:st=12.5:d=1.5' `
    -af 'adelay=2000:all=1,apad' -t 14 `
    -c:v libx264 -preset slow -crf 16 -pix_fmt yuv420p `
    -c:a aac -b:a 256k -movflags +faststart $Output
if ($LASTEXITCODE -ne 0) { throw "FFmpeg failed with exit code $LASTEXITCODE" }
Write-Output $Output
