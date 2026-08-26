Purpose

This file defines how AI coding agents must work on Resonance, a face-focused Unity VR prototype extending the VoiCE research context.

The prototype investigates whether an AI-driven virtual client's emotional state can be communicated through coherent facial behavior during counseling-training conversations.

Agents must optimize for:

controllability,

modularity,

repeatability,

real-time suitability,

honest research claims,

minimal project scope.

Read README.md before making changes.

1. Hard Scope Boundary

Resonance is a face-only project.

In scope

facial expressions and expression intensity,

blendshapes, FACS-style controls, action units, or equivalent rig controls,

emotion trajectories and smooth transitions,

speech-synchronized mouth motion,

phoneme/viseme animation,

emotion-conditioned facial animation,

blinking,

minimal eye behavior only when required to prevent an obviously artificial face,

avatar-head rendering in Unity and VR,

interfaces to dialogue state, text-to-speech, audio, or prosody,

logging and evaluation instrumentation.

Out of scope

Do not add or propose implementation work for:

body animation,

hands or gestures,

posture,

locomotion,

full-body tracking,

inverse kinematics unrelated to the head,

complex environments,

scene interaction not required for the experiment,

multiplayer,

multiple avatars,

trainee-emotion diagnosis,

automated therapy,

clinical-effectiveness claims,

photorealistic reconstruction as a goal by itself.

Do not silently expand eye behavior into a gaze or social-attention subsystem.

When a requested change crosses this boundary, stop and state why it is out of scope.

2. Source-of-Truth Priority

When project information conflicts, use this order:

explicit instructions in the current task,

this file,

repository documentation,

Unity project configuration,

existing code and tests,

assumptions.

Never override an observed project setting with a remembered Unity default.

Before using a Unity API or package feature, inspect:

ProjectSettings/ProjectVersion.txt,

Packages/manifest.json,

relevant assembly definitions,

existing project conventions.

Do not claim that a feature, package, model, or system is already implemented unless the repository shows that it is.

3. Intended Architecture

Keep the following responsibilities separable:

Dialogue / role-play engine

Emotional state and temporal trajectory

Text-to-speech and prosody

Speech articulation

Emotion-conditioned facial motion

Fusion, conflict resolution, and smoothing

Retargeting to the avatar rig

Unity / VR runtime

Logging and experiment instrumentation

Prefer stable interfaces over direct cross-component references.

A target data flow is:

Dialogue state ────────────────┐
                               v
                        Emotion trajectory
                               │
TTS / audio ──> articulation   │
                  │            │
                  └────┬───────┘
                       v
              fusion and smoothing
                       │
                       v
                 rig retargeting
                       │
                       v
                 Unity face renderer

Architectural rules

Do not put dialogue logic inside avatar components.

Do not put rig-specific blendshape names inside domain-level emotion logic.

Do not let several components write directly to the same blendshape weights.

Use one final facial-output stage as the authority for applied rig values.

Keep generated speech and emotional intent as distinct inputs.

Prefer explicit emotional state from the dialogue layer for the first controllable prototype.

Do not infer emotion from synthetic audio when the same emotion already exists upstream unless that inference is explicitly the research question.

Keep the face system testable without VR hardware.

Keep rig retargeting replaceable so a different head can be introduced without rewriting dialogue or emotion logic.

4. Facial Animation Model

Treat speech articulation and emotional expression as separate signals.

A useful conceptual form is:

\operatorname{Clamp}\left(\mathbf{w}{neutral}+\mathbf{w}{speech}(t)+\mathbf{w}{emotion}(t)+\mathbf{w}{micro}(t)\right)]

This is not a requirement to add all weights linearly. The fusion layer may need masks, priorities, normalization, or rig-specific constraints.

Required properties

Facial output should support:

continuous intensity,

smooth attack and release,

interruption by a new emotional target,

deterministic playback when given the same inputs,

separation of target state and current rendered state,

configurable smoothing,

neutral fallback,

safe handling of missing rig controls,

logging of requested and applied values.

Conflict handling

Speech and emotion may both affect the jaw, lips, cheeks, and mouth corners.

Do not solve conflicts by allowing "last script wins."

Use an explicit policy such as:

per-channel masks,

weighted contribution,

priority by facial region,

emotion applied as an offset around speech,

normalized blending,

authored compatibility rules.

Document the selected policy and its limitations.

Temporal behavior

Avoid one-frame jumps between expression labels.

Prefer a continuous trajectory containing at least:

source state,

