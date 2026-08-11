# Privacy

H3 Flow is designed for local operation.

- The HTTP server listens on `127.0.0.1` by default.
- The project contains no analytics, telemetry, advertising SDK, user account, or cloud upload code.
- Prompts and reference images are sent only to the user-configured ComfyUI endpoint.
- Reference images are stored by ComfyUI in its local input storage and are not automatically deleted.
- Compatibility responses expose component names and versions, not usernames, absolute paths, credentials, or model contents.
- Generated media, input media, model weights, logs, caches, and local configuration are ignored by Git.

Users are responsible for the content they process and for removing local inputs or outputs when required by their own retention policy.
