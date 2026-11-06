// First-party, deterministic expression scheduling. Independent of Unreal for replay tests.
#pragma once
#include <array>
#include <algorithm>
#include <cmath>
#include <cstdint>

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

class IdleState
{
public:
    Scores Target{}, Smoothed{};
    Curves Output{};
    float Neutral = 1.f;
    float EyeX = 0.f, EyeY = 0.f;
    double Time = 0.0;
    void SetScores(const Scores& Values)
    {
        for (int i=0; i<EmotionCount; ++i) Target[i] = Unit(Values[i]);
    }
    void Update(float DeltaTime, float TransitionSeconds = .8f)
    {
        if (!std::isfinite(DeltaTime) || DeltaTime <= 0.f) return;
        // Substeps retain bounded movement and stable scheduling during editor hitches.
        float Remaining = std::min(DeltaTime, 1.f);
        while (Remaining > 0.f)
        {
            const float Dt = std::min(Remaining, 1.f/60.f);
            Step(Dt, std::max(.15f, TransitionSeconds));
            Remaining -= Dt;
        }
    }
private:
    uint32_t RandomState = 12491;
    double NextEye = 1.6, NextVariation = 2.2, VariationStarted = -10.;
    float EyeTargetX = 0.f, EyeTargetY = 0.f, VariationStrength = 0.f;
    int VariationKind = 0;
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
        EyeX+=(EyeTargetX-EyeX)*EyeBlend;
        EyeY+=(EyeTargetY+Up-Down-EyeY)*EyeBlend;
        Output[15]=Output[16]=std::max(0.f,-EyeY);
        Output[17]=Output[18]=std::max(0.f,EyeY);
        // Conjugate horizontal eye movements: left-in pairs with right-out.
        Output[19]=Output[20]=std::max(0.f,EyeX);
        Output[21]=Output[22]=std::max(0.f,-EyeX);
        if (Time >= NextVariation)
        {
            VariationStarted=Time;
            VariationStrength=(2.f*Random()-1.f)*.16f;
            VariationKind=std::min(2,int(Random()*3.f));
            NextVariation=Time+3.5+Random()*4.;
        }
        const float Age=float(Time-VariationStarted);
        const float Pulse=Smooth(Age/.65f)*(1.f-Smooth((Age-1.1f)/1.1f));
        for (int i=2;i<15;++i)
        {
            // Three local variants per profile: brow emphasis, eyelid/cheek relaxation,
            // or a tiny asymmetric brow adjustment. Never a repeating full-face clip.
            const bool Brow=i>=6 && i<=10;
            float Change=0.f;
            if (VariationKind==0 && Brow) Change=VariationStrength*Pulse;
            if (VariationKind==1 && !Brow) Change=VariationStrength*Pulse;
            if (VariationKind==2 && (i==7 || i==8)) Change=VariationStrength*Pulse*(i==7 ? 1.f : -.5f);
            Output[i]=Unit(Output[i]*(1.f+Change));
        }
    }
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
