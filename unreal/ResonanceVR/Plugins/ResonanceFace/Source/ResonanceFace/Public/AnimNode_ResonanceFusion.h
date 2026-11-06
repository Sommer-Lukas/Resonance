#pragma once
#include "CoreMinimal.h"
#include "Animation/AnimNodeBase.h"
#include "AnimNode_ResonanceFusion.generated.h"

/** Sole final ARKit curve authority: ACE + emotion idle + blink + selectable showcase. */
USTRUCT(BlueprintInternalUseOnly)
struct RESONANCEFACE_API FAnimNode_ResonanceFusion : public FAnimNode_Base
{
    GENERATED_BODY()
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category=Links)
    FPoseLink SourcePose;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category=Fusion, meta=(PinShownByDefault))
    float ShowcaseAlpha = 0.f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category=Fusion, meta=(PinShownByDefault))
    float NaturalBlink = 0.f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category=Showcase, meta=(PinShownByDefault))
    float EyeBlinkLeft = 0.f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category=Showcase, meta=(PinShownByDefault))
    float EyeBlinkRight = 0.f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category=Showcase, meta=(PinShownByDefault))
    float EyeWideLeft = 0.f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category=Showcase, meta=(PinShownByDefault))
    float EyeWideRight = 0.f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category=Showcase, meta=(PinShownByDefault))
    float EyeSquintLeft = 0.f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category=Showcase, meta=(PinShownByDefault))
    float EyeSquintRight = 0.f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category=Showcase, meta=(PinShownByDefault))
    float BrowInnerUp = 0.f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category=Showcase, meta=(PinShownByDefault))
    float BrowOuterUpLeft = 0.f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category=Showcase, meta=(PinShownByDefault))
    float BrowOuterUpRight = 0.f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category=Showcase, meta=(PinShownByDefault))
    float BrowDownLeft = 0.f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category=Showcase, meta=(PinShownByDefault))
    float BrowDownRight = 0.f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category=Showcase, meta=(PinShownByDefault))
    float CheekSquintLeft = 0.f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category=Showcase, meta=(PinShownByDefault))
    float CheekSquintRight = 0.f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category=Showcase, meta=(PinShownByDefault))
    float NoseSneerLeft = 0.f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category=Showcase, meta=(PinShownByDefault))
    float NoseSneerRight = 0.f;
    virtual void Initialize_AnyThread(const FAnimationInitializeContext& Context) override;
    virtual void CacheBones_AnyThread(const FAnimationCacheBonesContext& Context) override;
    virtual void Update_AnyThread(const FAnimationUpdateContext& Context) override;
    virtual void Evaluate_AnyThread(FPoseContext& Output) override;
    virtual bool HasPreUpdate() const override { return true; }
    virtual void PreUpdate(const UAnimInstance* Instance) override;
private:
    TMap<FName,float> CachedIdle;
    float IdleWeight = 0.f;
};
