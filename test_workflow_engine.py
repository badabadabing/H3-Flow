from __future__ import annotations

import unittest
from io import BytesIO

from PIL import Image

import bridge


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


if __name__ == "__main__":
    unittest.main()
