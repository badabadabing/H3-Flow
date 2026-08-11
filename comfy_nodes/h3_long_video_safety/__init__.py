from __future__ import annotations

import ctypes
import json
import logging
from collections.abc import Iterable

import torch


GIB = 1024 ** 3
SEEDVR2_CHUNK_GIB_PER_MPX_FRAME = 0.55
SEEDVR2_CHUNK_RESERVED_GIB = 8.5
SEEDVR2_CHUNK_SIGMA_GIB = 0.55
SEEDVR2_CHUNK_SIGMA_K = 4.0
HOST_FIXED_HEADROOM_GIB = 8.0


def _available_commit_gib() -> float | None:
    if not hasattr(ctypes, "windll"):
        return None

    class MemoryStatusEx(ctypes.Structure):
        _fields_ = [
            ("dwLength", ctypes.c_ulong),
            ("dwMemoryLoad", ctypes.c_ulong),
            ("ullTotalPhys", ctypes.c_ulonglong),
            ("ullAvailPhys", ctypes.c_ulonglong),
            ("ullTotalPageFile", ctypes.c_ulonglong),
            ("ullAvailPageFile", ctypes.c_ulonglong),
            ("ullTotalVirtual", ctypes.c_ulonglong),
            ("ullAvailVirtual", ctypes.c_ulonglong),
            ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
        ]

    status = MemoryStatusEx()
    status.dwLength = ctypes.sizeof(MemoryStatusEx)
    if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
        return None
    return status.ullAvailPageFile / GIB


def _total_vram_gib() -> float:
    if not torch.cuda.is_available():
        return 0.0
    return torch.cuda.get_device_properties(torch.cuda.current_device()).total_memory / GIB


def build_memory_plan(
    *,
    output_width: int,
    output_height: int,
    output_frames: int,
    total_vram_gib: float,
    available_commit_gib: float | None,
) -> dict[str, float | int | bool | str | None]:
    if output_width <= 0 or output_height <= 0 or output_frames <= 0:
        raise ValueError("Output dimensions and frame count must be positive")

    pixels_per_frame = output_width * output_height
    mpx_per_frame = pixels_per_frame / 1_000_000.0

    # Native SeedVR2 tiled decode accumulates the entire RGB result in fp32 and
    # then casts the full tensor to fp16. Both allocations coexist at the peak.
    full_decode_peak_gib = output_frames * pixels_per_frame * 3 * (4 + 2) / GIB

    auto_budget_gib = (
        total_vram_gib
        - SEEDVR2_CHUNK_RESERVED_GIB
        - SEEDVR2_CHUNK_SIGMA_K * SEEDVR2_CHUNK_SIGMA_GIB
    )
    latent_frames = max(
        1,
        int(auto_budget_gib / (SEEDVR2_CHUNK_GIB_PER_MPX_FRAME * mpx_per_frame)),
    )
    auto_chunk_frames = 4 * (latent_frames - 1) + 1
    chunk_tensor_peak_gib = auto_chunk_frames * pixels_per_frame * 3 * (4 + 2) / GIB
    streamed_decode_peak_gib = (
        SEEDVR2_CHUNK_RESERVED_GIB
        + SEEDVR2_CHUNK_SIGMA_K * SEEDVR2_CHUNK_SIGMA_GIB
        + chunk_tensor_peak_gib
    )

    native_source_gib = output_frames * 864 * 480 * 3 * 4 / GIB
    full_reference_gib = output_frames * pixels_per_frame * 3 * 4 / GIB
    final_fp16_gib = output_frames * pixels_per_frame * 3 * 2 / GIB
    estimated_host_commit_gib = (
        native_source_gib
        + 2.0 * full_reference_gib
        + 2.0 * final_fp16_gib
        + HOST_FIXED_HEADROOM_GIB
    )

    safe = True
    reason = "safe"
    if total_vram_gib < streamed_decode_peak_gib:
        safe = False
        reason = (
            f"VRAM preflight failed: estimated streamed peak {streamed_decode_peak_gib:.2f} GiB "
            f"> installed {total_vram_gib:.2f} GiB"
        )
    elif available_commit_gib is not None and available_commit_gib < estimated_host_commit_gib:
        safe = False
        reason = (
            f"Host commit preflight failed: estimated {estimated_host_commit_gib:.2f} GiB "
            f"> currently available {available_commit_gib:.2f} GiB"
        )

    return {
        "safe": safe,
        "reason": reason,
        "output_width": output_width,
        "output_height": output_height,
        "output_frames": output_frames,
        "total_vram_gib": round(total_vram_gib, 3),
        "available_commit_gib": None if available_commit_gib is None else round(available_commit_gib, 3),
        "full_decode_peak_gib": round(full_decode_peak_gib, 3),
        "auto_chunk_frames": auto_chunk_frames,
        "streamed_decode_peak_gib": round(streamed_decode_peak_gib, 3),
        "estimated_host_commit_gib": round(estimated_host_commit_gib, 3),
        "strategy": "SeedVR2 temporal chunks -> per-chunk VAE decode -> CPU fp16 preallocated output",
    }


