// Deterministic head performance, optionally cued by audible speech and pauses.
#pragma once
#include <algorithm>
#include <array>
#include <cmath>
#include <cstdint>

namespace ResonanceFace
{
struct HeadStyle
{
    float Pitch, Yaw, Roll, TravelMin, TravelMax, HoldMin, HoldMax, ReturnChance;
};
// Artistic timings in seconds and amplitudes in degrees. Keep emotion-specific
// holds as well as amplitudes: anger should not simply be faster random noise.
inline constexpr HeadStyle HeadStyles[11] = {
    {1.20f,1.60f,.65f, .85f,1.65f,1.0f,2.8f,.48f}, // amazement
    {1.25f,1.80f,.50f, .75f,1.35f,1.1f,3.0f,.65f}, // anger: focused returns
    {.80f,1.40f,.95f, 1.0f,1.9f,.8f,2.8f,.35f}, // cheekiness
    {1.05f,1.50f,.75f, 1.1f,2.0f,1.2f,3.2f,.48f}, // disgust
    {1.05f,1.60f,.65f, .9f,1.7f,.9f,2.7f,.55f}, // fear
    {.95f,1.25f,.60f, 1.8f,3.0f,1.8f,4.5f,.65f}, // grief
    {.85f,1.45f,.85f, 1.0f,1.9f,.8f,2.7f,.38f}, // joy
    {1.00f,1.30f,.60f, 1.3f,2.3f,1.0f,3.0f,.55f}, // out of breath
    {1.00f,1.30f,.65f, 1.4f,2.5f,1.4f,3.6f,.60f}, // pain
    {1.05f,1.30f,.65f, 1.7f,2.8f,1.6f,4.2f,.60f}, // sadness
    {.80f,1.35f,.65f, 1.1f,2.0f,.8f,2.8f,.45f}  // neutral
};

class HeadIdle
{
public:
    enum class Gesture { Settle, Lift, Dip, Turn, Tilt, Nod };
    std::array<float,3> Position{}, Velocity{};
    Gesture ActiveGesture=Gesture::Settle;
    float ExpressionAccent=0.f;
    // Diagnostics for replay tests; a new shift begins only after its hold.
    int ShiftCount=0;
    double TravelSeconds=0., HoldSeconds=0.;
    bool UseSpeechTiming=false, PlaybackActive=false, HasEnvelope=false, SpeechVoiced=false;
    float Envelope=0.f;
    int SpeechCueCount=0;
    int QuietAdjustmentCount=0;
    float SpeechMotionScale=1.5f,QuietMotionScale=1.f,QuietIntervalSeconds=8.f;
    void SetSeed(uint32_t Value) { Seed=Value ? Value : 7919; QuietSeed=Seed^0x9e3779b9u; if (!QuietSeed) QuietSeed=3571; }

