# H3 Flow

H3 Flow is a local, guided frontend for MiniMax H3 workflows in ComfyUI. It turns prompt, reference-image, duration, aspect-ratio, and quality choices into validated API workflows while checking the local runtime, models, nodes, plugins, queue, and hardware before submission.

The current release supports text-to-video, real first-frame image-to-video, Ref2VA identity/style references, adaptive 5–30 second plans, guarded SeedVR2 restoration, and an optional provider-neutral prompt director. Its short-drama mode turns a theme into a validated 1–8 episode package. Genre and style may be AI-selected, preset, or extended with custom requirements. After the creator approves one reference image per main character, one click starts a background serial queue for every shot; longer planned shots are compiled into five-second execution units to reduce 16GB VRAM failure risk.

The prompt director defaults to DeepSeek's current OpenAI-compatible endpoint and model preset, but users supply their own API key and can replace the endpoint and model. Keys are never committed or returned by the local API. Reference images, local paths, hardware data, and workflows are not sent to the prompt provider. See [prompt-assistant.md](docs/prompt-assistant.md).

See the [Chinese README](README.md) for setup, the transparent [synthetic 100-creator cohort audit](docs/creator-cohort-audit.md), [compatibility contract](docs/compatibility.md), [continuity research](docs/continuity.md), [privacy policy](PRIVACY.md), and [security policy](SECURITY.md).

```powershell
git clone https://github.com/badabadabing/H3-Flow.git
cd H3-Flow
py -3 -m pip install -r requirements.txt
.\scripts\start.ps1 -ComfyRoot "D:\path\to\ComfyUI"
```

Open `http://127.0.0.1:4173` after ComfyUI is running.

The default five-second mode accepts one complete scene prompt. For 10, 15, or 30 seconds, use the visual beat builder or provide every five-second beat explicitly, for example `0-5s: ...` and `5-10s: ...`. H3 Flow preflights the timeline and blocks submission when a later beat is missing. Creative parameters and beat drafts can be recovered from this browser; API keys, reference images, and hardware data are excluded from that draft.

Switch the top navigation to **AI Short Drama**, enter the story, episode count, and duration, then approve each main character image. The **Generate all shots** action preflights assets, models, memory, VRAM, and queue state before a single background worker submits one five-second H3 unit at a time. API keys and provider configuration are excluded from browser drafts. See [short-drama-mode.md](docs/short-drama-mode.md).

This release generates every shot without page switching, then assembles each episode into an exact 24 fps MP4 while retaining the individual shot files for review and repair. Durable resume after the local bridge restarts, automated visual continuity scoring, and release-ready full-series claims remain gated and are documented in the [AI short-drama roadmap](docs/ai-short-drama-roadmap.md).

H3 Flow is MIT-licensed. Model weights, ComfyUI, and third-party plugins are not included and remain subject to their respective licenses.
