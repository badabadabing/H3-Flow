# H3 官方格式提示词编导

H3 Flow 的 AI 提示词编导不是自由聊天功能。它把用户的创意描述、目标时长、画面比例和当前参考模式整理为 MiniMax H3 可直接使用的结构化提示词，并在本地检查字段顺序、首帧对齐指令和长视频时间段是否完整。

## 官方依据

实现锁定到 MiniMaxAI/MiniMax-H3 Hugging Face 发布修订 `939557dc319dd91227e30195a763f272ba7f8765`：

- [Video Prompt Writing Guide：T2VA / I2VA / FL2VA / L2VA](https://huggingface.co/MiniMaxAI/MiniMax-H3/blob/main/docs/VIDEO_PROMPT_WRITING_GUIDE_base_en.md)
- [Full-Reference Mode Rewrite Output Format Guide](https://huggingface.co/MiniMaxAI/MiniMax-H3/blob/main/docs/VIDEO_PROMPT_WRITING_GUIDE_ref_en.md)
- [MiniMax H3 官方仓库](https://github.com/MiniMax-AI/MiniMax-H3)

T2VA 与首帧 I2VA 使用三个官方核心字段：

```text
integrated_multimodal_description: ...
overall_soundscape: ...
non_diegetic_music: ...
```

首帧 I2VA 还必须在第一行加入官方 `<Picture 1>` 对齐指令。Ref2VA 使用 `subject_definitions`、`summary`、`retention_analysis`、`detailed_description`、`overall_soundscape`、`non_diegetic_music` 六段结构。

10–30 秒工作流会额外要求 `0-5s:`、`5-10s:` 等连续生产时间段，使本地分段编译器能够为每一段提取独立的新剧情，而不是重复第一段。

## 模型服务

编导通过 OpenAI-compatible `POST /chat/completions` 接口工作。DeepSeek 是默认预设，但不是强制依赖；可以填写其他云端兼容接口或 `127.0.0.1` 上的本机服务。

DeepSeek 当前官方预设：

```text
Base URL: https://api.deepseek.com
Model: deepseek-v4-flash
```

模型名称会随服务商升级而变化，H3 Flow 不会自动替用户购买、创建或保存 API Key。DeepSeek 的当前模型和请求格式请以其[官方首次调用说明](https://api-docs.deepseek.com/zh-cn/)与[Chat Completions API](https://api-docs.deepseek.com/api/create-chat-completion/)为准。

## 配置方法

最简单的方法是在“AI 提示词编导”面板中填写服务地址、模型名称和 API Key。Key 只保留在当前页面内存，刷新或关闭页面后消失，不写入项目、浏览器存储或响应正文。

也可以在启动 H3 Flow 前通过当前 PowerShell 进程设置：

```powershell
$env:H3_FLOW_LLM_BASE_URL = "https://api.deepseek.com"
$env:H3_FLOW_LLM_MODEL = "deepseek-v4-flash"
$env:H3_FLOW_LLM_API_KEY = "由你自己的服务商提供"
```

随后正常运行启动脚本。远程服务必须使用 HTTPS；无 Key 的 HTTP 接口仅允许 `127.0.0.1`、`localhost` 或 `::1`。

## 隐私与验证边界

只有在用户明确点击“生成官方格式提示词”后，以下内容才会发送给所选模型服务：

- 当前文本创意；
- 视频时长；
- 画面比例；
- T2VA、首帧 I2VA 或 Ref2VA 模式名称。

参考图字节、文件名、本机路径、ComfyUI 工作流、模型清单、硬件信息和生成媒体都不会发送给提示词模型。由于模型看不到参考图，Ref2VA 编导不会捏造图片中的脸、服装、颜色、文字或构图；需要依赖的视觉事实应由用户在创意描述里明确写出。

外部大模型的输出会在本地经过格式复检，但这不能保证创意质量或视频生成结果。提交 ComfyUI 前仍会继续执行原有模型、节点、显存、队列和工作流 schema 门禁。
