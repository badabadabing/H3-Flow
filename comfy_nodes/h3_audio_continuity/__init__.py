from __future__ import annotations

import math

import torch
import torchaudio


def _as_float_audio(audio: dict, name: str) -> tuple[torch.Tensor, int]:
    if audio is None:
        raise ValueError(f"{name} is missing")
    if "waveform" not in audio or "sample_rate" not in audio:
        raise ValueError(f"{name} must contain waveform and sample_rate")

    waveform = audio["waveform"]
    if not isinstance(waveform, torch.Tensor) or waveform.ndim != 3:
        raise ValueError(f"{name}.waveform must have shape [batch, channels, samples]")
    if waveform.shape[-1] == 0:
        raise ValueError(f"{name}.waveform is empty")

    if not waveform.dtype.is_floating_point:
        waveform = waveform.float()
    else:
        waveform = waveform.to(dtype=torch.float32)

    sample_rate = int(audio["sample_rate"])
    if sample_rate <= 0:
        raise ValueError(f"{name}.sample_rate must be positive")

    if waveform.shape[1] == 1:
        waveform = waveform.repeat(1, 2, 1)

    return waveform, sample_rate


def _fit_length(waveform: torch.Tensor, length: int) -> tuple[torch.Tensor, int]:
    current = waveform.shape[-1]
    if current == length:
        return waveform, 0
    if current > length:
        return waveform[..., :length], current - length

    pad = waveform.new_zeros((*waveform.shape[:-1], length - current))
    return torch.cat((waveform, pad), dim=-1), -(length - current)


def _dbfs(value: float) -> float:
    return 20.0 * math.log10(max(value, 1.0e-12))


class H3AudioContinuityMaster:
    """Join two native H3 audio segments without changing their timeline."""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "audio1": ("AUDIO",),
                "audio2": ("AUDIO",),
                "first_segment_frames": (
                    "INT",
                    {"default": 362, "min": 1, "max": 3600, "step": 1},
                ),
                "second_trim_frames": (
                    "INT",
                    {"default": 1, "min": 0, "max": 120, "step": 1},
                ),
                "fps": (
                    "FLOAT",
                    {"default": 24.0, "min": 1.0, "max": 120.0, "step": 1.0},
                ),
                "final_duration": (
                    "FLOAT",
                    {"default": 30.0, "min": 0.1, "max": 600.0, "step": 0.01},
                ),
                "boundary_fade_ms": (
                    "FLOAT",
                    {"default": 15.0, "min": 0.0, "max": 100.0, "step": 1.0},
                ),
                "target_rms_dbfs": (
                    "FLOAT",
                    {"default": -18.0, "min": -36.0, "max": -6.0, "step": 0.5},
                ),
                "target_peak_dbfs": (
                    "FLOAT",
                    {"default": -1.0, "min": -12.0, "max": -0.1, "step": 0.1},
                ),
                "max_makeup_db": (
                    "FLOAT",
                    {"default": 3.0, "min": 0.0, "max": 12.0, "step": 0.5},
                ),
            }
        }

    RETURN_TYPES = ("AUDIO", "STRING")
    RETURN_NAMES = ("audio", "diagnostics")
    FUNCTION = "master"
    CATEGORY = "audio/minimax_h3"
    DESCRIPTION = (
        "Aligns two native MiniMax H3 audio segments to the video join, removes DC, "
        "applies a short click-safe boundary fade, conservative RMS gain and peak protection, "
        "then returns an exact-duration native-sample-rate master."
    )

    def master(
        self,
        audio1: dict,
        audio2: dict,
        first_segment_frames: int,
        second_trim_frames: int,
        fps: float,
        final_duration: float,
        boundary_fade_ms: float,
        target_rms_dbfs: float,
        target_peak_dbfs: float,
        max_makeup_db: float,
    ):
        first, first_rate = _as_float_audio(audio1, "audio1")
        second, second_rate = _as_float_audio(audio2, "audio2")

        if first.shape[0] != second.shape[0]:
            raise ValueError("audio batches do not match")
        if first.shape[1] != second.shape[1]:
            raise ValueError("audio channel counts do not match")

        if second_rate != first_rate:
            second = torchaudio.functional.resample(second, second_rate, first_rate)

        nonfinite = int((~torch.isfinite(first)).sum().item())
        nonfinite += int((~torch.isfinite(second)).sum().item())
        first = torch.nan_to_num(first)
        second = torch.nan_to_num(second)

        # Remove segment-level DC without filtering or inventing high-frequency content.
        first = first - first.mean(dim=-1, keepdim=True)
        second = second - second.mean(dim=-1, keepdim=True)

        join_samples = int(round(first_segment_frames / fps * first_rate))
        first, first_fit_delta = _fit_length(first, join_samples)

        second_trim_samples = int(round(second_trim_frames / fps * first_rate))
        if second_trim_samples >= second.shape[-1]:
            raise ValueError("second_trim_frames removes the entire second audio segment")
        second = second[..., second_trim_samples:]

        fade_samples = min(
            int(round(boundary_fade_ms / 1000.0 * first_rate)),
            first.shape[-1],
            second.shape[-1],
        )
        if fade_samples > 1:
            phase = torch.linspace(
                0.0,
                math.pi / 2.0,
                fade_samples,
                device=first.device,
                dtype=first.dtype,
            )
            first[..., -fade_samples:] *= torch.cos(phase)
            second[..., :fade_samples] *= torch.sin(phase)

        master = torch.cat((first, second), dim=-1)
        final_samples = int(round(final_duration * first_rate))
        master, final_fit_delta = _fit_length(master, final_samples)

        peak_before = float(master.abs().max().item())
        rms_before = float(torch.sqrt(torch.mean(master.square())).item())
        peak_before_db = _dbfs(peak_before)
        rms_before_db = _dbfs(rms_before)

        rms_gain_db = target_rms_dbfs - rms_before_db
        peak_gain_db = target_peak_dbfs - peak_before_db
        gain_db = min(max_makeup_db, rms_gain_db, peak_gain_db)
        master = master * (10.0 ** (gain_db / 20.0))

        # A final exact clamp is a safety net for floating point rounding, not a limiter.
        peak_ceiling = 10.0 ** (target_peak_dbfs / 20.0)
        master = master.clamp(min=-peak_ceiling, max=peak_ceiling)
        peak_after = float(master.abs().max().item())
        rms_after = float(torch.sqrt(torch.mean(master.square())).item())

        diagnostics = "\n".join(
            (
                f"sample_rate={first_rate}",
                f"channels={master.shape[1]}",
                f"duration_seconds={master.shape[-1] / first_rate:.6f}",
                f"video_join_seconds={first_segment_frames / fps:.6f}",
                f"second_trim_seconds={second_trim_samples / first_rate:.6f}",
                f"boundary_fade_ms={fade_samples / first_rate * 1000.0:.3f}",
                f"first_fit_delta_samples={first_fit_delta}",
                f"final_fit_delta_samples={final_fit_delta}",
                f"nonfinite_replaced={nonfinite}",
                f"gain_db={gain_db:.3f}",
                f"peak_before_dbfs={peak_before_db:.3f}",
                f"rms_before_dbfs={rms_before_db:.3f}",
                f"peak_after_dbfs={_dbfs(peak_after):.3f}",
                f"rms_after_dbfs={_dbfs(rms_after):.3f}",
            )
        )

        return ({"waveform": master, "sample_rate": first_rate}, diagnostics)


