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

namespace
{
FString InstallHeadPass(UAnimBlueprint* Blueprint,UEdGraph* Graph,UAnimGraphNode_ResonanceFusion* Fusion)
{
    for (UEdGraphNode* Node:Graph->Nodes)
        if (auto* Existing=Cast<UAnimGraphNode_ResonanceFusion>(Node))
            if (Existing->Node.bHeadOnly) return FString();
    UEdGraphPin* Result=nullptr;
    for (UEdGraphNode* Node:Graph->Nodes)
        if (Node->GetClass()->GetFName()==TEXT("AnimGraphNode_Root")) Result=Node->FindPin(TEXT("Result"));
    if (!Result || Result->LinkedTo.Num()!=1) return TEXT("Expected one final output pose for head pass");
    UEdGraphPin* Upstream=Result->LinkedTo[0];
    const FScopedTransaction Transaction(FText::FromString(TEXT("Install Resonance head pose pass")));
    Blueprint->Modify(); Graph->Modify(); Result->GetOwningNode()->Modify();
    FGraphNodeCreator<UAnimGraphNode_ResonanceFusion> Creator(*Graph);
    auto* Head=Creator.CreateNode();
    Head->Rename(TEXT("ResonanceFinalHeadPose"),Graph,REN_DontCreateRedirectors);
    Head->Node.bHeadOnly=true;
    Head->NodePosX=Result->GetOwningNode()->NodePosX-240;
    Head->NodePosY=Result->GetOwningNode()->NodePosY+260;
    Creator.Finalize();
    const UEdGraphSchema* Schema=Graph->GetSchema();
    bool OK=Schema->TryCreateConnection(Upstream,Head->FindPin(TEXT("SourcePose")));
    OK &= Schema->TryCreateConnection(Head->FindPin(TEXT("Pose")),Result);
    UEdGraphPin* Alpha=Fusion ? Fusion->FindPin(TEXT("ShowcaseAlpha")) : nullptr;
    UEdGraphPin* HeadAlpha=Head->FindPin(TEXT("ShowcaseAlpha"));
    if (Alpha && HeadAlpha)
    {
        HeadAlpha->DefaultValue=Alpha->DefaultValue;
        for (UEdGraphPin* Link:Alpha->LinkedTo) OK &= Schema->TryCreateConnection(Link,HeadAlpha);
    }
    if (!OK) return TEXT("Could not connect final head pass; undo the installation");
    FBlueprintEditorUtils::MarkBlueprintAsStructurallyModified(Blueprint);
    return FString();
}
}

FString UResonanceFaceEditorLibrary::InstallHeadFusion(UAnimBlueprint* Blueprint)
{
    if (!Blueprint) return TEXT("Missing post-process AnimBlueprint");
    TArray<UEdGraph*> Graphs; Blueprint->GetAllGraphs(Graphs);
    for (UEdGraph* Graph:Graphs)
        if (Graph->GetFName()==TEXT("AnimGraph")) return InstallHeadPass(Blueprint,Graph,nullptr);
    return TEXT("Missing post-process AnimGraph");
}

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
    // Migrate an earlier main-graph head pass: RigLogic must run BEFORE it.
    const auto ExistingNodes=Graph->Nodes;
    for (UEdGraphNode* Candidate:ExistingNodes)
        if (auto* Head=Cast<UAnimGraphNode_ResonanceFusion>(Candidate))
            if (Head->Node.bHeadOnly)
            {
                auto* Input=Head->FindPin(TEXT("SourcePose"));
                auto* Output=Head->FindPin(TEXT("Pose"));
                if (!Input || Input->LinkedTo.Num()!=1 || !Output) return TEXT("Invalid old head pass");
                Blueprint->Modify(); Graph->Modify(); Head->Modify();
                auto* Source=Input->LinkedTo[0];
                const auto Links=Output->LinkedTo;
                for (auto* Link:Links)
                    if (!Graph->GetSchema()->TryCreateConnection(Source,Link)) return TEXT("Cannot migrate old head pass");
                FBlueprintEditorUtils::RemoveNode(Blueprint,Head,true);
                FBlueprintEditorUtils::MarkBlueprintAsStructurallyModified(Blueprint);
            }
    UAnimGraphNode_ModifyCurve* Old=nullptr;
    UEdGraphNode* Blink=nullptr;
    for (UEdGraphNode* Candidate : Graph->Nodes)
    {
        if (auto* Existing=Cast<UAnimGraphNode_ResonanceFusion>(Candidate))
            if (!Existing->Node.bHeadOnly) return FString();
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
