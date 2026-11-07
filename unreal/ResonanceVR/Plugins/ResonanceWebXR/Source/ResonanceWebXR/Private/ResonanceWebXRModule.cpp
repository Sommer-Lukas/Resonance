#include "Modules/ModuleManager.h"
#include "Async/Async.h"
#include "Camera/CameraComponent.h"
#include "Containers/Ticker.h"
#include "Engine/Engine.h"
#include "Engine/GameViewportClient.h"
#include "Engine/World.h"
#include "GameFramework/Pawn.h"
#include "GameFramework/PlayerController.h"
#include "HAL/IConsoleManager.h"
#include "IHeadMountedDisplay.h"
#include "IPixelStreaming2InputHandler.h"
#include "IPixelStreaming2Module.h"
#include "IPixelStreaming2Streamer.h"
#include "IXRTrackingSystem.h"
#include "Misc/CommandLine.h"
#include "Misc/Parse.h"
#include "UnrealClient.h"

DEFINE_LOG_CATEGORY_STATIC(LogResonanceWebXR, Log, All);

// Only active in launcher sessions. No camera assets or saved settings change.
class FResonanceWebXRModule final : public IModuleInterface
{
    FTSTicker::FDelegateHandle TickHandle;
    FDelegateHandle WorldHandle;
    TWeakObjectPtr<UWorld> ActiveWorld;
    TWeakObjectPtr<UCameraComponent> Camera;
    TWeakObjectPtr<USceneComponent> Parent;
    FTransform CameraTransform, ParentTransform;
    FRotator ControlRotation;
    float FieldOfView = 45.f;
    bool LockToHmd = true;
    bool InVR = false;
    bool Active = false;
    int32 VRHeight = 1080;
    int32 VRFps = 30;
    int32 VRMaxWidth = 4096;
    int32 VRScreenPercentage = 100;
    int32 VRShadowBias = 2;
    int32 VRTexturePoolMB = 768;
    int32 VRTextureMipBias = 1;
    FIntPoint LastRequestedSize = FIntPoint::ZeroValue;
    double LastResizeTime = 0.0;
    TMap<FString, FString> SavedCVars;
    TWeakPtr<IPixelStreaming2Streamer> BoundStreamer;

    bool HasStreamingHMD() const
    {
        return GEngine && GEngine->XRSystem.IsValid()
            && GEngine->XRSystem->GetSystemName() == FName(TEXT("PixelStreaming2HMD"));
    }

    void SetCVar(const TCHAR* Name, const TCHAR* Value)
    {
        if (IConsoleVariable* Var = IConsoleManager::Get().FindConsoleVariable(Name))
            if (!FMath::IsNearlyEqual(Var->GetFloat(), FCString::Atof(Value)))
                Var->Set(Value, ECVF_SetByConsole);
    }

    void DisableTracking()
    {
        if (!HasStreamingHMD()) return;
        GEngine->XRSystem->GetStereoRenderingDevice()->EnableStereo(false);
        GEngine->XRSystem->GetHMDDevice()->EnableHMD(false);
    }

    UWorld* GameWorld() const
    {
        if (GEngine)
            for (const FWorldContext& Context : GEngine->GetWorldContexts())
                if (Context.World() && Context.WorldType == EWorldType::Game) return Context.World();
        return nullptr;
    }

