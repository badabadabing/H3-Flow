from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass


I2VA_ALIGNMENT = (
    "For the target video, at 0.00 seconds into the target video, "
    "<Picture 1> (from [Shot 1]) is fully referenced."
)

FIELD_PATTERN = re.compile(
    r"(?im)^[ \t]*(integrated_multimodal_description|overall_soundscape|non_diegetic_music)"
    r"[ \t]*[:：][ \t]*"
)
TIME_RANGE_PATTERN = re.compile(
    r"(?im)^[ \t]*\[?[ \t]*"
    r"(?P<start>\d{1,2}(?::\d{1,2})?(?:\.\d+)?)"
    r"[ \t]*(?:—|–|-|至|~|～)[ \t]*"
    r"(?P<end>\d{1,2}(?::\d{1,2})?(?:\.\d+)?)"
    r"[ \t]*\]?[ \t]*(?:秒|seconds?|s)?[ \t]*[:：][ \t]*"
)


@dataclass(frozen=True)
class TimedBeat:
    start: float
    end: float
    content: str


def _parse_seconds(value: str) -> float:
    parts = value.split(":")
    if len(parts) == 1:
        return float(parts[0])
    if len(parts) == 2:
        return float(parts[0]) * 60.0 + float(parts[1])
    raise ValueError(f"无法识别时间：{value}")


