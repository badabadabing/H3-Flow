# H3 Flow

H3 Flow is a local, guided frontend for MiniMax H3 workflows in ComfyUI. It turns prompt, reference-image, duration, aspect-ratio, and quality choices into validated API workflows while checking the local runtime, models, nodes, plugins, queue, and hardware before submission.

The current release supports text-to-video, real first-frame image-to-video, a single-image Ref2VA identity/style mode, adaptive 5–30 second plans, and guarded SeedVR2 restoration. Long outputs currently use pixel last-frame chaining and are labelled accordingly; latent audio/video continuation remains gated until the pinned plugin version passes end-to-end validation.

See the [Chinese README](README.md) for setup, [compatibility contract](docs/compatibility.md), [continuity research](docs/continuity.md), [privacy policy](PRIVACY.md), and [security policy](SECURITY.md).

```powershell
git clone https://github.com/badabadabing/H3-Flow.git
cd H3-Flow
py -3 -m pip install -r requirements.txt
.\scripts\start.ps1 -ComfyRoot "D:\path\to\ComfyUI"
```

Open `http://127.0.0.1:4173` after ComfyUI is running.

The default five-second mode accepts one complete scene prompt. For 10, 15, or 30 seconds, provide every five-second beat explicitly, for example `0-5s: ...` and `5-10s: ...`. H3 Flow preflights the timeline and blocks submission when a later beat is missing.

H3 Flow is MIT-licensed. Model weights, ComfyUI, and third-party plugins are not included and remain subject to their respective licenses.
