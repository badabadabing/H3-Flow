from __future__ import annotations

import argparse
import base64
import ctypes
import json
import math
import mimetypes
import os
import re
import secrets
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from collections import defaultdict, deque
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from io import BytesIO
from pathlib import Path
from threading import Lock, Thread
from typing import Any

from PIL import Image, UnidentifiedImageError

from prompt_assistant import prompt_assistant_status, rewrite_h3_prompt
from short_drama import expand_short_drama_batch_units, generate_short_drama, preflight_short_drama_batch, short_drama_status


STATIC_ROOT = Path(__file__).resolve().parent
PARENT_PROJECT = STATIC_ROOT.parent
ROOT = Path(os.environ.get("H3_FLOW_PROJECT_ROOT", PARENT_PROJECT if (PARENT_PROJECT / "runtime").is_dir() else STATIC_ROOT))
sys.path.insert(0, str(ROOT))

try:
    from custom_nodes.h3_prompt_continuity import compile_segment_series
except ModuleNotFoundError:
    from comfy_nodes.h3_prompt_continuity import compile_segment_series

PORTABLE_ROOT = Path(os.environ.get("H3_FLOW_PORTABLE_ROOT", ROOT / "runtime" / "ComfyUI_windows_portable"))
COMFY_ROOT = Path(os.environ.get("H3_FLOW_COMFY_ROOT", PORTABLE_ROOT / "ComfyUI"))
COMFY_INPUT = COMFY_ROOT / "input"
START_SCRIPT = Path(os.environ.get("H3_FLOW_START_SCRIPT", ROOT / "scripts" / "start_h3_prompt_workflow.ps1"))
COMFY_URL = os.environ.get("H3_FLOW_COMFY_URL", "http://127.0.0.1:8188").rstrip("/")
COMPATIBILITY_FILE = STATIC_ROOT / "compatibility.json"
COMPATIBILITY = json.loads(COMPATIBILITY_FILE.read_text(encoding="utf-8"))
QUEUE_SUBMIT_LOCK = Lock()
ENVIRONMENT_CACHE_LOCK = Lock()
ENVIRONMENT_CACHE: dict[str, Any] = {"at": 0.0, "value": None}
DRAMA_BATCH_LOCK = Lock()
DRAMA_BATCH_JOBS: dict[str, dict[str, Any]] = {}
DRAMA_BATCH_ACTIVE: str | None = None

FPS = 24
SEGMENT_FRAMES = 124
SUPPORTED_DURATIONS = (5, 10, 15, 30)
MAX_REFERENCE_BYTES = 12 * 1024 * 1024
MAX_REFERENCE_PIXELS = 40_000_000
REFERENCE_TOKEN = re.compile(r"^(?:h3_flow/)?h3_flow_[0-9a-f]{12}\.(?:jpg|png|webp)$")

ASPECTS = {
    "16:9": {"source": (864, 480), "balanced": (1280, 720), "studio": (1920, 1080)},
    "9:16": {"source": (480, 864), "balanced": (720, 1280), "studio": (1080, 1920)},
    "1:1": {"source": (640, 640), "balanced": (960, 960), "studio": (1080, 1080)},
}

MODEL_FILES = {
    name: COMFY_ROOT / "models" / definition["folder"] / definition["filename"]
    for name, definition in COMPATIBILITY["models"].items()
}


class MemoryStatus(ctypes.Structure):
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


def json_request(url: str, payload: dict | None = None, timeout: int = 10) -> dict:
    data = None
    headers: dict[str, str] = {}
    method = "GET"
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
        method = "POST"
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.load(response)
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", "replace")
        raise RuntimeError(f"ComfyUI HTTP {exc.code}: {body}") from exc


def windows_memory() -> dict[str, float | None]:
    if os.name != "nt":
        return {"ram_total_gb": None, "ram_free_gb": None, "commit_total_gb": None, "commit_free_gb": None}
    status = MemoryStatus()
    status.dwLength = ctypes.sizeof(MemoryStatus)
    if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
        return {"ram_total_gb": None, "ram_free_gb": None, "commit_total_gb": None, "commit_free_gb": None}
    gb = 1024**3
    return {
        "ram_total_gb": round(status.ullTotalPhys / gb, 1),
        "ram_free_gb": round(status.ullAvailPhys / gb, 1),
        "commit_total_gb": round(status.ullTotalPageFile / gb, 1),
        "commit_free_gb": round(status.ullAvailPageFile / gb, 1),
    }


def nvidia_hardware() -> dict[str, Any]:
    command = [
        "nvidia-smi",
        "--query-gpu=name,memory.total,memory.free",
        "--format=csv,noheader,nounits",
    ]
    try:
        completed = subprocess.run(command, capture_output=True, text=True, timeout=5, check=True)
        first = completed.stdout.strip().splitlines()[0]
        name, total, free = [part.strip() for part in first.split(",")]
        return {
            "gpu_name": name,
            "vram_total_gb": round(float(total) / 1024, 1),
            "vram_free_gb": round(float(free) / 1024, 1),
        }
    except (FileNotFoundError, subprocess.SubprocessError, ValueError, IndexError):
        return {"gpu_name": None, "vram_total_gb": None, "vram_free_gb": None}


def comfy_snapshot() -> dict[str, Any]:
    try:
        stats = json_request(f"{COMFY_URL}/system_stats", timeout=3)
        queue = json_request(f"{COMFY_URL}/queue", timeout=3)
        device = (stats.get("devices") or [{}])[0]
        system = stats.get("system", {})
        packages = {
            item.get("name"): item.get("installed")
            for item in system.get("comfy_package_versions", [])
            if item.get("name")
        }
        return {
            "online": True,
            "version": system.get("comfyui_version"),
            "frontend_version": packages.get("comfyui-frontend-package") or system.get("required_frontend_version"),
            "templates_version": packages.get("comfyui-workflow-templates") or system.get("installed_templates_version"),
            "python_version": str(system.get("python_version") or "").split()[0] or None,
            "pytorch_version": system.get("pytorch_version"),
            "device_name": device.get("name"),
            "vram_total_gb": round((device.get("vram_total") or 0) / 1024**3, 1),
            "vram_free_gb": round((device.get("vram_free") or 0) / 1024**3, 1),
            "queue_running": len(queue.get("queue_running", [])),
            "queue_pending": len(queue.get("queue_pending", [])),
        }
    except (OSError, RuntimeError, ValueError, urllib.error.URLError):
        return {
            "online": False,
            "version": None,
            "frontend_version": None,
            "templates_version": None,
            "python_version": None,
            "pytorch_version": None,
            "device_name": None,
            "vram_total_gb": None,
            "vram_free_gb": None,
            "queue_running": 0,
            "queue_pending": 0,
        }


def model_inventory(comfy_online: bool) -> dict[str, dict[str, Any]]:
    online_models: dict[str, set[str]] = {}
    if comfy_online:
        for folder in {item["folder"] for item in COMPATIBILITY["models"].values()}:
            try:
                result = json_request(f"{COMFY_URL}/models/{urllib.parse.quote(folder)}", timeout=8)
                online_models[folder] = {str(name) for name in result} if isinstance(result, list) else set()
            except (OSError, RuntimeError, ValueError, urllib.error.URLError):
                online_models[folder] = set()

    inventory: dict[str, dict[str, Any]] = {}
    for name, definition in COMPATIBILITY["models"].items():
        path = MODEL_FILES[name]
        file_present = path.is_file()
        actual_size = path.stat().st_size if file_present else None
        online_present = definition["filename"] in online_models.get(definition["folder"], set())
        present = file_present or online_present
        size_matches = bool(file_present and actual_size == definition["bytes"])
        inventory[name] = {
            "present": present,
            "filename": definition["filename"],
            "size_matches": size_matches if file_present else None,
            "verified_by": "size" if size_matches else "filesystem" if file_present else "comfy_api" if online_present else None,
        }
    return inventory


