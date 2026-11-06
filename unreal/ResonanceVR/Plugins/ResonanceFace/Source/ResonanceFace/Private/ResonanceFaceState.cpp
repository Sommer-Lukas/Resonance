#include "ResonanceFaceState.h"
#include "ACEAudioCurveSourceComponent.h"
#include "CoreGlobals.h"

bool UResonanceFaceState::PreviewEmotion(FName Emotion, float Strength)
{
    if (!FMath::IsFinite(Strength)) return false;
    ResonanceFace::Scores Values{};
    bool Found = Emotion == TEXT("neutral");
    for (int i=0;i<ResonanceFace::EmotionCount;++i)
    {
        if (Emotion == FName(UTF8_TO_TCHAR(ResonanceFace::EmotionNames[i])))
        {
            Values[i] = FMath::Clamp(Strength,0.f,1.f);
            Found = true;
        }
    }
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
        EmotionAudioTime = Source->CurrentEmotionTimestamp;
    }
    if (bManualPreview) Idle.SetScores(Preview);
    else if (bHasAutomaticEmotion && EmotionScores.Num()==ResonanceFace::EmotionCount)
    {
        ResonanceFace::Scores Values;
        for (int i=0;i<ResonanceFace::EmotionCount;++i) Values[i]=EmotionScores[i];
        Idle.SetScores(Values);
    }
    Idle.Update(DeltaTime, TransitionSeconds);
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
        IdleCurves.Add(FName(UTF8_TO_TCHAR(ResonanceFace::CurveNames[i])),Idle.Output[i]);
}
