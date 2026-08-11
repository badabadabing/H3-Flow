# H3 long-video safety nodes

`H3VideoMemoryPreflight` runs on the prompt dependency path before MiniMax H3 sampling. It rejects an unchanged placeholder, missing ComfyUI memory-management APIs, insufficient VRAM for the predicted SeedVR2 temporal chunk, or insufficient Windows commit capacity for the 30-second 1080P tensors.

`H3SeedVR2StreamedDecode` consumes the sampled SeedVR2 latent list without merging it into one full-duration latent. It unloads other models, decodes one temporal chunk at a time, writes directly into a preallocated CPU tensor, and Hann-crossfades the pixel overlap. The output is exactly the requested frame count.

The design follows the long-video memory-spike fix published by `numz/ComfyUI-SeedVR2_VideoUpscaler` (commit `3ab2c8409130572d8c03be1a160a2bb70cce7226`) and the model-unload approach proposed in ComfyUI PR `#15456`.