def plugin_inventory() -> dict[str, Any]:
    expected = COMPATIBILITY["capabilities"]["latent_continuity"]["plugin"]
    candidates = [
        COMFY_ROOT / "custom_nodes" / "ComfyUI-H3-Motion-Context",
        COMFY_ROOT / "custom_nodes" / "comfyui-h3-motion-context",
    ]
    plugin_root = next((path for path in candidates if path.is_dir()), None)
    version = None
    commit = None
    if plugin_root:
        pyproject = plugin_root / "pyproject.toml"
        if pyproject.is_file():
            match = re.search(r'^version\s*=\s*["\']([^"\']+)["\']', pyproject.read_text(encoding="utf-8"), re.MULTILINE)
            version = match.group(1) if match else None
        if (plugin_root / ".git").exists():
            try:
                completed = subprocess.run(
                    ["git", "-C", str(plugin_root), "rev-parse", "HEAD"],
                    capture_output=True,
                    text=True,
                    timeout=4,
                    check=True,
                )
                commit = completed.stdout.strip() or None
            except (FileNotFoundError, subprocess.SubprocessError):
                commit = None
    return {
        "installed": plugin_root is not None,
        "version": version,
        "commit": commit,
        "expected_version": expected["version"],
        "expected_commit": expected["commit"],
        "repository": expected["repository"],
        "version_matches": version == expected["version"] if version else False,
        "commit_matches": commit == expected["commit"] if commit else False,
    }


def compatibility_snapshot(comfy: dict[str, Any], model_details: dict[str, dict[str, Any]]) -> dict[str, Any]:
    tested = COMPATIBILITY["tested_runtime"]
    try:
        object_info = json_request(f"{COMFY_URL}/object_info", timeout=120) if comfy["online"] else {}
    except (OSError, RuntimeError, ValueError, urllib.error.URLError):
        object_info = {}

    capabilities: dict[str, Any] = {}
    for name, definition in COMPATIBILITY["capabilities"].items():
        missing_models = [model for model in definition.get("models", []) if not model_details[model]["present"]]
        missing_nodes = [node for node in definition.get("nodes", []) if node not in object_info]
        capabilities[name] = {
            "ready": comfy["online"] and not missing_models and not missing_nodes,
            "missing_models": missing_models,
            "missing_nodes": missing_nodes,
        }

    plugin = plugin_inventory()
    capabilities["latent_continuity"]["plugin"] = plugin
    if plugin["installed"] and not (plugin["version_matches"] and plugin["commit_matches"]):
        capabilities["latent_continuity"]["ready"] = False

    runtime_checks = {
        "comfyui": {"actual": comfy.get("version"), "tested": tested["comfyui"]},
        "frontend": {"actual": comfy.get("frontend_version"), "tested": tested["frontend"]},
        "workflow_templates": {"actual": comfy.get("templates_version"), "tested": tested["workflow_templates"]},
        "python": {"actual": comfy.get("python_version"), "tested": tested["python"]},
        "pytorch": {"actual": comfy.get("pytorch_version"), "tested": tested["pytorch"]},
    }
    for check in runtime_checks.values():
        check["matches"] = bool(check["actual"] and check["actual"] == check["tested"])

    required_ready = capabilities["base"]["ready"]
    runtime_exact = all(check["matches"] for check in runtime_checks.values())
    return {
        "status": "ready" if required_ready and runtime_exact else "compatible" if required_ready else "blocked",
        "runtime": runtime_checks,
        "models": model_details,
        "capabilities": capabilities,
        "summary": {
            "runtime": f"ComfyUI {comfy.get('version') or '未连接'}",
            "base": "H3 核心已就绪" if capabilities["base"]["ready"] else "H3 核心缺失",
            "reference": "Ref2VA 已就绪" if capabilities["reference"]["ready"] else "Ref2VA 未就绪",
            "continuity": "潜空间续接已就绪" if capabilities["latent_continuity"]["ready"] else "潜空间续接未安装",
        },
    }


def environment_snapshot(force: bool = False) -> dict[str, Any]:
    now = time.monotonic()
    with ENVIRONMENT_CACHE_LOCK:
        if not force and ENVIRONMENT_CACHE["value"] is not None and now - ENVIRONMENT_CACHE["at"] < 4.0:
            return ENVIRONMENT_CACHE["value"]
    local = {**nvidia_hardware(), **windows_memory()}
    comfy = comfy_snapshot()
    if comfy["vram_total_gb"]:
        local["gpu_name"] = comfy["device_name"] or local["gpu_name"]
        local["vram_total_gb"] = comfy["vram_total_gb"]
        local["vram_free_gb"] = comfy["vram_free_gb"]
    model_details = model_inventory(comfy["online"])
    models = {name: detail["present"] for name, detail in model_details.items()}
    value = {
        "hardware": local,
        "comfy": comfy,
        "models": models,
        "compatibility": compatibility_snapshot(comfy, model_details),
    }
    with ENVIRONMENT_CACHE_LOCK:
        ENVIRONMENT_CACHE["at"] = now
        ENVIRONMENT_CACHE["value"] = value
    return value


def normalize_config(raw: dict[str, Any]) -> dict[str, Any]:
    try:
        duration = int(raw.get("duration", 10))
    except (TypeError, ValueError) as exc:
        raise ValueError("视频时长无效") from exc
    if duration not in SUPPORTED_DURATIONS:
        raise ValueError("视频时长仅支持 5、10、15 或 30 秒")

    aspect = str(raw.get("aspect", "16:9"))
    if aspect not in ASPECTS:
        raise ValueError("画幅无效")

    quality = str(raw.get("quality", "balanced"))
    if quality not in {"draft", "balanced", "studio"}:
        raise ValueError("输出质量无效")

    seed_value = raw.get("seed")
    try:
        seed = int(seed_value) if seed_value not in (None, "") else secrets.randbits(32)
    except (TypeError, ValueError) as exc:
        raise ValueError("随机种子无效") from exc

    reference_value = raw.get("reference")
    reference = str(reference_value).strip() if reference_value not in (None, "") else None
    reference_mode = str(raw.get("reference_mode", "first_frame"))
    if reference_mode not in {"first_frame", "identity"}:
        raise ValueError("参考图模式无效")
    if reference and not REFERENCE_TOKEN.fullmatch(reference):
        raise ValueError("参考图令牌无效，请重新上传")
    if not reference:
        reference_mode = "none"

    return {
        "duration": duration,
        "aspect": aspect,
        "quality": quality,
        "reference": reference,
        "reference_mode": reference_mode,
        "seed": seed,
    }


