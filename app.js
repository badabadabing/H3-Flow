const state = {
  duration: 10,
  aspect: "16:9",
  quality: "balanced",
  reference: null,
  referenceMode: "first_frame",
  referenceUploading: false,
  plan: null,
  status: null,
  busy: false,
  promptId: null,
  pollTimer: null,
};

const templates = {
  commercial: `一个连续的高端产品广告镜头。主体是一件放在深色石材台面上的产品，镜头从侧后方缓慢环绕到正面，柔和侧光勾勒材质边缘，背景克制、没有多余道具。产品始终保持结构准确，焦点稳定，动作自然，没有文字、标志或水印。

overall_soundscape：安静室内空间感、轻微机械滑轨声与符合材质的细小触碰声。
non_diegetic_music：N/A。`,
  portrait: `一个连续的电影感人物表演镜头。一位成年人物在自然环境中完成一段清晰、连贯的动作，先保持中景，再由摄影机缓慢靠近面部。人物身份、发型、服装和光线始终一致，表情变化自然，肢体结构准确，没有切镜、字幕、标志或水印。

overall_soundscape：现场环境声、衣料摩擦和与动作同步的细节声音。
non_diegetic_music：N/A。`,
  atmosphere: `一个连续的氛围电影镜头。清晨薄雾中的城市街道，湿润路面反射柔和天光，摄影机以稳定的低机位缓慢向前移动。远处人物只作为环境尺度，不靠近镜头；构图克制、色彩自然、运动连贯，没有切镜、文字、标志或水印。

overall_soundscape：远处车流、微风、偶尔的脚步与自然城市底噪。
non_diegetic_music：极轻的原创氛围纹理，不盖过环境声。`,
};

const $ = (selector) => document.querySelector(selector);
const $$ = (selector) => [...document.querySelectorAll(selector)];

const elements = {
  form: $("#flowForm"),
  prompt: $("#prompt"),
  promptCount: $("#promptCount"),
  promptError: $("#promptError"),
  referenceInput: $("#referenceInput"),
  uploadButton: $("#uploadButton"),
  uploadEmpty: $("#uploadEmpty"),
  uploadPreview: $("#uploadPreview"),
  referencePreview: $("#referencePreview"),
  referenceName: $("#referenceName"),
  referenceMeta: $("#referenceMeta"),
  referenceModeControl: $("#referenceModeControl"),
  durationControl: $("#durationControl"),
  aspectControl: $("#aspectControl"),
  qualityControl: $("#qualityControl"),
  seed: $("#seed"),
  randomSeed: $("#randomSeed"),
  connectionButton: $("#connectionButton"),
  connectionDot: $("#connectionDot"),
  connectionText: $("#connectionText"),
  safetyState: $("#safetyState"),
  segmentTrack: $("#segmentTrack"),
  segmentLabel: $("#segmentLabel"),
  durationLabel: $("#durationLabel"),
  modeValue: $("#modeValue"),
  continuityValue: $("#continuityValue"),
  sourceValue: $("#sourceValue"),
  outputValue: $("#outputValue"),
  gpuValue: $("#gpuValue"),
  gpuMeter: $("#gpuMeter"),
  gpuNote: $("#gpuNote"),
  ramValue: $("#ramValue"),
  ramMeter: $("#ramMeter"),
  ramNote: $("#ramNote"),
  compatibilityCard: $("#compatibilityCard"),
  compatibilityState: $("#compatibilityState"),
  runtimeCompatibility: $("#runtimeCompatibility"),
  baseCompatibility: $("#baseCompatibility"),
  referenceCompatibility: $("#referenceCompatibility"),
  continuityCompatibility: $("#continuityCompatibility"),
  refreshStatus: $("#refreshStatus"),
  planNotice: $("#planNotice"),
  noticeTitle: $("#noticeTitle"),
  noticeDetail: $("#noticeDetail"),
  blockerList: $("#blockerList"),
  protectionList: $("#protectionList"),
  generateButton: $("#generateButton"),
  generateText: $("#generateText"),
  exportButton: $("#exportButton"),
  actionHint: $("#actionHint"),
  jobPanel: $("#jobPanel"),
  closeJob: $("#closeJob"),
  jobTitle: $("#jobTitle"),
  jobSummary: $("#jobSummary"),
  jobProgress: $("#jobProgress"),
  jobId: $("#jobId"),
  jobState: $("#jobState"),
  jobResults: $("#jobResults"),
  toast: $("#toast"),
};

