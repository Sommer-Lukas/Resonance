/* Small extension of Epic's UE5.6 reference player; no replacement frontend. */
(() => {
    'use strict';
    function install(stream) {
        const panel = document.createElement('div');
        panel.id = 'resonance-vr';
        panel.style.cssText = 'position:fixed;right:18px;top:18px;z-index:10000;max-width:300px;color:white;font:14px sans-serif;text-align:right';
        const button = document.createElement('button');
        button.id = 'resonance-open-vr';
        button.textContent = 'Open in VR';
        button.style.cssText = 'padding:12px 18px;border:1px solid #888;border-radius:8px;background:#20242b;color:white;font:inherit;cursor:pointer';
        const status = document.createElement('p');
        status.id = 'resonance-vr-status';
        status.setAttribute('role', 'status');
        status.style.cssText = 'background:#17191dcc;padding:8px;border-radius:6px;line-height:1.4';
        const style = document.createElement('style');
        style.textContent = '#xrBtn { display: none !important; }';
        document.head.appendChild(style);
        panel.append(button, status);
        document.body.appendChild(panel);

        // Use Epic's existing audio element (which is usually detached from the
        // DOM). Creating a second player would bring back the duplicate audio.
        const audioButton = document.createElement('button');
        audioButton.id = 'resonance-enable-audio';
        audioButton.textContent = 'Enable audio';
        const output = document.createElement('select');
        output.id = 'resonance-audio-output';
        output.setAttribute('aria-label', 'Audio output');
        output.style.cssText = 'max-width:190px;margin:8px 0 0 8px;padding:6px';
        const audioStatus = document.createElement('p');
        audioStatus.id = 'resonance-audio-status';
        audioStatus.setAttribute('role', 'status');
        audioStatus.style.cssText = 'font-size:12px;background:#17191dcc;padding:6px';
        panel.append(audioButton, output, audioStatus);
        let selectedSink = 'default';
        let explicitSink = false;
        let audioError = null;
        function audioElement() {
            const separate = stream._webRtcController?.streamController?.audioElement;
            if (separate?.srcObject) return separate;
            const video = document.querySelector('video');
            return video?.srcObject?.getAudioTracks().length ? video : null;
        }
        async function refreshOutputs() {
            const current = audioElement();
            const initial = document.createElement('option');
            initial.value = 'default'; initial.textContent = 'Windows default output';
            output.textContent = ''; output.appendChild(initial);
            output.disabled = !current?.setSinkId;
            try {
                const devices = await navigator.mediaDevices?.enumerateDevices() || [];
                for (const device of devices) {
                    if (device.kind !== 'audiooutput' || !device.label || device.deviceId === 'default') continue;
                    const option = document.createElement('option');
                    option.value = device.deviceId; option.textContent = device.label;
                    output.appendChild(option);
                }
                output.value = explicitSink ? selectedSink : (current?.sinkId || 'default');
            } catch (error) { console.warn('Could not enumerate audio outputs:', error); }
        }
        async function recoverAudio(userGesture = false) {
            const current = audioElement();
            if (!current) {
                if (userGesture) audioStatus.textContent = 'Start playback first; no speech track is connected yet.';
                return false;
            }
            if (userGesture) {
                current.muted = false;
                if (current.volume === 0) current.volume = 1;
            }
            try {
                // Call play immediately, before awaiting anything, so Open in VR
                // unlocks media playback under the same browser user gesture.
                const playing = current.play();
                const routing = explicitSink && current.setSinkId && current.sinkId !== selectedSink
                    ? current.setSinkId(selectedSink) : Promise.resolve();
                await Promise.all([playing, routing]);
                audioError = null;
                audioStatus.textContent = current.muted || current.volume === 0
                    ? 'Browser audio is muted. Click Enable audio to unmute it.'
                    : 'Browser audio playing. If silent, check the headset/Windows output and volume.';
                return true;
            } catch (error) {
                audioError = String(error.message || error);
                audioStatus.textContent = 'Audio could not start. Click Enable audio and choose the headset output before entering VR.';
                return false;
            }
        }
        audioButton.addEventListener('click', () => { void recoverAudio(true); void refreshOutputs(); });
        output.addEventListener('change', () => {
            selectedSink = output.value; explicitSink = true;
            void recoverAudio(true);
        });
        const onDeviceChange = () => { void refreshOutputs(); void recoverAudio(false); };
        navigator.mediaDevices?.addEventListener('devicechange', onDeviceChange);
        document.addEventListener('visibilitychange', () => {
            if (document.visibilityState === 'visible') void recoverAudio(false);
        });
        stream.addEventListener('playStream', () => { void refreshOutputs(); });
        window.ResonanceAudioDiagnostics = {
            get paused() { return audioElement()?.paused ?? null; },
            get muted() { return audioElement()?.muted ?? null; },
            get volume() { return audioElement()?.volume ?? null; },
            get sinkId() { return audioElement()?.sinkId ?? null; },
            get lastError() { return audioError; }
        };
        audioStatus.textContent = 'Audio uses the browser output. Select the headset if it is listed.';
        void refreshOutputs();

        let supported = false;
        let bridgeReady = false;
        let session = null;
        let requesting = false;
        let waitingForMode = null;
        let modeTimer = null;
        let desktopSent = false;
        let disposed = false;
        const preset = window.ResonanceStreamingPreset || {name:'Low graphics / Clear image',framebufferScale:1.0,refreshRate:72};

        async function startBrowserSession(controller, current, referenceSpace) {
            // Adapt only the initialization of the pinned UE5.6 controller. Its
            // existing shaders, stereo draw loop and tracking protocol stay in use.
            // The reference initializer allocates a full-size, antialiased XR layer
            // and requests 90 Hz even when the incoming stream has much fewer frames.
            controller.xrSession = current;
            current.addEventListener('end', () => controller.onXrSessionEnded(), {once:true});
            if (!controller.gl) {
                controller.gl = document.createElement('canvas').getContext('webgl2', {
                    xrCompatible:true, antialias:false, alpha:false, depth:false, stencil:false
                });
                if (!controller.gl) throw new Error('WebGL2 is unavailable.');
                controller.gl.clearColor(0,0,0,1);
            }
            controller.initShaders();
            controller.initBuffers();
            controller.xrRefSpace = referenceSpace;
            // A fresh immersive session must send its eye projection/IPD again.
            controller.lastSentLeftEyeProj = null;
            controller.lastSentRightEyeProj = null;
            controller.lastSentRelativeLeftEyePos = null;
            controller.lastSentRelativeRightEyePos = null;
            const scale = Math.min(1,Math.max(0.25,Number(preset.framebufferScale) || 1.0));
            const layer = new XRWebGLLayer(current, controller.gl, {
                framebufferScaleFactor:scale, antialias:false, alpha:false,
                depth:false, stencil:false, ignoreDepthValues:true
            });
            current.updateRenderState({baseLayer:layer});
            const rates = Array.from(current.supportedFrameRates || []).filter(rate => Number.isFinite(rate) && rate >= 60).sort((a,b)=>a-b);
            const preferred = Number(preset.refreshRate) || 72;
            const rate = rates.filter(value => value <= preferred).pop() || rates[0];
            if (rate && current.updateTargetFrameRate) {
                try { await current.updateTargetFrameRate(rate); }
                catch (error) { console.warn('Headset kept its runtime refresh rate:',error); }
            }
            window.ResonanceXRDiagnostics = {
                preset:preset.name, requestedScale:scale, requestedRefreshRate:rate || null,
                framebufferWidth:layer.framebufferWidth, framebufferHeight:layer.framebufferHeight,
                antialias:layer.antialias,
                get streamPixelsPerEye() {
                    const video = document.querySelector('video');
                    return video ? {width:Math.floor(video.videoWidth / 2),height:video.videoHeight} : null;
                }
            };
            current.requestAnimationFrame(controller.onXrFrame.bind(controller));
            controller.onSessionStarted.dispatchEvent(new Event('xrSessionStarted'));
        }

        function message(text) { status.textContent = text; }
        function send(mode) { return stream.emitCommand({ ResonanceWebXR: mode }); }
        function clearModeTimer() {
            if (modeTimer !== null) clearTimeout(modeTimer);
            modeTimer = null;
        }
        function requestMode(mode) {
            clearModeTimer();
            waitingForMode = mode;
            send(mode);
            modeTimer = setTimeout(async () => {
                waitingForMode = null;
                message('Unreal did not confirm the view change. Restart the launcher and try again.');
                if (session) await session.end().catch(() => {});
            }, 5000);
        }
        async function checkSupport() {
            try {
                supported = !!(window.isSecureContext && navigator.xr
                    && await navigator.xr.isSessionSupported('immersive-vr'));
                if (!session && !requesting) {
                    message(supported
                        ? (bridgeReady ? 'Desktop view. Click Open in VR to use your headset.' : 'Start playback to enable VR.')
                        : 'Desktop view. No immersive headset detected. Connect PC VR, then click Open in VR to check again.');
                }
            } catch {
                supported = false;
                message('Desktop view. The browser could not check headset support.');
            }
        }

        stream.addResponseEventListener('ResonanceWebXR', response => {
            if (!response.startsWith('ResonanceWebXR:')) return;
            const mode = response.slice('ResonanceWebXR:'.length);
            if (mode === 'error') {
                clearModeTimer();
                waitingForMode = null;
                message('Unreal could not enable VR. Desktop view will be restored.');
                if (session) void session.end();
                return;
            }
            bridgeReady = true;
            if (waitingForMode === mode) {
                clearModeTimer();
                waitingForMode = null;
            }
            if (mode === 'vr' && session) message('VR session active. Exit VR to return to desktop view.');
            if (mode === 'desktop' && !session) {
                button.textContent = 'Open in VR';
                message(supported ? 'Desktop view. Click Open in VR to use your headset.'
                    : 'Desktop view. No immersive headset detected. Connect PC VR, then click Open in VR to check again.');
            }
        });

        stream.webXrController.onSessionEnded.addEventListener('xrSessionEnded', () => {
            session = null;
            requesting = false;
            button.disabled = false;
            button.textContent = 'Open in VR';
            message('Returning to desktop view…');
            requestMode('desktop');
            void recoverAudio(false);
        });

        button.addEventListener('click', () => {
            if (session) { void session.end(); return; }
            if (requesting) return;
            if (!supported) { void checkSupport(); return; }
            if (!bridgeReady) { message('Click to start the stream first. VR becomes available after Unreal connects.'); return; }
            requesting = true;
            button.disabled = true;
            message('Waiting for headset permission…');
            void recoverAudio(true);
            // Call directly from this user gesture; never auto-enter on page load.
            navigator.xr.requestSession('immersive-vr', { optionalFeatures: [] }).then(async newSession => {
                session = newSession;
                let endedBeforeSetup = false;
                newSession.addEventListener('end', () => { endedBeforeSetup = true; }, { once: true });
                newSession.addEventListener('visibilitychange', () => {
                    if (newSession.visibilityState === 'visible') void recoverAudio(false);
                });
                try {
                    // Detect unsupported reference spaces before asking Unreal for stereo.
                    const referenceSpace = await newSession.requestReferenceSpace('local');
                    if (endedBeforeSetup) { session = null; message('VR session ended. Desktop view is unchanged.'); return; }
                    if (disposed) { await newSession.end(); return; }
                    await startBrowserSession(stream.webXrController, newSession, referenceSpace);
                    if (endedBeforeSetup) return;
                    void recoverAudio(false);
                    button.textContent = 'Exit VR';
                    message('Opening the Unreal view in VR…');
                    requestMode('vr');
                } catch (error) {
                    await newSession.end().catch(() => {});
                    session = null;
                    requestMode('desktop');
                    message(`Could not open VR: ${error.message || error}. Desktop view is available.`);
                }
            }).catch(error => {
                // Rejected permission/session creation must leave Unreal in mono.
                message(`VR was not opened: ${error.message || error}. Desktop view is unchanged.`);
            }).finally(() => {
                requesting = false;
                button.disabled = false;
            });
        });

        // On a fresh connection (including a refresh) restore desktop mode first.
        stream.addEventListener('webRtcDisconnected', () => {
            bridgeReady = false;
            desktopSent = false;
            if (session) void session.end().catch(() => {});
        });
        const handshake = setInterval(() => {
            if (bridgeReady) return;
            if (!desktopSent) desktopSent = send('desktop');
            else send('status');
        }, 500);
        if (navigator.xr) navigator.xr.addEventListener('devicechange', checkSupport);
        window.addEventListener('pagehide', () => {
            disposed = true;
            clearInterval(handshake);
            clearModeTimer();
            navigator.mediaDevices?.removeEventListener('devicechange', onDeviceChange);
            send('desktop');
            if (session) void session.end().catch(() => {});
        });
        void checkSupport();
    }

    // Epic's player creates window.pixelStreaming in its onload handler.
    const ready = setInterval(() => {
        if (window.pixelStreaming) {
            clearInterval(ready);
            install(window.pixelStreaming);
        }
    }, 25);
})();
