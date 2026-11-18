using UnrealBuildTool;
public class ResonanceFaceEditor : ModuleRules
{
    public ResonanceFaceEditor(ReadOnlyTargetRules Target) : base(Target)
    {
        PCHUsage=PCHUsageMode.UseExplicitOrSharedPCHs;
        PublicDependencyModuleNames.AddRange(new[] {"Core", "CoreUObject", "Engine", "AnimGraph", "BlueprintGraph", "ResonanceFace"});
        PrivateDependencyModuleNames.AddRange(new[] {"UnrealEd", "KismetCompiler", "InputCore"});
    }
}
