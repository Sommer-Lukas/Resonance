#pragma once
#include "CoreMinimal.h"
#include "Kismet/BlueprintFunctionLibrary.h"
#include "ResonanceFaceEditorLibrary.generated.h"
class UAnimBlueprint;

UCLASS()
class RESONANCEFACEEDITOR_API UResonanceFaceEditorLibrary : public UBlueprintFunctionLibrary
{
    GENERATED_BODY()
public:
    /** Migrate the known two-node blink/showcase chain, preserving its input links. */
    UFUNCTION(BlueprintCallable, Category="Resonance|Editor")
    static FString InstallFusion(UAnimBlueprint* Blueprint);
    /** Deliver a keyboard event through the actual PIE player input stack for verification. */
    UFUNCTION(BlueprintCallable, Category="Resonance|Editor")
    static bool SendPIEKey(FName Key, bool bPressed);
};
