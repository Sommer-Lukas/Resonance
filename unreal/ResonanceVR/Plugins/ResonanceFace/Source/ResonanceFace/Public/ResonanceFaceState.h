#pragma once
#include "CoreMinimal.h"
#include "Components/ActorComponent.h"
#include "ResonanceEmotionIdle.h"
#include "Engine/DataAsset.h"
#include "ResonanceFaceState.generated.h"

class UACEAudioCurveSourceComponent;
class UAnimInstance;

/** Assign one reusable calibration asset per character/rig. Empty curve maps use ARKit names. */
UCLASS(BlueprintType)
class RESONANCEFACE_API UResonanceFaceCalibration : public UDataAsset
{
    GENERATED_BODY()
public:
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Face")
    float ExpressionStrength = 1.3f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Face")
    float EyeStrength = 1.f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Face")
    float EyeLimit = .18f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Face")
    TMap<FName,float> CurveGains;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Face")
    TMap<FName,FName> CurveMapping;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Head")
    FName HeadBone = TEXT("head");
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Head")
    float HeadStrength = 1.f;
    /** Pitch, yaw, roll absolute limits in degrees. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Head")
    FVector HeadLimits = FVector(5.f,5.f,3.f);
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Head")
    FVector PitchAxis = FVector(0,0,1);
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Head")
    FVector YawAxis = FVector(1,0,0);
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Head")
    FVector RollAxis = FVector(0,1,0);
};

/** Game-thread state and diagnostics. The animation fusion node is the only curve writer. */
UCLASS(ClassGroup=(Resonance), meta=(BlueprintSpawnableComponent))
class RESONANCEFACE_API UResonanceFaceState : public UActorComponent
{
    GENERATED_BODY()
public:
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Resonance")
    TSubclassOf<UAnimInstance> HeadPostProcessClass;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Resonance")
    FName FaceComponentName = TEXT("Face");
    virtual void BeginPlay() override;
    float ShowcaseBlend = 0.f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Resonance")
    TObjectPtr<UResonanceFaceCalibration> Calibration;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Resonance")
    bool bEnableHeadMovement = true;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Resonance", meta=(ClampMin="-1", ClampMax="2"))
    int32 PreviewVariant = -1;
    UPROPERTY(BlueprintReadOnly, Category="Resonance")
    int32 ActiveVariant = 0;
    UPROPERTY(BlueprintReadOnly, Category="Resonance")
    FVector HeadDegrees = FVector::ZeroVector;
    UPROPERTY(BlueprintReadOnly, Category="Resonance")
    float EmotionBlink = 0.f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Resonance", meta=(ClampMin="0", ClampMax="1"))
    float SpeakingBlend = .65f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Resonance", meta=(ClampMin="0", ClampMax="1"))
    float IdleBlend = .90f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Resonance", meta=(ClampMin="0.15", ClampMax="4"))
    float TransitionSeconds = .3f;
    /** Additional expression delay after playback-aligned scores (not audio delay). */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Resonance", meta=(ClampMin="0", ClampMax="0.5"))
    float EmotionDelaySeconds = .12f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Resonance", meta=(ClampMin="0.08", ClampMax="1"))
    float VariantTransitionSeconds = .18f;
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
    int32 LastEmotionSamplesReceived = 0;
};
