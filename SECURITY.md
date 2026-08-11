# Security policy

## Supported version

Security fixes are applied to the latest release on the default branch.

## Reporting a vulnerability

Please use GitHub's private vulnerability reporting feature in the repository Security tab. Do not include secrets, personal media, model files, or private filesystem paths in a public issue.

## Trust boundaries

- H3 Flow does not install or execute third-party ComfyUI plugins automatically.
- Model and plugin detection is read-only.
- Workflow submission is blocked when required nodes, models, types, topology, or queue state fail validation.
- The bridge binds to localhost and should not be exposed directly to an untrusted network.
- Reference uploads validate MIME type, decoded image format, dimensions, pixel count, and size before forwarding to ComfyUI.
- Prompt-provider URLs reject embedded credentials, query strings, fragments, and remote plain HTTP. Plain HTTP is accepted only for loopback OpenAI-compatible services.
- Prompt-provider error handling returns a bounded upstream message and never returns the submitted API key.
- Short-drama model output is parsed as bounded JSON, normalised into a known schema, checked for stable IDs and resolvable references, capped at 128 shots, and rejected when five-second beats or episode duration budgets do not match.
- A failed short-drama package gets at most one targeted model repair request; it is not silently weakened, truncated, or submitted to ComfyUI.
- Browser draft persistence uses a single versioned localStorage key and deliberately excludes API keys, reference-image data, filesystem paths, hardware details, model inventories, and generated media.
- Starting a new creator draft clears only that localStorage entry and the visible form; it never deletes ComfyUI inputs or outputs.
- Never paste an API key into a public issue, commit, screenshot, workflow JSON, or shared terminal transcript.