class H3AudioSequenceMaster:
    """Join one to six short native H3 audio segments on the video frame grid."""

    @classmethod
    def INPUT_TYPES(cls):
        audio_input = ("AUDIO",)
        return {
            "required": {
                "audio1": audio_input,
                "segment_count": ("INT", {"default": 2, "min": 1, "max": 6, "step": 1}),
                "segment_frames": ("INT", {"default": 124, "min": 5, "max": 362, "step": 1}),
                "trim_frames": ("INT", {"default": 1, "min": 0, "max": 120, "step": 1}),
                "fps": ("FLOAT", {"default": 24.0, "min": 1.0, "max": 120.0, "step": 1.0}),
                "final_duration": ("FLOAT", {"default": 10.0, "min": 0.1, "max": 600.0, "step": 0.01}),
                "boundary_fade_ms": ("FLOAT", {"default": 15.0, "min": 0.0, "max": 100.0, "step": 1.0}),
                "target_rms_dbfs": ("FLOAT", {"default": -18.0, "min": -36.0, "max": -6.0, "step": 0.5}),
                "target_peak_dbfs": ("FLOAT", {"default": -1.0, "min": -12.0, "max": -0.1, "step": 0.1}),
                "max_makeup_db": ("FLOAT", {"default": 3.0, "min": 0.0, "max": 12.0, "step": 0.5}),
            },
            "optional": {
                "audio2": audio_input,
                "audio3": audio_input,
                "audio4": audio_input,
                "audio5": audio_input,
                "audio6": audio_input,
            },
        }

    RETURN_TYPES = ("AUDIO", "STRING")
    RETURN_NAMES = ("audio", "diagnostics")
    FUNCTION = "master"
    CATEGORY = "audio/minimax_h3"
    DESCRIPTION = (
        "Frame-aligns one to six short MiniMax H3 audio segments, removes duplicate "
        "boundary time, applies click-safe fades, and returns one exact-duration master."
    )

    def master(
        self,
        audio1: dict,
        segment_count: int,
        segment_frames: int,
        trim_frames: int,
        fps: float,
        final_duration: float,
        boundary_fade_ms: float,
        target_rms_dbfs: float,
        target_peak_dbfs: float,
        max_makeup_db: float,
        audio2: dict | None = None,
        audio3: dict | None = None,
        audio4: dict | None = None,
        audio5: dict | None = None,
        audio6: dict | None = None,
    ):
        supplied = [audio1, audio2, audio3, audio4, audio5, audio6][:segment_count]
        if any(audio is None for audio in supplied):
            raise ValueError(f"segment_count={segment_count} but one or more audio inputs are missing")

        prepared: list[torch.Tensor] = []
        reference_rate = 0
        nonfinite = 0
        segment_samples = 0
        trim_samples = 0

        for index, audio in enumerate(supplied):
            waveform, sample_rate = _as_float_audio(audio, f"audio{index + 1}")
            if index == 0:
                reference_rate = sample_rate
                segment_samples = int(round(segment_frames / fps * reference_rate))
                trim_samples = int(round(trim_frames / fps * reference_rate))
            elif sample_rate != reference_rate:
                waveform = torchaudio.functional.resample(waveform, sample_rate, reference_rate)

            nonfinite += int((~torch.isfinite(waveform)).sum().item())
            waveform = torch.nan_to_num(waveform)
            waveform = waveform - waveform.mean(dim=-1, keepdim=True)
            waveform, _ = _fit_length(waveform, segment_samples)
            if index > 0 and trim_samples:
                if trim_samples >= waveform.shape[-1]:
                    raise ValueError("trim_frames removes an entire audio segment")
                waveform = waveform[..., trim_samples:]
            prepared.append(waveform)

        fade_samples = min(
            int(round(boundary_fade_ms / 1000.0 * reference_rate)),
            *(waveform.shape[-1] for waveform in prepared),
        )
        if fade_samples > 1:
            phase = torch.linspace(0.0, math.pi / 2.0, fade_samples, dtype=prepared[0].dtype)
            fade_out = torch.cos(phase)
            fade_in = torch.sin(phase)
            for index in range(len(prepared) - 1):
                prepared[index][..., -fade_samples:] *= fade_out.to(prepared[index].device)
                prepared[index + 1][..., :fade_samples] *= fade_in.to(prepared[index + 1].device)

        master = torch.cat(prepared, dim=-1)
        final_samples = int(round(final_duration * reference_rate))
        master, final_fit_delta = _fit_length(master, final_samples)

        peak_before = float(master.abs().max().item())
        rms_before = float(torch.sqrt(torch.mean(master.square())).item())
        rms_gain_db = target_rms_dbfs - _dbfs(rms_before)
        peak_gain_db = target_peak_dbfs - _dbfs(peak_before)
        gain_db = min(max_makeup_db, rms_gain_db, peak_gain_db)
        master = master * (10.0 ** (gain_db / 20.0))

        peak_ceiling = 10.0 ** (target_peak_dbfs / 20.0)
        master = master.clamp(min=-peak_ceiling, max=peak_ceiling)
        diagnostics = "\n".join(
            (
                f"segments={segment_count}",
                f"sample_rate={reference_rate}",
                f"channels={master.shape[1]}",
                f"duration_seconds={master.shape[-1] / reference_rate:.6f}",
                f"segment_frames={segment_frames}",
                f"trim_frames={trim_frames}",
                f"boundary_fade_ms={fade_samples / reference_rate * 1000.0:.3f}",
                f"final_fit_delta_samples={final_fit_delta}",
                f"nonfinite_replaced={nonfinite}",
                f"gain_db={gain_db:.3f}",
                f"peak_after_dbfs={_dbfs(float(master.abs().max().item())):.3f}",
                f"rms_after_dbfs={_dbfs(float(torch.sqrt(torch.mean(master.square())).item())):.3f}",
            )
        )
        return ({"waveform": master, "sample_rate": reference_rate}, diagnostics)


NODE_CLASS_MAPPINGS = {
    "H3AudioContinuityMaster": H3AudioContinuityMaster,
    "H3AudioSequenceMaster": H3AudioSequenceMaster,
}
NODE_DISPLAY_NAME_MAPPINGS = {
    "H3AudioContinuityMaster": "MiniMax H3 Audio Continuity Master",
    "H3AudioSequenceMaster": "MiniMax H3 Audio Sequence Master",
}