function currentConfig() {
  return {
    duration: state.duration,
    aspect: state.aspect,
    quality: state.quality,
    reference: state.reference?.token || null,
    reference_mode: state.referenceMode,
    seed: elements.seed.value || null,
  };
}

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });
  let body;
  try {
    body = await response.json();
  } catch {
    body = { error: `本地服务返回了无法读取的响应（HTTP ${response.status}）` };
  }
  if (!response.ok) {
    throw new Error(body.error || `请求失败（HTTP ${response.status}）`);
  }
  return body;
}

function post(path, payload) {
  return api(path, { method: "POST", body: JSON.stringify(payload) });
}

let toastTimer;
function showToast(message) {
  clearTimeout(toastTimer);
  elements.toast.textContent = message;
  elements.toast.hidden = false;
  toastTimer = setTimeout(() => {
    elements.toast.hidden = true;
  }, 4600);
}

function setBusy(busy, text = "生成视频") {
  state.busy = busy;
  elements.generateButton.classList.toggle("is-loading", busy);
  elements.generateButton.disabled = busy || state.referenceUploading;
  elements.exportButton.disabled = busy || state.referenceUploading;
  elements.generateText.textContent = text;
}

function formatClock(seconds) {
  return `00:${String(seconds).padStart(2, "0")}`;
}

function setConnection(snapshot) {
  const comfy = snapshot?.comfy;
  elements.connectionButton.classList.remove("is-online", "is-offline", "is-loading");
  if (!comfy) {
    elements.connectionButton.classList.add("is-loading");
    elements.connectionText.textContent = "正在检测";
    return;
  }
  if (comfy.online) {
    elements.connectionButton.classList.add("is-online");
    elements.connectionText.textContent = "ComfyUI 已连接";
  } else {
    elements.connectionButton.classList.add("is-offline");
    elements.connectionText.textContent = "ComfyUI 未启动";
  }
}

function renderCompatibility(compatibility) {
  if (!compatibility) return;
  const labels = {
    ready: "版本完全匹配",
    compatible: "功能兼容 · 版本有差异",
    blocked: "环境不完整",
  };
  elements.compatibilityCard.classList.remove("is-compatible", "is-blocked");
  if (compatibility.status === "compatible") elements.compatibilityCard.classList.add("is-compatible");
  if (compatibility.status === "blocked") elements.compatibilityCard.classList.add("is-blocked");
  elements.compatibilityState.textContent = labels[compatibility.status] || "状态未知";
  elements.runtimeCompatibility.textContent = compatibility.summary?.runtime || "未连接";
  elements.baseCompatibility.textContent = compatibility.summary?.base || "未检测";
  elements.referenceCompatibility.textContent = compatibility.summary?.reference || "未检测";
  elements.continuityCompatibility.textContent = compatibility.summary?.continuity || "未检测";
}

