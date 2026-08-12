from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from typing import Any


DEFAULT_BASE_URL = "https://api.deepseek.com"
DEFAULT_MODEL = "deepseek-v4-flash"
GUIDE_REVISION = "939557dc319dd91227e30195a763f272ba7f8765"
GUIDE_BASE_URL = (
    "https://huggingface.co/MiniMaxAI/MiniMax-H3/blob/main/"
    "docs/VIDEO_PROMPT_WRITING_GUIDE_base_en.md"
)
GUIDE_REF_URL = (
    "https://huggingface.co/MiniMaxAI/MiniMax-H3/blob/main/"
    "docs/VIDEO_PROMPT_WRITING_GUIDE_ref_en.md"
)
SUPPORTED_DURATIONS = (5, 10, 15, 30)
SUPPORTED_ASPECTS = ("16:9", "9:16", "1:1")
SUPPORTED_REFERENCE_MODES = ("none", "first_frame", "identity")
MAX_BRIEF_CHARACTERS = 6000
MAX_PROMPT_CHARACTERS = 12000

I2VA_ALIGNMENT = (
    "For the target video, at 0.00 seconds into the target video, "
    "<Picture 1> (from [Shot 1]) is fully referenced."
)

BASE_SYSTEM_PROMPT = f"""
You are the H3 Flow prompt director. Rewrite a user's creative brief into a final MiniMax H3 Base prompt by following the official MiniMaxAI/MiniMax-H3 Video Prompt Writing Guide at revision {GUIDE_REVISION}.

Return only the final prompt. Do not use Markdown fences, headings outside the required fields, explanations, alternatives, or notes to the user.

Rules that must always hold:
1. Write the prompt in English. Preserve the original language only inside dialogue or lyrics in <d>[Language] ...</d> and for text visibly present in the scene.
2. The three fields must appear exactly once and in this order: integrated_multimodal_description, overall_soundscape, non_diegetic_music.
3. integrated_multimodal_description develops visible and audible events along the timeline. Begin with [Shot 1] and do not timestamp the first shot. A later cut begins with [Shot N] At MM:SS.mmm, and cut times strictly increase within the requested duration.
4. Prefer camera motion instead of a cut when only distance or a slight angle changes. Describe camera motion naturally using motion type plus meaningful amplitude and speed, such as pushes in with small amplitude at slow speed.
5. Give every actual vocal source a stable (S1), (S2), and so on. Preserve user-provided dialogue verbatim inside <d>[Language] ...</d>. Never invent dialogue, lyrics, signs, subtitles, or visible text.
6. overall_soundscape is one paragraph of 1-4 sentences covering ambience, physical action sounds, and non-verbal human sounds. Do not repeat dialogue, singing, or music there. Use N/A only when the user explicitly requests complete silence.
7. non_diegetic_music is 1-3 sentences about audience-only score using instrumentation, tempo, rhythm, and dynamics. Use N/A when the user requests no audience-only music. Diegetic music belongs in the timeline instead.
8. Add concrete details only when they support the user's intent. Keep identity, clothing, object state, lighting, camera axis, movement direction, and spatial relationships internally consistent.
9. Do not append generic negative-prompt lists. Do not claim to have inspected an image because no image bytes are supplied to you.
""".strip()

REF_SYSTEM_PROMPT = f"""
You are the H3 Flow prompt director. Rewrite a user's creative brief into a final MiniMax H3 Ref2VA full-reference prompt by following the official MiniMaxAI/MiniMax-H3 Full-Reference Mode Rewrite Output Format Guide at revision {GUIDE_REVISION}.

Return only the final prompt. Do not use Markdown fences, explanations, alternatives, or notes to the user. Write all sections in English, preserving the original language only inside dialogue or lyrics in <d>[Language] ...</d> and for text visibly present in the scene.

The six sections must appear exactly once and in this order:
subject_definitions
summary
retention_analysis
detailed_description
overall_soundscape
non_diegetic_music

Rules that must always hold:
1. Use <Subject 1> for the identity, product, environment, or style derived from <Picture 1>. The reference image itself is not supplied to you, so never invent facial features, clothing, colors, objects, text, or composition that the user's brief did not state.
2. summary begins with [reference generation] and concisely states the target and reference relationship.
3. retention_analysis uses only official markers: fully_preserved, partially_preserved, attribute_transfer, or weak_reference. Do not claim stronger preservation than the user's request supports.
4. detailed_description establishes style in one or two sentences before [Shot 1], then describes composition, subject position, environment, lighting, action and state changes, camera motion, synchronized sound, and where <Subject 1> applies.
5. The first shot has no timestamp. Later cuts use [Shot N] At MM:SS.mmm, with strictly increasing times inside the requested duration.
6. Use stable (S1), (S2) speaker IDs and preserve any user-provided dialogue verbatim inside <d>[Language] ...</d>. Never invent dialogue, lyrics, signs, subtitles, or visible text.
7. overall_soundscape and non_diegetic_music follow the same official separation as H3 Base. Use N/A for non_diegetic_music when no audience-only music is requested.
8. Do not use Markdown fences and do not add sections outside the six required sections.
""".strip()


