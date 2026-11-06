#include "AnimNode_ResonanceFusion.h"
#include "ACEAudioCurveSourceComponent.h"
#include "ResonanceFaceState.h"
#include "Animation/AnimInstance.h"
#include "Animation/AnimInstanceProxy.h"
#include "GameFramework/Actor.h"

void FAnimNode_ResonanceFusion::Initialize_AnyThread(const FAnimationInitializeContext& Context)
{
    FAnimNode_Base::Initialize_AnyThread(Context);
    SourcePose.Initialize(Context);
    CachedIdle.Reset();
    IdleWeight=0.f;
}
void FAnimNode_ResonanceFusion::CacheBones_AnyThread(const FAnimationCacheBonesContext& Context)
{ SourcePose.CacheBones(Context); }
void FAnimNode_ResonanceFusion::Update_AnyThread(const FAnimationUpdateContext& Context)
{
    GetEvaluateGraphExposedInputs().Execute(Context);
    SourcePose.Update(Context);
}
void FAnimNode_ResonanceFusion::PreUpdate(const UAnimInstance* Instance)
{
    CachedIdle.Reset();
    IdleWeight=0.f;
    if (AActor* Owner=Instance->GetOwningActor())
    {
        if (auto* State=Owner->FindComponentByClass<UResonanceFaceState>())
        {
            State->UpdateForAnimation(Owner->FindComponentByClass<UACEAudioCurveSourceComponent>(),
                Instance->GetDeltaSeconds());
            CachedIdle=State->IdleCurves;
            IdleWeight=State->CurrentBlend;
        }
    }
}
void FAnimNode_ResonanceFusion::Evaluate_AnyThread(FPoseContext& Output)
{
    SourcePose.Evaluate(Output);
    const float Showcase[]={EyeBlinkLeft,EyeBlinkRight,EyeWideLeft,EyeWideRight,EyeSquintLeft,EyeSquintRight,
        BrowInnerUp,BrowOuterUpLeft,BrowOuterUpRight,BrowDownLeft,BrowDownRight,
        CheekSquintLeft,CheekSquintRight,NoseSneerLeft,NoseSneerRight};
    for (int i=0;i<ResonanceFace::CurveCount;++i)
    {
        const FName Name(UTF8_TO_TCHAR(ResonanceFace::CurveNames[i]));
        const float* Idle=CachedIdle.Find(Name);
        // Preserve model blinks; the shared procedural scheduler closes the remaining opening.
        const float Weight = !Idle ? 0.f : (i<2 ? 0.f : (i>=15 ? 1.f : IdleWeight));
        const float Value=ResonanceFace::Fuse(Output.Curve.Get(Name),Idle ? *Idle : 0.f,
            Weight,NaturalBlink,i,i<15 ? Showcase[i] : 0.f,ShowcaseAlpha);
        Output.Curve.Set(Name,Value);
    }
}
