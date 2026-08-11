# Compatibility contract

`compatibility.json` is the machine-readable baseline for H3 Flow.

## Evidence levels

- `comfy_api`: ComfyUI enumerates the expected filename.
- `filesystem`: the configured ComfyUI root contains the file.
- `size`: filename and byte length match the published baseline.
- SHA-256 is recorded in the manifest for explicit offline integrity checks; it is not recalculated during every UI refresh because hashing tens of gigabytes would block normal use.

## Runtime status

- `ready`: core capabilities are present and all tested runtime versions match exactly.
- `compatible`: required models and node schemas are present, but one or more runtime versions differ from the tested baseline.
- `blocked`: at least one required core model or node is missing.

Version differences are visible rather than silently normalized. Submission still performs live node schema and model-enum validation, so a newer compatible runtime can work without pretending it is the tested build.

## Capability profiles

- `base`: T2V and first-frame I2V.
- `reference`: Ref2VA identity/style reference.
- `studio`: SeedVR2 temporal restoration.
- `latent_continuity`: optional H3 motion/audio latent continuation.

Optional capabilities do not block unrelated modes. Selecting a mode that requires one converts the missing capability into a pre-submit blocker.