def _clean_string(value: Any, *, maximum: int, label: str) -> str:
    text = str(value or "").strip()
    if len(text) > maximum:
        raise ValueError(f"{label}过长，最多 {maximum} 个字符")
    return text


def _is_loopback(hostname: str | None) -> bool:
    return (hostname or "").lower() in {"127.0.0.1", "localhost", "::1"}


def _normalise_endpoint(base_url: str) -> tuple[str, str]:
    base_url = base_url.strip().rstrip("/")
    if not base_url:
        raise ValueError("请填写模型服务地址")
    if len(base_url) > 2048:
        raise ValueError("模型服务地址过长")
    parsed = urllib.parse.urlsplit(base_url)
    if parsed.scheme not in {"https", "http"} or not parsed.hostname:
        raise ValueError("模型服务地址必须是有效的 HTTP(S) URL")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError("模型服务地址不能包含账号、密码、查询参数或片段")
    if parsed.scheme == "http" and not _is_loopback(parsed.hostname):
        raise ValueError("远程模型服务必须使用 HTTPS；HTTP 仅允许本机地址")
    endpoint = base_url if parsed.path.rstrip("/").endswith("/chat/completions") else base_url + "/chat/completions"
    return base_url, endpoint


def _provider_name(base_url: str) -> str:
    hostname = (urllib.parse.urlsplit(base_url).hostname or "").lower()
    if hostname == "api.deepseek.com" or hostname.endswith(".deepseek.com"):
        return "DeepSeek"
    if _is_loopback(hostname):
        return "本机兼容服务"
    return "OpenAI-compatible"


def prompt_assistant_status() -> dict[str, Any]:
    base_url = os.environ.get("H3_FLOW_LLM_BASE_URL", DEFAULT_BASE_URL).strip() or DEFAULT_BASE_URL
    model = os.environ.get("H3_FLOW_LLM_MODEL", DEFAULT_MODEL).strip() or DEFAULT_MODEL
    key_present = bool(os.environ.get("H3_FLOW_LLM_API_KEY", "").strip())
    try:
        normalised_base, _ = _normalise_endpoint(base_url)
    except ValueError:
        normalised_base = DEFAULT_BASE_URL
    return {
        "environment_configured": key_present,
        "default_base_url": normalised_base,
        "default_model": model,
        "provider": _provider_name(normalised_base),
        "guide_revision": GUIDE_REVISION,
        "guide_urls": {"base": GUIDE_BASE_URL, "reference": GUIDE_REF_URL},
        "privacy": "只发送提示词、时长、比例和参考模式；不发送参考图、路径、硬件或工作流。",
    }


def _resolve_config(raw: dict[str, Any] | None) -> dict[str, str]:
    raw = raw if isinstance(raw, dict) else {}
    env_base = os.environ.get("H3_FLOW_LLM_BASE_URL", DEFAULT_BASE_URL)
    env_model = os.environ.get("H3_FLOW_LLM_MODEL", DEFAULT_MODEL)
    env_key = os.environ.get("H3_FLOW_LLM_API_KEY", "")
    base_url, endpoint = _normalise_endpoint(_clean_string(raw.get("base_url") or env_base, maximum=2048, label="模型服务地址"))
    model = _clean_string(raw.get("model") or env_model, maximum=128, label="模型名称")
    api_key = _clean_string(raw.get("api_key") or env_key, maximum=1024, label="API Key")
    if not model or not re.fullmatch(r"[A-Za-z0-9._:/-]+", model):
        raise ValueError("模型名称无效")
    if not api_key and not _is_loopback(urllib.parse.urlsplit(base_url).hostname):
        raise ValueError("远程模型服务需要 API Key；Key 仅用于本次请求，不会写入项目")
    return {
        "base_url": base_url,
        "endpoint": endpoint,
        "model": model,
        "api_key": api_key,
        "provider": _provider_name(base_url),
    }


