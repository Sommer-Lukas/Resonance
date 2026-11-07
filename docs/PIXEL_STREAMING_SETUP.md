# Local Pixel Streaming 2 (UE 5.6.1)

The launcher runs Epic's **UE5.6** reference signalling/web server and TypeScript
player on the laptop. Unreal rendering, NVIDIA ACE inference, speech and facial
fusion remain in the existing application. No remote inference, backend changes,
new frontend, microphone integration, certificates, STUN/TURN, Docker or firewall
changes are included. Installation needs Internet access; subsequent launches use
the locally built files.

## Start on this machine

From this repository in Windows PowerShell:

```powershell
.\scripts\start-pixelstream.ps1
```

The maintained checkout is `C:\Users\Lukas\Documents\Resonance`. The launcher,
browser extension, tests, native plugin source and this guide are all normal
repository files. No external worktree is required. Dependencies/builds/logs are
generated under this repository's ignored `.pixelstream/` directory.

The ignored `scripts/pixelstream.local.json` selects this repository's project
using a relative path and the installed UE5.6.1 editor as a standalone game
(`UnrealEditor.exe <project> -game`). It does not start PIE inside the editor.
The local NVIDIA binaries/models and compiled plugin are installed on this
machine; fresh clones must provision/build them as described below. There is
currently no verified packaged build.

Expected URL: **http://localhost**. Port 80 falls back to 8080 if occupied;
`-HttpPort 8090` selects another port explicitly. Unreal connects to
`ws://127.0.0.1:8888`. Only one browser player is allowed per streamer.
The stream starts in normal desktop view. **Open in VR** at the top right is
optional: clicking it requests an immersive browser session, then enables Unreal
stereo/tracking only after the browser grants it. Exiting VR restores the desktop
portrait camera, field of view, resolution and streaming limits. No separate
HMD launch or application restart is needed. Without a detected PC-VR headset,
the button explains that VR is unavailable and desktop playback continues.

Click **Click to start** to satisfy browser audio autoplay requirements. Focus the
player and press **1–5** for the existing speech playlists if the startup clip
finished before connecting. Existing **X/Y** facial modes remain available.

The launcher supplies `-muteaudio` to suppress Unreal's local speaker playback
while retaining the browser audio stream. In UE5.6.1 this zeros the hardware
output after the main submix has notified Pixel Streaming's buffer listener.
It applies to standalone editor and **Development** packages. UE compiles out
this output-muting path in **Shipping** builds; use Development for this local
workflow. Do not substitute `-nosound`, which disables audio needed by the stream.

