# H3 Flow

H3 Flow 是一个面向普通创作者的本地 MiniMax H3 工作流前端。用户只需要填写提示词、选择时长与质量，并按用途上传参考图；H3 Flow 会连接本机 ComfyUI，检查硬件、模型、节点、插件和版本，再生成或提交可验证的 API 工作流。

[English](README.en.md) · [AI 短剧模式](docs/short-drama-mode.md) · [100 名创作者合成审计](docs/creator-cohort-audit.md) · [H3 提示词编导](docs/prompt-assistant.md) · [兼容性契约](docs/compatibility.md) · [长视频研究与边界](docs/continuity.md) · [安全策略](SECURITY.md) · [隐私说明](PRIVACY.md)

## 当前能力

- 文生视频：使用 `MiniMaxH3ImageToVideo` 的无图 FL2VA 路径。
- 首帧图生视频：参考图真实连接到 `LoadImage → ImageScale → MiniMaxH3ImageToVideo.first_frame`。
- 身份 / 风格参考：使用独立 Ref2VA 权重和 `MiniMaxH3ReferenceToVideo`；短剧角色使用正面、3/4 侧面、全侧面三视图锁定，三张图作为同一身份共同参与 H3 条件生成。
- AI 提示词编导：按 MiniMax H3 官方 Base / Ref2VA 指引生成结构化提示词；默认支持 DeepSeek，也可以填写其他 OpenAI-compatible 云端或本机接口。
- AI 短剧制片包：只需主题、集数和时长；题材与风格可交给 AI、使用预设或追加自定义要求。系统生成系列圣经、角色 / 服装 / 道具 / 场景资产、详细分集、场次和镜头，并本地校验稳定 ID、引用关系、五秒节拍和逐集时长。
- 角色确认与一键镜头队列：每个主要角色补齐并锁定三视图后，一次点击即可把全部镜头交给后台；10/15 秒计划镜头会自动拆成 5 秒安全单元，按显存安全顺序逐个生成，前台不再逐镜头切页操作。同场最多 3 位三视图角色，遵守 H3 的 9 张参考图上限。
- 自动整集合片：全部镜头完成后按分集顺序生成精确 24fps MP4，结果区优先提供整集播放，同时保留单镜头返修文件。
- 创作引导：主体 / 动作 / 镜头 / 声音四项简报检查，10–30 秒可视化 5 秒分镜编排，无需手写时间码。
- 本机草稿：自动保存提示词、时长、比例、质量与分镜；API Key、参考图、硬件信息不会写入草稿。
- 统一生成前总检：把创意缺项、长视频时间线、模型、版本、显存和队列问题合并成可返回修正的检查结果。
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

提示词编导的 API Key 可以直接在页面里填写，仅保留到页面关闭；单视频提示词编导与短剧模式共享同一份本页临时配置，任一处填写后都会显示“本页内存已就绪”。刷新或关闭页面会清除，且不会写入草稿、项目或响应。也可以在启动前设置 `H3_FLOW_LLM_BASE_URL`、`H3_FLOW_LLM_MODEL` 和 `H3_FLOW_LLM_API_KEY`。详细格式和隐私边界见 [docs/prompt-assistant.md](docs/prompt-assistant.md)。

短剧模式使用同一套用户自配模型规则。顶栏切换到“AI 短剧”，填写主题、集数和单集时长；题材与风格可直接交给 AI，也可选择预设或追加自定义要求。生成方案后上传并确认每个主要角色参考图，再点击“一键生成全部镜头”。制片包会保存在当前浏览器，但密钥、模型服务地址、参考图和本机信息不会进入草稿。完整步骤与执行边界见 [docs/short-drama-mode.md](docs/short-drama-mode.md)。

默认 5 秒档可以直接写完整场景。选择 10、15 或 30 秒时，可以在“逐段写清”区域填写每个 5 秒剧情段，H3 Flow 会自动编译时间码并检查完整性；也可以直接粘贴已有的完整时间线。缺少任一后续时间段时，界面会在排队前阻止生成。例如：

```text
0-5秒：人物从床边起身，走向宫门。
5-10秒：人物穿过宫门，继续进入藏书房。
overall_soundscape：脚步与室内环境声连续。
non_diegetic_music：N/A
```

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
- `GET /api/prompt-assistant`：提示词编导默认服务、模型、官方指引修订和无密钥状态。
- `POST /api/prompt-assistant`：调用用户选择的模型服务并在本地复检 H3 官方字段；不会提交 ComfyUI。
- `GET /api/short-drama`：短剧数据合同、支持范围、模型默认值与整季执行门禁。
- `POST /api/short-drama/plan`：生成并本地复检完整短剧制片包；不会提交 ComfyUI。
- `POST /api/short-drama/batch/preflight`：只读检查方案、角色批准、模型、内存、显存和队列，不提交任务。
- `POST /api/short-drama/batch/start`：启动一个后台串行镜头队列；同时只运行一个 5 秒 H3 单元。
- `GET /api/short-drama/batch/{job_id}`：返回当前镜头、完成数、错误与成片链接。
- `POST /api/workflow`：导出工作流但不排队。

## 隐私与开源边界

- 服务默认只监听 `127.0.0.1`，无遥测、无账号；只有用户点击 AI 改写时，当前提示词和制片参数才会发送给其自行选择的模型服务。
- 参考图通过本机 ComfyUI 官方上传接口进入其 `input` 目录。
- API 不返回 ComfyUI 绝对路径、用户名、Git 凭据或模型内容。
- `.gitignore` 阻止模型、媒体、日志、本机配置和缓存进入 Git。
- 公开前请运行 `scripts/privacy-check.ps1`。

项目代码采用 [MIT License](LICENSE)。MiniMax H3、SeedVR2、ComfyUI 和第三方插件分别适用其自身许可，本仓库不替代这些许可。

## 路线图

- [AI 短剧制片系统](docs/ai-short-drama-roadmap.md)：结构化制片包、角色参考图批准和一键串行生成全部镜头已经落地；下一阶段是断点恢复、分集自动装配、试播质量门禁与单镜头返修。
- 首尾帧 FL2VA 控制。
- Ref2VA 多图管理与引用标签助手。
- 潜空间声画续接的固定版本集成、接缝量化与真实长链验收。
- 跨平台启动器和可复现安装清单。

贡献前请阅读 [CONTRIBUTING.md](CONTRIBUTING.md)。
