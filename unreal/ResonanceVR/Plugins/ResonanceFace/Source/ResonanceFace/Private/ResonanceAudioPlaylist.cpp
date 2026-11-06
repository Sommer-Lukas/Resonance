#include "ResonanceAudioPlaylist.h"
#include "ACEAudioCurveSourceComponent.h"
#include "Engine/Engine.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "GameFramework/Actor.h"
#include "HAL/FileManager.h"
#include "Misc/Paths.h"
#include "UObject/UnrealType.h"

UResonanceAudioPlaylist::UResonanceAudioPlaylist()
{ PrimaryComponentTick.bCanEverTick=true; }

void UResonanceAudioPlaylist::BeginPlay()
{
    Super::BeginPlay();
    Source=GetOwner()->FindComponentByClass<UACEAudioCurveSourceComponent>();
    if (Source)
    {
        Source->OnAnimationStarted.AddDynamic(this,&UResonanceAudioPlaylist::HandleStarted);
        Source->OnAnimationEnded.AddDynamic(this,&UResonanceAudioPlaylist::HandleEnded);
    }
}
void UResonanceAudioPlaylist::EndPlay(const EEndPlayReason::Type Reason)
{
    bArmed=bWaitingToSend=bRequestInFlight=bPlaylistActive=false;
    if (Source)
    {
        Source->OnAnimationStarted.RemoveDynamic(this,&UResonanceAudioPlaylist::HandleStarted);
        Source->OnAnimationEnded.RemoveDynamic(this,&UResonanceAudioPlaylist::HandleEnded);
    }
    Super::EndPlay(Reason);
}
bool UResonanceAudioPlaylist::IsSending() const
{
    const auto* Property=FindFProperty<FBoolProperty>(GetOwner()->GetClass(),TEXT("FaceAudioSending"));
    return Property && Property->GetPropertyValue_InContainer(GetOwner());
}
void UResonanceAudioPlaylist::QueueCurrent()
{
    bArmed=false;
    bRequestInFlight=false;
    bWaitingToSend=true;
    bFinished=bFailed=false;
    SendFinishedAt=-1.;
    // A newer key replaces the old playlist. Stop its playback immediately,
    // then wait for the existing Blueprint send lock to clear before submitting.
    if (auto* Queue=FindFProperty<FBoolProperty>(GetOwner()->GetClass(),TEXT("FaceAudioReplayQueued")))
        Queue->SetPropertyValue_InContainer(GetOwner(),false);
    if (Source) Source->Stop();
}
void UResonanceAudioPlaylist::PlayBaseOnce()
{
    // A key pressed during the initial two-second delay takes precedence.
    if (bSelectionMade) return;
    bSelectionMade=true;
    ActiveSet=0;
    MixIndex=0;
    bPlaylistActive=false;
    RequestedAudioPath=TEXT("Resonance/Audio/voice_test.wav");
    QueueCurrent();
}
bool UResonanceAudioPlaylist::StartSet(int32 Set)
{
    if (Set<1 || Set>5 || !Source) return false;
    for (int Index=1;Index<=3;++Index)
    {
        const FString Relative=FString::Printf(TEXT("Resonance/Audio/MixedEmotionSets/key_%d_mix_%02d.wav"),Set,Index);
        if (!IFileManager::Get().FileExists(*(FPaths::ProjectContentDir()/Relative)))
        {
            UE_LOG(LogTemp,Error,TEXT("Resonance playlist missing %s"),*Relative);
            return false;
        }
    }
    bSelectionMade=true;
    ActiveSet=Set;
    MixIndex=0;
    CompletedMixes=0;
    bPlaylistActive=true;
    RequestedAudioPath=FString::Printf(TEXT("Resonance/Audio/MixedEmotionSets/key_%d_mix_01.wav"),Set);
    QueueCurrent();
    return true;
}
void UResonanceAudioPlaylist::ReplayCurrent()
{ bSelectionMade=true; QueueCurrent(); }
void UResonanceAudioPlaylist::HandleStarted()
{
    if (!bRequestInFlight || bWaitingToSend) return;
    bArmed=true;
    ++PlaybackStarts;
    UE_LOG(LogTemp,Log,TEXT("Resonance playlist audible start: set=%d mix=%d file=%s"),ActiveSet,MixIndex+1,*RequestedAudioPath);
}
void UResonanceAudioPlaylist::HandleEnded()
{
    // StopCharacter also emits an end event. Only a stream observed starting
    // after our own dispatch may advance the current playlist.
    if (!bArmed || bWaitingToSend) return;
    bArmed=false;
    bRequestInFlight=false;
    ++CompletedMixes;
    if (Source) Source->ExportEmotionStream();
    UE_LOG(LogTemp,Log,TEXT("Resonance playlist audible end: set=%d mix=%d"),ActiveSet,MixIndex+1);
    if (bPlaylistActive && MixIndex<2)
    {
        ++MixIndex;
        RequestedAudioPath=FString::Printf(TEXT("Resonance/Audio/MixedEmotionSets/key_%d_mix_%02d.wav"),ActiveSet,MixIndex+1);
        QueueCurrent();
    }
    else
    {
        bPlaylistActive=false;
        bFinished=true;
    }
}
void UResonanceAudioPlaylist::TickComponent(float DeltaTime,ELevelTick Type,FActorComponentTickFunction* Function)
{
    Super::TickComponent(DeltaTime,Type,Function);
    if (bWaitingToSend && !IsSending())
    {
        UFunction* Request=GetOwner()->FindFunction(TEXT("ResonanceRequestAudio"));
        bWaitingToSend=false;
        if (Request && Source)
        {
            bRequestInFlight=true;
            GetOwner()->ProcessEvent(Request,nullptr);
        }
        else { bFailed=true; bPlaylistActive=false; }
    }
    if (bRequestInFlight && !bArmed && !IsSending())
    {
        if (SendFinishedAt<0.) SendFinishedAt=GetWorld()->GetTimeSeconds();
        if (GetWorld()->GetTimeSeconds()-SendFinishedAt>3.)
        {
            bRequestInFlight=bPlaylistActive=false;
            bFailed=true;
            UE_LOG(LogTemp,Error,TEXT("Resonance playlist: audio submission did not start playback"));
        }
    }
    if (GEngine) GEngine->AddOnScreenDebugMessage(0x52657341,.2f,FColor::Cyan,GetStatusText());
}
FString UResonanceAudioPlaylist::GetStatusText() const
{
    const FString Item=ActiveSet ? FString::Printf(TEXT("Set %d | mix %d/3"),ActiveSet,MixIndex+1) : TEXT("Base: voice_test.wav");
    return Item+(bFailed ? TEXT(" | playback failed") : (bFinished ? TEXT(" | finished") : (bWaitingToSend ? TEXT(" | loading") : TEXT(""))))
        +TEXT("\n1-5: play a mixed EmoDB set");
}
bool UResonanceAudioPlaylist::PlayPortraitSet(UObject* WorldContextObject,int32 Set)
{
    UWorld* World=GEngine->GetWorldFromContextObject(WorldContextObject,EGetWorldErrorMode::ReturnNull);
    if (!World) return false;
    for (TActorIterator<AActor> Actor(World);Actor;++Actor)
        if (auto* Playlist=Actor->FindComponentByClass<UResonanceAudioPlaylist>()) return Playlist->StartSet(Set);
    return false;
}
