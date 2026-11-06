#pragma once
#include "CoreMinimal.h"
#include "Components/ActorComponent.h"
#include "ResonanceEmotionIdle.h"
#include "ResonanceFaceState.generated.h"

class UACEAudioCurveSourceComponent;

/** Game-thread state and diagnostics. The animation fusion node is the only curve writer. */
UCLASS(ClassGroup=(Resonance), meta=(BlueprintSpawnableComponent))
class RESONANCEFACE_API UResonanceFaceState : public UActorComponent
{
    GENERATED_BODY()
public:
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Resonance", meta=(ClampMin="0", ClampMax="1"))
    float SpeakingBlend = .65f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Resonance", meta=(ClampMin="0", ClampMax="1"))
    float IdleBlend = .90f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Resonance", meta=(ClampMin="0.15", ClampMax="4"))
    float TransitionSeconds = .8f;
    UPROPERTY(BlueprintReadOnly, Category="Resonance")
    TArray<float> EmotionScores;
    UPROPERTY(BlueprintReadOnly, Category="Resonance")
    TArray<float> SmoothedEmotionScores;
    UPROPERTY(BlueprintReadOnly, Category="Resonance")
    TMap<FName,float> IdleCurves;
    UPROPERTY(BlueprintReadOnly, Category="Resonance")
    FName DominantEmotion = TEXT("neutral");
    UPROPERTY(BlueprintReadOnly, Category="Resonance")
    bool bHasAutomaticEmotion = false;
    UPROPERTY(BlueprintReadOnly, Category="Resonance")
    bool bManualPreview = false;
    UPROPERTY(BlueprintReadOnly, Category="Resonance")
    float CurrentBlend = .90f;
    UPROPERTY(BlueprintReadOnly, Category="Resonance")
    double EmotionAudioTime = -1.;
    UFUNCTION(BlueprintCallable, Category="Resonance")
    bool PreviewEmotion(FName Emotion, float Strength = .7f);
    UFUNCTION(BlueprintCallable, Category="Resonance")
    void ResumeAutomaticEmotion() { bManualPreview = false; }
    void UpdateForAnimation(UACEAudioCurveSourceComponent* Source, float DeltaTime);
private:
    ResonanceFace::IdleState Idle;
    ResonanceFace::Scores Preview{};
    uint64 UpdatedFrame = MAX_uint64;
};
