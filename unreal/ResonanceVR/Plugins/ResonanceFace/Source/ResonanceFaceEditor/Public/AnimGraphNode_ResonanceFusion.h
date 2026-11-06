#pragma once
#include "CoreMinimal.h"
#include "AnimGraphNode_Base.h"
#include "AnimNode_ResonanceFusion.h"
#include "AnimGraphNode_ResonanceFusion.generated.h"

UCLASS()
class RESONANCEFACEEDITOR_API UAnimGraphNode_ResonanceFusion : public UAnimGraphNode_Base
{
    GENERATED_BODY()
public:
    UPROPERTY(EditAnywhere, Category=Settings)
    FAnimNode_ResonanceFusion Node;
    virtual FText GetNodeTitle(ENodeTitleType::Type Type) const override
    { return FText::FromString(TEXT("Resonance Animation Fusion")); }
    virtual FText GetTooltipText() const override
    { return FText::FromString(TEXT("Blend Audio2Face, emotion-conditioned idle, blinks and the authored showcase before retargeting.")); }
    virtual FText GetMenuCategory() const override { return FText::FromString(TEXT("Resonance")); }
};