    bool EnterVR(UWorld* World)
    {
        if (InVR) return true;
        APlayerController* Controller = World ? World->GetFirstPlayerController() : nullptr;
        APawn* Pawn = Controller ? Controller->GetPawn() : nullptr;
        UCameraComponent* ViewCamera = Pawn ? Pawn->FindComponentByClass<UCameraComponent>() : nullptr;
        if (!HasStreamingHMD() || !ViewCamera) return false;
        Camera = ViewCamera;
        CameraTransform = ViewCamera->GetRelativeTransform();
        FieldOfView = ViewCamera->FieldOfView;
        LockToHmd = ViewCamera->bLockToHmd;
        Parent = ViewCamera->GetAttachParent();
        if (Parent.IsValid()) ParentTransform = Parent->GetRelativeTransform();
        ControlRotation = Controller->GetControlRotation();
        SavedCVars.Empty();
        for (const TCHAR* Name : {TEXT("t.MaxFPS"), TEXT("PixelStreaming2.WebRTC.Fps"),
            TEXT("PixelStreaming2.DecoupleFrameRate"), TEXT("PixelStreaming2.Encoder.MaxQuality"),
            TEXT("PixelStreaming2.CaptureUseFence"), TEXT("PixelStreaming2.Encoder.KeyframeInterval"),
            TEXT("PixelStreaming2.HMD.MatchAspectRatio"), TEXT("r.ScreenPercentage"),
            TEXT("r.Shadow.Virtual.ResolutionLodBiasLocal"), TEXT("r.Streaming.PoolSize"), TEXT("r.Streaming.MipBias")})
            if (IConsoleVariable* Var = IConsoleManager::Get().FindConsoleVariable(Name))
                SavedCVars.Add(Name, Var->GetString());
        ViewCamera->bLockToHmd = true;
        SetCVar(TEXT("PixelStreaming2.HMD.MatchAspectRatio"), TEXT("0"));
        SetCVar(TEXT("PixelStreaming2.DecoupleFramerate"), TEXT("0"));
        SetCVar(TEXT("PixelStreaming2.Encoder.MaxQuality"), TEXT("70"));
        SetCVar(TEXT("PixelStreaming2.CaptureUseFence"), TEXT("0"));
        SetCVar(TEXT("PixelStreaming2.Encoder.KeyframeInterval"), TEXT("-1"));
        SetCVar(TEXT("r.ScreenPercentage"), *FString::FromInt(VRScreenPercentage));
        if (VRShadowBias > 0)
            SetCVar(TEXT("r.Shadow.Virtual.ResolutionLodBiasLocal"), *FString::FromInt(VRShadowBias));
        // Never raise texture detail above the selected engine scalability tier.
        // In UE5.6 Low sets a larger per-texture mip budget bias than this VR cap.
        IConsoleVariable* MipBias = IConsoleManager::Get().FindConsoleVariable(TEXT("r.Streaming.MipBias"));
        if (MipBias)
            SetCVar(TEXT("r.Streaming.MipBias"), *FString::FromInt(FMath::Max(MipBias->GetInt(), VRTextureMipBias)));
        if (VRTexturePoolMB > 0)
        {
            // UE5.6.1 CheckUserSettings permits runtime pool changes only with
            // UseFixedPoolSize=0. Respect a project that deliberately fixes it.
            IConsoleVariable* Fixed = IConsoleManager::Get().FindConsoleVariable(TEXT("r.Streaming.UseFixedPoolSize"));
            IConsoleVariable* Pool = IConsoleManager::Get().FindConsoleVariable(TEXT("r.Streaming.PoolSize"));
            if (Fixed && Fixed->GetInt() == 0 && Pool)
            {
                const int32 Budget = Pool->GetInt() > 0 ? FMath::Min(Pool->GetInt(), VRTexturePoolMB) : VRTexturePoolMB;
                SetCVar(TEXT("r.Streaming.PoolSize"), *FString::FromInt(Budget));
            }
        }
        LastRequestedSize = FIntPoint::ZeroValue;
        LastResizeTime = 0.0;
        GEngine->XRSystem->GetHMDDevice()->EnableHMD(true);
        GEngine->XRSystem->GetStereoRenderingDevice()->EnableStereo(true);
        InVR = true;
        UE_LOG(LogResonanceWebXR, Display, TEXT("Mode=vr; target=%d FPS, height=%d, width cap=%d, screen percentage=%d"), VRFps, VRHeight, VRMaxWidth, VRScreenPercentage);
        return true;
    }

    void Desktop(UWorld* World)
    {
        DisableTracking();
        if (InVR)
        {
            if (Parent.IsValid()) Parent->SetRelativeTransform(ParentTransform);
            if (Camera.IsValid())
            {
                Camera->SetRelativeTransform(CameraTransform);
                Camera->SetFieldOfView(FieldOfView);
                Camera->bLockToHmd = LockToHmd;
            }
            if (APlayerController* Controller = World ? World->GetFirstPlayerController() : nullptr)
                Controller->SetControlRotation(ControlRotation);
            for (const auto& Pair : SavedCVars) SetCVar(*Pair.Key, *Pair.Value);
            if (World) GEngine->Exec(World, TEXT("r.SetRes 1280x720w"));
        }
        InVR = false;
        UE_LOG(LogResonanceWebXR, Display, TEXT("Mode=desktop; stereo and headset tracking disabled; portrait camera restored"));
    }

    void BindStreamer()
    {
        if (!IPixelStreaming2Module::IsAvailable()) return;
        auto& Module = IPixelStreaming2Module::Get();
        TSharedPtr<IPixelStreaming2Streamer> Streamer = Module.FindStreamer(Module.GetDefaultStreamerID());
        if (!Streamer || Streamer == BoundStreamer.Pin()) return;
        TSharedPtr<IPixelStreaming2InputHandler> Input = Streamer->GetInputHandler().Pin();
        if (!Input) return;
        BoundStreamer = Streamer;
        TWeakPtr<IPixelStreaming2Streamer> WeakStreamer = Streamer;
        Input->SetCommandHandler(TEXT("ResonanceWebXR"),
            [this, WeakStreamer](FString PlayerId, FString, FString Mode)
            {
                // Use Epic's existing Command/Response messages; accept only these modes.
                AsyncTask(ENamedThreads::GameThread, [this, WeakStreamer, PlayerId, Mode]()
                {
                    if (!Active) return;
                    UWorld* World = GameWorld();
                    if (Mode == TEXT("desktop")) Desktop(World);
                    else if (Mode == TEXT("vr"))
                    {
                        if (!EnterVR(World))
                        {
                            if (auto Target = WeakStreamer.Pin()) Target->SendPlayerMessage(PlayerId, TEXT("Response"), TEXT("ResonanceWebXR:error"));
                            return;
                        }
                    }
                    else if (Mode != TEXT("status")) return;
                    if (auto Target = WeakStreamer.Pin())
                        Target->SendPlayerMessage(PlayerId, TEXT("Response"), InVR ? TEXT("ResonanceWebXR:vr") : TEXT("ResonanceWebXR:desktop"));
                });
            });
        UE_LOG(LogResonanceWebXR, Display, TEXT("Browser mode command handler ready"));
    }

