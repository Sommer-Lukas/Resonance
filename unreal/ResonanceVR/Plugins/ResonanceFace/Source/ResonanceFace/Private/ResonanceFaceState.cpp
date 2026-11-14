#include "ResonanceFaceState.h"
#include "ACEAudioCurveSourceComponent.h"
#include "CoreGlobals.h"
#include "Components/SkeletalMeshComponent.h"
#include "GameFramework/Actor.h"

void UResonanceFaceState::BeginPlay()
{
    Super::BeginPlay();
    if (!HeadPostProcessClass) return;
    TArray<USkeletalMeshComponent*> Meshes;
    GetOwner()->GetComponents(Meshes);
    for (auto* Mesh:Meshes)
        if (Mesh->GetFName()==FaceComponentName)
            Mesh->SetOverridePostProcessAnimBP(HeadPostProcessClass);
}

bool UResonanceFaceState::PreviewEmotion(FName Emotion, float Strength)
{
    if (!FMath::IsFinite(Strength)) return false;
    ResonanceFace::Scores Values{};
    const int Index=ResonanceFace::EmotionIndex(TCHAR_TO_UTF8(*Emotion.ToString().ToLower()));
    const bool Found=Index>=0;
    if (Index>=0 && Index<ResonanceFace::EmotionCount) Values[Index]=FMath::Clamp(Strength,0.f,1.f);
    if (Found) { Preview=Values; bManualPreview=true; }
    return Found;
}

void UResonanceFaceState::UpdateForAnimation(UACEAudioCurveSourceComponent* Source, float DeltaTime)
{
    check(IsInGameThread());
    if (UpdatedFrame == GFrameCounter) return;
    UpdatedFrame = GFrameCounter;
    bool Speaking=false;
    if (Source)
    {
        bHasAutomaticEmotion = Source->GetPlaybackEmotionScores(EmotionScores);
        Speaking = Source->IsEmotionPlaybackActive();
        if (Source->EmotionSamplesReceived<LastEmotionSamplesReceived ||
            Source->CurrentEmotionTimestamp<EmotionAudioTime)
            Idle.ResetPlaybackTiming();
        LastEmotionSamplesReceived=Source->EmotionSamplesReceived;
        EmotionAudioTime = Source->CurrentEmotionTimestamp;
    }
    if (bManualPreview) Idle.SetScores(Preview);
    else if (bHasAutomaticEmotion && EmotionScores.Num()==ResonanceFace::EmotionCount)
    {
        ResonanceFace::Scores Values;
        for (int i=0;i<ResonanceFace::EmotionCount;++i) Values[i]=EmotionScores[i];
        Idle.SetPlaybackScores(Values,EmotionDelaySeconds);
    }
    Idle.ForcedVariant=PreviewVariant;
    Idle.VariantTransitionSeconds=VariantTransitionSeconds;
    Idle.ExpressionStrength=Calibration && FMath::IsFinite(Calibration->ExpressionStrength)
        ? Calibration->ExpressionStrength : 1.3f;
    Idle.Update(DeltaTime, TransitionSeconds);
    ActiveVariant=PreviewVariant>=0 && PreviewVariant<3 ? PreviewVariant : Idle.VariantIndex;
    EmotionBlink=Idle.Blink;
    HeadDegrees=FVector(Idle.Head[0],Idle.Head[1],Idle.Head[2]);
    const float HeadGain=Calibration && FMath::IsFinite(Calibration->HeadStrength)
        ? FMath::Clamp(Calibration->HeadStrength,0.f,2.f) : 1.f;
    const FVector Limits=Calibration ? Calibration->HeadLimits : FVector(5,5,3);
    for (int i=0;i<3;++i)
        HeadDegrees[i]=FMath::Clamp(HeadDegrees[i]*HeadGain,
            -FMath::Clamp(FMath::IsFinite(Limits[i]) ? Limits[i] : 0.,0.,8.),
            FMath::Clamp(FMath::IsFinite(Limits[i]) ? Limits[i] : 0.,0.,8.));
    if (!bEnableHeadMovement) HeadDegrees=FVector::ZeroVector;
    const float Target=FMath::Clamp(Speaking ? SpeakingBlend : IdleBlend,0.f,1.f);
    CurrentBlend=FMath::Lerp(CurrentBlend,Target,1.f-FMath::Exp(-FMath::Max(0.f,DeltaTime)/.3f));
    SmoothedEmotionScores.Reset();
    DominantEmotion=TEXT("neutral");
    float Largest=Idle.Neutral;
    for (int i=0;i<ResonanceFace::EmotionCount;++i)
    {
        SmoothedEmotionScores.Add(Idle.Smoothed[i]);
        if (Idle.Smoothed[i]>Largest)
        {
            Largest=Idle.Smoothed[i];
            DominantEmotion=FName(UTF8_TO_TCHAR(ResonanceFace::EmotionNames[i]));
        }
    }
    IdleCurves.Reset();
    for (int i=0;i<ResonanceFace::CurveCount;++i)
    {
        const FName Name(UTF8_TO_TCHAR(ResonanceFace::CurveNames[i]));
        float Value=Idle.Output[i];
        if (Calibration)
        {
            if (const float* Gain=Calibration->CurveGains.Find(Name))
                Value*=FMath::IsFinite(*Gain) ? FMath::Clamp(*Gain,0.f,2.f) : 0.f;
            if (i>=15)
                Value=FMath::Min(Value*(FMath::IsFinite(Calibration->EyeStrength) ?
                    FMath::Clamp(Calibration->EyeStrength,0.f,2.f) : 0.f),
                    FMath::IsFinite(Calibration->EyeLimit) ? FMath::Clamp(Calibration->EyeLimit,0.f,.3f) : 0.f);
        }
        IdleCurves.Add(Name,ResonanceFace::Unit(Value));
    }
}