target state,

target intensity,

transition start,

transition duration,

interpolation policy.

Do not hard-code one universal transition duration if the architecture can expose it safely as configuration.

5. Emotion Representation

Do not choose a representation because it sounds more advanced.

Possible representations include:

discrete emotion classes,

valence-arousal-dominance,

appraisal variables,

FACS/action-unit intensities,

blendshape weights,

a hybrid mapping.

For an initial prototype, a practical separation is:

dialogue emotion state
        ↓
continuous emotion parameters
        ↓
rig-independent facial control target
        ↓
avatar-specific blendshape mapping

When introducing an emotion representation, document:

input format,

valid range,

neutral value,

interpolation behavior,

mapping to facial controls,

unsupported states,

expected failure cases.

Never label a blendshape combination as psychologically valid without evidence.

6. Unity Project Safety

Never modify or commit

Library/

Temp/

Logs/

obj/

generated IDE files

build output unless explicitly requested

Asset and metadata rules

Never delete or regenerate .meta files casually.

Never manually invent or change Unity GUIDs.

Preserve asset references.

Prefer moving or renaming assets through the Unity Editor or a Unity-aware MCP tool.

Do not mass-reserialize scenes or prefabs without a clear reason.

Avoid hand-editing .unity, .prefab, or serialized asset YAML unless no safer route exists.

Do not replace binary assets without reporting it explicitly.

Do not modify third-party package code unless the task requires it and the reason is documented.

Scene and prefab rules

Before changing a scene or prefab:

inspect its hierarchy,

identify existing components and serialized references,

check whether it is a shared asset,

make the smallest viable modification,

validate that references remain intact.

Do not create duplicate managers, cameras, XR origins, audio listeners, or event systems without inspecting the scene first.

Package rules

Do not upgrade Unity.

Do not add, remove, or upgrade packages without explicit justification.

Do not resolve package conflicts by changing several versions at once.

Record every package change in the final report.

Prefer existing dependencies over introducing another package for a small utility.

7. C# Standards

Use production-quality C# suitable for Unity.

Required

clear namespaces,

explicit access modifiers,

focused classes,

descriptive names,

serialized private fields instead of unnecessary public mutable fields,

[RequireComponent] where a hard component dependency exists,

[DisallowMultipleComponent] where duplicates would be invalid,

validation for serialized configuration,

null and bounds handling,

comments for design decisions, not obvious syntax.

Prefer

interfaces for replaceable modules,

plain C# classes for domain logic,

ScriptableObject assets for shared configuration,

MonoBehaviour only for Unity lifecycle or scene integration,

immutable event payloads where practical,

dependency injection through serialized references or explicit initialization,

testable math outside Unity components.

Avoid

global mutable singletons,

FindObjectOfType, GameObject.Find, or repeated hierarchy searches at runtime,

reflection for ordinary control flow,

string-based component coupling,

hidden static state,

deeply nested coroutines,

per-frame LINQ,

per-frame allocations,

logging every frame,

magic blendshape indices,

hard-coded avatar-specific names in general-purpose logic.

Runtime constraints

For code executed every frame:

avoid garbage allocations,

cache component references,

avoid repeated dictionary construction,

avoid unnecessary string operations,

keep logging disabled or sampled,

use profiler evidence before complex optimization.

Correctness and stable frame timing matter more than clever abstraction.

8. Suggested Interfaces

Use existing repository conventions when present. Otherwise, prefer small contracts similar to these concepts:

public interface IEmotionStateSource
{
    EmotionTarget CurrentTarget { get; }
}

public interface ISpeechArticulationSource
{
    FacialSignal Sample(double timeSeconds);
}

public interface IFacialExpressionSource
{
    FacialSignal Sample(double timeSeconds);
}

public interface IFacialFusion
{
    FacialSignal Combine(
        in FacialSignal articulation,
        in FacialSignal expression,
        in FacialSignal microMotion);
}

public interface IFaceRigTarget
{
    void Apply(in FacialSignal signal);
}

These examples communicate boundaries only. Do not add them blindly if equivalent abstractions already exist.

Represent blendshape channels using stable semantic identifiers where possible. Resolve semantic identifiers to avatar-specific indices in the retargeting layer.

9. Configuration and Serialization

Configuration that affects experiments should be inspectable and reproducible.

Examples:

expression mappings,

intensity limits,

transition durations,

smoothing parameters,

channel masks,

fusion weights,

blink timing,

rig bindings.

Prefer serialized configuration assets over hidden constants.

