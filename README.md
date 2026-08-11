# H3 Flow

H3 Flow 是一个面向普通创作者的本地 MiniMax H3 工作流前端。用户只需要填写提示词、选择时长与质量，并按用途上传参考图；H3 Flow 会连接本机 ComfyUI，检查硬件、模型、节点、插件和版本，再生成或提交可验证的 API 工作流。

[English](README.en.md) · [兼容性契约](docs/compatibility.md) · [长视频研究与边界](docs/continuity.md) · [安全策略](SECURITY.md) · [隐私说明](PRIVACY.md)

## 当前能力

- 文生视频：使用 `MiniMaxH3ImageToVideo` 的无图 FL2VA 路径。
- 首帧图生视频：参考图真实连接到 `LoadImage → ImageScale → MiniMaxH3ImageToVideo.first_frame`。
- 身份 / 风格参考：使用独立 Ref2VA 权重和 `MiniMaxH3ReferenceToVideo`；当前 UI 开放单图、5 秒安全档。
- 5、10、15、30 秒安全计划；长视频基础模式按 124 帧短片段生成并使用上一段末帧续接。
- 480P 原生预览、720P 成片和受硬件门禁保护的 SeedVR2 1080P 精修。
- 环境基线检测：ComfyUI、前端、工作流模板、Python、PyTorch、模型文件、节点以及可选潜空间续接插件。
- 提交前二次检查队列、节点 schema、模型枚举、连接类型和拓扑；检查失败不会提交工作流。

> “末帧续接”不等于潜空间无缝续接。H3 Flow 会在界面中明确标注当前策略。潜空间续接必须在固定插件版本通过实载验收后才会开放，详见 [docs/continuity.md](docs/continuity.md)。

## 前置条件

- Windows 10/11，NVIDIA GPU；当前完整测试基线为 16GB VRAM。
- 已能独立启动的 ComfyUI。
- 已按 [compatibility.json](compatibility.json) 准备模型与节点。
- Python 3.11 或更高版本；依赖仅为 Pillow。

本仓库不包含模型权重、ComfyUI 运行时或用户媒体。使用 MiniMax H3 前请自行阅读并接受其模型许可及适用地区限制。

## 启动

```powershell
git clone https://github.com/badabadabing/H3-Flow.git
cd H3-Flow
py -3 -m pip install -r requirements.txt
```

先启动 ComfyUI，再启动 H3 Flow：

```powershell
.\scripts\start.ps1 -ComfyRoot "D:\path\to\ComfyUI"
```

浏览器打开 `http://127.0.0.1:4173`。如 ComfyUI 不在默认 `http://127.0.0.1:8188`：

```powershell
.\scripts\start.ps1 -ComfyRoot "D:\path\to\ComfyUI" -ComfyUrl "http://127.0.0.1:9000"
```

所有配置仅写入当前启动进程的环境变量，不修改系统全局配置。

## 必需的自定义节点

将以下仓库内目录手动复制到 ComfyUI 的 `custom_nodes` 后重启 ComfyUI：

- `comfy_nodes/h3_audio_continuity`
- 使用 1080P 精修时再安装 `comfy_nodes/h3_long_video_safety`

`comfy_nodes/h3_prompt_continuity` 由 H3 Flow 桥接层直接调用，用于把带明确时间段的长视频主提示词编译为互不重演的局部片段提示；如需在 ComfyUI 节点图中单独使用 `H3SegmentPromptCompiler`，也可以手动复制该目录。

H3 原生节点来自兼容版本的 ComfyUI，不需要额外 H3 节点包。潜空间续接插件不会被自动下载或执行；H3 Flow 只检测 [兼容性清单](compatibility.json) 中锁定的版本。

## 验证

```powershell
py -3 -X utf8 -m unittest -v test_workflow_engine.py
node --check app.js
```

运行后可查看：

- `GET /api/status?refresh=1`：硬件、ComfyUI 与兼容性摘要。
- `GET /api/compatibility`：不包含绝对路径的完整模型、节点、插件和版本结果。
- `POST /api/workflow`：导出工作流但不排队。

## 隐私与开源边界

- 服务默认只监听 `127.0.0.1`，无遥测、无账号、无云端上传。
- 参考图通过本机 ComfyUI 官方上传接口进入其 `input` 目录。
- API 不返回 ComfyUI 绝对路径、用户名、Git 凭据或模型内容。
- `.gitignore` 阻止模型、媒体、日志、本机配置和缓存进入 Git。
- 公开前请运行 `scripts/privacy-check.ps1`。

项目代码采用 [MIT License](LICENSE)。MiniMax H3、SeedVR2、ComfyUI 和第三方插件分别适用其自身许可，本仓库不替代这些许可。

## 路线图

- 首尾帧 FL2VA 控制。
- Ref2VA 多图管理与引用标签助手。
- 潜空间声画续接的固定版本集成、接缝量化与真实长链验收。
- 跨平台启动器和可复现安装清单。

贡献前请阅读 [CONTRIBUTING.md](CONTRIBUTING.md)。
