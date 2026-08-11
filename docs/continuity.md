# Long-video continuity research and integration boundary

## What the official model supports

MiniMax H3's official repository documents 4–15 second output at 24 fps with 32 kHz stereo audio. FL2VA accepts zero, one, or two images for text, first-frame, last-frame, or first-and-last-frame generation. Ref2VA uses separate weights and supports up to nine images plus video and audio references.

Sources:

- [MiniMax H3 official repository](https://github.com/MiniMax-AI/MiniMax-H3)
- [Official ComfyUI H3 I2V template](https://github.com/Comfy-Org/workflow_templates/blob/main/templates/video_minimax_h3_i2v.json)
- [Official ComfyUI H3 Ref2VA template](https://github.com/Comfy-Org/workflow_templates/blob/main/templates/video_minimax_h3_r2v.json)

## Current safe baseline

H3 Flow splits requested long outputs into verified 124-frame chunks. Each later chunk receives the decoded final frame of the previous chunk as `first_frame`; one duplicate boundary frame is removed before concatenation. This preserves composition better than independent clips but can still drift in identity, color, motion phase, and audio.

For 10–30 second requests, the master prompt must contain explicit time ranges. `h3_prompt_continuity` rewrites only the beats that belong to each chunk onto its local timeline and inserts the official `<Picture 1>` alignment instruction for continuation chunks. Missing or ambiguous later beats stop before sampling instead of silently replaying the opening action.

The UI therefore labels this strategy `末帧像素续接（基础）`. It is not described as seamless.

## Higher-quality direction

The reviewed H3 Motion Context implementation carries the previous joint audio/video latent into the next run, trims the pinned head in both streams, and rejects resolution mismatch. Its documentation reports that avoiding pixel/VAE round trips removes a major source of visible seams, while also noting cumulative audio degradation and narrow hardware testing.

Reviewed baseline:

- Repository: [NikoDemon80/ComfyUI-H3-Motion-Context](https://github.com/NikoDemon80/ComfyUI-H3-Motion-Context)
- Version: `0.2.0`
- Commit: `c140ae99b8c38f782ebd8564c267b42aacade6a4`
- License: GPL-3.0

H3 Flow only detects this exact baseline. It does not download, install, patch, or execute the plugin automatically.

## Release gates for latent continuation

Latent continuation will be enabled only after all gates pass:

1. Offline plugin tests and startup self-checks pass against the supported ComfyUI version.
2. Node schemas and pinned plugin commit match `compatibility.json`.
3. Two-clip and six-clip renders pass resolution, frame-count, 32 kHz stereo, finite-sample, peak, and queue-isolation checks.
4. Join analysis measures video discontinuity and audio cross-correlation/lag before and after trimming.
5. Human review checks identity, motion direction, camera velocity, color, dialogue, ambience, and musical continuity.
6. Failure stops before expensive generation when versions or resources differ.

Research on long-video diffusion also supports retaining short- and long-term context rather than relying on a single last frame. Useful primary references include [Flexible Diffusion Modeling of Long Videos](https://arxiv.org/abs/2205.11495), [StreamingT2V](https://streamingt2v.github.io/), and [LongDiff](https://openaccess.thecvf.com/content/CVPR2025/html/Li_LongDiff_Training-Free_Long_Video_Generation_in_One_Go_CVPR_2025_paper.html). These guide evaluation design; their code is not copied into H3 Flow.
