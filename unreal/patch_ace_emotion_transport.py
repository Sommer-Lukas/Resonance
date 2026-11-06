"""Expose local ACE 2.5 emotion data; never edit bundled ThirdParty code.

Run before compiling the project. Vendor files are locally installed/ignored;
this checked-in, idempotent patch is the reproducible source of our changes.
Every replacement is checked before any file is written.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parent / 'ResonanceVR/Plugins/NV_ACE_Reference/Source'
MARKER = '// Resonance emotion transport v1'


def transformations():
    return {
        'ACECore/Public/AnimDataConsumer.h': [(
            '\t// Byte array corresponding to audio data samples',
            MARKER + '\n\t// Callback-lifetime view: consumers must copy before returning.\n'
            '\tTArrayView<const float> EmotionScores;\n\tdouble EmotionTimestamp = -1.0;\n\n'
            '\t// Byte array corresponding to audio data samples')],
        'A2FCommon/Private/AIMA2FContext.cpp': [(
            '\t\t// We don\'t pass through the emotion outputs yet.\n'
            '\t\t// The format is an array of 10 floats in the order defined by the nvaim::Audio2FaceEmotions struct. Essentially that struct without timeCode.\n'
            '\t\t//TArrayView<const float> Emotions = GetArrayViewFromAIMParameter<const float>(EmotionSlot->bytes);',
            '\t\t' + MARKER + '\n'
            '\t\tconst auto Emotions = GetArrayViewFromAIMParameter<const float>(EmotionSlot->bytes);\n'
            '\t\tif (Emotions.Num() == 10)\n\t\t{\n'
            '\t\t\tChunk.EmotionScores = Emotions;\n'
            '\t\t\t// Audio callbacks refer to their beginning; emotion-only callbacks to the current audio boundary.\n'
            '\t\t\tChunk.EmotionTimestamp = Chunk.Timestamp >= 0.0 ? Chunk.Timestamp :\n'
            '\t\t\t\tstatic_cast<double>(ReceivedAudioSampleCount) / (16000.0 * sizeof(int16_t));\n'
            '\t\t}\n\t\telse\n\t\t{\n'
            '\t\t\tUE_LOG(LogACEA2FCommon, Warning, TEXT("Resonance: expected 10 emotion scores, got %d"), Emotions.Num());\n'
            '\t\t}')],
        'ACERuntime/Public/ACEAudioCurveSourceComponent.h': [(
            '\t/** Stop audio and animation */',
            '\t' + MARKER + '\n'
            '\t/** Local processed/remapped A2E output, selected against the audio playback clock. */\n'
            '\tUFUNCTION(BlueprintCallable, Category="Resonance|Emotion")\n'
            '\tbool GetPlaybackEmotionScores(TArray<float>& Scores);\n'
            '\tUFUNCTION(BlueprintPure, Category="Resonance|Emotion")\n'
            '\tbool IsEmotionPlaybackActive() const { return IsPlaybackActive(); }\n'
            '\tUFUNCTION(BlueprintCallable, Category="Resonance|Emotion")\n'
            '\tFString ExportEmotionStream();\n'
            '\tUPROPERTY(BlueprintReadOnly, Category="Resonance|Emotion")\n'
            '\tdouble CurrentEmotionTimestamp = -1.0;\n'
            '\tUPROPERTY(BlueprintReadOnly, Category="Resonance|Emotion")\n'
            '\tint32 EmotionSamplesReceived = 0;\n\n'
            '\t/** Stop audio and animation */'), (
            '\t// audio data protected by CS',
            '\tstruct FEmotionSample { TArray<float> Scores; double Timestamp; int32 SessionID; };\n'
            '\tTQueue<FEmotionSample, EQueueMode::Mpsc> EmotionQueue;\n'
            '\tTArray<FEmotionSample> PendingEmotions;\n'
            '\tTArray<FEmotionSample> EmotionHistory;\n'
            '\tTArray<float> HeldEmotionScores;\n'
            '\t// audio data protected by CS')],
        'ACERuntime/Private/ACEAudioCurveSourceComponent.cpp': [(
            '#include "ACEAudioCurveSourceComponent.h"',
            '#include "ACEAudioCurveSourceComponent.h"\n#include "Misc/FileHelper.h"\n#include "Misc/Paths.h"\n#include "HAL/FileManager.h"\n' + MARKER), (
            '\tBSWeightSampleQueue.Empty();',
            '\tBSWeightSampleQueue.Empty();\n\tEmotionQueue.Empty();\n\tPendingEmotions.Reset();\n'
            '\tEmotionHistory.Reset();\n\tEmotionSamplesReceived = 0;\n'
            '\t// Held emotion intentionally survives replay/stream replacement.\n'), (
            '\tif (Chunk.Status != EACEAnimDataStatus::OK_NO_MORE_DATA)',
            '\t// Copy SDK-owned emotion memory even on an EOS callback.\n'
            '\tif (Chunk.EmotionScores.Num() == 10 && FMath::IsFinite(Chunk.EmotionTimestamp) && Chunk.EmotionTimestamp >= 0.0\n'
            '\t\t&& AnimState != EAnimState::ENDING)\n\t{\n'
            '\t\tFEmotionSample Sample;\n\t\tSample.SessionID = SessionID;\n'
            '\t\t// Same underflow compensation as facial samples. Do not shift origin for emotion-only data.\n'
            '\t\t{\n\t\t\tFScopeLock Lock(&AudioCompCS);\n'
            '\t\t\tSample.Timestamp = FMath::Max(0.0, Chunk.EmotionTimestamp - FirstACETimestamp.Get(0.0))\n'
            '\t\t\t\t+ static_cast<double>(TotalUnderflowSamples) / (AudioSampleRate * static_cast<float>(NumAudioChannels));\n\t\t}\n'
            '\t\tbool Valid = true;\n\t\tfor (float Value : Chunk.EmotionScores)\n\t\t{\n'
            '\t\t\tValid &= FMath::IsFinite(Value);\n\t\t\tSample.Scores.Add(FMath::Clamp(Value, 0.f, 1.f));\n\t\t}\n'
            '\t\tif (Valid) EmotionQueue.Enqueue(MoveTemp(Sample));\n\t}\n'
            '\tif (Chunk.Status != EACEAnimDataStatus::OK_NO_MORE_DATA)'), (
            '\tAnimState = EAnimState::ENDING;\n\n\t// clear the animation buffer',
            '\tAnimState = EAnimState::ENDING;\n\tEmotionQueue.Empty();\n\tPendingEmotions.Reset();\n\n\t// clear the animation buffer')],
    }


EXTRA = r'''

bool UACEAudioCurveSourceComponent::GetPlaybackEmotionScores(TArray<float>& Scores)
{
    check(IsInGameThread());
    FEmotionSample Incoming;
    while (EmotionQueue.Dequeue(Incoming))
    {
        if (Incoming.SessionID != CurrentSessionID) continue;
        if (!PendingEmotions.IsEmpty() && Incoming.Timestamp < PendingEmotions.Last().Timestamp) continue;
        PendingEmotions.Add(Incoming);
        // Per-stream bounded history, available for export without doing file IO in inference callbacks.
        if (EmotionHistory.Num() < 18000) EmotionHistory.Add(Incoming);
        ++EmotionSamplesReceived;
    }
    if (IsPlaybackActive())
    {
        EvaluateAndUpdateCurrentPlaybackTime();
        int32 Consumed = 0;
        for (const FEmotionSample& Sample : PendingEmotions)
        {
            if (Sample.Timestamp > CurrentPlaybackTime) break;
            HeldEmotionScores = Sample.Scores;
            CurrentEmotionTimestamp = Sample.Timestamp;
            ++Consumed;
        }
        if (Consumed) PendingEmotions.RemoveAt(0, Consumed, EAllowShrinking::No);
    }
    Scores = HeldEmotionScores;
    return Scores.Num() == 10;
}

FString UACEAudioCurveSourceComponent::ExportEmotionStream()
{
    check(IsInGameThread());
    TArray<float> Ignored;
    GetPlaybackEmotionScores(Ignored);
    FString CSV = TEXT("stream_id,audio_time,amazement,anger,cheekiness,disgust,fear,grief,joy,outofbreath,pain,sadness\n");
    for (const FEmotionSample& Sample : EmotionHistory)
    {
        CSV += FString::Printf(TEXT("%d,%.6f"), Sample.SessionID, Sample.Timestamp);
        for (float Value : Sample.Scores) CSV += FString::Printf(TEXT(",%.6f"), Value);
        CSV += TEXT("\n");
    }
    const FString Folder = FPaths::ProjectSavedDir() / TEXT("EmotionStreams");
    IFileManager::Get().MakeDirectory(*Folder, true);
    const FString File = Folder / FString::Printf(TEXT("emotion_%d.csv"), CurrentSessionID.load());
    return FFileHelper::SaveStringToFile(CSV, *File) ? FPaths::ConvertRelativePathToFull(File) : FString();
}
'''


def apply():
    changes = []
    for relative, replacements in transformations().items():
        path = ROOT / relative
        source = path.read_text(encoding='utf-8')
        if MARKER in source:
            print('Already patched:', relative)
            continue
        for before, after in replacements:
            if source.count(before) != 1:
                raise RuntimeError(f'Unsupported ACE source: {relative}: expected exactly one {before[:70]!r}')
            source = source.replace(before, after)
        if relative.endswith('ACEAudioCurveSourceComponent.cpp'):
            source += EXTRA
        changes.append((path, source))
    for path, source in changes:
        path.write_text(source, encoding='utf-8')
        print('Patched:', path.relative_to(ROOT))


if __name__ == '__main__':
    apply()
