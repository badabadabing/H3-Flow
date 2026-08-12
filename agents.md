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
- Structured AI short-drama planning from a theme to series bible, production assets, 1–8 episode scripts, scenes, validated shots, local export, approved character references, and one-click serial generation of every shot.
- Final episode assembly, bridge-restart recovery, automated continuity scoring, and release-ready full-season claims remain gated.

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
- [x] AI short-drama guided planner: story-first defaults, AI / preset / custom genre and style, strict local schema validation, stable asset IDs, exact episode budgets, local draft, ledger, and export.
- [x] Character reference approval and background all-shot queue: true ComfyUI upload, multi-reference Ref2VA mapping, five-second execution units, one active serial batch, one retry per unit, progress and result links.
- [ ] Durable resume after bridge restart, episode assembly, continuity scoring, shot repair, pilot quality gate, and release-ready full-series submission.

## Verification evidence

- 22 workflow-engine, prompt-director, and creator-guidance tests pass, including secret redaction, HTTPS enforcement, official field validation, long-video beat completeness, and draft privacy boundaries.
- Live ComfyUI 0.31.1 reports base and Ref2VA capabilities ready.
- Exported first-frame I2V workflow: 21 nodes, zero live-schema errors.
- Exported identity/style Ref2VA workflow: 20 nodes, zero live-schema errors.
- No `/prompt` call was made during reference-mode validation.

## 100-creator synthetic audit and workbench upgrade — 2026-08-12

- The cohort is explicitly synthetic, not a claim of 100 real interviews or telemetry sessions. It covers short-form, commerce, narrative, performance, visual, agency, technical, and first-time local-generation journeys.
- Ten ranked findings and their limits are recorded in `docs/creator-cohort-audit.md`; the first seven high-leverage issues were addressed in the working product.
- Long-video authors now write one five-second beat per row and compile a validated timeline instead of manually formatting timecodes.
- One local browser draft restores creative text and generation parameters after reload while excluding credentials, media, machine inventory, and workflows.
- Creative readiness and runtime readiness are combined into one preflight with a direct return-to-fix action; technical diagnostics remain available under progressive disclosure.
- Desktop and mobile browser flows were exercised against the live local bridge. A complete 30-second six-beat story survived reload and passed the timecode gate; the only remaining blocker was the existing ComfyUI queue.
- No generation request was submitted and no `/prompt` call was made during this audit. The existing ComfyUI job was left untouched.
- Follow-up opportunities remain: provider connection testing, validated multi-image Ref2VA labelling, and generation history with seed variants and per-segment retry.

## Desktop viewport-density repair — 2026-08-12

- At 2048×1027 the sticky plan was 952px tall but had only 855px from its sticky top to the viewport bottom; `overflow: visible` made the final actions permanently unreachable by page scrolling.
- Desktop widths from 1181px now use a single-screen cockpit below the 68px app bar. The hero is a compact two-column introduction, while the creator form and safety plan own bounded internal scrolling.
- The plan no longer relies on sticky positioning in cockpit mode. Timeline, specs, blockers, protection copy, and actions use a tighter rhythm without reducing the established text sizes or touch targets below their existing system.
- At 2048×1027 the document height equals 1027px and the plan is fully visible from y=88 to y=1007; its 917px client height equals its 917px scroll height in the collapsed state.
- At 1440×900 the plan is fully visible from y=88 to y=880. With technical details expanded, 186px of internal overflow remains reachable and the action area reaches the bottom correctly.
- The creator form reaches its quality section at its maximum internal scroll. The 390×844 layout retains normal page scrolling and the mobile preflight dock.
- Isolated current-code browser verification produced zero console errors or warnings and made no `/prompt` request.

## AI short-drama production research — 2026-08-12

- The requested future surface starts from a theme and optional genre, audience, style, episode count, per-episode duration, aspect ratio, cast, dialogue, and quality controls.
- Research across MiniMax H3, ComfyUI, LTX Studio, MovieAgent, FilmAgent, StoryDiffusion, and StreamingT2V supports a hierarchical production model rather than one unconstrained prompt: series bible → locked assets → episode plans → scene scripts → shot plans → storyboards → H3 compilation → pilot gate → resumable batch queue → continuity review and shot-level repair.
- The core contract is a versioned local project with stable IDs for characters, wardrobe states, props, locations, episodes, scenes, shots, and generation records. Changes such as costume swaps, damaged props, time of day, and character relationships must be explicit state transitions.
- One-click full-series execution remains gated behind approved assets, a passing pilot episode, runtime / model / storage checks, and a recoverable queue. Script-only and storyboard-only modes must not call ComfyUI.
- Development is staged as P0 structured planner, P1 asset bible, P2 pilot episode, P3 series batching and repair, and P4 controlled one-click production.
- The full product contract, schemas, consistency strategy, safety boundaries, acceptance gates, and primary research sources are recorded in `docs/ai-short-drama-roadmap.md`.

