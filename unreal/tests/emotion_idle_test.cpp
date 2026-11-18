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
    // Downward lid following never attenuates a model blink, even at full
    // authored weight, and showcase still takes precedence.
    assert(Fuse(1.f,.2f,1.f,0.f,0,0.f,0.f)==1.f);
    assert(Fuse(.4f,.2f,.9f,0.f,0,0.f,0.f)>.4f);
    assert(Fuse(.4f,.2f,.9f,1.f,0,0.f,0.f)==1.f);
    assert(Fuse(.4f,.2f,.9f,0.f,0,.3f,1.f)==.3f);
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
            // Expression variants must not retrigger a head-pose cycle.
            assert(Heads[a]==Heads[b]);
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
    // Neutral must explore all four eye directions and animate the surrounding
    // lids too. Avoid a forward-only neutral or rotating eyeballs in a frozen socket.
    IdleState EyePerformance;
    EyePerformance.ResetSeed(5173);
    std::array<float,4> EyeExtents{};
    float LidFollow=0.f,WideFollow=0.f;
    int OffCenterFrames=0;
    for(int f=0;f<7200;++f)
    {
        EyePerformance.Update(1.f/60.f);
        EyeExtents[0]=std::max(EyeExtents[0],EyePerformance.EyeX);
        EyeExtents[1]=std::max(EyeExtents[1],-EyePerformance.EyeX);
        EyeExtents[2]=std::max(EyeExtents[2],EyePerformance.EyeY);
        EyeExtents[3]=std::max(EyeExtents[3],-EyePerformance.EyeY);
        if(std::abs(EyePerformance.EyeX)+std::abs(EyePerformance.EyeY)>.04f) ++OffCenterFrames;
        if(EyePerformance.EyeY<-.04f) LidFollow=std::max(LidFollow,EyePerformance.Output[0]);
        if(EyePerformance.EyeY>.04f) WideFollow=std::max(WideFollow,EyePerformance.Output[2]);
        assert(EyePerformance.EyeX*EyePerformance.EyeX/(.18f*.18f)+
            EyePerformance.EyeY*EyePerformance.EyeY/(.16f*.16f)<1.001f);
        assert(EyePerformance.Output[19]==EyePerformance.Output[20]);
        assert(EyePerformance.Output[21]==EyePerformance.Output[22]);
    }
    for(float Extent:EyeExtents) assert(Extent>.035f);
    assert(OffCenterFrames>1800 && OffCenterFrames<7000);
    assert(LidFollow>.06f && WideFollow>.06f);
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
    // An emotion's arrival reads stronger than its held expression. It must
    // relax without losing the emotion when no further samples arrive.
    IdleState Arrival;
    Scores Amazement{}; Amazement[0]=1.f;
    Arrival.ForcedVariant=0;
    Arrival.SetScores(Amazement);
    float PeakBrow=0.f;
    for(int f=0;f<600;++f)
    {
        Arrival.Update(1.f/60.f);
        PeakBrow=std::max(PeakBrow,Arrival.Output[6]);
    }
    assert(Arrival.Output[6]>.30f && PeakBrow>Arrival.Output[6]+.04f);
    // Test motion kinematics independently of face/rig gains. Emotion changes
    // may alter the target abruptly, but speed/acceleration must stay bounded.
    std::array<float,11> Weights{}; Weights[10]=1.f;
    HeadIdle Motion;
    std::array<float,3> Pose{};
    int QuietFrames=0;
    std::array<float,3> Low{},High{};
    for(int f=0;f<7200;++f)
    {
        const auto PreviousVelocity=Motion.Velocity;
        if(f==3600) { Weights.fill(0.f); Weights[1]=1.f; Pose={3.f,3.f,1.f}; }
        Motion.Update(1.f/60.f,Weights,Pose);
        float Speed=0.f;
        for(int a=0;a<3;++a)
        {
            assert(std::abs(Motion.Velocity[a])<=6.f);
            assert(std::abs(Motion.Velocity[a]-PreviousVelocity[a])*60.f<18.001f);
            Speed+=std::abs(Motion.Velocity[a]);
            if(f<3600) { Low[a]=std::min(Low[a],Motion.Position[a]); High[a]=std::max(High[a],Motion.Position[a]); }
        }
        if(f<3600 && Speed<.1f) ++QuietFrames;
    }
    assert(QuietFrames>120 && QuietFrames<3500);
    assert(std::max({High[0]-Low[0],High[1]-Low[1],High[2]-Low[2]})>.3f);
    // Visible shifts have simultaneous pitch/yaw/roll and changing direction
    // inside a single excursion, instead of tracing axis-aligned spokes.
    HeadIdle Curved;
    int CoupledFrames=0,CurvingFrames=0;
    auto OldVelocity=Curved.Velocity;
    for(int f=0;f<7200;++f)
    {
        Curved.Update(1.f/60.f,Weights,{});
        int MovingAxes=0;
        for(float V:Curved.Velocity) MovingAxes+=std::abs(V)>.15f;
        CoupledFrames+=MovingAxes>=2;
        const float Cross=OldVelocity[0]*Curved.Velocity[1]-OldVelocity[1]*Curved.Velocity[0];
        CurvingFrames+=std::abs(Cross)>.001f;
        OldVelocity=Curved.Velocity;
    }
    assert(CoupledFrames>120 && CurvingFrames>60);
    // Distinct hold/travel times produce varied cadence; a sad performance has
    // fewer shifts than anger over the same replay duration.
    HeadIdle AngryMotion,SadMotion;
    std::array<float,11> AngryWeights{},SadWeights{};
    AngryWeights[1]=1.f; SadWeights[9]=1.f;
    float AngryDistance=0.f,SadDistance=0.f;
    for(int f=0;f<7200;++f)
    {
        const auto OldAngry=AngryMotion.Position,OldSad=SadMotion.Position;
        AngryMotion.Update(1.f/60.f,AngryWeights,{});
        SadMotion.Update(1.f/60.f,SadWeights,{});
        for(int a=0;a<3;++a)
        {
            AngryDistance+=std::abs(AngryMotion.Position[a]-OldAngry[a]);
            SadDistance+=std::abs(SadMotion.Position[a]-OldSad[a]);
        }
    }
    assert(AngryMotion.ShiftCount>SadMotion.ShiftCount);
    assert(AngryDistance>SadDistance*1.3f);
    HeadIdle Fine,Coarse;
    for(int f=0;f<600;++f) Fine.Update(1.f/60.f,AngryWeights,{});
    for(int f=0;f<300;++f) Coarse.Update(1.f/30.f,AngryWeights,{});
    for(int a=0;a<3;++a) assert(std::abs(Fine.Position[a]-Coarse.Position[a])<.0001f);
    const auto BeforeInvalid=Fine.Position;
    Fine.Update(std::numeric_limits<float>::quiet_NaN(),AngryWeights,{});
    assert(Fine.Position==BeforeInvalid);
    // Continuous speech and syllable-sized gaps cannot become a nod/idle loop.
    HeadIdle Continuous,Syllables,Silence,Phrases;
    Continuous.UseSpeechTiming=Syllables.UseSpeechTiming=Silence.UseSpeechTiming=Phrases.UseSpeechTiming=true;
    Continuous.HasEnvelope=Syllables.HasEnvelope=Silence.HasEnvelope=Phrases.HasEnvelope=true;
    Continuous.PlaybackActive=Syllables.PlaybackActive=Phrases.PlaybackActive=true;
    Continuous.Envelope=.08f;
    int LastCue=0,PreviousCueFrame=-1000;
    for(int f=0;f<7200;++f)
    {
        Syllables.Envelope=(f%24)<16 ? .08f : 0.f;
        Phrases.Envelope=(f%180)<110 ? .08f : 0.f;
        Continuous.Update(1.f/60.f,AngryWeights,{});
        Syllables.Update(1.f/60.f,AngryWeights,{});
        Silence.Update(1.f/60.f,AngryWeights,{});
        Phrases.Update(1.f/60.f,AngryWeights,{});
        if (Phrases.SpeechCueCount!=LastCue)
        {
            assert(f-PreviousCueFrame>150);
            PreviousCueFrame=f; LastCue=Phrases.SpeechCueCount;
        }
    }
    assert(Continuous.SpeechCueCount==1 && Syllables.SpeechCueCount==1);
    for(float Angle:Continuous.Position) assert(std::abs(Angle)<.4f);
    assert(Silence.SpeechCueCount==0);
    assert(Silence.QuietAdjustmentCount>=3 && Silence.QuietAdjustmentCount<25);
    assert(Phrases.SpeechCueCount>2 && Phrases.SpeechCueCount<30);
    // Silence contains sparse visible shifts, with both long quiet holds and
    // occasional changes; it cannot become either frozen or constant swaying.
    HeadIdle Quiet;
    Quiet.UseSpeechTiming=true; Quiet.HasEnvelope=true;
    std::array<float,11> QuietWeights{}; QuietWeights[10]=1.f;
    std::array<float,3> QuietLow{},QuietHigh{};
    int StillFrames=0,MovingFrames=0,LastAdjustment=0;
    std::array<int,25> AdjustmentFrames{};
    for(int f=0;f<7200;++f)
    {
        Quiet.Update(1.f/60.f,QuietWeights,{});
        float Speed=0.f;
        for(int a=0;a<3;++a)
        {
            Speed+=std::abs(Quiet.Velocity[a]);
            QuietLow[a]=std::min(QuietLow[a],Quiet.Position[a]);
            QuietHigh[a]=std::max(QuietHigh[a],Quiet.Position[a]);
        }
        if (Speed<.1f) ++StillFrames;
        if (Speed>.3f) ++MovingFrames;
        if (Quiet.QuietAdjustmentCount!=LastAdjustment && LastAdjustment<25)
            AdjustmentFrames[LastAdjustment++]=f;
    }
    assert(StillFrames>1800 && MovingFrames>120);
    assert(std::max({QuietHigh[0]-QuietLow[0],QuietHigh[1]-QuietLow[1],QuietHigh[2]-QuietLow[2]})>.8f);
    assert(LastAdjustment>=3);
    bool Uneven=false;
    for(int i=2;i<LastAdjustment;++i)
        Uneven|=std::abs((AdjustmentFrames[i]-AdjustmentFrames[i-1])-(AdjustmentFrames[1]-AdjustmentFrames[0]))>60;
    assert(Uneven);
    // Disabling the quiet accent layer keeps speech behaviour independent.
    HeadIdle NoQuiet; NoQuiet.UseSpeechTiming=true; NoQuiet.QuietMotionScale=0;
    for(int f=0;f<7200;++f) NoQuiet.Update(1.f/60.f,QuietWeights,{});
    assert(NoQuiet.QuietAdjustmentCount==0);
    // Behaviour episodes should coordinate fear's lowered head and aversion,
    // while anger favors forward attention. Seeded runs remain replayable.
    IdleState FearBehaviour,AngerBehaviour,ReplayFear,OtherFear;
    Scores FearScores{},AngerScores{}; FearScores[4]=1; AngerScores[1]=1;
    FearBehaviour.ResetSeed(3127); ReplayFear.ResetSeed(3127); OtherFear.ResetSeed(9781);
    FearBehaviour.SetScores(FearScores); ReplayFear.SetScores(FearScores); OtherFear.SetScores(FearScores);
    AngerBehaviour.SetScores(AngerScores);
    int FearAway=0,AngerAway=0; float FearPitch=0.f; bool Different=false;
    for(int f=0;f<18000;++f)
    {
        FearBehaviour.Update(1.f/60.f); ReplayFear.Update(1.f/60.f);
        OtherFear.Update(1.f/60.f); AngerBehaviour.Update(1.f/60.f);
        assert(FearBehaviour.Output==ReplayFear.Output && FearBehaviour.Head==ReplayFear.Head);
        Different|=FearBehaviour.Head!=OtherFear.Head;
        if(f>600)
        {
            FearAway+=FearBehaviour.LookingAway; AngerAway+=AngerBehaviour.LookingAway;
            FearPitch+=FearBehaviour.Head[0];
        }
    }
    assert(Different && FearAway>AngerAway*2 && FearAway>10000 && FearAway<17399);
    assert(FearPitch/17399.f>1.5f);
    std::cout << "Fear/anger away frames=" << FearAway << "/" << AngerAway << "\n";
    // Every emotion must continue responding to broad energy changes during
    // continuous speech, rather than make one initial turn and hold it.
    std::array<bool,6> GesturesSeen{};
    for(int Profile=0;Profile<11;++Profile)
    {
        HeadIdle Performance;
        Performance.UseSpeechTiming=Performance.PlaybackActive=Performance.HasEnvelope=true;
        Performance.SpeechMotionScale=2.f;
        std::array<float,11> EmotionWeights{}; EmotionWeights[Profile]=1.f;
        std::array<float,3> Min{},Max{};
        for(int f=0;f<3600;++f)
        {
            Performance.Envelope=(f%240>=150 && f%240<198) ? .13f : .02f;
            Performance.Update(1.f/60.f,EmotionWeights,{});
            if (Performance.ExpressionAccent>.5f)
                GesturesSeen[static_cast<int>(Performance.ActiveGesture)]=true;
            for(int a=0;a<3;++a)
            {
                Min[a]=std::min(Min[a],Performance.Position[a]);
                Max[a]=std::max(Max[a],Performance.Position[a]);
                assert(std::abs(Performance.Position[a])<5.5f);
            }
        }
        assert(Performance.SpeechCueCount>=5);
        assert(std::max({Max[0]-Min[0],Max[1]-Min[1],Max[2]-Min[2]})>1.8f);
        std::cout << EmotionNames[Profile] << ": speech excursions=" << Performance.SpeechCueCount << "\n";
    }
    for (std::size_t i=1;i<GesturesSeen.size();++i) assert(GesturesSeen[i]);
    std::cout << "Quiet head adjustments=" << Quiet.QuietAdjustmentCount
        << ", still/moving frames=" << StillFrames << "/" << MovingFrames << "\n";
    // Facial variant changes leave the head trajectory untouched, while the
    // face still has three distinct expression signatures (checked above).
    std::cout << "Speech head cues: continuous=" << Continuous.SpeechCueCount
        << ", syllables=" << Syllables.SpeechCueCount << ", pauses=" << Phrases.SpeechCueCount << "\n";
    std::cout << "Head motion: neutral quiet frames=" << QuietFrames
        << ", anger/sadness path=" << AngryDistance << "/" << SadDistance
        << ", shifts=" << AngryMotion.ShiftCount << "/" << SadMotion.ShiftCount << "\n";
    std::cout << "Emotion idle: profiles, transitions, retention, determinism and fusion passed\n";
}
