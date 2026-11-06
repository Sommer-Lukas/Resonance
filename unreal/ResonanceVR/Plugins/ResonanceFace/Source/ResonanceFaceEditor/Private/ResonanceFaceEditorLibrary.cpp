#include "ResonanceFaceEditorLibrary.h"
#include "ResonanceEmotionIdle.h"
#include "AnimGraphNode_ResonanceFusion.h"
#include "AnimGraphNode_ModifyCurve.h"
#include "Animation/AnimBlueprint.h"
#include "EdGraph/EdGraph.h"
#include "EdGraph/EdGraphSchema.h"
#include "Kismet2/BlueprintEditorUtils.h"
#include "ScopedTransaction.h"
#include "Editor.h"
#include "GameFramework/PlayerController.h"
#include "InputKeyEventArgs.h"

bool UResonanceFaceEditorLibrary::SendPIEKey(FName Key,bool bPressed)
{
    if (!GEditor || !GEditor->PlayWorld) return false;
    APlayerController* Controller=GEditor->PlayWorld->GetFirstPlayerController();
    if (!Controller) return false;
    return Controller->InputKey(FInputKeyEventArgs(nullptr,FInputDeviceId::CreateFromInternalId(0),
        FKey(Key),bPressed ? IE_Pressed : IE_Released,FPlatformTime::Cycles64()));
}

FString UResonanceFaceEditorLibrary::InstallFusion(UAnimBlueprint* Blueprint)
{
    if (!Blueprint) return TEXT("Missing face AnimBlueprint");
    UEdGraph* Graph=nullptr;
    TArray<UEdGraph*> Graphs;
    Blueprint->GetAllGraphs(Graphs);
    for (UEdGraph* Candidate : Graphs)
        if (Candidate->GetFName()==TEXT("AnimGraph")) Graph=Candidate;
    if (!Graph) return TEXT("Missing AnimGraph");
    UAnimGraphNode_ModifyCurve* Old=nullptr;
    UEdGraphNode* Blink=nullptr;
    for (UEdGraphNode* Candidate : Graph->Nodes)
    {
        if (Cast<UAnimGraphNode_ResonanceFusion>(Candidate)) return FString();
        if (Candidate->GetName().StartsWith(TEXT("ResonanceAnimationFusion"))) Old=Cast<UAnimGraphNode_ModifyCurve>(Candidate);
        if (Candidate->GetName().StartsWith(TEXT("ResonanceBlinkInput"))) Blink=Candidate;
    }
    if (!Old || !Blink) return TEXT("Expected original Resonance blink and showcase nodes");
    auto* BlinkSource=Blink->FindPin(TEXT("SourcePose"));
    auto* BlinkAlpha=Blink->FindPin(TEXT("Alpha"));
    auto* OldOutput=Old->FindPin(TEXT("Pose"));
    if (!BlinkSource || BlinkSource->LinkedTo.Num()!=1 || !BlinkAlpha || !OldOutput)
    return TEXT("Unexpected original face links");
    // Validate every showcase pin before mutating the graph.
    TArray<UEdGraphPin*> Inputs;
    for (int i=0;i<15;++i)
    {
        UEdGraphPin* Found=nullptr;
        for (UEdGraphPin* Pin : Old->Pins)
            if (Pin->PinFriendlyName.ToString()==UTF8_TO_TCHAR(ResonanceFace::CurveNames[i])) Found=Pin;
        if (!Found) return FString::Printf(TEXT("Missing authored curve input: %s"),UTF8_TO_TCHAR(ResonanceFace::CurveNames[i]));
        Inputs.Add(Found);
    }
    const FScopedTransaction Transaction(FText::FromString(TEXT("Install Resonance facial fusion")));
    Blueprint->Modify(); Graph->Modify(); Old->Modify(); Blink->Modify();
    FGraphNodeCreator<UAnimGraphNode_ResonanceFusion> Creator(*Graph);
    auto* New=Creator.CreateNode();
    New->Rename(TEXT("ResonanceAnimationFusionNative"), Graph, REN_DontCreateRedirectors);
    New->NodePosX=Old->NodePosX; New->NodePosY=Old->NodePosY;
    Creator.Finalize();
    const UEdGraphSchema* Schema=Graph->GetSchema();
    auto CopyInput=[&](UEdGraphPin* From, const TCHAR* ToName)
    {
        UEdGraphPin* To=New->FindPin(ToName);
        if (!From || !To) return false;
        To->DefaultValue=From->DefaultValue;
        const auto Links=From->LinkedTo;
        for (UEdGraphPin* Link : Links) if (!Schema->TryCreateConnection(Link,To)) return false;
        return true;
    };
    bool OK=CopyInput(BlinkSource,TEXT("SourcePose")) && CopyInput(BlinkAlpha,TEXT("NaturalBlink"))
        && CopyInput(Old->FindPin(TEXT("Alpha")),TEXT("ShowcaseAlpha"));
    for (int i=0;i<15;++i) OK &= CopyInput(Inputs[i],UTF8_TO_TCHAR(ResonanceFace::CurveNames[i]));
    const auto OutputLinks=OldOutput->LinkedTo;
    for (UEdGraphPin* Link : OutputLinks) OK &= Schema->TryCreateConnection(New->FindPin(TEXT("Pose")),Link);
    if (!OK) return TEXT("Could not migrate fusion links; undo the transaction and inspect pins");
    FBlueprintEditorUtils::RemoveNode(Blueprint,Old,true);
    FBlueprintEditorUtils::RemoveNode(Blueprint,Blink,true);
    FBlueprintEditorUtils::MarkBlueprintAsStructurallyModified(Blueprint);
    return FString();
}