def _format_time(seconds: float) -> str:
    minutes = int(seconds // 60)
    remainder = seconds - minutes * 60
    return f"{minutes:02d}:{remainder:06.3f}"


def _split_fields(prompt: str) -> tuple[str, dict[str, str]]:
    matches = list(FIELD_PATTERN.finditer(prompt))
    if not matches:
        return prompt.strip(), {}

    preamble = prompt[: matches[0].start()].strip()
    fields: dict[str, str] = {}
    for index, match in enumerate(matches):
        name = match.group(1).lower()
        if name in fields:
            raise ValueError(f"同一提示词中不能重复定义 {name}")
        end = matches[index + 1].start() if index + 1 < len(matches) else len(prompt)
        fields[name] = prompt[match.end() : end].strip()
    return preamble, fields


def _parse_timed_source(source: str, total_seconds: float) -> tuple[str, list[TimedBeat]]:
    matches = list(TIME_RANGE_PATTERN.finditer(source))
    if not matches:
        raise ValueError(
            "没有找到可分段的时间段。请至少使用“0-15秒：...”和“15-30秒：...”格式，"
            "否则工作流会在生成前停止以避免第二段重演第一段。"
        )

    global_text = source[: matches[0].start()].strip()
    beats: list[TimedBeat] = []
    for index, match in enumerate(matches):
        start = _parse_seconds(match.group("start"))
        end = _parse_seconds(match.group("end"))
        content_end = matches[index + 1].start() if index + 1 < len(matches) else len(source)
        content = source[match.end() : content_end].strip()
        if start < 0 or end <= start or end > total_seconds + 0.001:
            raise ValueError(
                f"时间段 {_format_time(start)}-{_format_time(end)} 无效；总时长为 {total_seconds:.2f} 秒。"
            )
        if not content:
            raise ValueError(f"时间段 {_format_time(start)}-{_format_time(end)} 没有剧情内容。")
        beats.append(TimedBeat(start=start, end=end, content=content))

    ordered = sorted(beats, key=lambda beat: (beat.start, beat.end))
    if ordered != beats:
        raise ValueError("时间段必须按剧情发生顺序递增书写。")
    return global_text, beats


def parse_master_prompt(master_prompt: str, total_seconds: float) -> tuple[str, list[TimedBeat], str, str]:
    prompt = str(master_prompt).strip()
    if not prompt:
        raise ValueError("提示词不能为空。")
    if total_seconds <= 0:
        raise ValueError("总时长必须大于 0。")

    preamble, fields = _split_fields(prompt)
    integrated = fields.get("integrated_multimodal_description", "")
    if TIME_RANGE_PATTERN.search(preamble):
        timed_source = preamble
        integrated_extra = integrated
    elif TIME_RANGE_PATTERN.search(integrated):
        timed_source = integrated
        integrated_extra = preamble
    else:
        timed_source = preamble or integrated
        integrated_extra = ""

    global_text, beats = _parse_timed_source(timed_source, total_seconds)
    global_parts = [part for part in (global_text, integrated_extra) if part]
    global_description = "\n\n".join(global_parts).strip()
    soundscape = fields.get(
        "overall_soundscape",
        "Physically plausible ambience and synchronized action sounds follow only the selected story beats.",
    )
    music = fields.get("non_diegetic_music", "N/A")
    return global_description, beats, soundscape, music


def compile_segment_prompt(
    master_prompt: str,
    *,
    segment_start: float,
    segment_end: float,
    total_seconds: float,
    has_first_frame: bool,
) -> tuple[str, dict]:
    if segment_start < 0 or segment_end <= segment_start or segment_end > total_seconds + 0.001:
        raise ValueError("分段边界无效。")

    global_description, beats, soundscape, music = parse_master_prompt(master_prompt, total_seconds)
    selected = [beat for beat in beats if beat.end > segment_start and beat.start < segment_end]
    starts_here = [beat for beat in beats if segment_start <= beat.start < segment_end]
    if not selected or not starts_here:
        raise ValueError(
            f"主提示词没有为 {segment_start:.2f}-{segment_end:.2f} 秒提供独立的新剧情时间段；"
            "已停止生成，避免复用上一段内容。"
        )

    duration = segment_end - segment_start
    continuity = (
        "The image in <Picture 1> is the exact final frame of the preceding segment. "
        f"The story state at master {_format_time(segment_start)} is already established. "
        "Continue forward immediately from the visible pose, object state, camera motion and spatial layout. "
        "All earlier master-timeline events are complete and remain absent from this target clip."
        if has_first_frame
        else (
            f"This target clip contains only master timeline {_format_time(segment_start)}-"
            f"{_format_time(segment_end)}. Later events have not happened yet."
        )
    )
    identity = (
        global_description
        or "Preserve the same subject identity, clothing, environment, lighting, camera axis and audiovisual style."
    )

    beat_lines: list[str] = []
    for beat in selected:
        local_start = max(0.0, beat.start - segment_start)
        local_end = min(duration, beat.end - segment_start)
        beat_lines.append(
            f"Target interval {_format_time(local_start)}-{_format_time(local_end)} "
            f"(master timeline {_format_time(max(beat.start, segment_start))}-"
            f"{_format_time(min(beat.end, segment_end))}): {beat.content}"
        )

    integrated_body = "\n".join(
        [
            f"[Shot 1] {continuity}",
            f"Continuity bible: {identity}",
            *beat_lines,
            "Execute these selected beats once, in order, as forward progression; end on their resulting new state.",
        ]
    )
    if has_first_frame:
        soundscape_value = (
            "Continue the already-established ambience, room tone, reverb, spatial perspective and speaker "
            "identities without a new intro. Follow only this target clip's selected beats. " + soundscape
        )
        music_value = (
            "N/A"
            if music.strip().upper() == "N/A"
            else (
                "Continue the already-playing musical phrase at its current measure with the same key, tempo, "
                "rhythm, instrumentation and mix. Do not restart the opening or replay earlier accents; apply "
                "changes only to this target clip's selected beats. Original continuity specification: " + music
            )
        )
    else:
        soundscape_value = soundscape
        music_value = music

    parts = []
    if has_first_frame:
        parts.extend([I2VA_ALIGNMENT, ""])
    parts.extend(
        [
            "integrated_multimodal_description: " + integrated_body,
            "",
            "overall_soundscape: " + soundscape_value,
            "",
            "non_diegetic_music: " + music_value,
        ]
    )
    compiled = "\n".join(parts).strip()
    diagnostics = {
        "segment_start": segment_start,
        "segment_end": segment_end,
        "local_duration": duration,
        "has_first_frame": has_first_frame,
        "master_ranges": [[beat.start, beat.end] for beat in selected],
        "compiled_sha256": hashlib.sha256(compiled.encode("utf-8")).hexdigest(),
        "compiled_characters": len(compiled),
    }
    return compiled, diagnostics


def compile_segment_prompts(
    master_prompt: str, *, split_seconds: float = 15.0, total_seconds: float = 30.0
) -> tuple[str, str, str]:
    if split_seconds <= 0 or split_seconds >= total_seconds:
        raise ValueError("剧情分割点必须位于总时长内部。")
    first, first_diagnostics = compile_segment_prompt(
        master_prompt,
        segment_start=0.0,
        segment_end=split_seconds,
        total_seconds=total_seconds,
        has_first_frame=False,
    )
    second, second_diagnostics = compile_segment_prompt(
        master_prompt,
        segment_start=split_seconds,
        segment_end=total_seconds,
        total_seconds=total_seconds,
        has_first_frame=True,
    )
    diagnostics = json.dumps(
        {
            "strategy": "one master prompt -> isolated local timelines; segment 2 uses official I2VA alignment",
            "first": first_diagnostics,
            "second": second_diagnostics,
        },
        ensure_ascii=False,
        indent=2,
    )
    return first, second, diagnostics


def compile_segment_series(
    master_prompt: str,
    *,
    segment_seconds: float,
    total_seconds: float,
    first_has_reference: bool = False,
) -> list[str]:
    if segment_seconds <= 0 or total_seconds <= 0:
        raise ValueError("分段时长和总时长必须大于 0。")
    segment_count = int(round(total_seconds / segment_seconds))
    if abs(segment_count * segment_seconds - total_seconds) > 0.001:
        raise ValueError("总时长必须能被分段时长整除。")
    return [
        compile_segment_prompt(
            master_prompt,
            segment_start=index * segment_seconds,
            segment_end=(index + 1) * segment_seconds,
            total_seconds=total_seconds,
            has_first_frame=first_has_reference if index == 0 else True,
        )[0]
        for index in range(segment_count)
    ]


class H3SegmentPromptCompiler:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "master_prompt": ("STRING", {"forceInput": True}),
                "split_seconds": ("FLOAT", {"default": 15.0, "min": 1.0, "max": 120.0, "step": 0.01}),
                "total_seconds": ("FLOAT", {"default": 30.0, "min": 2.0, "max": 240.0, "step": 0.01}),
            }
        }

    RETURN_TYPES = ("STRING", "STRING", "STRING")
    RETURN_NAMES = ("segment_1_prompt", "segment_2_prompt", "diagnostics")
    FUNCTION = "compile"
    CATEGORY = "MiniMax H3/prompt"

    def compile(self, master_prompt, split_seconds, total_seconds):
        return compile_segment_prompts(
            str(master_prompt),
            split_seconds=float(split_seconds),
            total_seconds=float(total_seconds),
        )


NODE_CLASS_MAPPINGS = {"H3SegmentPromptCompiler": H3SegmentPromptCompiler}
NODE_DISPLAY_NAME_MAPPINGS = {
    "H3SegmentPromptCompiler": "H3 Story Segment Prompt Compiler",
}
