#pragma once
#include "CoreMinimal.h"
#include "Components/ActorComponent.h"
#include "ResonanceAudioPlaylist.generated.h"
class UACEAudioCurveSourceComponent;

/** Serial speech playlists; advance on audible playback completion, never send completion. */
UCLASS(ClassGroup=(Resonance), meta=(BlueprintSpawnableComponent))
class RESONANCEFACE_API UResonanceAudioPlaylist : public UActorComponent
{
    GENERATED_BODY()
public:
    UResonanceAudioPlaylist();
    virtual void BeginPlay() override;
    virtual void EndPlay(const EEndPlayReason::Type Reason) override;
    virtual void TickComponent(float DeltaTime, ELevelTick Type, FActorComponentTickFunction* Function) override;
    UFUNCTION(BlueprintCallable, Category="Resonance|Audio")
    void PlayBaseOnce();
    UFUNCTION(BlueprintCallable, Category="Resonance|Audio")
    bool StartSet(int32 Set);
    UFUNCTION(BlueprintCallable, Category="Resonance|Audio")
    void ReplayCurrent();
    UFUNCTION(BlueprintPure, Category="Resonance|Audio")
    FString GetRequestedAudioPath() const { return RequestedAudioPath; }
    UFUNCTION(BlueprintPure, Category="Resonance|Audio")
    FString GetStatusText() const;
    UFUNCTION(BlueprintCallable, Category="Resonance|Audio", meta=(WorldContext="WorldContextObject"))
    static bool PlayPortraitSet(UObject* WorldContextObject, int32 Set);
    UPROPERTY(BlueprintReadOnly, Category="Resonance|Audio")
    int32 ActiveSet = 0;
    UPROPERTY(BlueprintReadOnly, Category="Resonance|Audio")
    int32 MixIndex = 0;
    UPROPERTY(BlueprintReadOnly, Category="Resonance|Audio")
    bool bPlaylistActive = false;
    UPROPERTY(BlueprintReadOnly, Category="Resonance|Audio")
    int32 PlaybackStarts = 0;
    UPROPERTY(BlueprintReadOnly, Category="Resonance|Audio")
    int32 CompletedMixes = 0;
    UPROPERTY(BlueprintReadOnly, Category="Resonance|Audio")
    FString RequestedAudioPath = TEXT("Resonance/Audio/voice_test.wav");
private:
    UPROPERTY(Transient)
    TObjectPtr<UACEAudioCurveSourceComponent> Source;
    bool bSelectionMade = false;
    bool bWaitingToSend = false;
    bool bRequestInFlight = false;
    bool bArmed = false;
    bool bFinished = false;
    bool bFailed = false;
    double SendFinishedAt = -1.;
    void QueueCurrent();
    bool IsSending() const;
    UFUNCTION()
    void HandleStarted();
    UFUNCTION()
    void HandleEnded();
};
