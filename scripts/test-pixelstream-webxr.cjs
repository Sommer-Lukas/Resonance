// Run with Node's built-in test runner; these simulate browser session lifecycle,
// not physical headset tracking or stereo presentation.
'use strict';
const {test} = require('node:test');
const assert = require('node:assert/strict');
const {readFileSync} = require('node:fs');
const {join} = require('node:path');
const vm = require('node:vm');
const delay = ms => new Promise(resolve => setTimeout(resolve,ms));
const source = readFileSync(join(__dirname,'pixelstream-webxr.js'),'utf8');

async function fixture({supported=true,reject=false,referenceFails=false,rates=[72,90],preset,audioReject=false}={}) {
    const elements=[];
    class Element extends EventTarget {
        style={}; textContent=''; disabled=false;
        constructor(){super();elements.push(this);}
        append(){} appendChild(){} setAttribute(){}
        getContext(type,options){
            assert.equal(type,'webgl2');
            assert.equal(options.antialias,false);
            return {clearColor(){}};
        }
    }
    const window = new EventTarget();
    window.isSecureContext=true;
    if(preset) window.ResonanceStreamingPreset=preset;
    const session = new EventTarget();
    session.requestReferenceSpace=async()=>{
        if(referenceFails) throw Error('No local reference space');
        return {};
    };
    session.end=async()=>session.dispatchEvent(new Event('end'));
    session.supportedFrameRates=rates;
    session.updateTargetFrameRate=async rate=>{session.requestedRate=rate;};
    session.updateRenderState=state=>{session.renderState=state;};
    session.requestAnimationFrame=()=>1;
    const xr = new EventTarget();
    const audio={srcObject:{},paused:true,muted:true,volume:0,sinkId:'default',playCalls:0,
        play(){this.playCalls++;if(audioReject)return Promise.reject(Error('Playback blocked'));this.paused=false;return Promise.resolve();},
        setSinkId(id){this.sinkId=id;return Promise.resolve();}};
    const mediaDevices=new EventTarget();
    mediaDevices.enumerateDevices=async()=>[
        {kind:'audiooutput',deviceId:'default',label:'Default'},
        {kind:'audiooutput',deviceId:'quest-speakers',label:'Quest headset'}
    ];
    let requests=0;
    xr.isSessionSupported=async()=>supported;
    xr.requestSession=async(mode)=>{
        requests++;
        assert.equal(mode,'immersive-vr');
        if(reject) throw Error('Permission denied');
        return session;
    };
    const responses=new Map();
    const commands=[];
    const listeners=new EventTarget();
    const controller={onSessionEnded:new EventTarget(),onSessionStarted:new EventTarget(),
        onXrSessionEnded(){this.onSessionEnded.dispatchEvent(new Event('xrSessionEnded'));},
        initShaders(){},initBuffers(){},onXrFrame(){}};
    window.pixelStreaming={
        _webRtcController:{streamController:{audioElement:audio}},
        webXrController:controller,
        emitCommand(command){
            commands.push(command.ResonanceWebXR);
            queueMicrotask(()=>{
                for(const callback of responses.values()) callback('ResonanceWebXR:'+command.ResonanceWebXR);
            });
            return true;
        },
        addResponseEventListener:(key,fn)=>responses.set(key,fn),
        addEventListener:(name,fn)=>listeners.addEventListener(name,fn)
    };
    const document = new EventTarget();
    document.createElement=()=>new Element();document.head=new Element();document.body=new Element();
    document.querySelector=()=>null;document.visibilityState='visible';
    vm.runInNewContext(source,{
        window,navigator:{xr,mediaDevices},document,
        setInterval,clearInterval,setTimeout,clearTimeout,Event,console,
        XRWebGLLayer:class {
            constructor(current,gl,options){
                this.framebufferWidth=2000*options.framebufferScaleFactor;
                this.framebufferHeight=2000*options.framebufferScaleFactor;
                this.antialias=options.antialias;
                this.options=options;
            }
        }
    });
    await delay(600);
    return {
        commands,requests:()=>requests,session,window,audio,mediaDevices,
        button:elements.find(e=>e.id==='resonance-open-vr'),
        status:elements.find(e=>e.id==='resonance-vr-status'),
        audioButton:elements.find(e=>e.id==='resonance-enable-audio'),
        output:elements.find(e=>e.id==='resonance-audio-output'),
        audioStatus:elements.find(e=>e.id==='resonance-audio-status'),
        cleanup:()=>window.dispatchEvent(new Event('pagehide'))
    };
}