def build_plan(raw: dict[str, Any], snapshot: dict[str, Any] | None = None) -> dict[str, Any]:
    config = normalize_config(raw)
    snapshot = snapshot or environment_snapshot()
    hardware = snapshot["hardware"]
    comfy = snapshot["comfy"]
    models = snapshot["models"]
    vram = hardware.get("vram_total_gb") or 0
    ram = hardware.get("ram_total_gb") or 0

    requested = config["quality"]
    applied = requested
    notices: list[dict[str, str]] = []
    if requested == "studio":
        max_studio_duration = 5 if vram < 20 else 15 if vram < 28 else 30
        if config["duration"] > max_studio_duration:
            applied = "balanced"
            notices.append(
                {
                    "level": "adjusted",
                    "title": "已自动保护显存",
                    "detail": f"当前 {vram or '未知'}GB 显存的 1080P 时序精修上限为 {max_studio_duration} 秒，本次改为 720P 智能成片。",
                }
            )

    segments = math.ceil(config["duration"] / 5)
    width, height = ASPECTS[config["aspect"]]["source"]
    if applied == "draft":
        output_width, output_height = width, height
    else:
        output_width, output_height = ASPECTS[config["aspect"]][applied]

    h3_model = "ref2va" if config["reference_mode"] == "identity" else "fl2va"
    missing_core = [name for name in (h3_model, "clip", "video_vae", "audio_vae") if not models.get(name)]
    if applied == "studio":
        missing_core.extend(name for name in ("seedvr", "seedvr_vae") if not models.get(name))

    blockers: list[str] = []
    if not comfy["online"]:
        blockers.append("ComfyUI 尚未启动")
    if vram and vram < 15:
        blockers.append("显存低于本项目已验证的 16GB 档位")
    if ram and ram < 24:
        blockers.append("系统内存低于 24GB 安全下限")
    if missing_core:
        blockers.append("缺少所需模型：" + "、".join(missing_core))
    if config["reference_mode"] == "identity" and config["duration"] > 5:
        blockers.append("多参考 Ref2VA 当前只开放已验证的 5 秒档；长视频需完成潜空间续接实载验收后再开放")
    if config["duration"] > 5:
        prompt_text = str(raw.get("prompt") or "").strip()
        try:
            compile_segment_series(
                prompt_text,
                segment_seconds=config["duration"] / segments,
                total_seconds=float(config["duration"]),
                first_has_reference=bool(config["reference"]),
            )
        except ValueError as exc:
            blockers.append("长视频剧情时间线：" + str(exc))
    if comfy["queue_running"] or comfy["queue_pending"]:
        blockers.append("ComfyUI 当前有任务，需等待队列清空以避免资源争抢")

    return {
        **config,
        "quality_requested": requested,
        "quality_applied": applied,
        "segments": segments,
        "segment_frames": SEGMENT_FRAMES,
        "final_frames": config["duration"] * FPS,
        "source_resolution": f"{width}×{height}",
        "output_resolution": f"{output_width}×{output_height}",
        "audio": "32kHz 立体声原生声轨 + 连续性母带",
        "workflow_mode": (
            "多参考身份 / 风格" if config["reference_mode"] == "identity"
            else "首帧图生视频" if config["reference"]
            else "文生视频"
        ),
        "continuity_mode": "单段原生生成" if segments == 1 else "末帧续接 + 剧情时间段隔离",
        "protection": [
            "每块固定 124 帧，避免长块解码峰值",
            "长片段由上一块末帧续接，并为每块编译独立局部剧情时间线",
            "保留 1.5GB 显存，不并发排队",
            "输出前按目标时长精确裁切声画",
        ],
        "notices": notices,
        "blockers": blockers,
        "ready": not blockers,
        "snapshot": snapshot,
    }


def segment_instruction(index: int, count: int, duration: int, has_reference: bool) -> str:
    start = index * duration / count
    end = (index + 1) * duration / count
    reference_rule = (
        "Use the supplied first frame as the identity, composition and visual continuity anchor. "
        if index == 0 and has_reference
        else "Continue naturally from the supplied previous final frame. " if index else ""
    )
    return (
        f"Internal H3 Flow instruction: segment {index + 1}/{count}, covering approximately "
        f"{start:05.2f}-{end:05.2f} seconds of one continuous scene. {reference_rule}"
        "Generate only the forward action and synchronized sound belonging to this interval. "
        "Preserve subject identity, face, clothing, environment, lighting, camera axis and movement direction. "
        "Keep ambience, voices and requested music continuous without re-introduction. "
        "No cut, reset, duplicated action, subtitle, logo, watermark, extra subject or abrupt audio sting."
    )


