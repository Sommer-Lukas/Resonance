# Research plan

Working questions are in README §3; finalize them in [#2](https://github.com/Sommer-Lukas/Resonance/issues/2). Literature work is [#5](https://github.com/Sommer-Lukas/Resonance/issues/5).

## Candidate contribution

A constrained, replayable facial listener and transition controller evaluated against idle/hard-switch baselines. Using VR or connecting Audio2Face to MetaHuman is integration, not by itself novelty.

## Search scope

Facial listener behavior, sparse reaction timing, turn transitions, emotion/articulation separation, controllable facial animation, perceived response delay and virtual-client training evaluation. Body gesture and general gaze modeling remain outside scope.

Compare controlled/authored state, dialogue-provided state and audio/text inference; do not assume inference is needed. Client facial reactions must fit the client's role rather than implying therapeutic understanding or agreement.

## Evidence ledger — to populate

No paper results or runtime claims have been invented for this planning pass.

| Primary source + canonical URL | Type/year | Method and representation | Emotion control | Runtime/hardware | Evaluation/results + section | Limitations, code/license | VoiCE relevance/confidence |
|---|---|---|---|---|---|---|---|
| Pending verified literature review | — | — | — | — | — | — | — |

For each selected paper inspect the full text when available, cite sections/pages/figures/tables, label preprints and separate reported evidence from inference. Select 5–8 useful primary sources; use backward/forward citation tracing rather than a collection of abstracts.

## Decision gates

1. Choose one primary outcome and question.
2. Select timing-only baseline and a small reaction set before considering trained models.
3. Add prosody/transcript only if interfaces and literature support a feasible, distinct comparison.
4. Keep emotion sequencing as an optional extension unless evaluation requires it.
