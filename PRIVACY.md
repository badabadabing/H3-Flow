# Privacy

H3 Flow is designed for local operation.

- The HTTP server listens on `127.0.0.1` by default.
- The project contains no analytics, telemetry, advertising SDK, or user account.
- Prompts and reference images are sent to the user-configured ComfyUI endpoint for generation.
- The optional prompt director sends the current prompt text, duration, aspect ratio, and reference-mode name to the model endpoint selected by the user only after an explicit click.
- The prompt director does not send reference-image bytes, filenames, local paths, hardware information, model inventories, workflows, or generated media.
- An API key entered in the UI remains only in page memory. Environment-configured keys are used by the bridge but are never returned by its status or rewrite responses.
- Reference images are stored by ComfyUI in its local input storage and are not automatically deleted.
- Compatibility responses expose component names and versions, not usernames, absolute paths, credentials, or model contents.
- Generated media, input media, model weights, logs, caches, and local configuration are ignored by Git.

Users are responsible for the content they process and for removing local inputs or outputs when required by their own retention policy.
