using UnrealBuildTool;
public class ResonanceWebXR : ModuleRules
{
    public ResonanceWebXR(ReadOnlyTargetRules Target) : base(Target)
    {
        PCHUsage = PCHUsageMode.UseExplicitOrSharedPCHs;
        PrivateDependencyModuleNames.AddRange(new[] {
            "Core", "CoreUObject", "Engine", "HeadMountedDisplay",
            "PixelStreaming2", "PixelStreaming2Core", "PixelStreaming2Input"
        });
    }
}