    bool Tick(float)
    {
        BindStreamer();
        UWorld* World = GameWorld();
        if (World && ActiveWorld.Get() != World)
        {
            ActiveWorld = World;
            InVR = false;
            Desktop(World);
        }
        if (InVR && HasStreamingHMD())
        {
            // The engine changes these on first XR data. Enforce a conservative
            // session-only target and restore previous values when leaving VR.
            const FString Fps = FString::FromInt(VRFps);
            SetCVar(TEXT("t.MaxFPS"), *Fps);
            SetCVar(TEXT("PixelStreaming2.WebRTC.Fps"), *Fps);
            float Horizontal = 0.f, Vertical = 0.f;
            GEngine->XRSystem->GetHMDDevice()->GetFieldOfView(Horizontal, Vertical);
            if (Horizontal > 1.f && Horizontal < 179.f && Vertical > 1.f && Vertical < 179.f
                && World && World->GetGameViewport() && World->GetGameViewport()->Viewport)
            {
                // Quantize width and request each target only once. Reissuing
                // SetRes while a resize is pending can repeatedly allocate targets.
                const int32 Width = FMath::Clamp(FMath::RoundToInt((2.f * VRHeight * FMath::Tan(FMath::DegreesToRadians(Horizontal * .5f))
                    / FMath::Tan(FMath::DegreesToRadians(Vertical * .5f)))) / 16 * 16, 480, VRMaxWidth);
                const FIntPoint Target(Width, VRHeight);
                const FIntPoint Size = World->GetGameViewport()->Viewport->GetSizeXY();
                if (Size != Target && Target != LastRequestedSize && FPlatformTime::Seconds() - LastResizeTime >= 1.0)
                {
                    LastRequestedSize = Target;
                    LastResizeTime = FPlatformTime::Seconds();
                    GEngine->Exec(World, *FString::Printf(TEXT("r.SetRes %dx%dw"), Width, VRHeight));
                }
            }
        }
        return true;
    }

public:
    virtual void StartupModule() override
    {
        Active = FParse::Param(FCommandLine::Get(), TEXT("ResonanceWebXR"));
        if (!Active) return;
        FParse::Value(FCommandLine::Get(), TEXT("ResonanceVRHeight="), VRHeight);
        FParse::Value(FCommandLine::Get(), TEXT("ResonanceVRFPS="), VRFps);
        FParse::Value(FCommandLine::Get(), TEXT("ResonanceVRScreenPercentage="), VRScreenPercentage);
        FParse::Value(FCommandLine::Get(), TEXT("ResonanceVRMaxWidth="), VRMaxWidth);
        FParse::Value(FCommandLine::Get(), TEXT("ResonanceVRShadowBias="), VRShadowBias);
        FParse::Value(FCommandLine::Get(), TEXT("ResonanceVRTexturePoolMB="), VRTexturePoolMB);
        FParse::Value(FCommandLine::Get(), TEXT("ResonanceVRTextureMipBias="), VRTextureMipBias);
        VRHeight = FMath::Clamp(VRHeight, 360, 1440);
        VRFps = FMath::Clamp(VRFps, 24, 90);
        VRMaxWidth = FMath::Clamp(VRMaxWidth, 480, 4096);
        VRScreenPercentage = FMath::Clamp(VRScreenPercentage, 50, 100);
        VRShadowBias = FMath::Clamp(VRShadowBias, 0, 4);
        VRTexturePoolMB = FMath::Clamp(VRTexturePoolMB, 0, 4096);
        VRTextureMipBias = FMath::Clamp(VRTextureMipBias, 0, 3);
        // Disable before pawn BeginPlay so the existing viewer follows its normal
        // desktop path instead of calibrating against an absent browser headset.
        WorldHandle = FWorldDelegates::OnPostWorldInitialization.AddLambda(
            [this](UWorld* World, const UWorld::InitializationValues)
            {
                if (World->WorldType == EWorldType::Game) DisableTracking();
            });
        DisableTracking();
        TickHandle = FTSTicker::GetCoreTicker().AddTicker(FTickerDelegate::CreateRaw(this, &FResonanceWebXRModule::Tick), .1f);
    }
    virtual void ShutdownModule() override
    {
        Active = false;
        if (auto Streamer = BoundStreamer.Pin())
            if (auto Input = Streamer->GetInputHandler().Pin())
                Input->SetCommandHandler(TEXT("ResonanceWebXR"), [](FString, FString, FString) {});
        if (TickHandle.IsValid()) FTSTicker::GetCoreTicker().RemoveTicker(TickHandle);
        if (WorldHandle.IsValid()) FWorldDelegates::OnPostWorldInitialization.Remove(WorldHandle);
    }
};
IMPLEMENT_MODULE(FResonanceWebXRModule, ResonanceWebXR)