function renderPlan(plan) {
  if (!plan) return;
  state.plan = plan;
  setConnection(plan.snapshot);

  elements.segmentTrack.replaceChildren();
  for (let index = 0; index < plan.segments; index += 1) {
    const segment = document.createElement("span");
    segment.dataset.index = String(index + 1).padStart(2, "0");
    segment.title = `第 ${index + 1} 个安全片段，固定 ${plan.segment_frames} 帧`;
    elements.segmentTrack.append(segment);
  }
  elements.segmentLabel.textContent = `${plan.segments} 个安全片段`;
  elements.durationLabel.textContent = formatClock(plan.duration);
  elements.modeValue.textContent = plan.workflow_mode;
  elements.continuityValue.textContent = plan.continuity_mode;
  elements.sourceValue.textContent = plan.source_resolution;
  elements.outputValue.textContent = plan.output_resolution;

  const hardware = plan.snapshot.hardware || {};
  const gpuTotal = Number(hardware.vram_total_gb || 0);
  const gpuFree = Number(hardware.vram_free_gb || 0);
  elements.gpuValue.textContent = gpuTotal ? `${gpuTotal.toFixed(1)}GB` : "未检测到";
  elements.gpuMeter.style.width = gpuTotal ? `${Math.min(100, Math.max(8, (gpuFree / gpuTotal) * 100))}%` : "0%";
  const cleanGpuName = String(hardware.gpu_name || "")
    .replace(/^cuda:\d+\s+NVIDIA\s+/i, "")
    .replace(/\s*:\s*cudaMallocAsync$/i, "")
    .replace(/^NVIDIA\s+/i, "");
  elements.gpuNote.textContent = hardware.gpu_name
    ? `${cleanGpuName} · 空闲 ${gpuFree.toFixed(1)}GB · 保留 1.5GB`
    : "需要 NVIDIA 显卡才能执行 H3 工作流";

  const commitTotal = Number(hardware.commit_total_gb || 0);
  const commitFree = Number(hardware.commit_free_gb || 0);
  const commitUsed = Math.max(0, commitTotal - commitFree);
  elements.ramValue.textContent = commitTotal ? `${commitUsed.toFixed(1)} / ${commitTotal.toFixed(1)}GB` : "未检测到";
  elements.ramMeter.style.width = commitTotal ? `${Math.min(100, (commitUsed / commitTotal) * 100)}%` : "0%";
  elements.ramNote.textContent = commitTotal ? `可用提交空间 ${commitFree.toFixed(1)}GB` : "长视频需要足够的提交空间";
  renderCompatibility(plan.snapshot.compatibility);

  const notice = plan.notices?.[0];
  elements.planNotice.hidden = !notice;
  if (notice) {
    elements.noticeTitle.textContent = notice.title;
    elements.noticeDetail.textContent = notice.detail;
  }

  elements.blockerList.replaceChildren();
  for (const blocker of plan.blockers || []) {
    const item = document.createElement("p");
    item.textContent = blocker;
    elements.blockerList.append(item);
  }

  elements.protectionList.replaceChildren();
  for (const protection of plan.protection || []) {
    const item = document.createElement("li");
    item.innerHTML = '<svg aria-hidden="true"><use href="#icon-check"></use></svg>';
    const copy = document.createElement("span");
    copy.textContent = protection;
    item.append(copy);
    elements.protectionList.append(item);
  }

  const offlineOnly = plan.blockers?.length === 1 && plan.blockers[0] === "ComfyUI 尚未启动";
  const adjusted = plan.quality_requested !== plan.quality_applied;
  elements.safetyState.className = "safety-state";
  if (plan.ready) {
    elements.safetyState.classList.add(adjusted ? "is-adjusted" : "is-ready");
    elements.safetyState.lastChild.textContent = adjusted ? "已自动优化" : "安全可执行";
  } else if (offlineOnly) {
    elements.safetyState.classList.add("is-adjusted");
    elements.safetyState.lastChild.textContent = "提交时自动启动";
  } else {
    elements.safetyState.classList.add("is-blocked");
    elements.safetyState.lastChild.textContent = "需要处理";
  }

  if (!state.busy) {
    elements.generateButton.disabled = state.referenceUploading || (!plan.ready && !offlineOnly);
    elements.generateText.textContent = offlineOnly ? "启动并生成" : `生成 ${plan.duration} 秒视频`;
  }
  elements.actionHint.textContent = adjusted
    ? `你选择了影院精修，本次会以 ${plan.output_resolution} 的安全档执行。`
    : "提交前会再次检查节点、模型、队列与显存档位。";
}

let planTimer;
function schedulePlan() {
  clearTimeout(planTimer);
  planTimer = setTimeout(requestPlan, 180);
}

async function requestPlan() {
  try {
    const { plan } = await post("/api/plan", currentConfig());
    renderPlan(plan);
  } catch (error) {
    showToast(error.message);
  }
}