def _crossfade_weights(overlap: int, dtype: torch.dtype) -> torch.Tensor:
    ramp = torch.linspace(0.0, 1.0, steps=overlap, device="cpu", dtype=torch.float32)
    ramp = ((ramp - 1.0 / 3.0) / (1.0 / 3.0)).clamp(0.0, 1.0)
    return (0.5 + 0.5 * torch.cos(torch.pi * ramp)).to(dtype=dtype)


def merge_decoded_chunks(
    decoded_chunks: Iterable[torch.Tensor],
    *,
    pixel_overlap: int,
    target_frames: int,
    output_dtype: torch.dtype,
) -> torch.Tensor:
    iterator = iter(decoded_chunks)
    try:
        first = next(iterator)
    except StopIteration as exc:
        raise ValueError("At least one decoded chunk is required") from exc

    first = first.detach().to(device="cpu", dtype=output_dtype)
    if first.ndim == 4:
        first = first.unsqueeze(0)
    if first.ndim != 5 or first.shape[0] != 1:
        raise ValueError(f"Expected decoded SeedVR2 chunk shape (1,T,H,W,C), got {tuple(first.shape)}")

    output = torch.empty(
        (1, target_frames, first.shape[2], first.shape[3], first.shape[4]),
        device="cpu",
        dtype=output_dtype,
    )
    written = min(target_frames, first.shape[1])
    output[:, :written].copy_(first[:, :written])
    del first

    for chunk in iterator:
        if written >= target_frames:
            break
        chunk = chunk.detach().to(device="cpu", dtype=output_dtype)
        if chunk.ndim == 4:
            chunk = chunk.unsqueeze(0)
        if chunk.ndim != 5 or chunk.shape[0] != 1 or chunk.shape[2:] != output.shape[2:]:
            raise ValueError(f"Decoded SeedVR2 chunk shape mismatch: {tuple(chunk.shape)}")

        fade = min(pixel_overlap, written, chunk.shape[1])
        if fade > 0:
            start = written - fade
            previous_weight = _crossfade_weights(fade, output_dtype).view(1, fade, 1, 1, 1)
            output[:, start:written].mul_(previous_weight).add_(
                chunk[:, :fade] * (1.0 - previous_weight)
            )

        remaining = chunk[:, fade:]
        count = min(target_frames - written, remaining.shape[1])
        if count > 0:
            output[:, written:written + count].copy_(remaining[:, :count])
            written += count
        del remaining, chunk

    if written != target_frames:
        raise RuntimeError(
            f"Streamed SeedVR2 decode produced {written} frames, expected exactly {target_frames}"
        )
    return output


class H3VideoMemoryPreflight:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "prompt": ("STRING", {"forceInput": True}),
                "output_width": ("INT", {"default": 1920, "min": 64, "max": 8192, "step": 8}),
                "output_height": ("INT", {"default": 1080, "min": 64, "max": 8192, "step": 8}),
                "output_frames": ("INT", {"default": 720, "min": 1, "max": 16384}),
            }
        }

    RETURN_TYPES = ("STRING", "STRING")
    RETURN_NAMES = ("prompt", "memory_plan")
    FUNCTION = "check"
    CATEGORY = "MiniMax H3/safety"

    def check(self, prompt, output_width, output_height, output_frames):
        prompt_text = str(prompt).strip()
        if not prompt_text or prompt_text.startswith("只修改这里："):
            raise RuntimeError("预检停止：请先在蓝色节点中填写真实 prompt，再开始生成。")

        try:
            import comfy.model_management as model_management
        except Exception as exc:
            raise RuntimeError(f"预检停止：无法加载 ComfyUI 显存管理模块：{exc}") from exc
        for required_name in ("free_memory", "LoadedModel", "soft_empty_cache"):
            if not hasattr(model_management, required_name):
                raise RuntimeError(f"预检停止：当前 ComfyUI 缺少 {required_name}，不能安全执行长视频分块解码。")

        plan = build_memory_plan(
            output_width=int(output_width),
            output_height=int(output_height),
            output_frames=int(output_frames),
            total_vram_gib=_total_vram_gib(),
            available_commit_gib=_available_commit_gib(),
        )
        diagnostics = json.dumps(plan, ensure_ascii=False, indent=2)
        logging.info("H3 30s memory preflight:\n%s", diagnostics)
        if not plan["safe"]:
            raise RuntimeError(f"预检停止：{plan['reason']}\n{diagnostics}")
        return (prompt_text, diagnostics)


