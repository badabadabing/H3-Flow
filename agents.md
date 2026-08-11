# H3 Flow project record

## Product goal

Provide a local, guided frontend that turns creative choices into validated ComfyUI workflows without exposing node graphs or hiding resource and compatibility failures.

## Current requirements

- T2V, true first-frame I2V, and Ref2VA identity/style modes.
- 5/10/15/30 second plans with truthful continuity labels.
- Hardware, runtime, model, node, plugin, and version detection.
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
- [ ] First-and-last-frame UI.
- [ ] Multi-image Ref2VA UI and tag assistant.
- [ ] Motion-context plugin security audit, installation by user, GPU validation, seam metrics, and release gate.
- [ ] Cross-platform packaged launcher.

## Verification evidence

- 15 workflow-engine unit tests pass.
- Live ComfyUI 0.31.1 reports base and Ref2VA capabilities ready.
- Exported first-frame I2V workflow: 21 nodes, zero live-schema errors.
- Exported identity/style Ref2VA workflow: 20 nodes, zero live-schema errors.
- No `/prompt` call was made during reference-mode validation.