The player includes **Enable audio** and an **Audio output** selector. The
extension resumes Epic's existing speech element in the Open in VR click gesture,
again after XR initialization, and when returning from an interrupted XR session
or an audio-device change. It does not create a second audible player or modify
Windows mute/volume settings. Select the Quest/PC-VR headphones if the browser
lists them. If only Windows default appears, choose the headset in Windows Sound
output/app volume settings and ensure that endpoint and the browser are unmuted.
Device listing is subject to browser permissions; no microphone capture or
microphone permission is requested to obtain more device names. See
[browser output selection](https://developer.mozilla.org/en-US/docs/Web/API/HTMLMediaElement/setSinkId)
and [device enumeration](https://developer.mozilla.org/en-US/docs/Web/API/MediaDevices/enumerateDevices).

Playback success means the browser accepted `play()`, not that sound passed a
muted Windows endpoint or reached the headset speakers. For diagnostics,
`window.ResonanceAudioDiagnostics` reports browser playback/mute state, selected
sink and the last playback error. The startup speech plays once and may finish
before entering VR. Press 1 to start an existing longer playlist before entering
VR when checking audio; switching views deliberately does not replay or restart
the conversation automatically.

Keep the launcher terminal open. Closing the browser player now automatically
stops the session after **five seconds** without a connected player. This grace
period allows a page refresh; `-DisconnectGraceSeconds 10` changes it.
If no player connects within `TimeoutSeconds` (default 180), it also stops.
Use `-KeepAlive` to keep Unreal/server running after disconnecting. `-ServerOnly`
keeps running for manual editor testing. Unreal renders offscreen: the browser
is the visible player, while one background Unreal process provides its frames.
A pre-existing editor window is separate and remains under your control.

Press **Q** or **Ctrl+C** for immediate cleanup. It stops
only its server/application process objects and their children, including the
packaged UE bootstrap child. It leaves your pre-existing editor, browser sessions
and other applications running. Avoid forcibly terminating the launcher host or
closing its terminal through Task Manager; that can bypass PowerShell `finally`.
`-RunSeconds 30` provides a bounded diagnostic run after the streamer registers.

## Configure another checkout or packaged build

Copy `scripts/pixelstream.local.example.json` to `scripts/pixelstream.local.json`
and edit the paths. Relative paths resolve against the repository root. This file
is ignored; do not commit machine paths. With a packaged build:

```json
{
  "ExecutablePath": ".pixelstream/Build/Windows/ResonanceVR.exe",
  "HttpPort": 80,
  "Development": false
}
```

Alternatively supply parameters directly:

```powershell
.\scripts\start-pixelstream.ps1 -ExecutablePath 'D:\Builds\Windows\ResonanceVR.exe'
.\scripts\start-pixelstream.ps1 -Development -ProjectPath 'D:\Resonance\unreal\ResonanceVR\ResonanceVR.uproject' -EditorPath 'D:\Epic\UE_5.6\Engine\Binaries\Win64\UnrealEditor.exe'
```

The editor may also be discovered from the Epic UE5.6 Windows registry entry.
No executable is built automatically. Missing application paths fail before
installing dependencies. `-SetupOnly` installs/builds infrastructure without
launching Unreal; `-ServerOnly` runs only the server for manual Editor
**Standalone Game** testing with the already configured additional launch
parameter. `-NoBrowser` leaves browser opening to you.

Requirements: Git, Node.js and npm on PATH, Chrome or Edge, Unreal **5.6.1** and
the existing project/vendor plugins. Upstream `NODE_VERSION` is **22.14.0**;
Node **24.19.0 / npm 11.17.0** successfully built and ran this pinned revision.
The launcher accepts Node majors 22/24 and installs no system software. Use a
process-scoped execution policy only if your organization's policy permits it;
the script does not change the machine's policy.

Infrastructure is pinned to UE5.6 commit
`3082a5f2faa2a6d2e57606180d34f1539abc9925` from
[Epic's official repository](https://github.com/EpicGames/PixelStreamingInfrastructure/tree/UE5.6).
The first setup clones UE5.6 and selects that revision. An existing checkout at a
different revision fails without resetting it. npm uses the upstream lockfile,
installs just the common/signalling/reference TypeScript workspace set and skips
install lifecycle scripts. `build:all:cjs` compiles those components without
requiring protobuf generation or a new framework. Dependencies, logs and builds
stay under ignored `.pixelstream/`; a revision stamp avoids rebuilding each run.
The identical official `player.html` is copied to generated `www/index.html` so
the site root works even under hidden parent directories, which Express
`sendFile` otherwise rejects as dot directories.

## Package Windows

Use this fully provisioned working checkout. The launcher resolves paths from
its repository root and does not synchronize other checkouts. Do not overwrite
other local modifications.

1. Open the project in UE **5.6.1**. Ensure **Pixel Streaming 2** and the new
   **ResonanceWebXR** source plugin are enabled and built. The latter is installed
   and compiled in this repository on this machine. Fresh clones
   must build it with the supported Windows C++ toolchain. Legacy
   **Pixel Streaming** must be disabled. For WebXR, OpenXR plus its eye/hand
   extensions must be disabled. Existing manual plugin selections in the
   `.uproject` have been preserved; do not repeat the completed editor steps unnecessarily.
2. Verify the existing NVIDIA ACE/James packages, local model weights and the
   ResonanceFace native plugin are installed and working. See
   [Audio2Face](../unreal/AUDIO2FACE.md) and
   [emotion transport/build](../unreal/EMOTION_IDLE.md). This repository excludes
   vendor binaries/models. Existing editor DLLs alone do not supply packaged game
   DLLs; packaging needs the UE5.6 Windows C++ toolchain and vendor runtime support.
3. In **Project Settings → Packaging**, choose **Development**, Windows/Win64,
   and add `/Game/Resonance/Levels/I_Resonance` to maps to package. Include any
   other maps you still use. Preserve existing startup maps and rendering settings.
4. Ensure **Additional Non-Asset Directories to Copy** includes `Resonance/Audio`
   (relative to Content). This is included in this branch's `DefaultGame.ini` as
   `DirectoriesToAlwaysStageAsNonUFS`. Existing playlist/ACE code opens physical
   WAV paths, including MixedEmotionSets, so cooked SoundWaves or files only
   inside a PAK are insufficient.
5. Use **Platforms → Windows → Package Project**, selecting
   `<repository>\.pixelstream\Build` as output. If prerequisites are missing,
   install the supported Visual Studio Windows game-development components/SDK
   manually; the launcher does not install them.
6. Confirm the resulting `Windows\ResonanceVR.exe`, runtime plugin DLLs and
   `Windows\ResonanceVR\Content\Resonance\Audio\voice_test.wav` exist. Verify all
   15 playlist WAVs under MixedEmotionSets. Check the NVIDIA plugin's staging
   instructions for James model files and model configuration; do not assume
   editor-only absolute model paths work after packaging. Run the package once
   and confirm local James initialization before claiming packaging success.
7. Set `ExecutablePath` to that executable and `Development` to `false` in the
   local JSON, then use the same one-command launcher.

Packaging is **not verified** in this task. The launcher explicitly supplies
Pixel Streaming and audio arguments to the packaged executable; Editor Preferences
do not propagate to it.

## Experimental WebXR with Quest PC VR

First confirm a working desktop stream and audible speech. Connect Quest 3 using
your existing PC-VR solution (for Meta Quest Link: start Meta's PC application,
connect USB Link or your existing Air Link connection and enter its PC-VR
environment). Keep that connection active while starting desktop Chrome/Edge.
No site is opened in the standalone Quest browser, and the server remains
unavailable over LAN.

The Windows OpenXR runtime is separate from Unreal's OpenXR plugin. The audit
found Meta's `oculus_openxr_64.json` selected in
`HKLM\SOFTWARE\Khronos\OpenXR\1\ActiveRuntime`; nothing changed it. For another
PC-VR solution, verify its documented browser/OpenXR support and active runtime.
Do not switch runtimes blindly or disable Windows OpenXR.

In Chrome/Edge DevTools at **http://localhost**, run:

```javascript
({secure: window.isSecureContext, xr: !!navigator.xr})
await navigator.xr?.isSessionSupported('immersive-vr')
```

Both first values and session support must be true before a VR request can
succeed. The added Open in VR control remains visible to explain unavailable
headsets and recheck support. A desktop mirror is insufficient. Localhost is a
[potentially trustworthy secure origin](https://developer.mozilla.org/en-US/docs/Web/Security/Defenses/Secure_Contexts),
so certificates are unnecessary here. Epic's
[UE5.6 experimental VR guide](https://dev.epicgames.com/documentation/en-us/unreal-engine/experimental-pixel-streaming-features?application_version=5.6)
uses a different headset-browser/network workflow; its HTTPS/STUN steps do not
apply to this same-machine localhost setup.

Start the same launcher for desktop and optional VR:

```powershell
.\scripts\start-pixelstream.ps1
```

Click to start the stream, then click **Open in VR**. Approve the browser's
immersive session permission. The button calls
`requestSession('immersive-vr')`, uses a `local` reference space and sends headset
position, orientation and eye projection data through Epic's existing data channel.
The small `scripts/pixelstream-webxr.js` extension uses Epic's existing WebXR
controller for headset rendering/input, adds session/error controls and waits
for native acknowledgments. It replaces the reference player's icon with the
labelled button, while retaining the reference frontend. `AutoEnterVR=false`
ensures that session initiation comes from your click. A denied request never
enables Unreal stereo. Browser/device errors leave normal playback available.

By default, the launcher supplies `-PixelStreamingEnableHMD` from Epic's guide and the explicit
UE5.6.1 setting argument `-PixelStreamingHMDEnable=true`. Installed engine source
maps `PixelStreaming2.HMD.Enable` to this latter spelling; the explicit flag
avoids relying on a legacy alias. This loads the driver at startup; the
`-ResonanceWebXR` bridge immediately disables tracking/stereo before the viewer
starts. It enables them only for an accepted browser session, using Epic's
existing Command/Response data-channel messages. Only `desktop`, `vr` and
`status` are accepted; unrestricted console commands remain disabled.
`-DesktopOnly` retains the earlier desktop-only fallback, without the bridge
or added button. `-Hmd` is a compatibility alias for the new desktop-first flow.
The startup window is 720p. VR selects its height from the quality preset below
and its width from the headset field of view; exiting restores 1280×720.
`-AudioMixer`, `-RenderOffscreen`, `-ForceRes` and H.264 are common. Desktop uses
1280×720 and a 30 FPS cap. VR uses the selected preset; targets are not measured
headset performance. UE5.6.1 changes several encoder settings on first XR data;
the bridge saves/restores the affected settings and reapplies its VR cap.
No global rendering defaults are changed.

### Resource presets for the 8 GB laptop

**Low is now the default**, including the usual one-command start. Stop an old
launcher before restarting; an already running session retains its old settings.

Low now selects **actual Unreal Low scalability (all eleven `sg.*Quality`
groups = 0)** from startup, for both desktop and VR. The earlier preset only
limited streaming/VR budgets and could inherit Epic graphics from saved settings;
that behavior was corrected on 7 November. Balanced selects Medium (1), and
Original selects Epic (3). Resolution scaling remains the explicit percentage
below rather than using a quality index as a percentage.

Each launch writes its own `GameUserSettings.ini` under the run's logs and passes
`-GameUserSettingsINI=<that file>`. This leaves normal Unreal user settings and
project defaults untouched. Startup queries the running engine and verifies every
quality group, saving `graphics-verification.json`; a mismatch stops the session
instead of silently running Epic under a Low label. Early engine default `@3`
initialization lines can still appear in the log; the later applied `@0` sections
and final queried values are the effective settings. The first Low run can need
additional shader compilation. Hair/material appearance will be less detailed.

```powershell
.\scripts\start-pixelstream.ps1 -Quality Low
# Keep Low graphics but increase image sharpness independently:
.\scripts\start-pixelstream.ps1 -Quality Low -VRClarity Clear
```

Graphics complexity and VR image sampling are now separate. **Low + Clear** is
the default; increasing image clarity does not enable Epic lighting or effects.

| Graphics preset | Unreal scalability | Unreal + stream FPS target | Desktop render scale | Preferred browser XR refresh |
|---|---|---|---|---|
| Low | Low, all groups 0 | 30 | 70% | 72 Hz |
| Balanced | Medium, all groups 1 | 45 | 85% | 72 Hz |
| Original | Epic, all groups 3 | 60 | 100% | 90 Hz |

| VRClarity | Stereo video height / total width cap | VR internal render scale | Browser XR framebuffer scale | Local bitrate range |
|---|---|---|---|---|
| Economy | 480 / 1920 | 70% | 0.5 | 1–6 Mbit/s |
| Clear (default) | 1080 / 4096 | 100% | 1.0 | 12–24 Mbit/s |
| Sharp | 1440 / 4096 | 100% | 1.0 | 16–32 Mbit/s |

The earlier Low preset produced approximately 944–960×480 packed stereo in
tests/recorded headset runs: only about 472–480×480 video pixels per eye, with
additional 70% internal resolution scaling. That is insufficient for a clear
headset image, regardless of whether the GPU is saturated. Clear removes that
internal VR downscale, raises the source resolution and reduces compression.
These bitrate ranges are for the same-computer connection, not a LAN deployment.
Frame rate and Low's graphics/texture limits remain unchanged.

Clear was increased from 900p to 1080p after headset feedback: approximately
44% more source pixels at the same aspect ratio, full recommended browser XR
framebuffer scale (previously 0.85), and a higher local bitrate range. It keeps
Low's 30 FPS target and all eleven engine graphics groups at 0. This adds some
rendering/memory cost; Sharp is a further, more expensive 1440p option rather
than enabling Epic graphics. The runtime may clamp its recommended framebuffer.

```powershell
# Recommended first test after stopping the old session:
.\scripts\start-pixelstream.ps1 -Quality Low -VRClarity Clear
# Higher image detail, at additional rendering/memory cost:
.\scripts\start-pixelstream.ps1 -Quality Low -VRClarity Sharp
# Explicit resource fallback; visibly soft in a headset:
.\scripts\start-pixelstream.ps1 -Quality Low -VRClarity Economy
```

Do not increase graphics to Epic just to address uniform pixelation. Use VRClarity
for source-image detail. A higher pixel count does cost more GPU work, so clarity
and performance still need a headset test; the defaults do not promise readable
facial detail or a particular motion-to-photon latency.

The browser's headset framebuffer is separate from the incoming video resolution.
The earlier reference initializer requested an unscaled, antialiased framebuffer
and 90 Hz. The extension now initializes Epic's same shaders/draw/tracking loop
with an explicitly scaled XRWebGLLayer, no multisampling, depth or stencil buffer,
and the selected refresh preference. Clear requests a 1.0 scale; Economy's
0.5 framebuffer scale requests half the
width and height (one quarter of the pixels); the browser/runtime may clamp it.
See the [WebXR framebuffer scaling explanation](https://github.com/immersive-web/webxr/blob/main/explainer.md).
Only a rate in the browser's supported list is requested. If 72 Hz is unsupported,
the lowest available supported rate is used; some PC-VR runtimes keep their own
configured refresh rate or do not expose refresh control at all.

Low additionally reduces local-light virtual shadow detail. Unreal's Low texture
group uses a 400 MB pool and adaptive per-texture mip bias in this UE5.6 build;
the VR bridge does not raise those limits/detail when entering VR. Its 768 MB
VR pool cap is an upper bound, respecting any smaller base scalability budget.
Balanced uses a maximum 1024 MB VR budget, also respecting smaller base settings.
A project with fixed-size streaming pools is not overridden.
Original selects Epic graphics without the extra VR texture-budget restriction;
VRClarity controls image sizing independently. Browser multisampling remains
disabled. VR settings are restored
on exit to the selected desktop tier, including texture budget/detail, render
scale, shadows and camera state. Low stays Low after leaving VR. Closing the
launcher ends these process-specific settings; normal Unreal operation is unchanged.
These limits do not reduce ACE model weights, non-streamable assets or the
Windows/PC-VR runtime's memory use. Lower detail and 30 FPS are deliberate tradeoffs
to test headroom; they do not establish acceptable VR responsiveness.

The bridge also avoids setting unchanged CVars every tick and quantizes/throttles
resize requests, rather than repeatedly reallocating targets while a resize is
pending. Presets and launch arguments are saved with each run's logs. Inspect
`window.ResonanceXRDiagnostics` in DevTools during VR to see the actual framebuffer,
video pixels per eye and requested refresh rate, rather than assuming the requested scale
was honored.

Close the separate Unreal Editor before starting the launcher; the launcher now
warns if another editor process is present. It does not terminate it for you.
Use your PC-VR application's lower render-resolution/refresh options as well;
those are independent of Unreal and browser settings and are not modified here.
The PC-connected Quest workflow still includes browser encode/decode/composition
in addition to the existing PC-VR transport. Native Unreal PC VR avoids that
browser stage and can remain the better option if this machine cannot sustain
the combined load. No headset performance improvement is claimed until measured
on the actual connected headset.

The native bridge is isolated in `Plugins/ResonanceWebXR` and is inactive without
its launch flag. It preserves the camera/parent transforms, control rotation and
FOV when entering VR, restoring them on exit. It does not replace the pawn,
GameMode, face fusion or audio implementation. The browser sends a desktop reset
on reconnect/page refresh. Closing the browser still ends the launcher session.

The existing portrait GameMode uses `BP_ResonanceViewer`, standard
`Engine.PlayerController`, a TrackingOrigin scene component and an HMD-locked
camera. The optional bridge disables HMD before BeginPlay so this existing
Blueprint follows its ordinary desktop startup path. In native VR, its builder
removes the initial tracking position/yaw once as before.
No pawn, map, motion controllers, locomotion or camera assets were replaced.
Initial calibration, stereo, actual movement and projection compatibility need
physical headset verification; identity pose before the first browser XR frame
may affect initial alignment. Face-camera actors remain framing references.

Do not change Meta XR settings as a speculative fix. The running working checkout
already has `OculusXR` disabled by the user; the MetaXR plugin files
and settings were left untouched. Native VR remains recoverable: stop the stream,
use a separate native configuration/checkout, disable PixelStreaming2 HMD,
re-enable Unreal OpenXR and the previously required native plugins, restart and
use VR Preview. Leave the Windows runtime intact. No assets were deleted using
the template-specific steps in Epic's example.

## Local networking and shutdown

Epic's pinned CLI has no host/bind option. `pixelstream-loopback.cjs` is a Node
preload applied only to this server process. It forces TCP listeners to
`127.0.0.1`; it changes neither Epic's protocol nor frontend. `netstat` confirmed
ports 80, 8888 and 8889 listening only on loopback. The stock server also creates
an unused SFU signalling listener on 8889; no SFU process is started. Ports are
checked before startup and can be overridden independently.

No Windows firewall or router changes are needed. Do not use upstream
`start_with_stun`/TURN scripts. Browser WebRTC media uses direct local ICE
candidates with no configured external ICE servers. The preload restricts server
TCP listeners, not Unreal's UDP media sockets or the system network stack; this
is not a network-isolation sandbox or authentication mechanism. Do not grant new
inbound firewall exceptions. Normal Windows policy remains unchanged.

Logs and the exact Unreal argument array are saved in
`.pixelstream/logs/<timestamp>/`. The launcher waits for HTTP readiness and an
API streamer with `streaming=true`; this verifies registration, not that a browser
has decoded frames or played speech. A failed launch/timeout stops owned
processes in `finally`; occupied ports never cause an unrelated process to stop.

## Verification performed on 6 November 2026

Repository relocation verified on **7 November 2026**: scripts, tests, native
source and documentation now live in Documents/Resonance. A fresh pinned
infrastructure checkout was installed and built under its own `.pixelstream/`.
The main-repository launcher served HTTP, registered Unreal and completed a
three-second diagnostic run with cleanup. Eight Node tests, thirteen Python
tests and the deterministic demo passed from this repository. No browser or
physical headset acceptance was repeated during this relocation. Machine
configuration and generated dependencies/binaries remain ignored; source files
and collaboration guides are included in Git.

| Check | Result and evidence |
|---|---|
| Initial working tree | Clean with LFS filters bypassed for read-only status; ordinary Git status hit a sandbox Git LFS subprocess error. |
| Original audit | UE5.6.1-44394996; the editor used Documents/Resonance while the original launcher was developed separately. Manual PixelStreaming2 and AdditionalLaunchParameters were verified there. Startup map I_Resonance, portrait GameMode/viewer/controller inspected live. The complete maintained implementation now resides in Documents/Resonance. |
| Infrastructure | UE5.6 pinned SHA cloned, 1,038 npm packages installed, six component builds passed. Reference root and player returned HTTP 200 after index-copy fix. |
| Loopback | Actual netstat listeners at 127.0.0.1:80/8888/8889; three Node listener tests passed. |
| Desktop Unreal | Standalone `-game` connected as DefaultStreamer, `streaming=true`. MetaHuman portrait visible in Chrome screenshot. |
| Repeat startup/shutdown | Second desktop launch using saved local configuration registered and opened the browser. Timed shutdown exited successfully, released ports and preserved the original editor (PID 9820). Ctrl+C also released the first run's listeners. |
| Browser disconnect shutdown | Local WebSocket player test: reconnect within the grace period preserved the session; final disconnect automatically stopped the launcher-owned Unreal/server and released ports. Tested with a two-second grace; default is five seconds. |
| Failure handling | Occupied 80 triggered the 8080 fallback; occupied 8888 safely aborted without killing that service. Missing packaged executable and duplicate ports produced explicit errors. |
| HMD startup smoke test | `-Hmd -NoBrowser -RunSeconds 15` launched and registered the streamer, then cleaned up successfully. This did not test browser stereo or a headset session. |
| Desktop/VR switch implementation | ResonanceWebXR compiled with UE5.6.1/MSVC 14.38 and was installed in the working Documents checkout. Browser showed a normal single-camera portrait and Open in VR button. Native acknowledgment confirmed desktop mode. |
| Simulated native transitions | Two Command/Response cycles entered native stereo (1440×720 before device projection data) and restored desktop (1280×720), without restarting Unreal. These deliberately injected mode commands test the bridge, not an actual WebXR/headset session. |
| Browser session lifecycle | Four Node tests passed: desktop-first/accepted session/exit; denied permission; missing headset; unsupported reference space. Together with listener tests, 7 Node tests passed. Browser audio remained nonzero after switching (peak RMS 0.1181). |
| Low preset follow-up | Updated plugin compiled; 8 Node tests and 13 Python tests passed. Two simulated VR transitions produced 960×480 (before device projection data) at a configured 30 FPS/70% render scale, restoring 1280×720 on exit. Browser speech remained nonzero (peak RMS 0.1197). Node tests verified half-scale XR framebuffer/no MSAA and supported refresh selection. Actual headset framebuffer allocation/performance has not been measured. |
| Actual Low scalability correction, 7 November | The earlier Low launch still applied Epic `@3` scalability sections. Corrected launcher now loads a per-run GameUserSettings.ini: all 11 queried graphics groups reported 0, material quality 0, render scale 70, texture pool 400 MB. Portrait rendering, a simulated 960×480 VR → 1280×720 desktop transition and nonzero browser speech (RMS peak 0.1274) were checked. The normal WindowsEditor/GameUserSettings.ini hash was unchanged. 8 Node tests, 13 Python tests and the demo passed. No physical-headset performance claim is made. |
| VR clarity correction, 7 November | Low graphics and image sampling are independent. Clear default produced 1792×900 decoded stereo in the browser at 30 FPS with zero dropped frames in a short simulated native-stereo sample, then restored 1280×720 desktop. All eleven graphics groups stayed Low; the native VR target was 100% render scale. Browser tests validated 0.85 framebuffer scale and explicit Economy fallback; 9 Node tests and 13 Python tests passed. No headset clarity or performance acceptance was performed. |
| VR audio recovery, 7 November | Browser recovery/output controls added; 12 Node tests and 13 Python tests passed. With native stereo enabled, an existing playlist produced decoded audio RMS peak 0.1118. Enable audio recovered the same deliberately paused/muted element (playing, unmuted, volume 1, no playback error). Browser exposed only default output; actual Quest audibility/Windows mute routing NOT VERIFIED. The prior operator run's startup clip ended at 14:10:48 UTC before VR entry at 14:11:34 UTC; a later playlist did run during VR, so clip completion alone does not diagnose the reported silence. |
| Clear 1080p follow-up, 7 November | Updated Clear produced 2160×1080 decoded stereo at 30 FPS with zero dropped frames in the short simulated-stereo sample, then restored 1280×720 desktop. All eleven graphics groups remained 0. Full recommended framebuffer scale was verified in browser lifecycle tests; 12 Node tests and 13 Python tests passed. Physical headset sharpness and sustained performance remain unverified. |
| VR texture restoration | Final native test logs confirmed 1000 MB desktop → 768 MB VR → 1000 MB desktop, twice. This verifies the runtime budget switch, not a measured reduction in total process VRAM. A separate desktop sample before the texture-budget change used 7,265/8,151 MiB with no physical immersive session; no before/after headset performance claim is made. |
| Input and ACE | Browser key 1 started the existing three-mix playlist. LocalA2F-James returned 539 animation samples and 431,199 audio samples for the startup clip; later playlist inference continued. |
| Audio transport | Live enabled WebRTC audio track, OPUS, nonzero decoded signal (peak RMS 0.1274 over a 16-second probe). Later totalAudioEnergy 1.694 and 11,336,160 samples received. Physical speaker/headset listening and perceived A/V synchronization NOT VERIFIED. |
| Duplicate-audio fix | Retested with `-muteaudio`: Unreal logged that local audio output was muted; browser playlist replay retained a live audio receiver and peak RMS 0.1246. Local final-output muting is confirmed by the engine implementation/log; physical listening remains an operator check. |
| Video/stability | 1280×720 H.264; initial approximately 57-second player sample: 25 FPS, 1,449 decoded frames, 0 dropped, 0 lost packets. Later sample: 18 FPS, 5,358 decoded frames, 0 dropped, 0 lost packets. Short desktop session only; no long-duration guarantee. |
| Latency | Initial frontend estimate: encode 25 ms, post-capture-to-send 58 ms, total 97 ms; rounded network RTT 0 ms. These are frontend estimates, not measured motion-to-photon or audio synchronization. |
| GPU | nvidia-smi sample: RTX 5070 Laptop, 7,875/8,151 MiB and 99% GPU utilization while both editor and game ran. Visible UE video-memory warning. CPU and independent Unreal frame-time profiling not collected. |
| Browser XR | Chrome: secure context true; navigator.xr present; immersive-vr support false. Current PC-VR/headset readiness cannot be confirmed. |
| Python regression | 13 tests passed; deterministic demo completed. Pipeline implementation unchanged. |
| Physical regression | MetaHuman appearance, animation activity and audio transport observed. Exhaustive face-mode/curve regression, native VR and subjective lip-sync NOT VERIFIED. |

Acceptance Test 1 is **PARTIALLY VERIFIED** until an operator confirms audible
playback and the packaged workflow. Acceptance Test 2 is **NOT VERIFIED**:
no immersive session, stereo-in-headset, tracked viewpoint or headset audio was
verified. Acceptance Test 3 has passing Python regression and observed desktop
behavior, with physical/native VR checks outstanding. Do not label 2D streaming
as a successful WebXR test.

The results above describe the original 6 November integration runs; their logs
and screenshots were local artifacts in the earlier development checkout, not
portable repository files. They are not prerequisites for startup and were not
copied as source. New runs write fresh evidence to this repository's ignored
`.pixelstream/logs/`. Package tests must be repeated against the actual package,
rather than inferred from standalone editor execution.

The repository audit also found runtime `ResonanceFace` and uncooked
`ResonanceFaceEditor` modules, the source `UnrealMCPython` editor plugin, MetaXR,
and separately installed NVIDIA packages. Existing scripts include
`unreal/Build-EmotionFace.ps1`, `unreal/Encode-Trailer.ps1` and editor Python scene
builders; no existing local Pixel Streaming launcher or packaged executable was
found. Global default GameMode remains the VR template fallback, with the
portrait level overriding it. Other maps include the preserved VRTemplate,
PitFallUebung and two trailer scenes. No changes to those maps or game modes were
needed. Development logs contain Live Coding vendor-DLL warnings and an ACE
worker flush timeout warning; subsequent local inference completed. These were
not treated as proof of a clean packaged runtime.

## Troubleshooting and performance

- **No streamer:** inspect `server.stderr.log` and `Unreal.log`. Verify exact UE
  version, plugins, URL/port, local vendor packages and application path. Do not
  run legacy Pixel Streaming alongside Pixel Streaming 2.
- **Occupied ports:** stop your earlier launcher with Q/Ctrl+C or choose other
  ports. The script refuses to reuse/kill an existing service. It checks 8889
  because the upstream CLI opens that listener too.
- **No audio:** click the player to satisfy autoplay, check browser/Windows output
  routing and mute state, then press 1–5 to replay. Startup speech plays once.
  Check ACE completion logs. A live silent track alone is not evidence of speech.
- **Speech heard twice:** stop the old launcher with Q/Ctrl+C and restart using
  the updated launcher, which includes `-muteaudio`. Confirm that argument in the
  new run's launch-arguments.json and the audio-output-muted message in Unreal.log.
  An independently running editor/PIE session can still play its own speech;
  stop its playback separately. This launcher does not mute unrelated processes.
- **Missing packaged speech:** confirm loose WAVs and vendor model staging,
  including James initialization. Missing models are a packaging prerequisite,
  not a reason to replace the facial pipeline.
- **VR unavailable:** run the three browser probes above. False secure context
  points to the origin/embedding. Missing navigator.xr points to browser/platform
  policy. `immersive-vr=false` with navigator.xr present points to browser/runtime/
  device availability before Unreal is involved. Verify the PC-VR environment is
  active, runtime selected and the connection solution supports desktop browser
  XR. Restart the browser after establishing PC VR. Chrome and Edge may differ;
  test another installed supported browser without changing security flags.
- **XR session starts but no stereo/tracking:** a separate `-Hmd` launch is no
  longer required. The saved launch arguments should include
  `-ResonanceWebXR` and `-PixelStreamingHMDEnable=true`. Check that the
  ResonanceWebXR plugin is enabled/compiled, and inspect its `Mode=vr` native
  acknowledgment plus PixelStreaming2HMD/headset transform messages.
  Inspect the existing viewer's camera lock and tracking origin; recenter/restart
  while facing the portrait. Do not replace the pawn with a VR template.
- **Pointer lock rejected during automation:** the reference player supports its
  Hovering Mouse control scheme in settings. A pointer-lock warning does not
  itself mean video or keyboard input failed.
- **Low FPS/VRAM pressure:** close the pre-existing editor manually before a
  standalone/package performance run. The launcher deliberately leaves it open.
  Start with `-Quality Low` and use the existing LOD 2 portrait. Profile
  with player statistics, UE `stat fps`/`stat unit`, Task Manager and
  `nvidia-smi --query-gpu=memory.used,memory.total,utilization.gpu --format=csv`.
  Record FPS, dropped frames, audio quality and memory during inference. If
  needed, trial a smaller streaming-only resolution/bitrate in the launch script
  and measure again; do not globally change project rendering quality. HMD mode
  requires its own GPU budget test before use.

Browser microphone capture is disabled with `UseMic=false`. Existing local
microphone/backend capture remains the responsibility of the existing workflow;
no browser audio is routed into VoiCE. A future browser microphone route would
need explicit capture permissions, PixelStreaming2 audio input handling and a
verified backend bridge, and is outside this implementation.

Modified tracked files: launcher, loopback preload/tests, the browser WebXR
extension and lifecycle tests, the isolated ResonanceWebXR runtime plugin,
local configuration example, this guide, `.gitignore`, project plugin descriptor,
WAV staging in DefaultGame.ini and the Unreal README link. The new plugin and its
descriptor entry, scripts, tests and this guide are maintained together in the
main repository; generated DLLs/manifests remain local. README.md, unreal/README.md
and AGENTS.md link to these instructions for other collaborators/agents.
No audio/animation implementation,
map, pawn, MetaHuman, MetaXR vendor file or VoiCE backend was changed.
