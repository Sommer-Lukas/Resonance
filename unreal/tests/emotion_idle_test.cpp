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
    assert(State.Smoothed[9] > Before-.03f);
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
    std::cout << "Emotion idle: profiles, transitions, retention, determinism and fusion passed\n";
}
