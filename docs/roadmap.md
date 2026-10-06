# Delivery roadmap — winter semester 2026/27

GitHub issues are the active backlog. Native milestones are the progress containers; this document supplies future work packages without creating dozens of untouched issues.

| Milestone | Due | Work / acceptance evidence |
|---|---|---|
| M0 — Project Definition | 2026-10-27 | Issues #1–#5, #9, #10; proposal, interface inventory, scope/RQs/risks/roles; exercise-app demo preparation. |
| M1 — Talking MetaHuman | 2026-11-10 | Issues #6–#8; controllable rig and verified fixed-audio adapter; timing evidence. |
| M2 — VR Prototype | 2026-11-17 | Quest/PCVR setup, scene/viewpoint, speech demo, frame-time profiling; record hardware/settings. |
| M3 — Conversation Baseline | 2026-11-24 | Observable phase controller, sparse idle/blinks, speaking/listening switch, hard-switch/crossfade baseline; assessed demo. |
| M4 — Reactive Listener | 2026-12-08 | Verified timing inputs, reaction set, scheduler/cooldowns/intensity constraints, deterministic replay, poster and demo. |
| M5 — VoiCE Integration | 2026-12-22 | Adapter, response audio/articulation, real turn events, waiting/error/cancellation handling where supported, logging, complete loop; feature freeze. |
| M6 — Evaluation Complete | 2027-01-12 | Piloted protocol, technical measurements, controlled participant comparison and minimized analysis dataset. |
| M7 — Final Project | 2027-01-19 | Analysis/limitations, reproducible demo, project report, WordPress contribution and final presentation. |

## Critical dependencies and early work

- Investigate VoiCE access and stack/GPU compatibility immediately in M0; M5 is completion of integration, not first investigation.
- Make protocol/recruitment feasible in M0; evaluation is not first planned in January.
- Profile headset performance early. Prefer an initial PCVR path; standalone support is unverified.
- Create later implementation issues just before their milestone; attach dependencies, acceptance criteria and one primary owner.
- Prosody/transcript/response-aware extensions are P3 until required functionality is reliable.

## Course dates and source sections

- **17772.jpg**, slide 9, “Was ist am 27.10 vorzustellen?”: exercise-application demo and VR proposal covering idea/objectives, scope, methodology, resources, milestones and risks.
- **17770.jpg**, “Prüfungsleistungen”: progress presentation **24.11.2026** (1/8), poster/presentation **08.12.2026** (2/8), final project presentation plus WordPress/report (5/8), and successful exercise acceptance.
- **17768.jpg**, slide 7, “Zeitplan”: final slots **19.01.2027 / 26.01.2027**; poster block visually aligns differently from the assessment date.

Use 8 December and 19 January as conservative readiness targets. Confirm poster date and group final slot in issue #9; neither ambiguity is silently treated as resolved.