def build_workflow(prompt_text: str, raw: dict[str, Any], snapshot: dict[str, Any] | None = None) -> tuple[dict[str, Any], dict[str, Any]]:
    prompt_text = prompt_text.strip()
    if len(prompt_text) < 12:
        raise ValueError("提示词至少需要 12 个字符，以便建立可执行场景")
    if len(prompt_text) > 12000:
        raise ValueError("提示词过长，最多 12000 个字符")

    plan = build_plan({**raw, "prompt": prompt_text}, snapshot=snapshot)
    width, height = ASPECTS[plan["aspect"]]["source"]
    identity_mode = plan["reference_mode"] == "identity"
    h3_model_name = (
        "minimax_h3_ref2va_pruned_int8_convrot.safetensors"
        if identity_mode
        else "minimax_h3_fl2va_pruned_int8_convrot.safetensors"
    )
    workflow: dict[str, dict[str, Any]] = {
        "1": {"class_type": "PrimitiveStringMultiline", "inputs": {"value": prompt_text}},
        "6": {"class_type": "UNETLoader", "inputs": {"unet_name": h3_model_name, "weight_dtype": "default"}},
        "9": {"class_type": "BasicScheduler", "inputs": {"model": ["6", 0], "scheduler": "beta" if identity_mode else "simple", "steps": 20, "denoise": 1.0}},
        "11": {"class_type": "VAELoader", "inputs": {"vae_name": "minimax_h3_video_vae_fp16.safetensors"}},
        "12": {"class_type": "VAELoader", "inputs": {"vae_name": "minimax_h3_audio_vae_fp32.safetensors"}},
        "13": {"class_type": "CLIPLoader", "inputs": {"clip_name": "qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors", "type": "minimax", "device": "default"}},
        "17": {"class_type": "KSamplerSelect", "inputs": {"sampler_name": "res_multistep"}},
    }

    if plan["reference"]:
        workflow["18"] = {"class_type": "LoadImage", "inputs": {"image": plan["reference"]}}
        if not identity_mode:
            workflow["19"] = {
                "class_type": "ImageScale",
                "inputs": {"image": ["18", 0], "upscale_method": "lanczos", "width": width, "height": height, "crop": "center"},
            }

    if plan["segments"] > 1 and not identity_mode:
        segment_prompts = compile_segment_series(
            prompt_text,
            segment_seconds=plan["duration"] / plan["segments"],
            total_seconds=float(plan["duration"]),
            first_has_reference=bool(plan["reference"]),
        )
    else:
        segment_prompts = [
            prompt_text
            + "\n\n"
            + segment_instruction(0, 1, plan["duration"], bool(plan["reference"]))
        ]

    accumulated_image: list[Any] | None = None
    audio_outputs: list[list[Any]] = []
    if identity_mode:
        workflow["20"] = {
            "class_type": "StringConcatenate",
            "inputs": {
                "string_a": ["1", 0],
                "string_b": (
                    "Use <Picture 1> as the explicit identity, product or visual-style reference. "
                    "Preserve its defining attributes while following the requested action, camera and sound."
                ),
                "delimiter": "\n\n",
            },
        }
        workflow["100"] = {
            "class_type": "MiniMaxH3ReferenceToVideo",
            "inputs": {
                "clip": ["13", 0],
                "vae": ["11", 0],
                "audio_vae": ["12", 0],
                "prompt": ["20", 0],
                "width": width,
                "height": height,
                "length": SEGMENT_FRAMES,
                "ref_image_size": "match",
                "ref_images": {"ref_image_0": ["18", 0]},
            },
        }
        workflow["110"] = {"class_type": "RandomNoise", "inputs": {"noise_seed": plan["seed"]}}
        workflow["120"] = {"class_type": "BasicGuider", "inputs": {"model": ["6", 0], "conditioning": ["100", 0]}}
        workflow["130"] = {
            "class_type": "SamplerCustomAdvanced",
            "inputs": {"noise": ["110", 0], "guider": ["120", 0], "sampler": ["17", 0], "sigmas": ["9", 0], "latent_image": ["100", 1]},
        }
        workflow["140"] = {"class_type": "VAEDecode", "inputs": {"samples": ["130", 0], "vae": ["11", 0]}}
        workflow["200"] = {"class_type": "VAEDecodeAudio", "inputs": {"samples": ["130", 0], "vae": ["12", 0]}}
        accumulated_image = ["140", 0]
        audio_outputs.append(["200", 0])

    for index in range(0 if identity_mode else plan["segments"]):
        h3_id = str(100 + index)
        noise_id = str(110 + index)
        guider_id = str(120 + index)
        sampler_id = str(130 + index)
        video_id = str(140 + index)
        audio_id = str(200 + index)
        h3_inputs: dict[str, Any] = {
            "clip": ["13", 0],
            "vae": ["11", 0],
            "prompt": segment_prompts[index],
            "width": width,
            "height": height,
            "length": SEGMENT_FRAMES,
        }
        if index == 0 and plan["reference"]:
            h3_inputs["first_frame"] = ["19", 0]
        elif index > 0:
            anchor_id = str(150 + index)
            workflow[anchor_id] = {
                "class_type": "ImageFromBatch",
                "inputs": {"image": [str(139 + index), 0], "batch_index": -1, "length": 1},
            }
            h3_inputs["first_frame"] = [anchor_id, 0]

        workflow[h3_id] = {"class_type": "MiniMaxH3ImageToVideo", "inputs": h3_inputs}
        workflow[noise_id] = {"class_type": "RandomNoise", "inputs": {"noise_seed": plan["seed"] + index}}
        workflow[guider_id] = {"class_type": "BasicGuider", "inputs": {"model": ["6", 0], "conditioning": [h3_id, 0]}}
        workflow[sampler_id] = {
            "class_type": "SamplerCustomAdvanced",
            "inputs": {"noise": [noise_id, 0], "guider": [guider_id, 0], "sampler": ["17", 0], "sigmas": ["9", 0], "latent_image": [h3_id, 1]},
        }
        workflow[video_id] = {"class_type": "VAEDecode", "inputs": {"samples": [sampler_id, 0], "vae": ["11", 0]}}
        workflow[audio_id] = {"class_type": "VAEDecodeAudio", "inputs": {"samples": [sampler_id, 0], "vae": ["12", 0]}}
        audio_outputs.append([audio_id, 0])

        if index == 0:
            accumulated_image = [video_id, 0]
        else:
            trim_id = str(160 + index)
            batch_id = str(180 + index)
            workflow[trim_id] = {
                "class_type": "ImageFromBatch",
                "inputs": {"image": [video_id, 0], "batch_index": 1, "length": SEGMENT_FRAMES - 1},
            }
            workflow[batch_id] = {
                "class_type": "ImageBatch",
                "inputs": {"image1": accumulated_image, "image2": [trim_id, 0]},
            }
            accumulated_image = [batch_id, 0]

    workflow["250"] = {
        "class_type": "ImageFromBatch",
        "inputs": {"image": accumulated_image, "batch_index": 0, "length": plan["final_frames"]},
    }
    audio_inputs: dict[str, Any] = {
        "segment_count": plan["segments"],
        "segment_frames": SEGMENT_FRAMES,
        "trim_frames": 1,
        "fps": float(FPS),
        "final_duration": float(plan["duration"]),
        "boundary_fade_ms": 15.0,
        "target_rms_dbfs": -18.0,
        "target_peak_dbfs": -1.0,
        "max_makeup_db": 3.0,
    }
    for index, output in enumerate(audio_outputs, start=1):
        audio_inputs[f"audio{index}"] = output
    workflow["260"] = {"class_type": "H3AudioSequenceMaster", "inputs": audio_inputs}
    workflow["261"] = {
        "class_type": "SaveAudio",
        "inputs": {"audio": ["260", 0], "filename_prefix": f"audio/H3_Flow_{plan['duration']}s_master"},
    }

    output_images: list[Any] = ["250", 0]
    quality = plan["quality_applied"]
    if quality == "draft":
        output_width, output_height = width, height
    else:
        output_width, output_height = ASPECTS[plan["aspect"]][quality]
    if quality == "balanced":
        workflow["300"] = {
            "class_type": "ImageScale",
            "inputs": {"image": output_images, "upscale_method": "lanczos", "width": output_width, "height": output_height, "crop": "disabled"},
        }
        output_images = ["300", 0]
    elif quality == "studio":
        workflow["300"] = {
            "class_type": "ImageScale",
            "inputs": {"image": output_images, "upscale_method": "lanczos", "width": output_width, "height": output_height, "crop": "disabled"},
        }
        workflow["301"] = {"class_type": "SeedVR2Preprocess", "inputs": {"resized_images": ["300", 0]}}
        workflow["302"] = {"class_type": "VAELoader", "inputs": {"vae_name": "seedvr2_ema_vae_fp16.safetensors"}}
        workflow["303"] = {"class_type": "VAEEncodeTiled", "inputs": {"pixels": ["301", 0], "vae": ["302", 0], "tile_size": 512, "overlap": 128, "temporal_size": 64, "temporal_overlap": 8}}
        workflow["304"] = {"class_type": "UNETLoader", "inputs": {"unet_name": "seedvr2_3b_int8_convrot.safetensors", "weight_dtype": "default"}}
        workflow["305"] = {"class_type": "SeedVR2TemporalChunk", "inputs": {"latent": ["303", 0], "temporal_overlap": 2, "chunking_mode": "auto"}}
        workflow["306"] = {"class_type": "SeedVR2Conditioning", "inputs": {"model": ["304", 0], "vae_conditioning": ["305", 0]}}
        workflow["307"] = {"class_type": "KSampler", "inputs": {"model": ["304", 0], "seed": plan["seed"] + 97, "steps": 1, "cfg": 1.0, "sampler_name": "euler", "scheduler": "simple", "positive": ["306", 0], "negative": ["306", 1], "latent_image": ["305", 0], "denoise": 1.0}}
        workflow["308"] = {"class_type": "SeedVR2TemporalMerge", "inputs": {"latents": ["307", 0], "temporal_overlap": ["305", 1]}}
        workflow["309"] = {"class_type": "VAEDecodeTiled", "inputs": {"samples": ["308", 0], "vae": ["302", 0], "tile_size": 512, "overlap": 128, "temporal_size": 64, "temporal_overlap": 8}}
        workflow["310"] = {"class_type": "SeedVR2PostProcessing", "inputs": {"images": ["309", 0], "original_resized_images": ["300", 0], "color_correction_method": "lab"}}
        output_images = ["310", 0]

    workflow["270"] = {
        "class_type": "CreateVideo",
        "inputs": {"images": output_images, "audio": ["260", 0], "fps": float(FPS), "bit_depth": 8},
    }
    workflow["271"] = {
        "class_type": "SaveVideo",
        "inputs": {
            "video": ["270", 0],
            "filename_prefix": f"video/H3_Flow_{plan['duration']}s_{quality}_{plan['aspect'].replace(':', 'x')}",
            "format": "mp4",
            "codec": "auto",
        },
    }
    return workflow, plan