def _normalise_request(raw: dict[str, Any]) -> dict[str, Any]:
    brief = _clean_string(raw.get("brief"), maximum=MAX_BRIEF_CHARACTERS, label="创意描述")
    if len(brief) < 12:
        raise ValueError("请先写至少 12 个字符的创意描述")
    try:
        duration = int(raw.get("duration", 5))
    except (TypeError, ValueError) as exc:
        raise ValueError("视频时长无效") from exc
    if duration not in SUPPORTED_DURATIONS:
        raise ValueError("提示词编导仅支持 5、10、15 或 30 秒")
    aspect = str(raw.get("aspect") or "16:9")
    if aspect not in SUPPORTED_ASPECTS:
        raise ValueError("画面比例无效")
    reference_mode = str(raw.get("reference_mode") or "none")
    if reference_mode not in SUPPORTED_REFERENCE_MODES:
        raise ValueError("参考模式无效")
    if reference_mode == "identity" and duration > 5:
        raise ValueError("Ref2VA 提示词编导当前只开放已验证的 5 秒档")
    return {"brief": brief, "duration": duration, "aspect": aspect, "reference_mode": reference_mode}


def _task_instruction(request: dict[str, Any]) -> str:
    mode = request["reference_mode"]
    duration = request["duration"]
    if mode == "identity":
        task = (
            "Task mode: Ref2VA identity/style reference. Picture 1 exists, but its bytes are deliberately not sent. "
            "Use only visual facts explicitly stated in the brief and otherwise refer to <Subject 1> abstractly."
        )
    elif mode == "first_frame":
        task = (
            "Task mode: I2VA first-frame generation. The final output must begin with this exact line, followed by "
            f"one blank line: {I2VA_ALIGNMENT} Establish Picture 1 as the opening anchor, then develop forward."
        )
    else:
        task = "Task mode: T2VA. Begin directly with the required core fields and do not add an image-alignment line."

    timeline = ""
    if duration > 5:
        ranges = ", ".join(f"{start}-{start + 5}s:" for start in range(0, duration, 5))
        timeline = (
            " This long request is assembled from five-second production beats. Inside "
            "integrated_multimodal_description, put each required range marker at the start of its own line in this "
            f"exact sequence: {ranges} Each range must introduce new forward action, while official [Shot N] and "
            "absolute cut-time syntax remains intact."
        )
    return f"{task}{timeline}"


def build_messages(raw: dict[str, Any]) -> tuple[list[dict[str, str]], dict[str, Any]]:
    request = _normalise_request(raw)
    system_prompt = REF_SYSTEM_PROMPT if request["reference_mode"] == "identity" else BASE_SYSTEM_PROMPT
    user_prompt = (
        f"Target duration: {request['duration']} seconds\n"
        f"Target aspect ratio: {request['aspect']}\n"
        f"{_task_instruction(request)}\n\n"
        "User creative brief:\n"
        f"{request['brief']}"
    )
    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ], request


def _strip_fences(content: str) -> str:
    content = content.strip()
    if content.startswith("```"):
        lines = content.splitlines()
        if lines and lines[0].lstrip().startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        content = "\n".join(lines).strip()
    return content


def _field_positions(prompt: str, fields: tuple[str, ...]) -> list[int]:
    positions: list[int] = []
    for field in fields:
        matches = list(re.finditer(rf"(?im)^\s*{re.escape(field)}\s*:\s*", prompt))
        if len(matches) != 1:
            raise ValueError(f"模型输出不符合 H3 官方结构：{field} 必须且只能出现一次")
        positions.append(matches[0].start())
    if positions != sorted(positions):
        raise ValueError("模型输出不符合 H3 官方字段顺序")
    return positions


