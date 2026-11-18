#include "AnimNode_ResonanceFusion.h"
#include "ACEAudioCurveSourceComponent.h"
#include "ResonanceFaceState.h"
#include "Animation/AnimInstance.h"
#include "Animation/AnimInstanceProxy.h"
#include "GameFramework/Actor.h"
#include "BoneContainer.h"
#include "BonePose.h"

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
    CachedMapping.Reset();
    CachedHeadBone=NAME_None;
    CachedNeckBone=NAME_None;
    CachedHeadRotation=FQuat::Identity;
    bEmotionBlink=false;
    if (AActor* Owner=Instance->GetOwningActor())
    {
        if (auto* State=Owner->FindComponentByClass<UResonanceFaceState>())
        {
            State->UpdateForAnimation(Owner->FindComponentByClass<UACEAudioCurveSourceComponent>(),
                Instance->GetDeltaSeconds());
            CachedIdle=State->IdleCurves;
            IdleWeight=State->CurrentBlend;
            CachedBlink=State->EmotionBlink;
            bEmotionBlink=true;
            if (!bHeadOnly) State->ShowcaseBlend=ShowcaseAlpha;
            CachedShowcase=State->ShowcaseBlend;
            const auto* Rig=State->Calibration.Get();
            if (Rig) CachedMapping=Rig->CurveMapping;
            CachedHeadBone=Rig ? Rig->HeadBone : FName(TEXT("head"));
            CachedNeckBone=Rig ? Rig->NeckBone : FName(TEXT("neck_02"));
            CachedNeckShare=Rig && FMath::IsFinite(Rig->NeckShare) ? FMath::Clamp(Rig->NeckShare,0.f,.4f) : .25f;
            const auto Rotation=[](FVector Axis,double Degrees)
            {
                return Axis.ContainsNaN() || Axis.IsNearlyZero() ? FQuat::Identity :
                    FQuat(Axis.GetSafeNormal(),FMath::DegreesToRadians(Degrees));
            };
            // MetaHuman head's local X is up, Y is forward, Z is lateral.
            CachedHeadRotation=Rotation(Rig ? Rig->YawAxis : FVector(1,0,0),State->HeadDegrees.Y)*
                Rotation(Rig ? Rig->PitchAxis : FVector(0,0,1),State->HeadDegrees.X)*
                Rotation(Rig ? Rig->RollAxis : FVector(0,1,0),State->HeadDegrees.Z);
        }
    }
}
void FAnimNode_ResonanceFusion::Evaluate_AnyThread(FPoseContext& Output)
{
    SourcePose.Evaluate(Output);
    const float Showcase[]={EyeBlinkLeft,EyeBlinkRight,EyeWideLeft,EyeWideRight,EyeSquintLeft,EyeSquintRight,
        BrowInnerUp,BrowOuterUpLeft,BrowOuterUpRight,BrowDownLeft,BrowDownRight,
        CheekSquintLeft,CheekSquintRight,NoseSneerLeft,NoseSneerRight};
    for (int i=0;!bHeadOnly && i<ResonanceFace::CurveCount;++i)
    {
        const FName Canonical(UTF8_TO_TCHAR(ResonanceFace::CurveNames[i]));
        const FName* Mapped=CachedMapping.Find(Canonical);
        const FName Name=Mapped ? *Mapped : Canonical;
        if (Name.IsNone()) continue;
        const float* Idle=CachedIdle.Find(Canonical);
        // Preserve model blinks; the shared procedural scheduler closes the remaining opening.
        const float Weight = !Idle ? 0.f : (i>=15 ? 1.f : IdleWeight);
        const float Value=ResonanceFace::Fuse(Output.Curve.Get(Name),Idle ? *Idle : 0.f,
            Weight,bEmotionBlink ? CachedBlink : NaturalBlink,i,i<15 ? Showcase[i] : 0.f,ShowcaseAlpha);
        Output.Curve.Set(Name,Value);
    }
    // Add local head rotation to the source pose; never rotate the actor or camera.
    if (bHeadOnly && !CachedHeadBone.IsNone())
    {
        FBoneReference Bone;
        Bone.BoneName=CachedHeadBone;
        const FBoneContainer& Bones=Output.Pose.GetBoneContainer();
        Bone.Initialize(Bones);
        if (Bone.IsValidToEvaluate(Bones))
        {
            FTransform& Transform=Output.Pose[Bone.GetCompactPoseIndex(Bones)];
            const FQuat Delta=FQuat::Slerp(FQuat::Identity,CachedHeadRotation,
                1.f-ResonanceFace::Unit(CachedShowcase));
            FBoneReference Neck;
            Neck.BoneName=CachedNeckBone;
            Neck.Initialize(Bones);
            // Never apply a second rotation to the same bone. Optional neck
            // support falls back to the full head rotation at reduced LODs.
            const bool HasNeck=Neck.IsValidToEvaluate(Bones) &&
                Neck.GetCompactPoseIndex(Bones)!=Bone.GetCompactPoseIndex(Bones);
            const float Share=HasNeck ? CachedNeckShare : 0.f;
            if (Share>0.f)
            {
                FTransform& NeckTransform=Output.Pose[Neck.GetCompactPoseIndex(Bones)];
                // The shared calibration axes are in the head's local frame.
                // Map that frame into the neck rather than assuming identical
                // rest orientations on replacement facial skeletons.
                FQuat HeadToNeck=FQuat::Identity;
                FCompactPoseBoneIndex Ancestor=Bone.GetCompactPoseIndex(Bones);
                while (Ancestor.GetInt()!=INDEX_NONE && Ancestor!=Neck.GetCompactPoseIndex(Bones))
                {
                    HeadToNeck=Output.Pose[Ancestor].GetRotation()*HeadToNeck;
                    Ancestor=Bones.GetParentBoneIndex(Ancestor);
                }
                if (Ancestor==Neck.GetCompactPoseIndex(Bones))
                {
                    const FQuat NeckDelta=HeadToNeck*FQuat::Slerp(FQuat::Identity,Delta,Share)*HeadToNeck.Inverse();
                    NeckTransform.SetRotation((NeckTransform.GetRotation()*NeckDelta).GetNormalized());
                    Transform.SetRotation((Transform.GetRotation()*FQuat::Slerp(FQuat::Identity,Delta,1.f-Share)).GetNormalized());
                }
                else Transform.SetRotation((Transform.GetRotation()*Delta).GetNormalized());
            }
            else Transform.SetRotation((Transform.GetRotation()*Delta).GetNormalized());
        }
    }
}