async function refreshStatus({ announce = false } = {}) {
  setConnection(null);
  elements.refreshStatus.disabled = true;
  try {
    state.status = await api(`/api/status${announce ? "?refresh=1" : ""}`);
    setConnection(state.status);
    await requestPlan();
    if (announce) {
      showToast(state.status.comfy.online ? "ComfyUI 连接与本机资源已刷新" : "本机资源已读取，ComfyUI 当前未启动");
    }
  } catch (error) {
    elements.connectionButton.classList.remove("is-loading");
    elements.connectionButton.classList.add("is-offline");
    elements.connectionText.textContent = "本地桥接异常";
    showToast(error.message);
  } finally {
    elements.refreshStatus.disabled = false;
  }
}

function selectControl(container, value) {
  for (const button of container.querySelectorAll("button")) {
    const selected = button.dataset.value === String(value);
    button.classList.toggle("is-selected", selected);
    if (button.getAttribute("role") === "radio") {
      button.setAttribute("aria-checked", String(selected));
    }
  }
}

function validatePrompt() {
  const value = elements.prompt.value.trim();
  if (value.length < 12) {
    elements.promptError.textContent = "请至少用 12 个字符描述一个可执行场景。";
    elements.prompt.focus();
    return false;
  }
  elements.promptError.textContent = "";
  return true;
}

function setPrompt(text) {
  const existing = elements.prompt.value.trim();
  elements.prompt.value = existing ? `${existing}\n\n${text}` : text;
  elements.prompt.dispatchEvent(new Event("input"));
  elements.prompt.focus();
}

async function uploadReference(file) {
  if (!file) return;
  const allowed = ["image/jpeg", "image/png", "image/webp"];
  if (!allowed.includes(file.type)) {
    showToast("仅支持 JPG、PNG 或 WebP 参考图");
    return;
  }
  if (file.size > 12 * 1024 * 1024) {
    showToast("参考图必须小于 12MB");
    return;
  }

  state.referenceUploading = true;
  elements.generateButton.disabled = true;
  elements.exportButton.disabled = true;
  elements.uploadEmpty.hidden = true;
  elements.uploadPreview.hidden = false;
  elements.referenceName.textContent = file.name;
  elements.referenceMeta.textContent = "正在安全上传到本机 ComfyUI";
  const previewUrl = URL.createObjectURL(file);
  elements.referencePreview.src = previewUrl;

  try {
    const data = await new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => resolve(reader.result);
      reader.onerror = reject;
      reader.readAsDataURL(file);
    });
    const { reference } = await post("/api/upload", { filename: file.name, data });
    state.reference = reference;
    const sizeLabel = reference.bytes < 1024 * 1024
      ? `${Math.max(1, Math.round(reference.bytes / 1024))}KB`
      : `${(reference.bytes / 1024 / 1024).toFixed(1)}MB`;
    elements.referenceMeta.textContent = `${reference.width}×${reference.height} · ${sizeLabel} · 已就绪`;
    showToast(state.referenceMode === "identity"
      ? "参考图已就绪，将进入独立 Ref2VA 身份 / 风格工作流"
      : "参考图已就绪，将真实连接到 H3 首帧输入");
    await requestPlan();
  } catch (error) {
    state.reference = null;
    elements.uploadEmpty.hidden = false;
    elements.uploadPreview.hidden = true;
    elements.referenceInput.value = "";
    showToast(error.message);
  } finally {
    state.referenceUploading = false;
    URL.revokeObjectURL(previewUrl);
    if (state.plan) renderPlan(state.plan);
    elements.exportButton.disabled = state.busy;
  }
}

async function startComfy() {
  setBusy(true, "正在启动 ComfyUI");
  elements.connectionButton.classList.remove("is-offline", "is-online");
  elements.connectionButton.classList.add("is-loading");
  elements.connectionText.textContent = "正在启动 ComfyUI";
  const response = await post("/api/start", {});
  state.status = response.status;
  setConnection(state.status);
  await requestPlan();
  showToast("ComfyUI 已用稳定低内存参数启动");
}