## AI short-drama P0 delivery — 2026-08-12

- The top navigation now switches between the existing single-video desk and a dedicated short-drama production desk without changing the established ComfyUI generation path.
- Users can define theme, title, genre, 1–8 episodes, 30–120 seconds per episode, aspect ratio, 1–6 core characters, ending style, dialogue density, language, audience, and visual style.
- `short_drama.py` treats all creative input as data, calls only the user-selected OpenAI-compatible service, requests JSON mode, and allows one bounded repair attempt after local validation failure.
- Local validation rewrites stable IDs, resolves every asset reference, requires 5/10/15-second shots, requires consecutive five-second beats, caps the package at 128 shots, and enforces the exact selected duration for every episode.
- The season ledger exposes overview, production assets, episodes, scenes, hooks, and shots. JSON and Markdown exports remain local. A shot handoff clears any previous reference image, writes its beats and sound into the existing H3 desk, and never submits the queue automatically.
- Browser drafts persist creative fields and the validated package only. API key, model endpoint, model name, reference media, machine inventory, and workflows are excluded.
- Full-series submission is visibly disabled until real reference assets, a pilot, resource checks, and resumable execution are implemented and verified.

## DeepSeek ephemeral-Key and constraint repair — 2026-08-12

- Browser interception reproduced two separate issues without contacting DeepSeek: the short-drama Key entered the local request while the UI kept showing the static “Key 不落盘” copy, and a Key entered in the single-video prompt director was not available after switching to short-drama mode.
- The prompt director and short-drama desk now share one in-memory-only base URL, model, and API Key. Either input updates the other, successful entry shows “本页内存已就绪 / Key 已就绪 · 不落盘”, and refresh or page close still clears the secret.
- No credential was added to localStorage, project files, drafts, exports, logs, or API responses. The server continues to send `Authorization: Bearer <key>` only to the user-selected OpenAI-compatible endpoint.
- DeepSeek HTTP 401, 402, 422, 429, and 503 responses now map to actionable Chinese explanations for invalid Key, insufficient balance, invalid parameters, rate limiting, and service load.
- All short-drama creator settings are now explicit hard constraints in both the system and user messages. The selected working title is deterministically preserved, dialogue density is recorded, and genre, aspect, visual style, audience, language, dialogue density, and quality are injected into every downstream H3 shot brief.
- Official DeepSeek JSON mode remains enabled with `response_format: {"type": "json_object"}`, an explicit JSON contract in the prompt, bounded output length, and local schema validation plus at most one repair attempt.
- Verification: JavaScript syntax passed; 30/30 Python tests passed; live browser interception showed one shared temporary Key, 13/13 creator settings in the request, explicit ready-state feedback, and no external DeepSeek or ComfyUI generation call.

## AI short-drama guided one-click shot production — 2026-08-12

- Replaced the production-led form with a three-step creator journey: tell the story, confirm characters, generate all shots. Genre and visual style now support AI selection, a restrained preset, and an optional custom requirement; secondary production controls are collapsed by default.
- Removed the primary per-shot page handoff. Each principal character now has a real local image upload and explicit approval gate. Approved tokens are mapped to ordered `<Picture n>` inputs of `MiniMaxH3ReferenceToVideo` for every scene cast member.
- `POST /api/short-drama/batch/start` now creates one background batch. Only one batch and one H3 unit run at a time; completion releases the queue before the next unit. A unit receives one bounded retry and the batch safely stops on a second failure while preserving previous outputs.
- Planned 10/15-second legacy shots are deterministically expanded into five-second execution units; new model instructions request five-second shots. This keeps the automatic path aligned with the known safer RTX 5080 16GB operating unit instead of relying on unsupported concurrency or a long Ref2VA decode claim.
- The UI polls `GET /api/short-drama/batch/{job_id}`, shows shot-level progress and completed video links, and never saves character tokens or API credentials in the browser draft.
- Truthful boundary: this release generates all shot files in one user action, but it does not yet auto-assemble episodes, persist a resumable queue across bridge restarts, or certify visual continuity. `full_series_generation` therefore remains false while `all_shot_batch_generation` is true.
- Verification: both repository copies pass 34/34 Python tests, JavaScript syntax, Python compilation, and diff checks. A live ComfyUI 0.31.1 `object_info` validation returned zero schema errors for the 18-node Ref2VA shot graph. Playwright desktop and 390×844 mobile render checks passed. The pre-existing ComfyUI job remained running and no `/prompt` request was made.
