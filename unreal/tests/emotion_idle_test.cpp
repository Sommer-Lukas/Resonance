#include "ResonanceEmotionIdle.h"
#include <cassert>
#include <iostream>
#include <limits>

using namespace ResonanceFace;
int main()
{
    // All profiles are distinct, bounded, and reach a stable held emotion.
    std::array<Curves,11> Signatures;
    for (int Profile=0;Profile<11;++Profile)
    {
        IdleState State;
        Scores Input{};
        if (Profile<10) Input[Profile]=.8f;
        State.SetScores(Input);
        Curves Previous{};
        for (int Frame=0;Frame<3600;++Frame)
        {
            State.Update(1.f/60.f);
            for (int i=0;i<CurveCount;++i)
            {
                assert(State.Output[i]>=0.f && State.Output[i]<=1.f);
                assert(std::abs(State.Output[i]-Previous[i])<.06f);
            }
            Previous=State.Output;
        }
        if (Profile<10) assert(std::abs(State.Smoothed[Profile]-.8f)<.001f);
        else assert(State.Neutral==1.f);
        Signatures[Profile]=State.Output;
    }
    for (int i=0;i<11;++i) for (int j=i+1;j<11;++j) assert(Signatures[i]!=Signatures[j]);

    // A short input fluctuation cannot snap the face. No new samples retain the target.
    IdleState State;
    Scores Sad{}; Sad[9]=1.f; State.SetScores(Sad);
    for (int i=0;i<300;++i) State.Update(1.f/60.f);
    const float Before=State.Smoothed[9];
    Scores Joy{}; Joy[6]=1.f; State.SetScores(Joy); State.Update(1.f/60.f);
    assert(State.Smoothed[9] > Before-.06f);
    for (int i=0;i<600;++i) State.Update(1.f/60.f);
    assert(State.Smoothed[6]>.999f);
    assert(State.Smoothed[9]<.001f);

    // Frame-rate-independent transitions; stable seeded schedules.
    IdleState A,B,C;
    A.SetScores(Sad); B.SetScores(Sad); C.SetScores(Sad);
    for(int i=0;i<600;++i) { A.Update(1.f/60.f); C.Update(1.f/60.f); }
    for(int i=0;i<300;++i) B.Update(1.f/30.f);
    assert(A.Output==C.Output);
    for(int i=0;i<10;++i) assert(std::abs(A.Smoothed[i]-B.Smoothed[i])<.0001f);

    // Invalid scores and overlaid categories cannot propagate NaNs or overflow curves.
    Scores Bad; Bad.fill(1.f); Bad[2]=std::numeric_limits<float>::quiet_NaN();
    A.SetScores(Bad);
    for(int i=0;i<300;++i) A.Update(1.f/60.f);
    for(float Value:A.Output) assert(std::isfinite(Value) && Value>=0.f && Value<=1.f);

    // Final fusion preserves blinks, suppresses widening at closure, and honours showcase.
    assert(Fuse(.2f,.7f,.65f,1.f,0,0.f,0.f)==1.f);
    assert(Fuse(.8f,.4f,.65f,1.f,2,0.f,0.f)==0.f);
    assert(std::abs(Fuse(.8f,.4f,.65f,1.f,2,.37f,1.f)-.37f)<.00001f);
    assert(std::abs(Fuse(.8f,.4f,0.f,0.f,6,0.f,0.f)-.8f)<.00001f);
    // Six-class input aliases map onto ten controllable dimensions; never
    // invent grief/pain/etc. from a six-class observation.
    assert(EmotionIndex("neutral")==10 && EmotionIndex("angry")==1);
    assert(EmotionIndex("happy")==6 && EmotionIndex("sad")==9);
    assert(EmotionIndex("fear")==4 && EmotionIndex("disgust")==3);
    assert(EmotionIndex("shy")==-1 && EmotionIndex(nullptr)==-1);
    for (int p=0;p<11;++p)
    {
        std::array<Curves,3> Faces;
        std::array<std::array<float,3>,3> Heads;
        for (int v=0;v<3;++v)
        {
            IdleState S; Scores Input{};
            if (p<10) Input[p]=1.f;
            S.SetScores(Input); S.ForcedVariant=v;
            auto PreviousHead=S.Head;
            int BlinkEvents=0; bool WasClosed=false;
            for (int f=0;f<7200;++f)
            {
                S.Update(1.f/60.f);
                for (int axis=0;axis<3;++axis)
                {
                    assert(std::isfinite(S.Head[axis]) && std::abs(S.Head[axis])<6.f);
                    assert(std::abs(S.Head[axis]-PreviousHead[axis])<.15f);
                }
                PreviousHead=S.Head;
                assert(S.Blink>=0 && S.Blink<=1);
                if(S.Blink>.95f && !WasClosed) ++BlinkEvents;
                WasClosed=S.Blink>.95f;
                for(float Value:S.Output) assert(std::isfinite(Value) && Value>=0 && Value<=1);
            }
            assert(BlinkEvents>10 && BlinkEvents<60);
            Faces[v]=S.Output; Heads[v]=S.Head;
        }
        for(int a=0;a<3;++a) for(int b=a+1;b<3;++b)
        {
            assert(Faces[a]!=Faces[b]);
            assert(Heads[a]!=Heads[b]);
        }
    }
    // Identical timelines replay head/eye/variant/blink schedules exactly.
    IdleState D,E;
    D.SetScores(Joy); E.SetScores(Joy);
    std::array<bool,3> Seen{};
    int Last=-1;
    for(int f=0;f<18000;++f)
    {
        D.Update(1.f/60.f); E.Update(1.f/60.f);
        Seen[D.VariantIndex]=true;
        assert(D.Output==E.Output && D.Head==E.Head && D.Blink==E.Blink);
        if(D.VariantIndex!=Last) Last=D.VariantIndex;
    }
    assert(Seen[0] && Seen[1] && Seen[2]);
    const auto SavedHead=D.Head;
    D.Update(std::numeric_limits<float>::quiet_NaN()); D.Update(-1.f);
    assert(D.Head==SavedHead);
    // Calibration may remove expression without removing head/blink scheduling.
    E.ExpressionStrength=0;
    for(int f=0;f<600;++f) E.Update(1.f/60.f);
    for(int i=2;i<15;++i) assert(E.Output[i]<.0001f);
    // Automatic changes must not anticipate the configured onset delay. Held
    // identical samples cannot keep pushing that deadline into the future.
    IdleState Timed;
    for(int f=0;f<10;++f) { Timed.SetPlaybackScores(Joy,.12f); Timed.Update(.01f); }
    assert(Timed.Target[6]==0.f && Timed.Smoothed[6]==0.f);
    for(int f=0;f<4;++f) { Timed.SetPlaybackScores(Joy,.12f); Timed.Update(.01f); }
    assert(Timed.Target[6]==1.f && Timed.Smoothed[6]>0.f);
    // Manual selection cancels delayed automatic samples, including across
    // stream replacement; stale emotions cannot overwrite a preview.
    Timed.SetPlaybackScores(Sad,.4f); Timed.SetScores(Joy);
    for(int f=0;f<60;++f) Timed.Update(.01f);
    assert(Timed.Target==Joy);
    Timed.SetPlaybackScores(Sad,.4f); Timed.ResetPlaybackTiming();
    for(int f=0;f<60;++f) Timed.Update(.01f);
    assert(Timed.Target==Joy);
    // New defaults reach a readable expression faster than the old cascaded
    // .8s/.4s filters, without snapping straight to full strength.
    IdleState Faster,Slower;
    Faster.SetScores(Sad); Slower.SetScores(Sad);
    Faster.ForcedVariant=Slower.ForcedVariant=0;
    Slower.VariantTransitionSeconds=.4f;
    for(int f=0;f<80;++f) { Faster.Update(.01f); Slower.Update(.01f,.8f); }
    assert(Faster.Output[6]>Slower.Output[6]*1.5f);
    assert(Faster.Smoothed[9]>.9f && Faster.Smoothed[9]<1.f);
    std::cout << "Emotion idle: profiles, transitions, retention, determinism and fusion passed\n";
}