For any configuration used in evaluation:

provide a stable identifier or version,

make default values explicit,

validate ranges,

log the active configuration,

avoid changing defaults silently.

Do not serialize transient runtime state into shared assets.

10. Logging and Instrumentation

The prototype must support later evaluation.

Where relevant, log timestamps for:

dialogue response availability,

emotional target changes,

TTS request and audio start,

articulation availability,

facial target generation,

final rig application,

frame timing.

Logs should distinguish:

requested emotional state,

smoothed state,

speech contribution,

emotional contribution,

final applied facial controls.

Requirements:

use one consistent clock,

document timestamp units,

avoid personally identifying data,

do not record raw conversation audio unless explicitly approved,

support disabling instrumentation,

do not let logging destabilize frame timing.

11. Testing Requirements

Tests should target logic that can fail silently.

Prioritize tests for:

emotion interpolation,

target interruption,

clamping and normalization,

missing facial channels,

semantic-to-rig mapping,

speech/emotion fusion,

deterministic output,

neutral fallback,

configuration validation.

Use:

Edit Mode tests for pure logic and mappings,

Play Mode tests for component integration and lifecycle behavior,

manual visual checks for animation quality,

device tests for VR frame timing and latency.

A classifier score or passing unit test does not establish that a face looks natural.

Do not claim perceptual validity without human evaluation.

12. Agent Workflow

For every non-trivial task, follow this sequence.

Step 1: Inspect

Inspect all relevant files before editing.

At minimum, check:

current implementation,

call sites,

tests,

serialized references,

package and Unity versions,

naming and folder conventions.

Do not propose replacing a system you have not inspected.

Step 2: State the smallest valid change

Identify:

the exact responsibility being changed,

affected files and assets,

expected behavior,

risks,

validation method.

Prefer one bounded subsystem per change.

Step 3: Implement minimally

preserve existing public behavior unless the task requires a change,

reuse current abstractions where reasonable,

avoid unrelated cleanup,

avoid project-wide renaming,

do not introduce speculative infrastructure.

Step 4: Validate

When tools permit:

compile scripts,

inspect Unity Console errors and warnings,

run relevant Edit Mode tests,

run relevant Play Mode tests,

inspect modified scenes and prefabs,

verify serialized references,

report anything that could not be checked.

Never report "working" solely because the code looks plausible.

Step 5: Report precisely

Use this format:

Summary
- What changed and why.

Modified
- File or asset: concrete change.

Validation
- Checks run and results.

Risks / Limitations
- Remaining uncertainty or known edge cases.

Next
- One recommended next step, only when necessary.

List every modified scene, prefab, asset, package, and project setting.

13. MCP and Autonomous Editor Rules

An MCP server may be used to inspect or modify the Unity project, but it does not replace verification.

Allowed

inspect project structure,

inspect scenes, GameObjects, components, and serialized values,

create bounded scripts,

attach a known component to a known object,

run compilation and tests,

inspect Console output,

create small test scenes when explicitly justified.

Require extra caution

moving or deleting assets,

modifying shared prefabs,

editing project settings,

changing XR configuration,

changing package versions,

bulk operations,

generated materials or meshes,

dynamic C# execution.

Prohibited without explicit approval

destructive Git operations,

deleting scenes or prefabs,

replacing the active scene,

package upgrades,

changing render pipelines,

changing Unity versions,

broad asset reorganization,

automatic import of large third-party frameworks,

rewriting several architecture layers in one operation.

Before autonomous scene changes, ensure the working tree can be restored. Do not overwrite uncommitted user work.

17. Definition of Done

A change is complete only when:

it stays within the face-only scope,

the architecture boundary is preserved or intentionally documented,

code compiles in the project's Unity version,

relevant tests pass or missing test access is stated,

scenes and prefabs retain valid references,

no new Console errors are introduced,

runtime behavior is deterministic where required,

configuration is inspectable,

performance-sensitive code avoids obvious per-frame allocation,

modified files and limitations are reported,

documentation is updated when behavior or setup changes.

For visual changes, completion also requires a manual visual inspection or an explicit statement that visual inspection was not possible.

18. Default Decision Policy

When several approaches are possible, prefer the option that is:

easiest to control,

easiest to reproduce,

easiest to evaluate,

least coupled to one avatar,

sufficiently real-time,

smallest in scope.

A simple procedural solution is preferable to a learned model when both answer the same prototype question.

Do not add complexity merely because an AI-generated solution can.
