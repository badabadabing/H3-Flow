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
