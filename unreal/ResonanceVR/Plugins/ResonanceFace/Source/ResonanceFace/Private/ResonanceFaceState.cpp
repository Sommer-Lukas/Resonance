#include "ResonanceFaceState.h"
#include "ACEAudioCurveSourceComponent.h"
#include "CoreGlobals.h"
#include "Components/SkeletalMeshComponent.h"
#include "GameFramework/Actor.h"
#include "Components/AudioComponent.h"
#include "ResonanceAudioPlaylist.h"
#include "Audio.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"

void UResonanceFaceState::LoadLocalSpeechEnvelope()
{
    const auto* Playlist=GetOwner()->FindComponentByClass<UResonanceAudioPlaylist>();
    const FString Path=Playlist ? FPaths::ProjectContentDir()/Playlist->GetRequestedAudioPath() : FString();
    if (Path==LocalSpeechPath) return;
    LocalSpeechPath=Path; LocalSpeechEnvelope.Reset();
    if (Path.IsEmpty()) return;
    TArray<uint8> Data;
    if (!FFileHelper::LoadFileToArray(Data,*Path)) return;
    FWaveModInfo Wave;
    if (!Wave.ReadWaveInfo(Data.GetData(),Data.Num()) || !Wave.pBitsPerSample || *Wave.pBitsPerSample!=16 ||
        !Wave.pFormatTag || *Wave.pFormatTag!=1 || !Wave.pSamplesPerSec || !*Wave.pSamplesPerSec ||
        !Wave.pChannels || !*Wave.pChannels) return;
    const int32 Block=FMath::Max(1,int32(*Wave.pSamplesPerSec/100))*int32(*Wave.pChannels);
    LocalSpeechEnvelopeRate=float(*Wave.pSamplesPerSec)*float(*Wave.pChannels)/float(Block);
    const int32 Count=int32(Wave.SampleDataSize/2);
    for (int32 Begin=0;Begin<Count;Begin+=Block)
    {
        const int32 End=FMath::Min(Begin+Block,Count);
        double Energy=0.;
        for (int32 i=Begin;i<End;++i)
        {
            int16 Sample;
            FMemory::Memcpy(&Sample,Wave.SampleDataStart+i*2,2);
            const double Value=double(Sample)/32768.; Energy+=Value*Value;
        }
        LocalSpeechEnvelope.Add(float(FMath::Sqrt(Energy/double(End-Begin))));
    }
}

void UResonanceFaceState::EndPlay(const EEndPlayReason::Type Reason)
{
    if (auto* Audio=SpeechAudio.Get()) Audio->OnAudioSingleEnvelopeValueNative.RemoveAll(this);
    SpeechAudio.Reset();
    Super::EndPlay(Reason);
}

void UResonanceFaceState::HandleSpeechEnvelope(const UAudioComponent* Component,const USoundWave*,float Envelope)
{
    check(IsInGameThread());
    if (Component!=SpeechAudio.Get()) return;
    MixerEnvelope=ResonanceFace::Unit(Envelope);
    EnvelopeAge=0.f;
    bEnvelopeObserved=true;
    bEnvelopeHasEnergy|=MixerEnvelope>.0001f;
    ++SpeechEnvelopeSamples;
}

void UResonanceFaceState::ObserveSpeechAudio(UACEAudioCurveSourceComponent* Source)
{
    UAudioComponent* Found=nullptr;
    if (Source)
    {
        TArray<USceneComponent*> Children;
        Source->GetChildrenComponents(false,Children);
        for (auto* Child:Children)
            if (auto* Audio=Cast<UAudioComponent>(Child)) { Found=Audio; break; }
    }
    if (Found==SpeechAudio.Get()) return;
    if (auto* Old=SpeechAudio.Get()) Old->OnAudioSingleEnvelopeValueNative.RemoveAll(this);
    SpeechAudio=Found;
    SpeechEnvelope=MixerEnvelope=0.f; EnvelopeAge=100.f; bEnvelopeObserved=false; bEnvelopeHasEnergy=false;
    LoadLocalSpeechEnvelope();
    if (Found) Found->OnAudioSingleEnvelopeValueNative.AddUObject(this,&UResonanceFaceState::HandleSpeechEnvelope);
}

void UResonanceFaceState::BeginPlay()
{
    Super::BeginPlay();
    const FGuid RunId=FGuid::NewGuid();
    ActiveBehaviourSeed=bUseFixedBehaviourSeed ? BehaviourSeed :
        static_cast<int32>((RunId.A^RunId.B^RunId.C^RunId.D)&0x7fffffffu);
    if (!ActiveBehaviourSeed) ActiveBehaviourSeed=12491;
    Idle.ResetSeed(static_cast<uint32>(ActiveBehaviourSeed));
    if (!HeadPostProcessClass) return;
    TArray<USkeletalMeshComponent*> Meshes;
    GetOwner()->GetComponents(Meshes);
    for (auto* Mesh:Meshes)
        if (Mesh->GetFName()==FaceComponentName)
            Mesh->SetOverridePostProcessAnimBP(HeadPostProcessClass);
}

