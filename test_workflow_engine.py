from __future__ import annotations

import unittest
from io import BytesIO
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError

from PIL import Image

import bridge
import prompt_assistant
import short_drama


def ready_snapshot(vram: float = 16.0) -> dict:
    return {
        "hardware": {
            "gpu_name": "NVIDIA GeForce RTX Test",
            "vram_total_gb": vram,
            "vram_free_gb": vram - 1.0,
            "ram_total_gb": 64.0,
            "ram_free_gb": 48.0,
            "commit_total_gb": 128.0,
            "commit_free_gb": 100.0,
        },
        "comfy": {
            "online": True,
            "version": "test",
            "device_name": "NVIDIA GeForce RTX Test",
            "vram_total_gb": vram,
            "vram_free_gb": vram - 1.0,
            "queue_running": 0,
            "queue_pending": 0,
        },
        "models": {name: True for name in bridge.MODEL_FILES},
    }


class WorkflowEngineTests(unittest.TestCase):
    prompt = (
        "一个连续电影镜头，成年人物沿着雨后街道缓慢走向镜头，身份、服装、光线与镜头方向始终一致。"
        "环境声包含远处车流、脚步和轻微雨声，不要字幕、标志或水印。"
    )

    def short_drama_payload(self) -> dict:
        shot_base = {
            "shot_size": "中景",
            "camera": "稳定缓慢推进",
            "lighting": "清晨冷光",
            "action": "林澜走进档案室并确认门后的脚步声。",
            "dialogue": [{"speaker_id": "CHAR-X", "text": "这里不该有人。"}],
            "sound": "脚步声与远处通风机底噪",
            "music": "低频悬疑铺底",
            "continuity_in": "林澜穿深色风衣，手中没有物品。",
            "continuity_out": "林澜停在第二排档案柜前，视线朝画面右侧。",
            "h3_brief": "成年调查员林澜穿深色风衣走入冷光档案室，稳定中景缓慢推进，她停在第二排柜前望向画面右侧，脚步与通风机声同步。",
            "beats": [
                {"start_second": 0, "end_second": 5, "action": "林澜推门进入档案室，摄影机稳定后退。"},
                {"start_second": 5, "end_second": 10, "action": "她沿第一排档案柜向前，听见右侧脚步。"},
                {"start_second": 10, "end_second": 15, "action": "她停在第二排柜前并望向画面右侧。"},
            ],
        }
        return {
            "project": {
                "title": "失声档案",
                "logline": "调查员追查一份会抹去证人记忆的旧档案。",
                "tone": "克制的都市悬疑",
                "narrative_engine": "每集揭开一页档案，同时暴露新的记忆缺口。",
            },
            "bible": {
                "world_rules": ["记忆只能被档案改写", "改写会留下声音缺口"],
                "continuity_rules": ["林澜始终穿深色风衣", "伤痕位置固定", "档案页码不可跳变", "保持人物运动轴线"],
                "visual_language": "低饱和冷色，稳定构图，关键线索用近景。",
                "audio_language": "环境声先于画面暴露异常，不使用旁白解释线索。",
            },
            "characters": [{
                "id": "CHAR-X",
                "name": "林澜",
                "role": "调查员",
                "age_range": "30-35",
                "appearance": "短发，左眉尾有浅痕，神态克制。",
                "personality": "谨慎、执着",
                "goal": "找回被改写的证词",
                "conflict": "她自己的记忆也在消失",
                "voice": "偏低、语速稳定",
                "wardrobe_states": [{
                    "id": "WARD-X",
                    "label": "调查装",
                    "description": "深色风衣、灰色衬衫、黑色长裤。",
                    "continuity_note": "本集风衣保持干燥，衣领始终翻下。",
                }],
            }],
            "props": [],
            "locations": [{
                "id": "LOC-X",
                "name": "旧档案室",
                "description": "狭长房间，两列金属档案柜。",
                "lighting_rule": "窗外冷光从画面左侧进入。",
                "continuity_rule": "入口在画面后方，第二排柜在右侧。",
            }],
            "episodes": [{
                "id": "EP-X",
                "title": "空白证词",
                "logline": "林澜在封存档案里听见不存在的证人录音。",
                "hook": "黑屏中先出现一段被剪断的证词。",
                "ending_hook": "档案签名竟是林澜本人。",
                "scenes": [{
                    "id": "SC-X",
                    "title": "潜入档案室",
                    "location_id": "LOC-X",
                    "time_of_day": "清晨",
                    "summary": "林澜循声音进入档案室并发现异常档案。",
                    "cast_ids": ["CHAR-X"],
                    "wardrobe_ids": ["WARD-X"],
                    "prop_ids": [],
                    "shots": [dict(shot_base, id="SHOT-X1", duration_seconds=15), dict(shot_base, id="SHOT-X2", duration_seconds=15)],
                }],
            }],
        }

    @staticmethod
    def timed_prompt(duration: int) -> str:
        beats = "\n".join(
            f"{start}-{start + 5}秒：SCENE_{start:02d}，人物执行这一时间段唯一的新动作。"
            for start in range(0, duration, 5)
        )
        return (
            "电影级连续镜头，固定成年人物身份、服装、环境、光线和镜头方向。\n"
            + beats
            + "\noverall_soundscape：环境声和动作声连续。"
            + "\nnon_diegetic_music：N/A"
        )

    def assert_connections_resolve(self, workflow: dict) -> None:
        for node_id, node in workflow.items():
            for value in node["inputs"].values():
                if isinstance(value, list) and len(value) == 2 and isinstance(value[0], str):
                    self.assertIn(value[0], workflow, f"{node_id} references missing node {value[0]}")

    def test_creator_guidance_ui_keeps_drafts_local_without_api_keys(self) -> None:
        root = Path(__file__).resolve().parent
        html = (root / "index.html").read_text(encoding="utf-8")
        javascript = (root / "app.js").read_text(encoding="utf-8")
        for marker in ("studioSteps", "briefHealth", "beatBuilder", "preflightSummary", "mobileReviewDock"):
            self.assertIn(f'id="{marker}"', html)
        self.assertIn("h3-flow:creator-draft:v1", javascript)
        draft_writer = javascript.split("function persistDraft()", 1)[1].split("function queueDraftSave()", 1)[0]
        self.assertNotIn("assistantApiKey", draft_writer)
        self.assertNotIn("api_key", draft_writer)

    def test_short_drama_ui_exposes_planner_and_keeps_credentials_out_of_draft(self) -> None:
        root = Path(__file__).resolve().parent
        html = (root / "index.html").read_text(encoding="utf-8")
        javascript = (root / "app.js").read_text(encoding="utf-8")
        for marker in ("dramaWorkspace", "dramaTheme", "dramaProviderSettings", "seasonLedger", "dramaPackageView"):
            self.assertIn(f'id="{marker}"', html)
        self.assertIn("h3-flow:short-drama-project:v1", javascript)
        draft_writer = javascript.split("function persistDramaDraft()", 1)[1].split("function queueDramaDraftSave()", 1)[0]
        self.assertNotIn("apiKey", draft_writer)
        self.assertNotIn("baseUrl", draft_writer)
        self.assertNotIn("api_key", draft_writer)
        self.assertNotIn("generation.model", draft_writer)
        self.assertIn("function renderDramaAssetGate", javascript)
        self.assertIn("function startDramaBatch", javascript)
        self.assertIn("/api/short-drama/batch/start", javascript)
        self.assertIn("for (const beat of shot.beats)", javascript)

    def test_short_drama_guides_first_time_creators_and_accepts_custom_genre_and_style(self) -> None:
        root = Path(__file__).resolve().parent
        html = (root / "index.html").read_text(encoding="utf-8")
        javascript = (root / "app.js").read_text(encoding="utf-8")
        for marker in (
            "dramaJourney", "dramaGenrePreset", "dramaGenreCustom", "dramaStylePreset",
            "dramaStyleCustom", "dramaAdvancedSettings", "dramaAssetGate", "dramaBatchGenerate",
        ):
            self.assertIn(f'id="{marker}"', html)
        self.assertIn("题材交给 AI 判断", html)
        self.assertIn("风格交给 AI 设计", html)
        self.assertIn("function composeDramaCreativeChoice", javascript)
        self.assertIn("function renderDramaAssetGate", javascript)
        self.assertNotIn("送入 H3 工作台", html)

    def test_creator_modes_share_one_ephemeral_llm_config_with_clear_key_state(self) -> None:
        root = Path(__file__).resolve().parent
        html = (root / "index.html").read_text(encoding="utf-8")
        javascript = (root / "app.js").read_text(encoding="utf-8")
        self.assertIn('id="dramaSecurityState"', html)
        self.assertIn("function bindEphemeralLlmConfig()", javascript)
        self.assertIn("function sessionLlmApiKey()", javascript)
        self.assertIn("本页内存已就绪", javascript)
        self.assertNotIn("apiKey", javascript.split("function persistDramaDraft()", 1)[1].split("function queueDramaDraftSave()", 1)[0])
        self.assertNotIn("assistantApiKey", javascript.split("function persistDraft()", 1)[1].split("function queueDraftSave()", 1)[0])

    def test_duration_is_split_into_verified_short_segments(self) -> None:
        for duration, expected_segments in ((5, 1), (10, 2), (15, 3), (30, 6)):
            workflow, plan = bridge.build_workflow(
                self.timed_prompt(duration),
                {"duration": duration, "aspect": "16:9", "quality": "balanced"},
                snapshot=ready_snapshot(),
            )
            self.assertEqual(plan["segments"], expected_segments)
            self.assertEqual(plan["segment_frames"], 124)
            self.assertEqual(plan["final_frames"], duration * 24)
            self.assertEqual(workflow["250"]["inputs"]["length"], duration * 24)
            self.assertEqual(workflow["260"]["inputs"]["segment_count"], expected_segments)
            self.assert_connections_resolve(workflow)

    def test_node_ids_are_unique_after_six_segment_composition(self) -> None:
        workflow, _ = bridge.build_workflow(
            self.timed_prompt(30),
            {"duration": 30, "aspect": "16:9", "quality": "balanced", "seed": 123},
            snapshot=ready_snapshot(),
        )
        self.assertEqual(len(workflow), len(set(workflow)))
        self.assertEqual(workflow["205"]["class_type"], "VAEDecodeAudio")
        self.assertEqual(workflow["145"]["class_type"], "VAEDecode")
        self.assert_connections_resolve(workflow)

    def test_16gb_long_studio_request_is_downgraded_before_queue(self) -> None:
        workflow, plan = bridge.build_workflow(
            self.timed_prompt(30),
            {"duration": 30, "aspect": "9:16", "quality": "studio"},
            snapshot=ready_snapshot(16.0),
        )
        self.assertEqual(plan["quality_requested"], "studio")
        self.assertEqual(plan["quality_applied"], "balanced")
        self.assertEqual(plan["output_resolution"], "720×1280")
        self.assertNotIn("SeedVR2Preprocess", {node["class_type"] for node in workflow.values()})
        self.assertTrue(plan["notices"])

    def test_long_segments_receive_isolated_local_story_prompts(self) -> None:
        workflow, _ = bridge.build_workflow(
            self.timed_prompt(30),
            {"duration": 30, "aspect": "16:9", "quality": "balanced", "seed": 123},
            snapshot=ready_snapshot(),
        )
        first_prompt = workflow["100"]["inputs"]["prompt"]
        second_prompt = workflow["101"]["inputs"]["prompt"]
        last_prompt = workflow["105"]["inputs"]["prompt"]
        self.assertIn("SCENE_00", first_prompt)
        self.assertNotIn("SCENE_05", first_prompt)
        self.assertTrue(
            second_prompt.startswith(
                "For the target video, at 0.00 seconds into the target video, "
                "<Picture 1> (from [Shot 1]) is fully referenced."
            )
        )
        self.assertIn("SCENE_05", second_prompt)
        self.assertNotIn("SCENE_00", second_prompt)
        self.assertIn("SCENE_25", last_prompt)
        self.assertNotIn("SCENE_00", last_prompt)

    def test_16gb_five_second_studio_keeps_temporal_restoration(self) -> None:
        workflow, plan = bridge.build_workflow(
            self.prompt,
            {"duration": 5, "aspect": "16:9", "quality": "studio"},
            snapshot=ready_snapshot(16.0),
        )
        classes = {node["class_type"] for node in workflow.values()}
        self.assertEqual(plan["quality_applied"], "studio")
        self.assertEqual(plan["output_resolution"], "1920×1080")
        self.assertIn("SeedVR2TemporalChunk", classes)
        self.assertIn("SeedVR2PostProcessing", classes)

    def test_busy_queue_blocks_parallel_submission(self) -> None:
        snapshot = ready_snapshot()
        snapshot["comfy"]["queue_running"] = 1
        plan = bridge.build_plan(
            {"duration": 10, "aspect": "1:1", "quality": "draft"},
            snapshot=snapshot,
        )
        self.assertFalse(plan["ready"])
        self.assertIn("资源争抢", "".join(plan["blockers"]))
        self.assertEqual(plan["output_resolution"], "640×640")

    def test_long_plan_blocks_ambiguous_story_before_queue(self) -> None:
        plan = bridge.build_plan(
            {"duration": 10, "aspect": "16:9", "quality": "draft", "prompt": self.prompt},
            snapshot=ready_snapshot(),
        )
        self.assertFalse(plan["ready"])
        self.assertIn("剧情时间线", "".join(plan["blockers"]))
        self.assertIn("时间段", "".join(plan["blockers"]))
        self.assertIn("0-5秒", "".join(plan["blockers"]))

    def test_long_plan_accepts_isolated_timecoded_story(self) -> None:
        plan = bridge.build_plan(
            {
                "duration": 10,
                "aspect": "16:9",
                "quality": "draft",
                "prompt": self.timed_prompt(10),
            },
            snapshot=ready_snapshot(),
        )
        self.assertTrue(plan["ready"])
        self.assertEqual(plan["continuity_mode"], "末帧续接 + 剧情时间段隔离")

    def test_invalid_seed_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "随机种子无效"):
            bridge.normalize_config({"duration": 5, "seed": "not-a-number"})

    def test_null_reference_stays_in_text_to_video_mode(self) -> None:
        config = bridge.normalize_config({"duration": 5, "reference": None})
        self.assertIsNone(config["reference"])
        self.assertEqual(config["reference_mode"], "none")

    def test_reference_image_builds_real_first_frame_connection(self) -> None:
        token = "h3_flow_0123456789ab.png"
        workflow, plan = bridge.build_workflow(
            self.prompt,
            {"duration": 5, "reference": token, "reference_mode": "first_frame"},
            snapshot=ready_snapshot(),
        )
        self.assertEqual(plan["workflow_mode"], "首帧图生视频")
        self.assertEqual(workflow["18"]["class_type"], "LoadImage")
        self.assertEqual(workflow["19"]["class_type"], "ImageScale")
        self.assertEqual(workflow["100"]["class_type"], "MiniMaxH3ImageToVideo")
        self.assertEqual(workflow["100"]["inputs"]["first_frame"], ["19", 0])

    def test_identity_reference_builds_ref2va_workflow(self) -> None:
        token = "h3_flow_abcdef012345.webp"
        workflow, plan = bridge.build_workflow(
            self.prompt,
            {"duration": 5, "reference": token, "reference_mode": "identity", "seed": 88},
            snapshot=ready_snapshot(),
        )
        self.assertEqual(plan["workflow_mode"], "多参考身份 / 风格")
        self.assertEqual(workflow["6"]["inputs"]["unet_name"], "minimax_h3_ref2va_pruned_int8_convrot.safetensors")
        self.assertEqual(workflow["9"]["inputs"]["scheduler"], "beta")
        self.assertEqual(workflow["100"]["class_type"], "MiniMaxH3ReferenceToVideo")
        self.assertEqual(workflow["100"]["inputs"]["ref_images"]["ref_image_0"], ["18", 0])
        self.assertNotIn("19", workflow)

    def test_long_identity_reference_is_blocked_until_continuity_is_verified(self) -> None:
        plan = bridge.build_plan(
            {"duration": 10, "reference": "h3_flow_0123456789ab.png", "reference_mode": "identity"},
            snapshot=ready_snapshot(),
        )
        self.assertFalse(plan["ready"])
        self.assertIn("实载验收", "".join(plan["blockers"]))

    def test_arbitrary_reference_path_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "令牌无效"):
            bridge.normalize_config({"duration": 5, "reference": "../../private.png"})

    def test_reference_image_content_is_verified(self) -> None:
        buffer = BytesIO()
        Image.new("RGB", (64, 48), "#88aa33").save(buffer, format="PNG")
        self.assertEqual(bridge.validate_reference_image(buffer.getvalue(), "image/png"), (64, 48))
        with self.assertRaisesRegex(ValueError, "有效图片"):
            bridge.validate_reference_image(b"not an image", "image/png")

    def test_prompt_assistant_uses_official_i2va_alignment(self) -> None:
        messages, request = prompt_assistant.build_messages(
            {
                "brief": self.prompt,
                "duration": 5,
                "aspect": "16:9",
                "reference_mode": "first_frame",
            }
        )
        self.assertEqual(request["reference_mode"], "first_frame")
        self.assertIn(prompt_assistant.I2VA_ALIGNMENT, messages[1]["content"])
        self.assertIn("three fields must appear exactly once", messages[0]["content"])

    def test_prompt_assistant_rejects_insecure_remote_http(self) -> None:
        with self.assertRaisesRegex(ValueError, "必须使用 HTTPS"):
            prompt_assistant._resolve_config(
                {"base_url": "http://example.com/v1", "model": "custom-model", "api_key": "secret"}
            )

    def test_prompt_assistant_status_never_returns_environment_key(self) -> None:
        with patch.dict(
            prompt_assistant.os.environ,
            {"H3_FLOW_LLM_API_KEY": "private-test-key", "H3_FLOW_LLM_MODEL": "deepseek-v4-flash"},
            clear=False,
        ):
            status = prompt_assistant.prompt_assistant_status()
        self.assertTrue(status["environment_configured"])
        self.assertNotIn("private-test-key", str(status))

    def test_deepseek_error_codes_have_actionable_chinese_messages(self) -> None:
        expected = {
            401: "API Key 无效",
            402: "账户余额不足",
            422: "请求参数不符合 DeepSeek 接口要求",
            429: "请求过于频繁",
            503: "DeepSeek 服务繁忙",
        }
        for code, message in expected.items():
            error = HTTPError(
                "https://api.deepseek.com/chat/completions",
                code,
                "upstream error",
                {},
                BytesIO(b'{"error":{"message":"upstream detail"}}'),
            )
            self.assertIn(message, prompt_assistant._upstream_error(error, "DeepSeek"))

    def test_prompt_assistant_validates_full_reference_format(self) -> None:
        request = {"duration": 5, "reference_mode": "identity"}
        generated = """subject_definitions:
<Subject 1> is the primary product in <Picture 1>, preserving only the identity stated by the user.
summary:
[reference generation] The target shows <Subject 1> in one continuous product shot.
retention_analysis:
<Subject 1> (appears in [Shot 1]): fully_preserved - the requested product identity remains consistent.
detailed_description:
The target video uses a live-action cinematic product style with controlled side lighting.
[Shot 1] A medium-wide static shot holds <Subject 1> at the center while the light moves gradually across its surface and the camera pushes in with small amplitude at slow speed.
overall_soundscape:
Quiet indoor room tone and a soft mechanical camera movement continue throughout the shot.
non_diegetic_music:
N/A"""
        checks = prompt_assistant.validate_generated_prompt(generated, request)
        self.assertEqual(checks[0], "subject_definitions")
        self.assertEqual(checks[-1], "non_diegetic_music")

    def test_prompt_assistant_requires_every_long_video_beat(self) -> None:
        request = {"duration": 10, "reference_mode": "none"}
        generated = """integrated_multimodal_description:
0-5s: [Shot 1] Live-action, cinematic, a tracking shot follows an adult walking through a quiet hall while the camera pushes in with small amplitude at slow speed. The subject reaches the first doorway and pauses with a stable posture.
overall_soundscape:
Soft footsteps and steady indoor room tone continue under faint fabric movement.
non_diegetic_music:
N/A"""
        with self.assertRaisesRegex(ValueError, "5-10"):
            prompt_assistant.validate_generated_prompt(generated, request)

    def test_prompt_assistant_calls_openai_compatible_api_without_leaking_key(self) -> None:
        generated = """integrated_multimodal_description: [Shot 1] Live-action, cinematic, a medium-wide shot frames an adult walking through a rain-lit station. The camera tracks the subject at slow speed while clothing, lighting, movement direction, and spatial relationships remain consistent until the subject stops beside the final doorway.
overall_soundscape: Rain taps the glass while distant trains, measured footsteps, and soft fabric movement remain synchronized with the action.
non_diegetic_music: Sparse piano notes at a slow tempo with sustained low strings that gradually decrease in volume."""
        response_payload = {
            "model": "custom-model",
            "choices": [{"message": {"content": generated}}],
            "usage": {"prompt_tokens": 20, "completion_tokens": 40, "total_tokens": 60},
        }
        captured: dict[str, str] = {}

        class FakeResponse(BytesIO):
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, traceback):
                self.close()
                return False

        def fake_urlopen(request, timeout=0):
            captured["authorization"] = request.headers.get("Authorization", "")
            captured["url"] = request.full_url
            self.assertEqual(timeout, 90)
            return FakeResponse(prompt_assistant.json.dumps(response_payload).encode("utf-8"))

        with patch.object(prompt_assistant.urllib.request, "urlopen", side_effect=fake_urlopen):
            result = prompt_assistant.rewrite_h3_prompt(
                {
                    "brief": self.prompt,
                    "duration": 5,
                    "aspect": "16:9",
                    "reference_mode": "none",
                    "api_config": {
                        "base_url": "https://llm.example.com/v1",
                        "model": "custom-model",
                        "api_key": "private-test-key",
                    },
                }
            )
        self.assertEqual(captured["authorization"], "Bearer private-test-key")
        self.assertEqual(captured["url"], "https://llm.example.com/v1/chat/completions")
        self.assertEqual(result["prompt"], generated)
        self.assertNotIn("private-test-key", str(result))

    def test_short_drama_validator_stabilises_ids_and_duration_budget(self) -> None:
        request = short_drama.normalise_short_drama_request(
            {
                "theme": "一名调查员发现自己的记忆正在被一份旧档案逐页改写。",
                "episode_count": 1,
                "episode_duration_seconds": 30,
                "cast_count": 1,
            }
        )
        package = short_drama.validate_short_drama_package(self.short_drama_payload(), request)
        self.assertEqual(package["characters"][0]["id"], "CHAR-01")
        self.assertEqual(package["episodes"][0]["scenes"][0]["location_id"], "LOC-01")
        self.assertEqual(package["episodes"][0]["scenes"][0]["shots"][0]["dialogue"][0]["speaker_id"], "CHAR-01")
        self.assertEqual(package["episodes"][0]["duration_seconds"], 30)
        self.assertTrue(package["checks"]["references_resolved"])

    def test_short_drama_treats_every_creator_setting_as_a_hard_constraint(self) -> None:
        request = short_drama.normalise_short_drama_request(
            {
                "theme": "一名调查员发现自己的记忆正在被一份旧档案逐页改写。",
                "working_title": "记忆审判",
                "genre": "女性向科幻悬疑",
                "visual_style": "冷白实验室与琥珀色记忆闪回形成严格对比",
                "audience": "喜爱强情节反转的成年观众",
                "language": "四川方言",
                "episode_count": 1,
                "episode_duration_seconds": 30,
                "cast_count": 1,
                "aspect": "9:16",
                "ending_style": "closed",
                "dialogue_density": "lean",
                "quality": "studio",
            }
        )
        messages = short_drama.build_short_drama_messages(request)
        self.assertIn("Every CREATIVE_INPUT field is a hard production constraint", messages[0]["content"])
        for key, value in request.items():
            self.assertIn(f'"{key}"', messages[1]["content"])
            if isinstance(value, str) and value:
                self.assertIn(value, messages[1]["content"])

        package = short_drama.validate_short_drama_package(self.short_drama_payload(), request)
        self.assertEqual(package["project"]["title"], "记忆审判")
        self.assertEqual(package["project"]["dialogue_density"], "lean")
        self.assertTrue(package["checks"]["constraints_applied"])
        h3_brief = package["episodes"][0]["scenes"][0]["shots"][0]["h3_brief"]
        for expected in ("9:16", "四川方言", "冷白实验室", "studio"):
            self.assertIn(expected, h3_brief)

    def test_short_drama_accepts_ai_selected_and_custom_genre_and_style(self) -> None:
        request = short_drama.normalise_short_drama_request(
            {
                "theme": "一名调查员发现自己的记忆正在被一份旧档案逐页改写。",
                "genre": "由编剧模型根据主题判断最合适的题材；用户自定义要求：不要爱情线，重点写家族秘密",
                "visual_style": "由编剧模型根据故事设计统一、可执行的视觉风格；用户自定义要求：手持纪实感，雨夜暖色窗光",
                "episode_count": 1,
                "episode_duration_seconds": 30,
                "cast_count": 1,
            }
        )
        self.assertIn("不要爱情线", request["genre"])
        self.assertIn("手持纪实感", request["visual_style"])

    def test_short_drama_batch_preflight_requires_plan_and_approved_character_assets(self) -> None:
        with self.assertRaisesRegex(ValueError, "先生成并确认短剧方案"):
            short_drama.preflight_short_drama_batch({}, {}, ready_snapshot())
        package = short_drama.validate_short_drama_package(
            self.short_drama_payload(),
            short_drama.normalise_short_drama_request(
                {
                    "theme": "一名调查员发现自己的记忆正在被一份旧档案逐页改写。",
                    "episode_count": 1,
                    "episode_duration_seconds": 30,
                    "cast_count": 1,
                }
            ),
        )
        with self.assertRaisesRegex(ValueError, "CHAR-01"):
            short_drama.preflight_short_drama_batch(package, {}, ready_snapshot())
        result = short_drama.preflight_short_drama_batch(
            package,
            {"CHAR-01": {"token": "h3_flow_0123456789ab.png", "approved": True}},
            ready_snapshot(),
        )
        self.assertTrue(result["ready"])
        self.assertEqual(result["execution_mode"], "serial_one_shot_at_a_time")
        self.assertEqual(result["shot_count"], 6)
        self.assertEqual(result["planned_shot_count"], 2)
        self.assertFalse(result["submitted"])

    def test_short_drama_batch_builds_real_ref2va_shot_without_page_handoff(self) -> None:
        package = short_drama.validate_short_drama_package(
            self.short_drama_payload(),
            short_drama.normalise_short_drama_request(
                {
                    "theme": "一名调查员发现自己的记忆正在被一份旧档案逐页改写。",
                    "episode_count": 1,
                    "episode_duration_seconds": 30,
                    "cast_count": 1,
                    "quality": "balanced",
                }
            ),
        )
        scene = package["episodes"][0]["scenes"][0]
        unit = short_drama.expand_short_drama_batch_units(package)[0]
        workflow, plan = bridge.build_short_drama_shot_workflow(
            package,
            unit["scene"],
            unit["shot"],
            {"CHAR-01": {"token": "h3_flow_0123456789ab.png", "approved": True}},
            job_id="drama_test",
            quality="balanced",
            seed=123,
        )
        self.assertEqual(workflow["100"]["class_type"], "MiniMaxH3ReferenceToVideo")
        self.assertEqual(workflow["100"]["inputs"]["ref_images"]["ref_image_0"], ["18", 0])
        self.assertEqual(workflow["100"]["inputs"]["length"], 124)
        self.assertEqual(workflow["250"]["inputs"]["length"], 120)
        self.assertIn("<Picture 1>", workflow["100"]["inputs"]["prompt"])
        self.assertIn("video/short_drama/drama_test", workflow["271"]["inputs"]["filename_prefix"])
        self.assertEqual(plan["reference_mode"], "identity")
        self.assert_connections_resolve(workflow)

    def test_short_drama_recognises_savevideo_mp4_when_comfy_reports_it_as_image(self) -> None:
        self.assertTrue(bridge.is_video_output({"kind": "images", "filename": "shot_00001.mp4"}))
        self.assertFalse(bridge.is_video_output({"kind": "images", "filename": "preview_00001.png"}))

    def test_short_drama_validator_rejects_wrong_episode_duration(self) -> None:
        request = short_drama.normalise_short_drama_request(
            {
                "theme": "一名调查员发现自己的记忆正在被一份旧档案逐页改写。",
                "episode_count": 1,
                "episode_duration_seconds": 60,
                "cast_count": 1,
            }
        )
        with self.assertRaisesRegex(ValueError, "必须等于 60 秒"):
            short_drama.validate_short_drama_package(self.short_drama_payload(), request)

    def test_short_drama_status_exposes_gate_without_secret(self) -> None:
        with patch.dict(prompt_assistant.os.environ, {"H3_FLOW_LLM_API_KEY": "private-test-key"}, clear=False):
            status = short_drama.short_drama_status()
        self.assertFalse(status["capabilities"]["full_series_generation"])
        self.assertTrue(status["capabilities"]["serial_batch_generation"])
        self.assertTrue(status["capabilities"]["all_shot_batch_generation"])
        self.assertNotIn("private-test-key", str(status))

    def test_short_drama_generation_uses_json_mode_without_leaking_key(self) -> None:
        response_payload = {
            "model": "custom-model",
            "choices": [{"message": {"content": prompt_assistant.json.dumps(self.short_drama_payload(), ensure_ascii=False)}}],
            "usage": {"prompt_tokens": 100, "completion_tokens": 500, "total_tokens": 600},
        }
        captured: dict[str, object] = {}

        class FakeResponse(BytesIO):
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, traceback):
                self.close()
                return False

        def fake_urlopen(request, timeout=0):
            captured["authorization"] = request.headers.get("Authorization", "")
            captured["body"] = prompt_assistant.json.loads(request.data.decode("utf-8"))
            self.assertEqual(timeout, 180)
            return FakeResponse(prompt_assistant.json.dumps(response_payload).encode("utf-8"))

        with patch.object(prompt_assistant.urllib.request, "urlopen", side_effect=fake_urlopen):
            package = short_drama.generate_short_drama(
                {
                    "theme": "一名调查员发现自己的记忆正在被一份旧档案逐页改写。",
                    "episode_count": 1,
                    "episode_duration_seconds": 30,
                    "cast_count": 1,
                    "api_config": {
                        "base_url": "https://llm.example.com/v1",
                        "model": "custom-model",
                        "api_key": "private-test-key",
                    },
                }
            )
        self.assertEqual(captured["authorization"], "Bearer private-test-key")
        self.assertEqual(captured["body"]["response_format"], {"type": "json_object"})
        self.assertFalse(package["generation"]["api_key_persisted"])
        self.assertNotIn("private-test-key", str(package))


if __name__ == "__main__":
    unittest.main()