async function generate() {
  if (!validatePrompt() || state.referenceUploading) return;
  try {
    const offline = !state.plan?.snapshot?.comfy?.online;
    if (offline) {
      await startComfy();
    }
    setBusy(true, "正在执行提交前检查");
    const payload = { ...currentConfig(), prompt: elements.prompt.value.trim() };
    const result = await post("/api/generate", payload);
    state.promptId = result.prompt_id;
    showJob(result);
    startJobPolling();
    await refreshStatus();
  } catch (error) {
    showToast(error.message);
  } finally {
    setBusy(false, state.plan ? `生成 ${state.plan.duration} 秒视频` : "生成视频");
  }
}

function showJob(result) {
  elements.jobPanel.hidden = false;
  document.body.style.overflow = "hidden";
  elements.jobTitle.textContent = "工作流已进入制作队列";
  elements.jobSummary.textContent = `系统将按 ${result.plan.segments} 个安全片段逐段生成，并交付 ${result.plan.output_resolution} 声画成片。关闭面板不会中断任务。`;
  elements.jobId.textContent = result.prompt_id;
  elements.jobState.textContent = "等待 ComfyUI 接管";
  elements.jobProgress.style.width = "12%";
  elements.jobResults.hidden = true;
  elements.jobResults.replaceChildren();
}

function closeJob() {
  elements.jobPanel.hidden = true;
  document.body.style.overflow = "";
}

function startJobPolling() {
  clearTimeout(state.pollTimer);
  pollJob();
}

async function pollJob() {
  if (!state.promptId) return;
  try {
    const result = await api(`/api/job/${encodeURIComponent(state.promptId)}`);
    if (result.state === "complete") {
      elements.jobTitle.textContent = "成片已经完成";
      elements.jobSummary.textContent = "ComfyUI 已完成声画输出。文件保存在本机输出目录，也可以从这里直接打开。";
      elements.jobState.textContent = "完成";
      elements.jobProgress.style.width = "100%";
      renderResults(result.files || []);
      showToast("视频生成完成");
      state.pollTimer = null;
      await refreshStatus();
      return;
    }
    if (result.state === "error") {
      elements.jobTitle.textContent = "工作流执行失败";
      elements.jobSummary.textContent = "ComfyUI 返回了错误状态。任务没有被伪装成完成；请查看错误记录后再决定是否重试。";
      elements.jobState.textContent = "失败";
      elements.jobProgress.style.width = "100%";
      showToast("ComfyUI 执行失败，详情已保留在运行记录中");
      state.pollTimer = null;
      await refreshStatus();
      return;
    }
    const running = result.queue?.queue_running?.length || 0;
    const pending = result.queue?.queue_pending?.length || 0;
    elements.jobState.textContent = running ? "正在生成安全片段" : pending ? "等待资源" : "正在整理输出";
    elements.jobProgress.style.width = running ? "58%" : pending ? "28%" : "76%";
  } catch (error) {
    elements.jobState.textContent = "暂时无法读取进度";
  }
  state.pollTimer = setTimeout(pollJob, 5000);
}

function renderResults(files) {
  elements.jobResults.replaceChildren();
  const relevant = files.filter((file) => ["videos", "video", "audio"].includes(file.kind));
  for (const file of relevant) {
    const link = document.createElement("a");
    link.href = file.url;
    link.target = "_blank";
    link.rel = "noopener";
    const label = document.createElement("span");
    label.textContent = file.kind === "audio" ? "打开无损母带" : "打开生成视频";
    const name = document.createElement("small");
    name.textContent = file.filename;
    link.append(label, name);
    elements.jobResults.append(link);
  }
  if (!relevant.length) {
    const note = document.createElement("p");
    note.textContent = "任务已完成，但 ComfyUI 没有返回可直接打开的媒体文件。";
    elements.jobResults.append(note);
  }
  elements.jobResults.hidden = false;
}