bool UResonanceFaceState::PreviewEmotion(FName Emotion, float Strength, int32 Variant)
{
    if (!FMath::IsFinite(Strength) || Variant < -1 || Variant > 2) return false;
    ResonanceFace::Scores Values{};
    const int Index=ResonanceFace::EmotionIndex(TCHAR_TO_UTF8(*Emotion.ToString().ToLower()));
    const bool Found=Index>=0;
    if (Index>=0 && Index<ResonanceFace::EmotionCount) Values[Index]=FMath::Clamp(Strength,0.f,1.f);
    if (Found) { Preview=Values; bManualPreview=true; PreviewVariant=Variant; }
    return Found;
}

void UResonanceFaceState::UpdateForAnimation(UACEAudioCurveSourceComponent* Source, float DeltaTime)
{
    check(IsInGameThread());
    if (UpdatedFrame == GFrameCounter) return;
    UpdatedFrame = GFrameCounter;
    ObserveSpeechAudio(Source);
    EnvelopeAge+=FMath::Max(0.f,DeltaTime);
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
    // The mixer can report zeros when editor playback is suppressed in the
    // background. For known local playlist WAVs, sample their original PCM
    // envelope on ACE's playback-selected timestamp; never change audio volume.
    SpeechEnvelope=EnvelopeAge<.3f ? MixerEnvelope : 0.f;
    bSpeechEnvelopeFromFile=Speaking && !bEnvelopeHasEnergy && !LocalSpeechEnvelope.IsEmpty() &&
        EmotionAudioTime>=0. && Source && Source->EmotionSamplesReceived>0;
    if (bSpeechEnvelopeFromFile)
    {
        const int32 Index=FMath::Clamp(int32(EmotionAudioTime*LocalSpeechEnvelopeRate),0,LocalSpeechEnvelope.Num()-1);
        SpeechEnvelope=LocalSpeechEnvelope[Index];
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
    Idle.UseSpeechTiming=bUseSpeechTiming;
    Idle.PlaybackActive=Speaking;
    Idle.HasSpeechEnvelope=bEnvelopeObserved || bSpeechEnvelopeFromFile;
    Idle.SpeechEnvelope=bSpeechEnvelopeFromFile || EnvelopeAge<.3f ? SpeechEnvelope : 0.f;
    Idle.SpeechMotionScale=Calibration ? Calibration->SpeechMotionScale : 1.5f;
    Idle.QuietMotionScale=Calibration ? Calibration->QuietMotionScale : 1.f;
    Idle.QuietIntervalSeconds=Calibration ? Calibration->QuietIntervalSeconds : 8.f;
    Idle.ExpressionStrength=Calibration && FMath::IsFinite(Calibration->ExpressionStrength)
        ? Calibration->ExpressionStrength : 1.3f;
    Idle.Update(DeltaTime, TransitionSeconds);
    ActiveVariant=PreviewVariant>=0 && PreviewVariant<3 ? PreviewVariant : Idle.VariantIndex;
    EmotionBlink=Idle.Blink;
    bLookingAway=Idle.LookingAway;
    bSpeechVoiced=Idle.SpeechVoiced;
    HeadSpeechCues=Idle.HeadSpeechCues;
    QuietHeadAdjustments=Idle.QuietHeadAdjustments;
    HeadDegrees=FVector(Idle.Head[0],Idle.Head[1],Idle.Head[2]);
    const float HeadGain=Calibration && FMath::IsFinite(Calibration->HeadStrength)
        ? FMath::Clamp(Calibration->HeadStrength,0.f,2.f) : 1.f;
    const FVector Limits=Calibration ? Calibration->HeadLimits : FVector(5,5,3);
    double RadiusSquared=0.;
    for (int i=0;i<3;++i)
    {
        const double Limit=FMath::Clamp(FMath::IsFinite(Limits[i]) ? Limits[i] : 0.,0.,8.);
        HeadDegrees[i]=Limit>0. ? HeadDegrees[i]*HeadGain : 0.;
        if (Limit>0.) RadiusSquared+=FMath::Square(HeadDegrees[i]/Limit);
    }
    // Smoothly approach an ellipsoid, rather than flattening separate axes
    // against a box. Combined turns retain their direction near the limits.
    HeadDegrees*=1./FMath::Pow(1.+RadiusSquared*RadiusSquared,.25);
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
