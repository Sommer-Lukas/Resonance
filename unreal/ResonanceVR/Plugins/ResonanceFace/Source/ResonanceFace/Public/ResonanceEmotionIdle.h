// First-party, deterministic expression scheduling. Independent of Unreal for replay tests.
#pragma once
#include <array>
#include <algorithm>
#include <cmath>
#include <cstdint>
#include <deque>

namespace ResonanceFace
{
constexpr int EmotionCount = 10;
constexpr int CurveCount = 23;
using Scores = std::array<float, EmotionCount>;
using Curves = std::array<float, CurveCount>;
// SDK remapped order. These are animation control scores, not probabilities.
inline constexpr const char* EmotionNames[] = {"amazement", "anger", "cheekiness", "disgust", "fear",
    "grief", "joy", "outofbreath", "pain", "sadness", "neutral"};
inline constexpr const char* CurveNames[] = {
    "EyeBlinkLeft", "EyeBlinkRight", "EyeWideLeft", "EyeWideRight", "EyeSquintLeft", "EyeSquintRight",
    "BrowInnerUp", "BrowOuterUpLeft", "BrowOuterUpRight", "BrowDownLeft", "BrowDownRight",
    "CheekSquintLeft", "CheekSquintRight", "NoseSneerLeft", "NoseSneerRight",
    "EyeLookDownLeft", "EyeLookDownRight", "EyeLookUpLeft", "EyeLookUpRight",
    "EyeLookInLeft", "EyeLookOutRight", "EyeLookOutLeft", "EyeLookInRight"};

struct Profile
{
    float Inner, OuterLeft, OuterRight, Down, Wide, Squint, Cheek, Nose;
    float EyeDown, EyeUp, EyeRange, PauseMin, PauseMax;
};
inline constexpr Profile Profiles[11] = {
    {.30f,.38f,.38f,.00f,.22f,.00f,.01f,.00f, .00f,.025f,.055f,2.4f,4.7f}, // amazement
    {.02f,.01f,.01f,.38f,.00f,.18f,.05f,.04f, .00f,.000f,.025f,3.2f,5.8f}, // anger
    {.06f,.26f,.10f,.03f,.01f,.10f,.12f,.00f, .00f,.000f,.060f,2.6f,4.8f}, // cheekiness
    {.02f,.04f,.04f,.24f,.00f,.20f,.10f,.28f, .02f,.000f,.035f,3.0f,5.4f}, // disgust
    {.27f,.21f,.21f,.12f,.23f,.02f,.00f,.00f, .00f,.015f,.070f,1.8f,3.8f}, // fear
    {.38f,.03f,.03f,.13f,.00f,.12f,.03f,.00f, .07f,.000f,.025f,3.8f,6.4f}, // grief
    {.04f,.12f,.12f,.00f,.00f,.13f,.24f,.00f, .00f,.010f,.055f,2.8f,5.2f}, // joy
    {.13f,.11f,.11f,.04f,.07f,.04f,.02f,.00f, .03f,.000f,.040f,3.1f,5.5f}, // out of breath
    {.18f,.04f,.04f,.27f,.00f,.28f,.12f,.09f, .04f,.000f,.025f,3.5f,5.8f}, // pain
    {.29f,.03f,.03f,.10f,.00f,.08f,.02f,.00f, .055f,.00f,.030f,3.8f,6.6f}, // sadness
    {.025f,.025f,.025f,.00f,.00f,.015f,.015f,.00f, .00f,.00f,.040f,3.0f,5.8f} // neutral
};
inline float Unit(float x) { return std::isfinite(x) ? std::clamp(x, 0.f, 1.f) : 0.f; }
inline float Smooth(float x) { x = Unit(x); return x*x*(3.f-2.f*x); }

// Three authored accents per dimension (including neutral). Pitch/yaw/roll are
// degrees in a rig-independent frame; the adapter maps them onto the head bone.
struct Variant { float Brow, Lid, Cheek, Nose, EyeX, EyeY, Pitch, Yaw, Roll; };
inline constexpr Variant Variants[11][3] = {
    {{.16f,.08f,0,0,0,.03f,-2,0,0},{.05f,.15f,0,0,.04f,.02f,-1,2,1},{.10f,.04f,0,0,0,0,-1,-2,-1}},
    {{.18f,.12f,0,.04f,0,0,2,0,0},{.10f,.18f,.03f,.06f,.015f,0,1,3,-1},{.22f,.06f,0,.02f,0,0,3,-2,0}},
    {{.16f,.07f,.10f,0,.05f,0,0,2,2},{.08f,.12f,.07f,0,-.04f,0,1,-2,-2},{.20f,.04f,.04f,0,0,0,-1,0,1}},
    {{.12f,.14f,.04f,.16f,0,-.02f,1,2,0},{.08f,.08f,.10f,.20f,-.04f,0,-1,-3,1},{.16f,.18f,0,.10f,0,0,1,0,-1}},
    {{.18f,.10f,0,0,.06f,0,-1,2,1},{.12f,.16f,0,0,-.05f,0,0,-2,-1},{.22f,.04f,0,0,0,-.03f,1,0,0}},
    {{.18f,.10f,0,0,0,-.06f,3,0,1},{.10f,.16f,.02f,0,-.025f,-.04f,2,-1,-1},{.22f,.06f,0,0,0,-.02f,1,0,0}},
    {{.06f,.10f,.20f,0,0,0,-1,0,1},{.12f,.06f,.14f,0,.03f,0,0,2,2},{.04f,.14f,.24f,0,0,0,-1,-2,-1}},
    {{.08f,.06f,.02f,0,0,-.02f,1,0,0},{.12f,.10f,0,0,.025f,0,-1,1,1},{.04f,.14f,.03f,0,0,-.03f,2,-1,0}},
    {{.14f,.20f,.10f,.08f,0,-.03f,2,0,-1},{.08f,.24f,.06f,.12f,-.02f,0,1,-2,1},{.20f,.14f,.12f,.04f,0,-.02f,2,1,0}},
    {{.16f,.10f,0,0,0,-.05f,2,0,1},{.10f,.14f,.02f,0,-.03f,-.03f,2,-1,-1},{.20f,.06f,0,0,0,0,1,0,0}},
    {{.015f,.02f,.02f,0,0,0,0,1,.5f},{.025f,.015f,0,0,-.02f,0,.5f,-1,-.5f},{.01f,.025f,.01f,0,0,-.01f,0,0,.5f}}
};
// Relative motion activity and blink timing are artistic starting points.
inline constexpr float Activity[11] = {1.1f,1.6f,1.1f,.9f,1.2f,.45f,1.f,.7f,.6f,.5f,.45f};
inline constexpr float BlinkPauses[11][2] = {{2.8f,5.5f},{3.8f,6.5f},{2.6f,5.f},{3.2f,5.8f},
    {2.f,4.f},{3.8f,6.5f},{2.8f,5.2f},{2.8f,5.f},{3.2f,5.8f},{3.6f,6.2f},{3.f,5.8f}};

inline int EmotionIndex(const char* Name)
{
    if (!Name) return -1;
    const auto Equal=[](const char* A,const char* B) { while (*A && *A==*B) { ++A; ++B; } return *A==*B; };
    if (Equal(Name,"angry")) return 1;
    if (Equal(Name,"happy")) return 6;
    if (Equal(Name,"sad")) return 9;
    for (int i=0;i<11;++i) if (Equal(Name,EmotionNames[i])) return i;
    return -1;
}

class IdleState
{
public:
    Scores Target{}, Smoothed{};
    Curves Output{};
    float Neutral = 1.f;
    float EyeX = 0.f, EyeY = 0.f;
    double Time = 0.0;
    std::array<float,3> Head{};
    float Blink = 0.f;
    int VariantIndex = 0;
    // -1 schedules all three variants; 0..2 hold a variant for repeatable previews.
    int ForcedVariant = -1;
    float ExpressionStrength = 1.3f;
    float VariantTransitionSeconds = .18f;
    void SetScores(const Scores& Values)
    {
        Pending.clear();
        for (int i=0; i<EmotionCount; ++i) Target[i] = Unit(Values[i]);
        LastObserved=Target;
    }
    // The adapter has already selected playback-aligned scores. Delay only the
    // expression target, never audio/articulation or a manual preview.
    void SetPlaybackScores(const Scores& Values,float DelaySeconds=.12f)
    {
        Scores Clean{};
        for (int i=0;i<EmotionCount;++i) Clean[i]=Unit(Values[i]);
        if (Clean==LastObserved) return;
        LastObserved=Clean;
        const float Delay=std::isfinite(DelaySeconds) ? std::clamp(DelaySeconds,0.f,.5f) : .12f;
        // Keep chronological order even if the delay is edited while playing.
        const double Due=std::max(Time+Delay,Pending.empty() ? Time : Pending.back().Due);
        if (Pending.size()>=256) Pending.back()={Due,Clean};
        else Pending.push_back({Due,Clean});
    }
    void ResetPlaybackTiming() { Pending.clear(); LastObserved=Target; }
    void Update(float DeltaTime, float TransitionSeconds = .3f)
    {
        if (!std::isfinite(DeltaTime) || DeltaTime <= 0.f) return;
        // Substeps retain bounded movement and stable scheduling during editor hitches.
        float Remaining = std::min(DeltaTime, 1.f);
        while (Remaining > 0.f)
        {
            const float Dt = std::min(Remaining, 1.f/60.f);
            Step(Dt, std::isfinite(TransitionSeconds) ? std::clamp(TransitionSeconds,.15f,4.f) : .3f);
            Remaining -= Dt;
        }
    }
private:
    struct PendingScore { double Due; Scores Values; };
    std::deque<PendingScore> Pending;
    Scores LastObserved{};
    uint32_t RandomState = 12491;
    double NextEye = 1.6, NextVariation = 2.2, NextHead = 1.2, NextBlink = 2.1, BlinkStart = -10.;
    float EyeTargetX = 0.f, EyeTargetY = 0.f, BlinkDuration = .28f;
    std::array<float,3> HeadTarget{}, Accent{};
    float Random()
    {
        RandomState ^= RandomState << 13;
        RandomState ^= RandomState >> 17;
        RandomState ^= RandomState << 5;
        return float(RandomState & 0xffffffu) / float(0x1000000u);
    }
    void Step(float Dt, float TransitionSeconds)
    {
        Time += Dt;
        while (!Pending.empty() && Pending.front().Due<=Time)
        {
            Target=Pending.front().Values;
            Pending.pop_front();
        }
        const float Blend = 1.f-std::exp(-Dt/TransitionSeconds);
        float Sum=0.f;
        for (int i=0;i<EmotionCount;++i)
        {
            Smoothed[i] += (Target[i]-Smoothed[i])*Blend;
            Sum += Smoothed[i];
        }
        // Preserve low-intensity signals. Normalize only overlapping scores above one.
        Neutral = std::max(0.f, 1.f-Sum);
        const float Divisor = std::max(1.f, Sum);
        std::array<float,11> Weights{};
        for (int i=0;i<EmotionCount;++i) Weights[i] = Smoothed[i]/Divisor;
        Weights[10] = Neutral;
        if (Time >= NextVariation)
        {
            // Choose either of the other variants; never immediately repeat.
            VariantIndex=(VariantIndex+1+int(Random()*2.f))%3;
            NextVariation=Time+3.5+Random()*4.;
        }
        const int Selected=ForcedVariant>=0 && ForcedVariant<3 ? ForcedVariant : VariantIndex;
        float Brow=0, Lid=0, Cheek=0, Nose=0, BiasX=0, BiasY=0, Motion=0, BlinkMin=0, BlinkMax=0;
        std::array<float,3> Desired{};
        for (int i=0;i<11;++i)
        {
            const auto& V=Variants[i][Selected]; const float W=Weights[i];
            Brow+=W*V.Brow; Lid+=W*V.Lid; Cheek+=W*V.Cheek; Nose+=W*V.Nose;
            BiasX+=W*V.EyeX; BiasY+=W*V.EyeY; Motion+=W*Activity[i];
            Desired[0]+=W*V.Pitch; Desired[1]+=W*V.Yaw; Desired[2]+=W*V.Roll;
            BlinkMin+=W*BlinkPauses[i][0]; BlinkMax+=W*BlinkPauses[i][1];
        }
        if (Time>=NextHead)
        {
            for (int i=0;i<3;++i) Accent[i]=(2.f*Random()-1.f)*(i==1 ? 1.4f : .7f);
            NextHead=Time+1.4+Random()*2.8;
        }
        for (int i=0;i<3;++i)
        {
            HeadTarget[i]=Desired[i]+Accent[i]*Motion;
            Head[i]+=(HeadTarget[i]-Head[i])*(1.f-std::exp(-Dt/(.65f+.3f/(Motion+.2f))));
        }
        if (Time>=NextBlink)
        {
            BlinkStart=Time; BlinkDuration=.25f+Random()*.08f;
            NextBlink=Time+BlinkMin+Random()*(BlinkMax-BlinkMin);
        }
        const float Phase=float(Time-BlinkStart)/BlinkDuration;
        Blink=Smooth(Phase/.22f)*(1.f-Smooth((Phase-.32f)/.68f));
        float Range=0.f, Down=0.f, Up=0.f, PauseMin=0.f, PauseMax=0.f;
        Output.fill(0.f);
        for (int i=0;i<11;++i)
        {
            const auto& P=Profiles[i]; const float W=Weights[i];
            Output[2]+=W*P.Wide; Output[3]+=W*P.Wide;
            Output[4]+=W*P.Squint; Output[5]+=W*P.Squint;
            Output[6]+=W*P.Inner; Output[7]+=W*P.OuterLeft; Output[8]+=W*P.OuterRight;
            Output[9]+=W*P.Down; Output[10]+=W*P.Down;
            Output[11]+=W*P.Cheek; Output[12]+=W*P.Cheek;
            Output[13]+=W*P.Nose; Output[14]+=W*P.Nose;
            Range+=W*P.EyeRange; Down+=W*P.EyeDown; Up+=W*P.EyeUp;
            PauseMin+=W*P.PauseMin; PauseMax+=W*P.PauseMax;
        }
        // Discrete targets with stationary holds, rather than continuous eye oscillation.
        if (Time >= NextEye)
        {
            const bool Center = Random() < .55f;
            EyeTargetX = Center ? 0.f : (2.f*Random()-1.f)*Range;
            EyeTargetY = Center ? 0.f : (2.f*Random()-1.f)*Range*.5f;
            NextEye = Time + PauseMin + Random()*(PauseMax-PauseMin);
        }
        const float EyeBlend=1.f-std::exp(-Dt/.12f);
        EyeX+=(EyeTargetX+BiasX-EyeX)*EyeBlend;
        EyeY+=(EyeTargetY+Up-Down+BiasY-EyeY)*EyeBlend;
        Output[15]=Output[16]=std::max(0.f,-EyeY);
        Output[17]=Output[18]=std::max(0.f,EyeY);
        // Conjugate horizontal eye movements: left-in pairs with right-out.
        Output[19]=Output[20]=std::max(0.f,EyeX);
        Output[21]=Output[22]=std::max(0.f,-EyeX);
        for (int i=2;i<15;++i)
        {
            const float Change=i<=5 ? Lid : (i<=10 ? Brow : (i<=12 ? Cheek : Nose));
            const float DesiredCurve=Unit(Output[i]*std::clamp(ExpressionStrength,0.f,2.f)*(1.f+Change));
            // Smooth the variant itself as well as emotion transitions.
            const float VariantTime=std::isfinite(VariantTransitionSeconds) ?
                std::clamp(VariantTransitionSeconds,.08f,1.f) : .18f;
            HeldCurves[i]+=(DesiredCurve-HeldCurves[i])*(1.f-std::exp(-Dt/VariantTime));
            Output[i]=HeldCurves[i];
        }
    }
    Curves HeldCurves{};
};

// Only owned upper-face curves enter this function. Mouth, jaw and head pass through.
inline float Fuse(float Model, float Idle, float IdleWeight, float Blink, int CurveIndex,
                  float Showcase, float ShowcaseWeight)
{
    float Value=Unit(Model)*(1.f-Unit(IdleWeight))+Unit(Idle)*Unit(IdleWeight);
    const float Close=Unit(Blink);
    if (CurveIndex<2) Value=Value+(1.f-Value)*Close;
    else if (CurveIndex<6) Value*=1.f-Close;
    Value=Value*(1.f-Unit(ShowcaseWeight))+Unit(Showcase)*Unit(ShowcaseWeight);
    return Unit(Value);
}
}
