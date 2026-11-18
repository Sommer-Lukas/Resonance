using UnrealBuildTool;
public class ResonanceFace : ModuleRules
{
    public ResonanceFace(ReadOnlyTargetRules Target) : base(Target)
    {
        PCHUsage = PCHUsageMode.UseExplicitOrSharedPCHs;
        PublicDependencyModuleNames.AddRange(new[] {"Core", "CoreUObject", "Engine", "AnimGraphRuntime", "ACERuntime", "ACECore"});
    }
}