test('desktop first; only an accepted session enables VR, and exit restores desktop',async()=>{
    const app=await fixture();
    try {
        assert.equal(app.requests(),0);
        assert.deepEqual(app.commands,['desktop']);
        app.button.dispatchEvent(new Event('click'));
        await delay(20);
        assert.equal(app.requests(),1);
        assert.equal(app.button.textContent,'Exit VR');
        assert.deepEqual(app.commands,['desktop','vr']);
        assert.equal(app.session.requestedRate,72);
        assert.equal(app.session.renderState.baseLayer.options.framebufferScaleFactor,1.0);
        assert.equal(app.session.renderState.baseLayer.options.antialias,false);
        assert.equal(app.session.renderState.baseLayer.options.depth,false);
        assert.equal(app.window.ResonanceXRDiagnostics.framebufferWidth,2000);
        await app.session.end();
        await delay(20);
        assert.equal(app.button.textContent,'Open in VR');
        assert.equal(app.commands.at(-1),'desktop');
    } finally {app.cleanup();}
});
test('denied headset permission leaves desktop active',async()=>{
    const app=await fixture({reject:true});
    try {
        app.button.dispatchEvent(new Event('click'));
        await delay(20);
        assert.equal(app.commands.includes('vr'),false);
        assert.match(app.status.textContent,/Permission denied/);
        assert.equal(app.button.disabled,false);
    } finally {app.cleanup();}
});
test('no headset keeps the normal stream and reports why VR is unavailable',async()=>{
    const app=await fixture({supported:false});
    try {
        app.button.dispatchEvent(new Event('click'));
        await delay(20);
        assert.equal(app.requests(),0);
        assert.equal(app.commands.includes('vr'),false);
        assert.match(app.status.textContent,/No immersive headset/);
    } finally {app.cleanup();}
});
test('failed reference space never enables stereo',async()=>{
    const app=await fixture({referenceFails:true});
    try {
        app.button.dispatchEvent(new Event('click'));
        await delay(20);
        assert.equal(app.commands.includes('vr'),false);
        assert.equal(app.commands.at(-1),'desktop');
        assert.equal(app.button.disabled,false);
    } finally {app.cleanup();}
});
test('headset refresh selection uses only supported rates',async()=>{
    const app=await fixture({rates:[80,90]});
    try {
        app.button.dispatchEvent(new Event('click'));
        await delay(20);
        assert.equal(app.session.requestedRate,80);
        assert.equal(app.session.renderState.baseLayer.options.framebufferScaleFactor,1.0);
    } finally {app.cleanup();}
});
test('Economy image downscaling is explicit rather than the default',async()=>{
    const app=await fixture({preset:{name:'Low graphics / Economy image',framebufferScale:0.5,refreshRate:72}});
    try {
        app.button.dispatchEvent(new Event('click'));
        await delay(20);
        assert.equal(app.session.renderState.baseLayer.options.framebufferScaleFactor,0.5);
        assert.equal(app.window.ResonanceXRDiagnostics.framebufferWidth,1000);
    } finally {app.cleanup();}
});
test('VR entry resumes the existing speech player instead of creating another one',async()=>{
    const app=await fixture();
    try {
        app.button.dispatchEvent(new Event('click'));
        assert.ok(app.audio.playCalls > 0, 'play is called in the click gesture');
        await delay(20);
        assert.equal(app.audio.paused,false);
        assert.equal(app.audio.muted,false);
        assert.equal(app.audio.volume,1);
        assert.ok(app.audio.playCalls >= 2, 'playback is recovered after XR initialization too');
        app.audio.paused=true;app.session.visibilityState='visible';
        app.session.dispatchEvent(new Event('visibilitychange'));
        await delay(20);
        assert.equal(app.audio.paused,false);
    } finally {app.cleanup();}
});
test('explicit headset output survives VR entry and output-device changes',async()=>{
    const app=await fixture();
    try {
        app.output.value='quest-speakers';app.output.dispatchEvent(new Event('change'));
        await delay(20);
        assert.equal(app.audio.sinkId,'quest-speakers');
        app.button.dispatchEvent(new Event('click'));await delay(20);
        app.mediaDevices.dispatchEvent(new Event('devicechange'));await delay(20);
        assert.equal(app.audio.sinkId,'quest-speakers');
        assert.equal(app.audio.paused,false);
    } finally {app.cleanup();}
});
test('audio playback failures are shown rather than reported as audible output',async()=>{
    const app=await fixture({audioReject:true});
    try {
        app.audioButton.dispatchEvent(new Event('click'));await delay(20);
        assert.match(app.audioStatus.textContent,/Audio could not start/);
        assert.match(app.window.ResonanceAudioDiagnostics.lastError,/Playback blocked/);
    } finally {app.cleanup();}
});