async function exportWorkflow() {
  if (!validatePrompt()) return;
  elements.exportButton.disabled = true;
  try {
    const payload = { ...currentConfig(), prompt: elements.prompt.value.trim() };
    const result = await post("/api/workflow", payload);
    const blob = new Blob([JSON.stringify(result.workflow, null, 2)], { type: "application/json" });
    const link = document.createElement("a");
    link.href = URL.createObjectURL(blob);
    link.download = `h3-flow-${result.plan.duration}s-${result.plan.quality_applied}.json`;
    document.body.append(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(link.href);
    showToast("工作流 JSON 已导出；未向 ComfyUI 排队");
  } catch (error) {
    showToast(error.message);
  } finally {
    elements.exportButton.disabled = false;
  }
}

function bindControls() {
  elements.prompt.addEventListener("input", () => {
    elements.promptCount.textContent = `${elements.prompt.value.length} / 12000`;
    if (elements.promptError.textContent && elements.prompt.value.trim().length >= 12) {
      elements.promptError.textContent = "";
    }
  });

  for (const button of $$('[data-template]')) {
    button.addEventListener("click", () => setPrompt(templates[button.dataset.template]));
  }

  elements.durationControl.addEventListener("click", (event) => {
    const button = event.target.closest("button[data-value]");
    if (!button) return;
    state.duration = Number(button.dataset.value);
    selectControl(elements.durationControl, state.duration);
    schedulePlan();
  });

  elements.aspectControl.addEventListener("click", (event) => {
    const button = event.target.closest("button[data-value]");
    if (!button) return;
    state.aspect = button.dataset.value;
    selectControl(elements.aspectControl, state.aspect);
    schedulePlan();
  });

  elements.qualityControl.addEventListener("click", (event) => {
    const button = event.target.closest("button[data-value]");
    if (!button) return;
    state.quality = button.dataset.value;
    selectControl(elements.qualityControl, state.quality);
    schedulePlan();
  });

  elements.referenceModeControl.addEventListener("click", (event) => {
    const button = event.target.closest("button[data-value]");
    if (!button) return;
    state.referenceMode = button.dataset.value;
    selectControl(elements.referenceModeControl, state.referenceMode);
    if (state.reference) {
      showToast(state.referenceMode === "identity"
        ? "已切换到 Ref2VA 身份 / 风格参考"
        : "已切换到首帧图生视频");
    }
    schedulePlan();
  });

  elements.seed.addEventListener("change", schedulePlan);
  elements.randomSeed.addEventListener("click", () => {
    const values = new Uint32Array(1);
    crypto.getRandomValues(values);
    elements.seed.value = values[0];
    schedulePlan();
  });

  elements.uploadButton.addEventListener("click", () => elements.referenceInput.click());
  elements.referenceInput.addEventListener("change", () => uploadReference(elements.referenceInput.files[0]));
  for (const eventName of ["dragenter", "dragover"]) {
    elements.uploadButton.addEventListener(eventName, (event) => {
      event.preventDefault();
      elements.uploadButton.classList.add("is-dragging");
    });
  }
  for (const eventName of ["dragleave", "drop"]) {
    elements.uploadButton.addEventListener(eventName, (event) => {
      event.preventDefault();
      elements.uploadButton.classList.remove("is-dragging");
    });
  }
  elements.uploadButton.addEventListener("drop", (event) => uploadReference(event.dataTransfer.files[0]));

  elements.refreshStatus.addEventListener("click", () => refreshStatus({ announce: true }));
  elements.connectionButton.addEventListener("click", async () => {
    if (state.status?.comfy?.online) {
      showToast("ComfyUI 已连接；本页会在提交前再次执行完整检查");
      return;
    }
    try {
      await startComfy();
    } catch (error) {
      showToast(error.message);
    } finally {
      setBusy(false, state.plan ? `生成 ${state.plan.duration} 秒视频` : "生成视频");
    }
  });
  elements.generateButton.addEventListener("click", generate);
  elements.exportButton.addEventListener("click", exportWorkflow);
  elements.closeJob.addEventListener("click", closeJob);
  elements.jobPanel.querySelector(".job-panel__backdrop").addEventListener("click", closeJob);
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && !elements.jobPanel.hidden) closeJob();
  });
}

bindControls();
refreshStatus();
