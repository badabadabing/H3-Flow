# H3 Flow project record

## Product goal

Provide a local, guided frontend that turns creative choices into validated ComfyUI workflows without exposing node graphs or hiding resource and compatibility failures.

## Current requirements

- T2V, true first-frame I2V, and Ref2VA identity/style modes.
- 5/10/15/30 second plans with truthful continuity labels.
- Hardware, runtime, model, node, plugin, and version detection.
- Optional user-configured DeepSeek or OpenAI-compatible prompt rewriting that follows the pinned official MiniMax H3 Base and Ref2VA guides.
- No automatic third-party plugin installation.
- Localhost-only by default, no telemetry, no personal data in the public repository.
- Public GitHub documentation, tests, contribution, security, privacy, and license files.

## Progress

- [x] First-frame upload is wired to `MiniMaxH3ImageToVideo.first_frame`.
- [x] Single-image Ref2VA mode uses the separate Ref2VA model and node.
- [x] Reference image bytes are decoded and verified before ComfyUI upload.
- [x] Compatibility manifest and `/api/compatibility` endpoint implemented.
- [x] Tested runtime, model sizes/hashes, capability nodes, and optional motion-context plugin baseline recorded.
- [x] Long-video baseline is labelled pixel last-frame chaining rather than seamless latent continuation.
- [x] Time-coded master prompts are compiled into isolated per-segment story beats; missing later beats stop before sampling.
- [x] Five seconds is the safe default; 10–30 second prompts are preflighted live and blocked until every five-second story beat is present.
- [x] Provider-neutral AI prompt director emits and locally validates official H3 Base/I2VA/Ref2VA field structures without sending reference images or local machine data.
- [x] A synthetic 100-creator journey audit is documented with affected-journey counts, evidence limits, and ten prioritized opportunities.
- [x] Creator workbench upgrade adds four-step navigation, brief completeness guidance, visual long-video beat building, local draft recovery, actionable unified preflight, and progressive technical disclosure.
- [ ] First-and-last-frame UI.
- [ ] Multi-image Ref2VA UI and tag assistant.
- [ ] Motion-context plugin security audit, installation by user, GPU validation, seam metrics, and release gate.
- [ ] Cross-platform packaged launcher.

## Verification evidence

- 22 workflow-engine, prompt-director, and creator-guidance tests pass, including secret redaction, HTTPS enforcement, official field validation, long-video beat completeness, and draft privacy boundaries.
- Live ComfyUI 0.31.1 reports base and Ref2VA capabilities ready.
- Exported first-frame I2V workflow: 21 nodes, zero live-schema errors.
- Exported identity/style Ref2VA workflow: 20 nodes, zero live-schema errors.
- No `/prompt` call was made during reference-mode validation.

## 100-creator synthetic audit and workbench upgrade — 2026-08-12

- The cohort is explicitly synthetic, not a claim of 100 real interviews or telemetry sessions. It covers short-form, commerce, narrative, performance, visual, agency, technical, and first-time local-generation journeys.
- Ten ranked findings and their limits are recorded in `docs/creator-cohort-audit.md`; the first six high-leverage issues were addressed in the working product.
- Long-video authors now write one five-second beat per row and compile a validated timeline instead of manually formatting timecodes.
- One local browser draft restores creative text and generation parameters after reload while excluding credentials, media, machine inventory, and workflows.
- Creative readiness and runtime readiness are combined into one preflight with a direct return-to-fix action; technical diagnostics remain available under progressive disclosure.
- Desktop and mobile browser flows were exercised against the live local bridge. A complete 30-second six-beat story survived reload and passed the timecode gate; the only remaining blocker was the existing ComfyUI queue.
- No generation request was submitted and no `/prompt` call was made during this audit. The existing ComfyUI job was left untouched.
- Follow-up opportunities remain: provider connection testing, validated multi-image Ref2VA labelling, and generation history with seed variants and per-segment retry.