class H3SeedVR2StreamedDecode:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "latents": ("LATENT",),
                "vae": ("VAE",),
                "temporal_overlap": ("INT", {"forceInput": True, "default": 2, "min": 1, "max": 1024}),
                "target_frames": ("INT", {"default": 720, "min": 1, "max": 16384}),
                "tile_size": ("INT", {"default": 512, "min": 128, "max": 2048, "step": 64}),
                "overlap": ("INT", {"default": 128, "min": 0, "max": 1024, "step": 32}),
                "output_dtype": (["fp16", "fp32"], {"default": "fp16"}),
            }
        }

    INPUT_IS_LIST = True
    OUTPUT_IS_LIST = (False,)
    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("images",)
    FUNCTION = "decode"
    CATEGORY = "MiniMax H3/video"

    @staticmethod
    def _one(values, name):
        if not isinstance(values, list) or not values:
            raise ValueError(f"{name} must contain exactly one workflow value")
        return values[0]

    def decode(self, latents, vae, temporal_overlap, target_frames, tile_size, overlap, output_dtype):
        import comfy.model_management as model_management

        vae_object = self._one(vae, "vae")
        temporal_overlap_value = int(self._one(temporal_overlap, "temporal_overlap"))
        target_frames_value = int(self._one(target_frames, "target_frames"))
        tile_size_value = int(self._one(tile_size, "tile_size"))
        overlap_value = int(self._one(overlap, "overlap"))
        dtype_name = str(self._one(output_dtype, "output_dtype"))
        dtype = torch.float16 if dtype_name == "fp16" else torch.float32

        if not latents or not all(isinstance(entry, dict) and "samples" in entry for entry in latents):
            raise ValueError("latents must be the ordered list output from SeedVR2TemporalChunk/KSampler")
        if temporal_overlap_value < 1 and len(latents) > 1:
            raise ValueError("temporal_overlap must be at least 1 when streamed decoding uses multiple chunks")

        first_stage = getattr(vae_object, "first_stage_model", None)
        temporal_factor = int(getattr(first_stage, "temporal_downsample_factor", 4))
        pixel_overlap = 0
        if temporal_overlap_value > 0:
            pixel_overlap = temporal_overlap_value * temporal_factor - (temporal_factor - 1)
        if len(latents) > 1 and pixel_overlap < 1:
            raise ValueError("The configured temporal overlap does not cover a continuous pixel-frame boundary")

        device = vae_object.device
        keep_loaded = [model_management.LoadedModel(vae_object.patcher)]
        model_management.free_memory(1e30, device, keep_loaded=keep_loaded)
        model_management.soft_empty_cache()

        compression = max(1, int(vae_object.spacial_compression_decode()))
        tile_latent = max(1, tile_size_value // compression)
        overlap_latent = max(0, overlap_value // compression)

        def decoded_stream():
            for index, entry in enumerate(latents):
                samples = entry["samples"]
                logging.info(
                    "H3 SeedVR2 streamed decode chunk %d/%d, latent_shape=%s",
                    index + 1,
                    len(latents),
                    tuple(samples.shape),
                )
                images = vae_object.decode_tiled(
                    samples,
                    tile_x=tile_latent,
                    tile_y=tile_latent,
                    overlap=overlap_latent,
                )
                images = images.detach().to(device="cpu", dtype=dtype)
                yield images
                del images
                model_management.soft_empty_cache()

        output = merge_decoded_chunks(
            decoded_stream(),
            pixel_overlap=pixel_overlap,
            target_frames=target_frames_value,
            output_dtype=dtype,
        )
        output_images = output.squeeze(0)
        logging.info(
            "H3 SeedVR2 streamed decode complete: shape=%s dtype=%s pixel_overlap=%d",
            tuple(output_images.shape),
            output_images.dtype,
            pixel_overlap,
        )
        return (output_images,)


NODE_CLASS_MAPPINGS = {
    "H3VideoMemoryPreflight": H3VideoMemoryPreflight,
    "H3SeedVR2StreamedDecode": H3SeedVR2StreamedDecode,
}
NODE_DISPLAY_NAME_MAPPINGS = {
    "H3VideoMemoryPreflight": "H3 30s Memory Preflight",
    "H3SeedVR2StreamedDecode": "H3 SeedVR2 Streamed Chunk Decode",
}