    void Update(float Dt,const std::array<float,11>& Weights,const std::array<float,3>& Pose)
    {
        if (!std::isfinite(Dt) || Dt<=0.f) return;
        float Remaining=std::min(Dt,1.f);
        while (Remaining>0.f)
        {
            const float DtStep=std::min(Remaining,1.f/60.f);
            Advance(DtStep,Weights,Pose);
            Remaining-=DtStep;
        }
    }
private:
    void Advance(float Step,const std::array<float,11>& Weights,const std::array<float,3>& Pose)
    {
        // Head scheduling has its own RNG,
        // so changing it never reorders eye/blink/expression random samples.
        Time+=Step;
        if (!UseSpeechTiming) RecoverSpeech=false;
        const float Level=std::isfinite(Envelope) ? std::clamp(Envelope,0.f,1.f) : 0.f;
        Peak=std::max(Level,Peak*std::exp(-Step/4.f));
        const float Threshold=std::max(.003f,Peak*(SpeechVoiced ? .08f : .16f));
        const bool VoiceNow=PlaybackActive && (!HasEnvelope || Level>Threshold);
        if (PlaybackActive && !WasPlaybackActive) FirstPhrase=true;
        WasPlaybackActive=PlaybackActive;
        if (VoiceNow) { VoicedFor+=Step; QuietFor=0.f; }
        else { QuietFor+=Step; VoicedFor=0.f; }
        bool Onset=false,Pause=false;
        if (!SpeechVoiced && VoicedFor>=.1f)
        { SpeechVoiced=true; Onset=true; PhraseFor=0.f; }
        if (SpeechVoiced) PhraseFor+=Step;
        if (SpeechVoiced && QuietFor>=.35f)
        { SpeechVoiced=false; Pause=PhraseFor>=.8f; }
        const bool OpeningOnset=Onset && FirstPhrase;
        FastEnergy+=(Level-FastEnergy)*(1.f-std::exp(-Step/.25f));
        SlowEnergy+=(Level-SlowEnergy)*(1.f-std::exp(-Step/.95f));
        const bool Prominent=HasEnvelope && SpeechVoiced && PhraseFor>1.f &&
            FastEnergy>SlowEnergy*1.45f && FastEnergy>Peak*.4f;
        const bool Emphasis=Prominent && !WasProminent;
        WasProminent=Prominent;
        bool SpeechRequest=false;
        if (UseSpeechTiming && Time>=NextSpeechCue && (Onset || Pause || Emphasis))
        {
            const bool Select=Random()<(Emphasis ? .8f : (Onset ? .65f : .4f));
            SpeechRequest=OpeningOnset || Select;
            if (Onset) FirstPhrase=false;
        }
        HeadStyle Style{};
        for (int i=0;i<11;++i)
        {
            const float W=Weights[i]; const auto& S=HeadStyles[i];
            Style.Pitch+=W*S.Pitch; Style.Yaw+=W*S.Yaw; Style.Roll+=W*S.Roll;
            Style.TravelMin+=W*S.TravelMin; Style.TravelMax+=W*S.TravelMax;
            Style.HoldMin+=W*S.HoldMin; Style.HoldMax+=W*S.HoldMax;
            Style.ReturnChance+=W*S.ReturnChance;
        }
        const float QuietScale=std::isfinite(QuietMotionScale) ? std::clamp(QuietMotionScale,0.f,2.f) : 1.f;
        const float Interval=std::isfinite(QuietIntervalSeconds) ? std::clamp(QuietIntervalSeconds,2.f,30.f) : 8.f;
        if (NextQuietShift<0.) NextQuietShift=Time+2.-std::log(std::max(.0001f,1.f-QuietRandom()))*Interval;
        bool QuietRequest=false;
        if (UseSpeechTiming && !SpeechRequest && !SpeechVoiced && QuietFor>.8f &&
            Time>=NextQuietShift && Time>Started+TravelSeconds+.8)
        {
            NextQuietShift=Time+2.-std::log(std::max(.0001f,1.f-QuietRandom()))*
                Interval*(Style.HoldMin+Style.HoldMax)/4.f;
            QuietRequest=QuietScale>0.f && QuietRandom()>.15f;
        }
        if (UseSpeechTiming ? (SpeechRequest || QuietRequest) : Time>=NextShift)
        {
            From=Accent; To.fill(0.f);
            ActiveGesture=Gesture::Settle;
            const auto Pick=[&]() { return QuietRequest ? QuietRandom() : Random(); };
            const float Sign=Pick()<.5f ? -1.f : 1.f;
            float Size=.8f+Pick()*.2f;
            if (SpeechRequest)
                Size*=std::isfinite(SpeechMotionScale) ? std::clamp(SpeechMotionScale,0.f,2.f) : 1.5f;
            if (QuietRequest)
            {
                // Mostly small changes, with occasional larger adjustments.
                // This is not a repeating small/big/return sequence.
                Size=(Pick()<.2f ? 1.f+Pick()*.3f : .6f+Pick()*.3f)*QuietScale;
            }
            float Kind=SpeechRequest && Pause ? 0.f : Pick();
            if (SpeechRequest && (Onset || Emphasis) && (OpeningOnset || DistanceSquared(From,{})<.025f))
                Kind=1.f; // A selected speech onset must not be a zero-length return.
            if (QuietRequest && DistanceSquared(From,{})<.025f)
                Kind=1.f; // Quiet opportunities can be skipped above; selected ones should be visible.
            if (Kind>=Style.ReturnChance)
            {
                // Speaking cues favor a visible dip/turn rather than a tiny
                // roll that disappears in a front-facing portrait.
                const float PitchBias=.45f+Weights[5]*.25f+Weights[9]*.25f+Weights[0]*.2f;
                const float Direction=Pick();
                const bool Nod=SpeechRequest && Emphasis && !OpeningOnset && Direction<.24f;
                const int Axis=Nod ? 0 : (SpeechRequest ?
                    (Direction<PitchBias ? 0 : (Direction>.92f && !OpeningOnset ? 2 : 1)) :
                    std::min(2,int(Direction*3.f)));
                if (Axis==0)
                {
                    const float DownChance=.5f+.25f*Weights[9]+.3f*Weights[5]+.15f*Weights[8]-.25f*Weights[0]-.1f*Weights[4];
                    const bool Down=Pick()<DownChance;
                    ActiveGesture=Nod ? Gesture::Nod : (Down ? Gesture::Dip : Gesture::Lift);
                    To[0]=(Down || Nod ? 1.f : -1.f)*Style.Pitch*Size*(Nod ? .72f : 1.f);
                    To[1]=(2.f*Pick()-1.f)*Style.Yaw*.18f;
                }
                else if (Axis==1) // Turn with a restrained coupled tilt.
                {
                    ActiveGesture=Gesture::Turn;
                    To[1]=Sign*Style.Yaw*Size;
                    To[2]=-Sign*Style.Roll*Size*.25f;
                    To[0]=(2.f*Pick()-1.f)*Style.Pitch*.2f;
                }
                else
                {
                    ActiveGesture=Gesture::Tilt;
                    To[2]=Sign*Style.Roll*Size;
                    To[1]=Sign*Style.Yaw*Size*.25f;
                }
                // Sample a continuous direction, rather than the same pitch/
                // yaw/roll spokes. The original axis remains the main accent,
                // with independently varied support on the other two axes.
                const float Azimuth=Pick()*6.2831853f;
                const float Vertical=2.f*Pick()-1.f;
                const float Radial=std::sqrt(std::max(0.f,1.f-Vertical*Vertical));
                To[0]+=.48f*Style.Pitch*Size*Vertical;
                To[1]+=.48f*Style.Yaw*Size*Radial*std::cos(Azimuth);
                To[2]+=.65f*Style.Roll*Size*Radial*std::sin(Azimuth);
                if (SpeechRequest && OpeningOnset)
                {
                    const float Scale=std::isfinite(SpeechMotionScale) ? std::clamp(SpeechMotionScale,0.f,2.f) : 1.5f;
                    To[Axis]=(To[Axis]>=0.f ? 1.f : -1.f)*std::max(std::abs(To[Axis]),(Axis==1 ? 1.5f : 1.2f)*Scale);
                }
            }
            // A different bowed path for each excursion. This vanishes with
            // zero velocity at both endpoints, including a return to center.
            const float Distance=std::sqrt(DistanceSquared(From,To));
            for (int i=0;i<3;++i)
                Arc[i]=(2.f*Pick()-1.f)*std::min(.65f,Distance*.30f);
            TravelSeconds=Style.TravelMin+Pick()*(Style.TravelMax-Style.TravelMin);
            if (SpeechRequest) TravelSeconds*=.65;
            if (QuietRequest) TravelSeconds*=1.15;
            if (ActiveGesture==Gesture::Nod) TravelSeconds=std::clamp(TravelSeconds,.5,.75);
            if (ActiveGesture==Gesture::Tilt) TravelSeconds*=1.2;
            // A deadline is permission to reconsider, not an instruction to
            // move. Exponential pauses avoid a recurring bounded idle cadence.
            HoldSeconds=Style.HoldMin-std::log(std::max(.0001f,1.f-Pick()))*
                (Style.HoldMax-Style.HoldMin)*2.f;
            Started=Time;
            NextShift=Time+TravelSeconds+HoldSeconds;
            const bool Visible=DistanceSquared(From,To)>.025f;
            if (SpeechRequest)
            {
                NextSpeechCue=Time+TravelSeconds+1.4+Random()*1.4;
                NextQuietShift=std::max(NextQuietShift,Time+TravelSeconds+3.);
                // Speech is an excursion with a varied hold and slower recovery,
                // not a new pose held until another event happens to arrive.
                const double Hold=.2+Random()*.55;
                RecoveryStart=Time+TravelSeconds+(ActiveGesture==Gesture::Nod ? .06 :
                    (ActiveGesture==Gesture::Tilt ? Hold+.45 : Hold));
                RecoverySeconds=.8+Random()*1.1;
                if (ActiveGesture==Gesture::Nod) RecoverySeconds*=.65;
                RecoverSpeech=true;
                if (Visible) ++SpeechCueCount;
            }
            if (QuietRequest)
            {
                RecoverSpeech=false;
                NextQuietShift=std::max(NextQuietShift,Time+TravelSeconds+2.);
                if (Visible) ++QuietAdjustmentCount;
            }
            if (Visible) ++ShiftCount;
        }
        const float Blend=Ease(float((Time-Started)/std::max(.5,TravelSeconds)));
        const float Recovery=RecoverSpeech ? 1.f-Ease(float((Time-RecoveryStart)/RecoverySeconds)) : 1.f;
        // A facial accent leads the slower head gesture and eases away once
        // the gesture settles. Both share the same accepted cue.
        const float Age=float(Time-Started);
        ExpressionAccent=RecoverSpeech && ActiveGesture!=Gesture::Settle ?
            Ease(Age/.18f)*(1.f-Ease((Age-.18f)/float(TravelSeconds+.25))) : 0.f;
        if (Time>=NextDrift)
        {
            DriftFrom=Drift;
            for (int i=0;i<3;++i) DriftTo[i]=(2.f*Random()-1.f)*(i==1 ? .30f : .18f);
            DriftStarted=Time; DriftDuration=4.5+Random()*4.;
            NextDrift=Time+DriftDuration+1.+Random()*2.;
        }
        const float DriftBlend=Ease(float((Time-DriftStarted)/DriftDuration));
        for (int i=0;i<3;++i)
        {
            const float Bow=16.f*Blend*Blend*(1.f-Blend)*(1.f-Blend);
            Accent[i]=(From[i]+(To[i]-From[i])*Blend+Arc[i]*Bow)*Recovery;
            Drift[i]=DriftFrom[i]+(DriftTo[i]-DriftFrom[i])*DriftBlend;
            const float Goal=Pose[i]+Accent[i]*1.15f+Drift[i];
            // Damped acceleration preserves momentum across emotion/variant
            // changes. Speed and acceleration limits prevent a sudden whip.
            const float Omega=5.f;
            const float Accel=std::clamp(Omega*Omega*(Goal-Position[i])-2.f*Omega*Velocity[i],-18.f,18.f);
            const float Previous=Velocity[i];
            Velocity[i]=std::clamp(Velocity[i]+Accel*Step,-6.f,6.f);
            Position[i]+=(Previous+Velocity[i])*.5f*Step;
        }
    }
private:
    uint32_t Seed=7919;
    double Time=0., NextShift=.6, Started=0., NextDrift=.2, DriftStarted=0., DriftDuration=5.;
    double NextSpeechCue=0.;
    double NextQuietShift=-1.;
    uint32_t QuietSeed=3571;
    float Peak=.02f,VoicedFor=0.f,QuietFor=0.f,PhraseFor=0.f;
    bool WasPlaybackActive=false,FirstPhrase=true;
    float FastEnergy=0.f,SlowEnergy=0.f;
    bool WasProminent=false,RecoverSpeech=false;
    double RecoveryStart=0.,RecoverySeconds=1.;
    std::array<float,3> Accent{}, From{}, To{}, Arc{}, Drift{}, DriftFrom{}, DriftTo{};
    float Random()
    {
        Seed^=Seed<<13; Seed^=Seed>>17; Seed^=Seed<<5;
        return float(Seed & 0xffffffu)/float(0x1000000u);
    }
    float QuietRandom()
    {
        QuietSeed^=QuietSeed<<13; QuietSeed^=QuietSeed>>17; QuietSeed^=QuietSeed<<5;
        return float(QuietSeed & 0xffffffu)/float(0x1000000u);
    }
    static float Ease(float X)
    {
        X=std::clamp(X,0.f,1.f);
        return X*X*X*(10.f+X*(-15.f+6.f*X)); // zero speed/acceleration at each end
    }
    static float DistanceSquared(const std::array<float,3>& A,const std::array<float,3>& B)
    {
        float Value=0.f;
        for (int i=0;i<3;++i) Value+=(A[i]-B[i])*(A[i]-B[i]);
        return Value;
    }
};
}