def build_short_drama_shot_workflow(
    package: dict[str, Any],
    scene: dict[str, Any],
    shot: dict[str, Any],
    character_assets: dict[str, Any],
    *,
    job_id: str,
    quality: str,
    seed: int,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Build one self-contained Ref2VA shot using every confirmed on-screen identity."""
    project = package["project"]
    aspect = str(project.get("aspect") or "9:16")
    if aspect not in ASPECTS:
        raise ValueError(f"{shot.get('id', '镜头')} 画幅无效")
    duration = int(shot.get("duration_seconds") or 0)
    if duration not in (5, 10, 15):
        raise ValueError(f"{shot.get('id', '镜头')} 时长必须是 5、10 或 15 秒")
    if quality not in {"draft", "balanced", "studio"}:
        raise ValueError("短剧镜头质量档位无效")

    character_map = {item["id"]: item for item in package["characters"]}
    cast_ids = list(dict.fromkeys(str(item) for item in scene.get("cast_ids", [])))
    if not cast_ids or len(cast_ids) > 9:
        raise ValueError(f"{scene.get('id', '场景')} 需要 1 到 9 个可引用角色")
    references: list[tuple[str, dict[str, Any], str]] = []
    for character_id in cast_ids:
        character = character_map.get(character_id)
        asset = character_assets.get(character_id)
        if not character or not isinstance(asset, dict) or asset.get("approved") is not True:
            raise ValueError(f"{shot.get('id')} 缺少已确认的 {character_id} 参考图")
        token = str(asset.get("token") or "").strip()
        if not REFERENCE_TOKEN.fullmatch(token):
            raise ValueError(f"{character_id} 参考图令牌无效，请重新上传")
        references.append((character_id, character, token))

    wardrobe_map = {
        wardrobe["id"]: (character["id"], wardrobe)
        for character in package["characters"]
        for wardrobe in character.get("wardrobe_states", [])
    }
    wardrobe_lines = []
    for wardrobe_id in scene.get("wardrobe_ids", []):
        owner_and_state = wardrobe_map.get(wardrobe_id)
        if owner_and_state:
            owner, wardrobe = owner_and_state
            wardrobe_lines.append(f"{owner} 使用 {wardrobe_id}：{wardrobe.get('description', '')}")

    definitions = []
    retention = []
    for index, (character_id, character, _token) in enumerate(references, 1):
        definitions.append(
            f"<Subject {index}> 是 {character.get('name')}（{character_id}），以 <Picture {index}> 为唯一脸部、发型、年龄与体态身份参考；"
            f"固定外观：{character.get('appearance', '')}"
        )
        retention.append(
            f"<Subject {index}>：完整保留 <Picture {index}> 的身份特征；动作、表情、服装与场景按本镜头要求变化，不改变人物身份。"
        )
    dialogue = "；".join(f"{line.get('speaker_id')}：{line.get('text')}" for line in shot.get("dialogue", [])) or "无对白"
    beats = "\n".join(
        f"{beat.get('start_second')}-{beat.get('end_second')}秒：[Shot {index}] {beat.get('action')}"
        for index, beat in enumerate(shot.get("beats", []), 1)
    )
    prompt_text = (
        "subject_definitions:\n" + "\n".join(definitions)
        + "\n\nsummary:\n"
        + f"[reference generation] {project.get('genre')}；{project.get('visual_style')}；{aspect}；{project.get('quality')}。"
        + "\n\nretention_analysis:\n" + "\n".join(retention)
        + "\n\ndetailed_description:\n"
        + f"{shot.get('h3_brief')}\n场景服装：{'；'.join(wardrobe_lines) or '保持角色固定服装'}。"
        + f"\n对白：{dialogue}。\n连续性进入：{shot.get('continuity_in')}。\n连续性离开：{shot.get('continuity_out')}。\n{beats}"
        + "\n\noverall_soundscape:\n" + str(shot.get("sound") or "自然现场声")
        + "\n\nnon_diegetic_music:\n" + str(shot.get("music") or "N/A")
    )
    if len(prompt_text) > 12000:
        raise ValueError(f"{shot.get('id')} H3 提示词超过 12000 字符")

    width, height = ASPECTS[aspect]["source"]
    raw_frames = min(SEGMENT_FRAMES if duration == 5 else duration * FPS + 2, 362)
    final_frames = duration * FPS
    workflow: dict[str, dict[str, Any]] = {
        "6": {"class_type": "UNETLoader", "inputs": {"unet_name": "minimax_h3_ref2va_pruned_int8_convrot.safetensors", "weight_dtype": "default"}},
        "9": {"class_type": "BasicScheduler", "inputs": {"model": ["6", 0], "scheduler": "beta", "steps": 20, "denoise": 1.0}},
        "11": {"class_type": "VAELoader", "inputs": {"vae_name": "minimax_h3_video_vae_fp16.safetensors"}},
        "12": {"class_type": "VAELoader", "inputs": {"vae_name": "minimax_h3_audio_vae_fp32.safetensors"}},
        "13": {"class_type": "CLIPLoader", "inputs": {"clip_name": "qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors", "type": "minimax", "device": "default"}},
        "17": {"class_type": "KSamplerSelect", "inputs": {"sampler_name": "res_multistep"}},
        "100": {
            "class_type": "MiniMaxH3ReferenceToVideo",
            "inputs": {
                "clip": ["13", 0], "vae": ["11", 0], "audio_vae": ["12", 0], "prompt": prompt_text,
                "width": width, "height": height, "length": raw_frames, "ref_image_size": "match",
                "ref_images": {},
            },
        },
        "110": {"class_type": "RandomNoise", "inputs": {"noise_seed": seed}},
        "120": {"class_type": "BasicGuider", "inputs": {"model": ["6", 0], "conditioning": ["100", 0]}},
        "130": {"class_type": "SamplerCustomAdvanced", "inputs": {"noise": ["110", 0], "guider": ["120", 0], "sampler": ["17", 0], "sigmas": ["9", 0], "latent_image": ["100", 1]}},
        "140": {"class_type": "VAEDecode", "inputs": {"samples": ["130", 0], "vae": ["11", 0]}},
        "200": {"class_type": "VAEDecodeAudio", "inputs": {"samples": ["130", 0], "vae": ["12", 0]}},
        "250": {"class_type": "ImageFromBatch", "inputs": {"image": ["140", 0], "batch_index": 0, "length": final_frames}},
        "260": {"class_type": "H3AudioSequenceMaster", "inputs": {
            "segment_count": 1, "segment_frames": raw_frames, "trim_frames": 1, "fps": float(FPS),
            "final_duration": float(duration), "boundary_fade_ms": 15.0, "target_rms_dbfs": -18.0,
            "target_peak_dbfs": -1.0, "max_makeup_db": 3.0, "audio1": ["200", 0],
        }},
    }
    for index, (_character_id, _character, token) in enumerate(references):
        load_id = str(18 + index)
        workflow[load_id] = {"class_type": "LoadImage", "inputs": {"image": token}}
        workflow["100"]["inputs"]["ref_images"][f"ref_image_{index}"] = [load_id, 0]

    output_images: list[Any] = ["250", 0]
    if quality in {"balanced", "studio"}:
        output_width, output_height = ASPECTS[aspect][quality]
        workflow["300"] = {"class_type": "ImageScale", "inputs": {"image": output_images, "upscale_method": "lanczos", "width": output_width, "height": output_height, "crop": "disabled"}}
        output_images = ["300", 0]
    if quality == "studio":
        workflow["301"] = {"class_type": "SeedVR2Preprocess", "inputs": {"resized_images": ["300", 0]}}
        workflow["302"] = {"class_type": "VAELoader", "inputs": {"vae_name": "seedvr2_ema_vae_fp16.safetensors"}}
        workflow["303"] = {"class_type": "VAEEncodeTiled", "inputs": {"pixels": ["301", 0], "vae": ["302", 0], "tile_size": 512, "overlap": 128, "temporal_size": 64, "temporal_overlap": 8}}
        workflow["304"] = {"class_type": "UNETLoader", "inputs": {"unet_name": "seedvr2_3b_int8_convrot.safetensors", "weight_dtype": "default"}}
        workflow["305"] = {"class_type": "SeedVR2TemporalChunk", "inputs": {"latent": ["303", 0], "temporal_overlap": 2, "chunking_mode": "auto"}}
        workflow["306"] = {"class_type": "SeedVR2Conditioning", "inputs": {"model": ["304", 0], "vae_conditioning": ["305", 0]}}
        workflow["307"] = {"class_type": "KSampler", "inputs": {"model": ["304", 0], "seed": seed + 97, "steps": 1, "cfg": 1.0, "sampler_name": "euler", "scheduler": "simple", "positive": ["306", 0], "negative": ["306", 1], "latent_image": ["305", 0], "denoise": 1.0}}
        workflow["308"] = {"class_type": "SeedVR2TemporalMerge", "inputs": {"latents": ["307", 0], "temporal_overlap": ["305", 1]}}
        workflow["309"] = {"class_type": "VAEDecodeTiled", "inputs": {"samples": ["308", 0], "vae": ["302", 0], "tile_size": 512, "overlap": 128, "temporal_size": 64, "temporal_overlap": 8}}
        workflow["310"] = {"class_type": "SeedVR2PostProcessing", "inputs": {"images": ["309", 0], "original_resized_images": ["300", 0], "color_correction_method": "lab"}}
        output_images = ["310", 0]

    safe_shot_id = re.sub(r"[^A-Za-z0-9_-]+", "_", str(shot.get("id") or "shot"))
    workflow["270"] = {"class_type": "CreateVideo", "inputs": {"images": output_images, "audio": ["260", 0], "fps": float(FPS), "bit_depth": 8}}
    workflow["271"] = {"class_type": "SaveVideo", "inputs": {
        "video": ["270", 0], "filename_prefix": f"video/short_drama/{job_id}/{safe_shot_id}",
        "format": "mp4", "codec": "auto",
    }}
    plan = {
        "ready": True,
        "blockers": [],
        "reference_mode": "identity",
        "quality_applied": quality,
        "quality_requested": str(project.get("quality") or quality),
        "duration": duration,
        "aspect": aspect,
        "seed": seed,
        "shot_id": shot.get("id"),
    }
    return workflow, plan


def enum_options(object_info: dict[str, Any], node_name: str, input_name: str) -> set[str]:
    definition = object_info[node_name]["input"]["required"][input_name]
    choices = definition[0]
    return {str(choice) for choice in choices} if isinstance(choices, (list, tuple)) else set()


def nested_connections(value: Any, path: str = "") -> list[tuple[str, list[Any]]]:
    if isinstance(value, list) and len(value) == 2 and isinstance(value[0], str):
        return [(path, value)]
    if isinstance(value, dict):
        connections: list[tuple[str, list[Any]]] = []
        for key, child in value.items():
            child_path = f"{path}.{key}" if path else str(key)
            connections.extend(nested_connections(child, child_path))
        return connections
    return []


def expected_connection_type(spec: Any) -> str | None:
    if not isinstance(spec, (list, tuple)) or not spec:
        return None
    if spec[0] != "COMFY_AUTOGROW_V3":
        return spec[0] if isinstance(spec[0], str) else None
    try:
        required = spec[1]["template"]["input"]["required"]
        nested_spec = next(iter(required.values()))
        return nested_spec[0] if isinstance(nested_spec[0], str) else None
    except (KeyError, StopIteration, TypeError, IndexError):
        return None


def validate_workflow_schema(workflow: dict[str, Any], object_info: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    graph: dict[str, set[str]] = defaultdict(set)
    indegree = {node_id: 0 for node_id in workflow}

    for node_id, node in workflow.items():
        class_type = node.get("class_type")
        schema = object_info.get(class_type)
        if not schema:
            errors.append(f"节点 {node_id} 使用了未注册类型 {class_type}")
            continue
        required = schema.get("input", {}).get("required", {})
        optional = schema.get("input", {}).get("optional", {})
        inputs = node.get("inputs", {})
        missing = sorted(set(required) - set(inputs))
        if missing:
            errors.append(f"节点 {node_id} 缺少必填输入：{', '.join(missing)}")

        accepted = {**required, **optional}
        for input_name, value in inputs.items():
            expected_spec = accepted.get(input_name)
            expected_type = expected_connection_type(expected_spec)
            for nested_name, connection in nested_connections(value, input_name):
                origin_id, origin_slot = connection
                if origin_id not in workflow:
                    errors.append(f"节点 {node_id}.{nested_name} 指向不存在的节点 {origin_id}")
                    continue
                if not isinstance(origin_slot, int):
                    errors.append(f"节点 {node_id}.{nested_name} 的输出槽位不是整数")
                    continue
                origin_schema = object_info.get(workflow[origin_id].get("class_type"), {})
                outputs = origin_schema.get("output", [])
                if origin_slot < 0 or origin_slot >= len(outputs):
                    errors.append(f"节点 {node_id}.{nested_name} 引用了 {origin_id} 的无效输出槽位 {origin_slot}")
                    continue
                actual_type = outputs[origin_slot]
                if isinstance(expected_type, str) and expected_type != "*" and actual_type != "*" and expected_type != actual_type:
                    errors.append(
                        f"节点 {node_id}.{nested_name} 需要 {expected_type}，但 {origin_id}:{origin_slot} 输出 {actual_type}"
                    )
                if node_id not in graph[origin_id]:
                    graph[origin_id].add(node_id)
                    indegree[node_id] += 1

    queue = deque(node_id for node_id, degree in indegree.items() if degree == 0)
    visited = 0
    while queue:
        current = queue.popleft()
        visited += 1
        for target in graph[current]:
            indegree[target] -= 1
            if indegree[target] == 0:
                queue.append(target)
    if visited != len(workflow):
        errors.append(f"工作流存在环路：仅完成 {visited}/{len(workflow)} 个节点的拓扑检查")
    return errors


def preflight(workflow: dict[str, Any], plan: dict[str, Any]) -> dict[str, Any]:
    if not plan["ready"]:
        raise RuntimeError("；".join(plan["blockers"]))
    object_info = json_request(f"{COMFY_URL}/object_info", timeout=120)
    classes = {node["class_type"] for node in workflow.values()}
    missing_nodes = sorted(node for node in classes if node not in object_info)
    if missing_nodes:
        raise RuntimeError("ComfyUI 缺少节点：" + "、".join(missing_nodes))
    schema_errors = validate_workflow_schema(workflow, object_info)
    if schema_errors:
        raise RuntimeError("工作流结构检查失败：" + "；".join(schema_errors))

    required_models = {
        ("UNETLoader", "unet_name"): {
            "minimax_h3_ref2va_pruned_int8_convrot.safetensors"
            if plan["reference_mode"] == "identity"
            else "minimax_h3_fl2va_pruned_int8_convrot.safetensors"
        },
        ("CLIPLoader", "clip_name"): {"qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors"},
        ("VAELoader", "vae_name"): {"minimax_h3_video_vae_fp16.safetensors", "minimax_h3_audio_vae_fp32.safetensors"},
    }
    if plan["quality_applied"] == "studio":
        required_models[("UNETLoader", "unet_name")].add("seedvr2_3b_int8_convrot.safetensors")
        required_models[("VAELoader", "vae_name")].add("seedvr2_ema_vae_fp16.safetensors")
    for (node, input_name), required in required_models.items():
        missing = sorted(required - enum_options(object_info, node, input_name))
        if missing:
            raise RuntimeError(f"{node}.{input_name} 未发现模型：" + "、".join(missing))
    queue = json_request(f"{COMFY_URL}/queue", timeout=10)
    if queue.get("queue_running") or queue.get("queue_pending"):
        raise RuntimeError("ComfyUI 队列在提交前发生变化；为避免资源争抢，本次没有排队")
    return {"nodes": len(classes), "models": sorted({name for values in required_models.values() for name in values})}


def validate_reference_image(raw: bytes, mime: str) -> tuple[int, int]:
    expected_formats = {"image/jpeg": "JPEG", "image/png": "PNG", "image/webp": "WEBP"}
    try:
        with Image.open(BytesIO(raw)) as image:
            width, height = image.size
            actual_format = image.format
            if width < 32 or height < 32:
                raise ValueError("参考图尺寸过小，宽高至少为 32px")
            if width * height > MAX_REFERENCE_PIXELS:
                raise ValueError("参考图像素过大，最多 4000 万像素")
            if actual_format != expected_formats[mime]:
                raise ValueError("参考图内容与文件类型不一致")
            image.verify()
    except (UnidentifiedImageError, OSError) as exc:
        raise ValueError("参考图不是可读取的有效图片") from exc
    return width, height


def upload_image_to_comfy(raw: bytes, safe_name: str, mime: str) -> str:
    boundary = f"----H3Flow{uuid.uuid4().hex}"
    separator = f"--{boundary}\r\n".encode("ascii")
    body = bytearray()
    body.extend(separator)
    body.extend(f'Content-Disposition: form-data; name="image"; filename="{safe_name}"\r\n'.encode("ascii"))
    body.extend(f"Content-Type: {mime}\r\n\r\n".encode("ascii"))
    body.extend(raw)
    body.extend(b"\r\n")
    for name, value in (("type", "input"), ("overwrite", "false")):
        body.extend(separator)
        body.extend(f'Content-Disposition: form-data; name="{name}"\r\n\r\n{value}\r\n'.encode("ascii"))
    body.extend(f"--{boundary}--\r\n".encode("ascii"))
    request = urllib.request.Request(
        f"{COMFY_URL}/upload/image",
        data=bytes(body),
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            result = json.load(response)
    except (OSError, ValueError, urllib.error.URLError) as exc:
        raise RuntimeError("参考图无法写入 ComfyUI 输入目录") from exc
    name = str(result.get("name") or "")
    subfolder = str(result.get("subfolder") or "").strip("/\\")
    token = f"{subfolder}/{name}" if subfolder else name
    if not REFERENCE_TOKEN.fullmatch(token):
        raise RuntimeError("ComfyUI 返回了无法验证的参考图令牌")
    return token


def upload_reference(payload: dict[str, Any]) -> dict[str, Any]:
    filename = str(payload.get("filename", "reference"))
    data_url = str(payload.get("data", ""))
    if "," not in data_url:
        raise ValueError("参考图数据无效")
    header, encoded = data_url.split(",", 1)
    mime = header.removeprefix("data:").split(";", 1)[0].lower()
    extensions = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp"}
    if mime not in extensions:
        raise ValueError("仅支持 JPG、PNG 或 WebP 参考图")
    try:
        raw = base64.b64decode(encoded, validate=True)
    except ValueError as exc:
        raise ValueError("参考图编码无效") from exc
    if not raw or len(raw) > MAX_REFERENCE_BYTES:
        raise ValueError("参考图必须小于 12MB")
    width, height = validate_reference_image(raw, mime)
    safe_name = f"h3_flow_{uuid.uuid4().hex[:12]}{extensions[mime]}"
    if comfy_snapshot()["online"]:
        token = upload_image_to_comfy(raw, safe_name, mime)
    elif COMFY_ROOT.is_dir():
        COMFY_INPUT.mkdir(parents=True, exist_ok=True)
        destination = COMFY_INPUT / safe_name
        with destination.open("xb") as handle:
            handle.write(raw)
        token = safe_name
    else:
        raise RuntimeError("ComfyUI 未启动，且未配置可写的 H3_FLOW_COMFY_ROOT")
    return {
        "token": token,
        "original_name": Path(filename).name,
        "bytes": len(raw),
        "width": width,
        "height": height,
    }


def collect_outputs(record: dict[str, Any]) -> list[dict[str, Any]]:
    files: list[dict[str, Any]] = []
    for node_output in record.get("outputs", {}).values():
        for key in ("videos", "video", "gifs", "images", "audio"):
            value = node_output.get(key, [])
            if isinstance(value, dict):
                value = [value]
            for item in value:
                if isinstance(item, dict) and item.get("filename"):
                    query = urllib.parse.urlencode(
                        {
                            "filename": item["filename"],
                            "subfolder": item.get("subfolder", ""),
                            "type": item.get("type", "output"),
                        }
                    )
                    files.append({**item, "kind": key, "url": f"/api/view?{query}"})
    return files


def is_video_output(item: dict[str, Any]) -> bool:
    suffix = Path(str(item.get("filename") or "")).suffix.lower()
    return item.get("kind") in {"videos", "video", "gifs"} or suffix in {".mp4", ".webm", ".mov", ".mkv", ".gif"}


def _update_drama_batch_job(job_id: str, **changes: Any) -> None:
    with DRAMA_BATCH_LOCK:
        job = DRAMA_BATCH_JOBS.get(job_id)
        if not job:
            return
        job.update(changes)
        job["updated_at"] = time.time()


def _wait_for_empty_comfy_queue(timeout_seconds: int = 90) -> None:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        queue = json_request(f"{COMFY_URL}/queue", timeout=10)
        if not queue.get("queue_running") and not queue.get("queue_pending"):
            return
        time.sleep(3)
    raise RuntimeError("ComfyUI 队列释放超时；为避免显存叠加，整批任务已安全停止")


def _wait_for_drama_prompt(prompt_id: str, timeout_seconds: int = 7200) -> dict[str, Any]:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        history = json_request(f"{COMFY_URL}/history/{urllib.parse.quote(prompt_id)}", timeout=12)
        record = history.get(prompt_id)
        if record:
            status = record.get("status", {})
            if status.get("status_str") == "error":
                messages = status.get("messages") or []
                detail = str(messages[-1]) if messages else "ComfyUI 返回镜头生成错误"
                raise RuntimeError(detail[:1200])
            if record.get("outputs"):
                return record
        time.sleep(5)
    raise RuntimeError("单镜头生成超过两小时仍未完成，整批任务已安全停止")


def _run_short_drama_batch(
    job_id: str,
    package: dict[str, Any],
    character_assets: dict[str, Any],
    gate: dict[str, Any],
) -> None:
    global DRAMA_BATCH_ACTIVE
    work = [(unit["episode"], unit["scene"], unit["shot"]) for unit in expand_short_drama_batch_units(package)]
    completed = 0
    outputs: list[dict[str, Any]] = []
    _update_drama_batch_job(job_id, state="running", detail="后台队列已启动，正在准备第一个镜头")
    try:
        for ordinal, (episode, scene, shot) in enumerate(work, 1):
            shot_id = str(shot["id"])
            last_error: Exception | None = None
            for attempt in (1, 2):
                _update_drama_batch_job(
                    job_id,
                    current_shot=shot_id,
                    detail=(
                        f"正在生成 {episode['id']} · {shot_id}（{ordinal}/{len(work)}）"
                        if attempt == 1 else f"{shot_id} 第一次未完成，正在进行唯一一次安全重试"
                    ),
                )
                try:
                    _wait_for_empty_comfy_queue()
                    snapshot = environment_snapshot(force=True)
                    if not snapshot["comfy"].get("online"):
                        raise RuntimeError("ComfyUI 在批量生成期间断开连接")
                    workflow, plan = build_short_drama_shot_workflow(
                        package,
                        scene,
                        shot,
                        character_assets,
                        job_id=job_id,
                        quality=gate["quality_applied"],
                        seed=secrets.randbits(32),
                    )
                    with QUEUE_SUBMIT_LOCK:
                        preflight(workflow, plan)
                        queued = json_request(
                            f"{COMFY_URL}/prompt",
                            {"prompt": workflow, "client_id": str(uuid.uuid4())},
                            timeout=30,
                        )
                    prompt_id = str(queued["prompt_id"])
                    _update_drama_batch_job(job_id, current_prompt_id=prompt_id)
                    record = _wait_for_drama_prompt(prompt_id)
                    shot_files = collect_outputs(record)
                    if not any(is_video_output(item) for item in shot_files):
                        raise RuntimeError(f"{shot_id} 未返回视频文件")
                    outputs.append({"episode_id": episode["id"], "shot_id": shot_id, "files": shot_files})
                    completed += 1
                    _update_drama_batch_job(
                        job_id,
                        completed_shots=completed,
                        outputs=outputs,
                        detail=f"{shot_id} 已完成；释放资源后继续下一个镜头",
                    )
                    last_error = None
                    break
                except Exception as exc:
                    last_error = exc
                    if attempt == 1:
                        _update_drama_batch_job(job_id, detail=f"{shot_id} 未完成：{exc}；等待队列释放后重试一次")
                        _wait_for_empty_comfy_queue()
            if last_error is not None:
                raise RuntimeError(f"{shot_id} 连续两次未完成：{last_error}")
        _update_drama_batch_job(
            job_id,
            state="complete",
            current_shot=None,
            current_prompt_id=None,
            detail=f"全部 {completed} 个镜头已完成，并按分集与镜头编号保存到 ComfyUI 输出目录",
        )
    except Exception as exc:
        _update_drama_batch_job(
            job_id,
            state="error",
            current_prompt_id=None,
            detail=str(exc)[:1600],
        )
    finally:
        with DRAMA_BATCH_LOCK:
            if DRAMA_BATCH_ACTIVE == job_id:
                DRAMA_BATCH_ACTIVE = None


def start_short_drama_batch(payload: dict[str, Any]) -> dict[str, Any]:
    global DRAMA_BATCH_ACTIVE
    package = payload.get("package")
    character_assets = payload.get("character_assets")
    snapshot = environment_snapshot(force=True)
    gate = preflight_short_drama_batch(package, character_assets, snapshot)
    for character_id, asset in character_assets.items():
        token = str(asset.get("token") or "").strip() if isinstance(asset, dict) else ""
        if not REFERENCE_TOKEN.fullmatch(token):
            raise ValueError(f"{character_id} 参考图令牌无效，请重新上传")
    with DRAMA_BATCH_LOCK:
        if DRAMA_BATCH_ACTIVE:
            active = DRAMA_BATCH_JOBS.get(DRAMA_BATCH_ACTIVE, {})
            if active.get("state") in {"queued", "running"}:
                raise RuntimeError(f"已有短剧任务 {DRAMA_BATCH_ACTIVE} 正在运行，请等待完成")
        job_id = f"drama_{uuid.uuid4().hex[:12]}"
        job = {
            "job_id": job_id,
            "state": "queued",
            "total_shots": gate["shot_count"],
            "completed_shots": 0,
            "current_shot": None,
            "current_prompt_id": None,
            "quality_requested": gate["quality_requested"],
            "quality_applied": gate["quality_applied"],
            "execution_mode": gate["execution_mode"],
            "outputs": [],
            "detail": "已通过生成前检查，正在启动后台串行队列",
            "created_at": time.time(),
            "updated_at": time.time(),
        }
        DRAMA_BATCH_JOBS[job_id] = job
        DRAMA_BATCH_ACTIVE = job_id
    worker = Thread(
        target=_run_short_drama_batch,
        args=(job_id, package, character_assets, gate),
        name=f"H3DramaBatch-{job_id}",
        daemon=True,
    )
    worker.start()
    return {"job_id": job_id, "job": dict(job), "preflight": gate}


def get_short_drama_batch(job_id: str) -> dict[str, Any]:
    with DRAMA_BATCH_LOCK:
        job = DRAMA_BATCH_JOBS.get(job_id)
        if not job:
            raise ValueError("短剧后台任务不存在或服务已重启")
        return json.loads(json.dumps(job, ensure_ascii=False))


class H3FlowHandler(BaseHTTPRequestHandler):
    server_version = "H3Flow/1.0"

    def log_message(self, format: str, *args: Any) -> None:
        print(f"[{time.strftime('%H:%M:%S')}] {self.address_string()} {format % args}")

    def send_json(self, payload: dict[str, Any], status: int = 200) -> None:
        encoded = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(encoded)

    def read_json(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0"))
        if length <= 0 or length > 16 * 1024 * 1024:
            raise ValueError("请求大小无效")
        return json.loads(self.rfile.read(length).decode("utf-8"))

    def do_GET(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/api/status":
            query = urllib.parse.parse_qs(parsed.query)
            self.send_json(environment_snapshot(force=query.get("refresh") == ["1"]))
            return
        if parsed.path == "/api/compatibility":
            self.send_json(environment_snapshot(force=True)["compatibility"])
            return
        if parsed.path == "/api/prompt-assistant":
            self.send_json(prompt_assistant_status())
            return
        if parsed.path == "/api/short-drama":
            self.send_json(short_drama_status())
            return
        if parsed.path.startswith("/api/short-drama/batch/"):
            job_id = parsed.path.rsplit("/", 1)[-1]
            try:
                self.send_json(get_short_drama_batch(job_id))
            except ValueError as exc:
                self.send_json({"error": str(exc)}, 404)
            return
        if parsed.path.startswith("/api/job/"):
            prompt_id = parsed.path.rsplit("/", 1)[-1]
            try:
                history = json_request(f"{COMFY_URL}/history/{urllib.parse.quote(prompt_id)}", timeout=8)
                queue = json_request(f"{COMFY_URL}/queue", timeout=8)
                record = history.get(prompt_id)
                if record:
                    status = record.get("status", {})
                    state = "error" if status.get("status_str") == "error" else "complete" if record.get("outputs") else "running"
                    self.send_json({"state": state, "status": status, "files": collect_outputs(record), "queue": queue})
                else:
                    self.send_json({"state": "running", "files": [], "queue": queue})
            except Exception as exc:
                self.send_json({"error": str(exc)}, 503)
            return
        if parsed.path == "/api/view":
            query = urllib.parse.parse_qs(parsed.query)
            upstream = urllib.parse.urlencode(
                {
                    "filename": query.get("filename", [""])[0],
                    "subfolder": query.get("subfolder", [""])[0],
                    "type": query.get("type", ["output"])[0],
                }
            )
            try:
                with urllib.request.urlopen(f"{COMFY_URL}/view?{upstream}", timeout=30) as response:
                    body = response.read()
                    self.send_response(200)
                    self.send_header("Content-Type", response.headers.get("Content-Type", "application/octet-stream"))
                    self.send_header("Content-Length", str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)
            except Exception as exc:
                self.send_json({"error": str(exc)}, 502)
            return
        self.serve_static(parsed.path)

    def do_POST(self) -> None:
        try:
            payload = self.read_json()
            if self.path == "/api/plan":
                self.send_json({"plan": build_plan(payload)})
                return
            if self.path == "/api/upload":
                self.send_json({"reference": upload_reference(payload)}, 201)
                return
            if self.path == "/api/prompt-assistant":
                self.send_json(rewrite_h3_prompt(payload))
                return
            if self.path == "/api/short-drama/plan":
                self.send_json(generate_short_drama(payload))
                return
            if self.path == "/api/short-drama/batch/preflight":
                self.send_json(preflight_short_drama_batch(
                    payload.get("package"), payload.get("character_assets"), environment_snapshot(force=True)
                ))
                return
            if self.path == "/api/short-drama/batch/start":
                self.send_json(start_short_drama_batch(payload), 202)
                return
            if self.path == "/api/start":
                if not START_SCRIPT.is_file():
                    raise RuntimeError("未配置 ComfyUI 启动脚本；请先启动 ComfyUI，或设置 H3_FLOW_START_SCRIPT")
                completed = subprocess.run(
                    ["powershell.exe", "-NoProfile", "-File", str(START_SCRIPT)],
                    cwd=ROOT,
                    capture_output=True,
                    text=True,
                    timeout=70,
                    check=False,
                )
                if completed.returncode:
                    raise RuntimeError((completed.stderr or completed.stdout or "ComfyUI 启动失败").strip())
                self.send_json({"status": environment_snapshot(force=True), "detail": completed.stdout.strip()})
                return
            if self.path in {"/api/generate", "/api/workflow"}:
                prompt_text = str(payload.pop("prompt", ""))
                snapshot = environment_snapshot()
                workflow, plan = build_workflow(prompt_text, payload, snapshot=snapshot)
                if self.path == "/api/workflow":
                    self.send_json({"workflow": workflow, "plan": plan})
                    return
                with QUEUE_SUBMIT_LOCK:
                    verified = preflight(workflow, plan)
                    queued = json_request(
                        f"{COMFY_URL}/prompt",
                        {"prompt": workflow, "client_id": str(uuid.uuid4())},
                        timeout=30,
                    )
                self.send_json({"prompt_id": queued["prompt_id"], "number": queued.get("number"), "plan": plan, "verified": verified}, 202)
                return
            self.send_json({"error": "接口不存在"}, 404)
        except (ValueError, json.JSONDecodeError) as exc:
            self.send_json({"error": str(exc)}, 400)
        except subprocess.TimeoutExpired:
            self.send_json({"error": "ComfyUI 启动超时，请查看运行时日志"}, 504)
        except Exception as exc:
            self.send_json({"error": str(exc)}, 503)

    def serve_static(self, path: str) -> None:
        static_files = {
            "/": "index.html",
            "/index.html": "index.html",
            "/styles.css": "styles.css",
            "/app.js": "app.js",
        }
        filename = static_files.get(path)
        if not filename:
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        file_path = STATIC_ROOT / filename
        if not file_path.is_file():
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        body = file_path.read_bytes()
        content_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"
        self.send_response(200)
        self.send_header("Content-Type", f"{content_type}; charset=utf-8" if content_type.startswith("text/") else content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(body)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the local H3 Flow guided frontend.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=4173)
    args = parser.parse_args()
    server = ThreadingHTTPServer((args.host, args.port), H3FlowHandler)
    print(f"H3 Flow is ready at http://{args.host}:{args.port}")
    print("Press Ctrl+C to stop the frontend bridge. ComfyUI jobs are not interrupted.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
