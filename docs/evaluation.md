# Evaluation plan — draft before recruitment

Tracked initially in [#10](https://github.com/Sommer-Lukas/Resonance/issues/10). Protocol, hypotheses and sample size remain to be agreed; no completed study is claimed.

## Conditions and controls

| Condition | Facial behavior |
|---|---|
| A | Minimal idle/blinking + speech articulation |
| B | A + timing-aware facial listening |
| C | B + turn-aware waiting/transition behavior |

Keep client appearance, audio, dialogue content and response delay matched for controlled comparisons. Choose one primary outcome, counterbalance order and use multiple repeatable scenarios. First pilot with fixed recordings/replayed events; separately test live integration. A hard-switch versus crossfade technical comparison can be a focused ablation, not necessarily another full participant condition.

## Technical measurements

Record frame-time distribution/dropped frames, hardware/settings, turn-end-to-playback delay, event-to-visible-motion delay, audio/visual offset, jitter and transition continuity. Explain instrumentation, clock alignment and measurement limits. Compare deformation errors only if defensible ground truth exists. A performance target must follow the chosen headset/runtime configuration and early profiling.

## Perception and training relevance

Assess perceived responsiveness, reaction appropriateness, conversational coherence, naturalness, uncomfortable/uncanny response and perceived waiting time. Select validated questionnaire items only after checking their source and applicability.

For client-state evaluation measure perceived emotion/intensity and congruence with the same voice. A classifier score does not establish human recognition. Include a voice-only comparison or focused pilot if making claims about added training value; test client-state interpretation, intervention choices, confidence or cognitive load. Perception evidence alone does not establish learning or clinical effectiveness.

## Protocol decisions still required

- Primary hypothesis/outcome, feasibility-driven participant count and effect-size/power or precision reasoning.
- Recruitment, within/between-subject design, order controls and exclusion rules.
- Pilot, validated instrument sources, analysis plan and uncertainty reporting.
- Standardized scenarios, replay seeds and minimum acceptable technical quality.
- Consent, minimal logs, scenario boundaries, debriefing and human oversight.

Recruitment and protocol work starts during M0. Freeze features at M5 (22 December); complete data collection by M6 (12 January), then analyze and finalize. Revisit this schedule if access/recruitment makes it infeasible.