def validate_generated_prompt(prompt: str, request: dict[str, Any]) -> list[str]:
    if len(prompt) < 100:
        raise ValueError("模型返回的提示词过短，未达到可执行细节要求")
    if len(prompt) > MAX_PROMPT_CHARACTERS:
        raise ValueError(f"模型返回的提示词超过 {MAX_PROMPT_CHARACTERS} 个字符")
    if "```" in prompt:
        raise ValueError("模型返回了 Markdown 代码块，而不是纯 H3 提示词")

    mode = request["reference_mode"]
    if mode == "identity":
        fields = (
            "subject_definitions",
            "summary",
            "retention_analysis",
            "detailed_description",
            "overall_soundscape",
            "non_diegetic_music",
        )
        _field_positions(prompt, fields)
        if "<Subject 1>" not in prompt or "[reference generation]" not in prompt:
            raise ValueError("Ref2VA 输出缺少 <Subject 1> 或 [reference generation] 关系")
    else:
        fields = ("integrated_multimodal_description", "overall_soundscape", "non_diegetic_music")
        _field_positions(prompt, fields)
        if mode == "first_frame" and not prompt.startswith(I2VA_ALIGNMENT + "\n\n"):
            raise ValueError("I2VA 输出缺少官方首帧对齐指令")
        if mode == "none" and prompt.startswith("For the target video"):
            raise ValueError("T2VA 输出不应包含图像对齐指令")

    if "[Shot 1]" not in prompt:
        raise ValueError("模型输出缺少 [Shot 1]")
    if request["duration"] > 5:
        for start in range(0, request["duration"], 5):
            pattern = rf"(?im)^\s*\[?\s*{start}\s*-\s*{start + 5}\s*\]?\s*(?:seconds?|s|秒)\s*[:：]"
            if not re.search(pattern, prompt):
                raise ValueError(f"模型输出缺少 {start}-{start + 5} 秒剧情时间段")
    return list(fields)


def _upstream_error(exc: urllib.error.HTTPError, provider: str = "模型服务") -> str:
    try:
        payload = json.loads(exc.read().decode("utf-8", "replace"))
        message = str(payload.get("error", {}).get("message") or payload.get("message") or "").strip()
    except (json.JSONDecodeError, AttributeError, TypeError):
        message = ""
    safe = re.sub(r"(?i)(api[-_ ]?key|authorization)\s*[:=]\s*\S+", r"\1: [redacted]", message)[:500]
    provider_label = "DeepSeek" if provider == "DeepSeek" else "模型服务"
    actionable = {
        401: "API Key 无效，请到 DeepSeek 开放平台核对后重新填写",
        402: f"{provider_label} 账户余额不足，请充值或更换账户后重试",
        422: f"请求参数不符合 {provider_label} 接口要求，请核对模型名与服务地址",
        429: f"{provider_label} 请求过于频繁，请稍后再提交",
        503: f"{provider_label} 服务繁忙，请稍后再提交",
    }.get(exc.code)
    if actionable:
        return f"{actionable}（HTTP {exc.code}）"
    return safe or f"HTTP {exc.code}"


def request_chat_completion(
    messages: list[dict[str, str]],
    api_config: dict[str, Any] | None,
    *,
    temperature: float,
    max_tokens: int,
    json_mode: bool = False,
    timeout: int = 90,
) -> tuple[str, dict[str, Any], dict[str, str]]:
    """Call a user-configured OpenAI-compatible service without persisting credentials."""
    config = _resolve_config(api_config)
    body: dict[str, Any] = {
        "model": config["model"],
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": False,
    }
    if json_mode:
        body["response_format"] = {"type": "json_object"}
    if config["provider"] == "DeepSeek" and config["model"].startswith("deepseek-v4"):
        body["thinking"] = {"type": "disabled"}
    headers = {"Content-Type": "application/json", "User-Agent": "H3-Flow/1.2"}
    if config["api_key"]:
        headers["Authorization"] = f"Bearer {config['api_key']}"
    upstream = urllib.request.Request(
        config["endpoint"],
        data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    try:
        with urllib.request.urlopen(upstream, timeout=timeout) as response:
            result = json.load(response)
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"模型服务拒绝请求：{_upstream_error(exc, config['provider'])}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"无法连接模型服务：{exc.reason}") from exc
    except TimeoutError as exc:
        raise RuntimeError("模型服务响应超时，请检查接口状态后重试") from exc

    try:
        content = result["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise RuntimeError("模型服务返回了无法识别的 Chat Completions 响应") from exc
    return _strip_fences(str(content or "")), result, config


def rewrite_h3_prompt(raw: dict[str, Any]) -> dict[str, Any]:
    messages, request = build_messages(raw)
    prompt, result, config = request_chat_completion(
        messages,
        raw.get("api_config"),
        temperature=0.35,
        max_tokens=4096,
    )
    checks = validate_generated_prompt(prompt, request)
    usage = result.get("usage") if isinstance(result.get("usage"), dict) else {}
    return {
        "prompt": prompt,
        "provider": config["provider"],
        "model": str(result.get("model") or config["model"]),
        "usage": {
            key: int(usage[key])
            for key in ("prompt_tokens", "completion_tokens", "total_tokens")
            if isinstance(usage.get(key), int)
        },
        "checks": checks,
        "guide_revision": GUIDE_REVISION,
    }
