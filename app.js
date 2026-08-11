const state = {
  duration: 5,
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
  assistantStatus: null,
  assistantBusy: false,
  beatDrafts: {},
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
  shortform: `一个面向竖屏短视频的连续知识口播镜头。一位成年讲述者站在简洁、真实的室内空间，先以稳定中景看向镜头说明主题，再用自然手势强调一个关键观点；摄影机只做轻微缓慢推近，人物身份、服装、视线和光线保持一致，不出现字幕、标志或水印。

overall_soundscape：清晰的人声、轻微室内空间感和自然衣料摩擦声。
non_diegetic_music：N/A。`,
};

const $ = (selector) => document.querySelector(selector);
const $$ = (selector) => [...document.querySelectorAll(selector)];

const elements = {
  form: $("#flowForm"),
  prompt: $("#prompt"),
  promptCount: $("#promptCount"),
  draftState: $("#draftState"),
  newDraftButton: $("#newDraftButton"),
  briefScore: $("#briefScore"),
  briefGuidance: $("#briefGuidance"),
  briefChecks: $("#briefChecks"),
  promptError: $("#promptError"),
  timelineHint: $("#timelineHint"),
  promptAssistantOpen: $("#promptAssistantOpen"),
  promptAssistantDialog: $("#promptAssistantDialog"),
  promptAssistantClose: $("#promptAssistantClose"),
  promptAssistantCancel: $("#promptAssistantCancel"),
  promptAssistantGenerate: $("#promptAssistantGenerate"),
  promptAssistantGenerateText: $("#promptAssistantGenerateText"),
  assistantContext: $("#assistantContext"),
  assistantBriefPreview: $("#assistantBriefPreview"),
  assistantEnvironmentState: $("#assistantEnvironmentState"),
  assistantProviderSwitch: $("#assistantProviderSwitch"),
  assistantBaseUrl: $("#assistantBaseUrl"),
  assistantModel: $("#assistantModel"),
  assistantApiKey: $("#assistantApiKey"),
  assistantKeyState: $("#assistantKeyState"),
  assistantError: $("#assistantError"),
  assistantGuideState: $("#assistantGuideState"),
  referenceInput: $("#referenceInput"),
  uploadButton: $("#uploadButton"),
  uploadEmpty: $("#uploadEmpty"),
  uploadPreview: $("#uploadPreview"),
  referencePreview: $("#referencePreview"),
  referenceName: $("#referenceName"),
  referenceMeta: $("#referenceMeta"),
  referenceModeControl: $("#referenceModeControl"),
  durationControl: $("#durationControl"),
  beatBuilder: $("#beatBuilder"),
  beatProgress: $("#beatProgress"),
  continuityBrief: $("#continuityBrief"),
  beatRows: $("#beatRows"),
  beatBuilderHint: $("#beatBuilderHint"),
  applyBeats: $("#applyBeats"),
  aspectControl: $("#aspectControl"),
  formatNote: $("#formatNote"),
  qualityControl: $("#qualityControl"),
  seed: $("#seed"),
  randomSeed: $("#randomSeed"),
  connectionButton: $("#connectionButton"),
  connectionDot: $("#connectionDot"),
  connectionText: $("#connectionText"),
  safetyState: $("#safetyState"),
  studioSteps: $("#studioSteps"),
  planPanel: $("#planPanel"),
  preflightLabel: $("#preflightLabel"),
  preflightDetail: $("#preflightDetail"),
  fixPlanButton: $("#fixPlanButton"),
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
  technicalPlan: $("#technicalPlan"),
  technicalState: $("#technicalState"),
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
  mobileReviewDock: $("#mobileReviewDock"),
  mobileReviewState: $("#mobileReviewState"),
  mobileReviewButton: $("#mobileReviewButton"),
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

const DRAFT_KEY = "h3-flow:creator-draft:v1";
const briefSignals = {
  action: /走|拿|打开|关闭|转身|看向|移动|展开|奔跑|说|讲述|触碰|升起|倒入|展示|进入|离开|表演|坐下|站起|旋转|举起|落下|穿过|靠近|推开|拉开|伸手|挥手|微笑|哭泣|跳舞/,
  camera: /镜头|摄影机|机位|推近|推进|拉远|后退|环绕|跟随|中景|近景|远景|特写|航拍|手持|固定|摇摄|俯拍|仰拍|低机位|高机位|景深/,
  sound: /声音|声场|环境音|环境声|对白|旁白|配乐|音乐|安静|静音|雨声|脚步|风声|车流|鸟鸣|衣料|人声|音效|overall_soundscape|non_diegetic_music/i,
};

let draftTimer;
function updateDraftState(savedAt = null, restored = false) {
  if (!elements.draftState) return;
  if (!savedAt) {
    elements.draftState.textContent = "仅保存在本机";
    return;
  }
  const stamp = new Date(savedAt);
  const time = Number.isNaN(stamp.getTime())
    ? "刚刚"
    : stamp.toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit" });
  elements.draftState.textContent = restored ? `已恢复本机草稿 · ${time}` : `已自动保存 · ${time}`;
}

function persistDraft() {
  const updatedAt = new Date().toISOString();
  try {
    localStorage.setItem(DRAFT_KEY, JSON.stringify({
      prompt: elements.prompt.value,
      duration: state.duration,
      aspect: state.aspect,
      quality: state.quality,
      referenceMode: state.referenceMode,
      seed: elements.seed.value,
      continuityBrief: elements.continuityBrief.value,
      beatDrafts: state.beatDrafts,
      updatedAt,
    }));
    updateDraftState(updatedAt);
  } catch {
    elements.draftState.textContent = "本机草稿不可用";
  }
}

function queueDraftSave() {
  clearTimeout(draftTimer);
  draftTimer = setTimeout(persistDraft, 320);
}

function restoreDraft() {
  let draft;
  try {
    draft = JSON.parse(localStorage.getItem(DRAFT_KEY) || "null");
  } catch {
    draft = null;
  }
  if (!draft || typeof draft !== "object") {
    updateDraftState();
    return;
  }
  if (typeof draft.prompt === "string") elements.prompt.value = draft.prompt.slice(0, 12000);
  if ([5, 10, 15, 30].includes(Number(draft.duration))) state.duration = Number(draft.duration);
  if (["16:9", "9:16", "1:1"].includes(draft.aspect)) state.aspect = draft.aspect;
  if (["draft", "balanced", "studio"].includes(draft.quality)) state.quality = draft.quality;
  if (["first_frame", "identity"].includes(draft.referenceMode)) state.referenceMode = draft.referenceMode;
  if (typeof draft.seed === "string") elements.seed.value = draft.seed;
  if (typeof draft.continuityBrief === "string") elements.continuityBrief.value = draft.continuityBrief.slice(0, 1200);
  if (draft.beatDrafts && typeof draft.beatDrafts === "object") {
    state.beatDrafts = Object.fromEntries(
      Object.entries(draft.beatDrafts)
        .filter(([key, value]) => ["10", "15", "30"].includes(key) && Array.isArray(value))
        .map(([key, value]) => [key, value.map((beat) => String(beat || "").slice(0, 1800))]),
    );
  }
  selectControl(elements.durationControl, state.duration);
  selectControl(elements.aspectControl, state.aspect);
  selectControl(elements.qualityControl, state.quality);
  selectControl(elements.referenceModeControl, state.referenceMode);
  updateDraftState(draft.updatedAt, true);
}

function resetCreatorDraft() {
  if (elements.prompt.value.trim() && !window.confirm("新建创作会清空当前文字、分镜和参数。参考图不会从 ComfyUI input 目录删除。继续吗？")) {
    return;
  }
  try {
    localStorage.removeItem(DRAFT_KEY);
  } catch {
    // A blocked storage backend should not prevent a new local draft.
  }
  state.duration = 5;
  state.aspect = "16:9";
  state.quality = "balanced";
  state.referenceMode = "first_frame";
  state.reference = null;
  state.beatDrafts = {};
  elements.prompt.value = "";
  elements.seed.value = "";
  elements.continuityBrief.value = "";
  elements.referenceInput.value = "";
  elements.referencePreview.removeAttribute("src");
  elements.uploadEmpty.hidden = false;
  elements.uploadPreview.hidden = true;
  selectControl(elements.durationControl, state.duration);
  selectControl(elements.aspectControl, state.aspect);
  selectControl(elements.qualityControl, state.quality);
  selectControl(elements.referenceModeControl, state.referenceMode);
  renderBeatBuilder();
  updateFormatNote();
  updateDraftState();
  elements.prompt.dispatchEvent(new Event("input", { bubbles: true }));
  showToast("新的本机创作已建立；旧参考图文件没有被自动删除");
}

function analyzeBrief(text) {
  const value = text.trim();
  return {
    subject: value.length >= 12,
    action: briefSignals.action.test(value),
    camera: briefSignals.camera.test(value),
    sound: briefSignals.sound.test(value),
  };
}

function updateBriefHealth() {
  const checks = analyzeBrief(elements.prompt.value);
  const labels = {
    subject: "先写清画面里的核心人物、产品或场景",
    action: "补充主体在镜头里发生的明确动作",
    camera: "补充景别、机位或摄影机运动",
    sound: "补充环境声、对白或是否需要配乐",
  };
  let completed = 0;
  for (const item of elements.briefChecks.querySelectorAll("[data-brief-check]")) {
    const key = item.dataset.briefCheck;
    const ready = Boolean(checks[key]);
    item.classList.toggle("is-complete", ready);
    completed += ready ? 1 : 0;
  }
  elements.briefScore.textContent = `${completed} / 4`;
  const next = Object.keys(checks).find((key) => !checks[key]);
  elements.briefGuidance.textContent = next ? labels[next] : "主体、动作、镜头与声音已经齐全";
  elements.briefScore.classList.toggle("is-complete", completed === 4);
}

function parseBeatLines(text) {
  const beats = new Map();
  const pattern = /(\d+(?:\.\d+)?)\s*(?:-|–|—|至|到)\s*(\d+(?:\.\d+)?)\s*(?:秒|s)?\s*[：:]\s*([^\n]+)/gi;
  let match;
  while ((match = pattern.exec(text)) !== null) {
    beats.set(`${Number(match[1])}-${Number(match[2])}`, match[3].trim());
  }
  return beats;
}

function expectedBeatCount() {
  return Math.max(1, Math.ceil(state.duration / 5));
}

function promptContainsAllBeats(text = elements.prompt.value) {
  if (state.duration <= 5) return true;
  const parsed = parseBeatLines(text);
  return Array.from({ length: expectedBeatCount() }, (_, index) => parsed.has(`${index * 5}-${(index + 1) * 5}`)).every(Boolean);
}

function beatDraftForCurrentDuration() {
  const key = String(state.duration);
  const count = expectedBeatCount();
  if (!Array.isArray(state.beatDrafts[key]) || state.beatDrafts[key].length !== count) {
    const parsed = parseBeatLines(elements.prompt.value);
    const next = Array.from({ length: count }, (_, index) => parsed.get(`${index * 5}-${(index + 1) * 5}`) || "");
    if (!next.some(Boolean) && elements.prompt.value.trim()) next[0] = elements.prompt.value.trim();
    state.beatDrafts[key] = next;
  }
  return state.beatDrafts[key];
}

function updateBeatProgress() {
  if (state.duration <= 5) return;
  const draft = beatDraftForCurrentDuration();
  const completed = draft.filter((beat) => beat.trim().length >= 6).length;
  elements.beatProgress.textContent = `${completed} / ${draft.length} 段`;
  elements.applyBeats.disabled = completed !== draft.length;
  elements.beatBuilderHint.textContent = completed === draft.length
    ? "所有片段已写清，可以整理为长视频简报。"
    : `还差 ${draft.length - completed} 段；每段至少写一个新动作或场景变化。`;
}

function renderBeatBuilder() {
  elements.beatBuilder.hidden = state.duration <= 5;
  if (state.duration <= 5) {
    updateStudioProgress();
    return;
  }
  const draft = beatDraftForCurrentDuration();
  elements.beatRows.replaceChildren();
  draft.forEach((value, index) => {
    const start = index * 5;
    const end = (index + 1) * 5;
    const row = document.createElement("label");
    row.className = "beat-row";
    row.htmlFor = `beat-${start}-${end}`;
    const timing = document.createElement("span");
    timing.className = "beat-row__time";
    timing.innerHTML = `<strong>${String(index + 1).padStart(2, "0")}</strong><span>${start}–${end} 秒</span>`;
    const textarea = document.createElement("textarea");
    textarea.id = `beat-${start}-${end}`;
    textarea.rows = 2;
    textarea.maxLength = 1800;
    textarea.value = value;
    textarea.placeholder = index === 0
      ? "这一段如何开场？主体在哪里，先做什么？"
      : "承接上一段后，这 5 秒发生什么新的动作或场景变化？";
    textarea.addEventListener("input", () => {
      draft[index] = textarea.value;
      updateBeatProgress();
      updateStudioProgress();
      queueDraftSave();
    });
    row.append(timing, textarea);
    elements.beatRows.append(row);
  });
  updateBeatProgress();
}

function applyBeatDraft() {
  const draft = beatDraftForCurrentDuration();
  const firstMissing = draft.findIndex((beat) => beat.trim().length < 6);
  if (firstMissing >= 0) {
    elements.beatRows.querySelectorAll("textarea")[firstMissing]?.focus();
    showToast(`请先补完第 ${firstMissing + 1} 段剧情`);
    return;
  }
  if (/integrated_multimodal_description\s*:/i.test(elements.prompt.value)) {
    showToast("当前已是官方结构，请在提示词编导中重新生成，避免破坏字段顺序");
    openPromptAssistant();
    return;
  }
  const continuity = elements.continuityBrief.value.trim();
  const lines = draft.map((beat, index) => `${index * 5}-${(index + 1) * 5}秒：${beat.trim()}`);
  elements.prompt.value = [continuity ? `全片连续要求：${continuity}` : "", ...lines].filter(Boolean).join("\n");
  elements.prompt.dispatchEvent(new Event("input", { bubbles: true }));
  showToast("长视频分镜已写入主提示词，正在重新执行生成前总检");
}

function updateFormatNote() {
  const copy = {
    "16:9": "横屏 16:9 · 适合叙事短片、展示页与大屏观看",
    "9:16": "竖屏 9:16 · 适合短视频信息流与移动端全屏观看",
    "1:1": "方形 1:1 · 适合商品展示、社交信息流与多平台裁切",
  };
  elements.formatNote.textContent = copy[state.aspect];
}

function scrollToTarget(id) {
  const target = document.getElementById(id);
  if (!target) return;
  target.scrollIntoView({ behavior: "smooth", block: "start" });
  const focusable = target.querySelector("textarea, button, input, summary");
  if (focusable) setTimeout(() => focusable.focus({ preventScroll: true }), 360);
}

function updateStudioProgress() {
  if (!elements.studioSteps) return;
  const status = {
    sceneSection: elements.prompt.value.trim().length >= 12,
    formatSection: state.duration <= 5 || promptContainsAllBeats(),
    qualitySection: Boolean(state.quality),
    planPanel: Boolean(state.plan?.ready && elements.prompt.value.trim().length >= 12 && promptContainsAllBeats()),
  };
  let currentAssigned = false;
  for (const button of elements.studioSteps.querySelectorAll("button[data-scroll-target]")) {
    const complete = status[button.dataset.scrollTarget];
    button.classList.toggle("is-complete", complete);
    button.removeAttribute("aria-current");
    if (!currentAssigned && !complete) {
      button.setAttribute("aria-current", "step");
      currentAssigned = true;
    }
  }
  if (!currentAssigned) {
    elements.studioSteps.querySelector('[data-scroll-target="planPanel"]')?.setAttribute("aria-current", "step");
  }
}

function jumpToFirstBlocker() {
  if (elements.prompt.value.trim().length < 12) {
    scrollToTarget("sceneSection");
    return;
  }
  if (state.duration > 5 && !promptContainsAllBeats()) {
    scrollToTarget("formatSection");
    const firstEmpty = [...elements.beatRows.querySelectorAll("textarea")]
      .find((textarea) => textarea.value.trim().length < 6);
    if (firstEmpty) setTimeout(() => firstEmpty.focus({ preventScroll: true }), 380);
    return;
  }
  if ((state.plan?.blockers || []).some((blocker) => /参考图|Ref2VA|首帧/.test(blocker))) {
    scrollToTarget("sceneSection");
    return;
  }
  elements.technicalPlan.open = true;
  scrollToTarget("planPanel");
}

function setupPlanObserver() {
  if (!("IntersectionObserver" in window)) return;
  const observer = new IntersectionObserver(([entry]) => {
    elements.mobileReviewDock.classList.toggle("is-hidden", entry.isIntersecting);
  }, { threshold: 0.18 });
  observer.observe(elements.planPanel);
}

function currentConfig() {
  return {
    duration: state.duration,
    aspect: state.aspect,
    quality: state.quality,
    reference: state.reference?.token || null,
    reference_mode: state.referenceMode,
    seed: elements.seed.value || null,
    prompt: elements.prompt.value.trim(),
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
  const creatorReady = elements.prompt.value.trim().length >= 12 && promptContainsAllBeats();
  const offlineOnly = state.plan?.blockers?.length === 1 && state.plan.blockers[0] === "ComfyUI 尚未启动";
  const executable = Boolean(state.plan && (state.plan.ready || offlineOnly));
  elements.generateButton.disabled = busy || state.referenceUploading || !creatorReady || !executable;
  elements.exportButton.disabled = busy || state.referenceUploading || !creatorReady;
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
  elements.technicalState.textContent = compatibility.status === "blocked"
    ? "需要处理"
    : compatibility.status === "compatible"
      ? "可用 · 有版本差异"
      : "环境已就绪";
  if (compatibility.status === "blocked") elements.technicalPlan.open = true;
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
  elements.timelineHint.hidden = plan.duration <= 5;
  elements.timelineHint.textContent = plan.duration <= 5
    ? ""
    : `长视频请按每 5 秒写完整时间段，例如 0-5秒、5-10秒，直到 ${plan.duration} 秒。系统会把每段剧情隔离后再续接。`;
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

  const creatorBlockers = [];
  if (elements.prompt.value.trim().length < 12) {
    creatorBlockers.push("创意简报：请至少用 12 个字符写清一个可执行场景。");
  }
  if (state.duration > 5 && !promptContainsAllBeats()) {
    creatorBlockers.push(`分镜节拍：请补完 ${expectedBeatCount()} 个 5 秒片段并写入主提示词。`);
  }
  const visibleBlockers = [...creatorBlockers, ...(plan.blockers || [])];
  elements.blockerList.replaceChildren();
  for (const blocker of visibleBlockers) {
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
  const overallReady = plan.ready && creatorBlockers.length === 0;
  const canAutoStart = offlineOnly && creatorBlockers.length === 0;
  const adjusted = plan.quality_requested !== plan.quality_applied;
  elements.safetyState.className = "safety-state";
  if (overallReady) {
    elements.safetyState.classList.add(adjusted ? "is-adjusted" : "is-ready");
    elements.safetyState.lastChild.textContent = adjusted ? "已自动优化" : "安全可执行";
  } else if (canAutoStart) {
    elements.safetyState.classList.add("is-adjusted");
    elements.safetyState.lastChild.textContent = "提交时自动启动";
  } else {
    elements.safetyState.classList.add("is-blocked");
    elements.safetyState.lastChild.textContent = "需要处理";
  }

  const creatorFixNeeded = creatorBlockers.length > 0
    || (plan.blockers || []).some((blocker) => /参考图|Ref2VA|首帧|剧情时间线/.test(blocker));
  if (overallReady) {
    elements.preflightLabel.textContent = adjusted ? "已按本机能力优化，可以生成" : "创意与环境已就绪，可以生成";
    elements.preflightDetail.textContent = `${plan.segments} 个安全片段 · ${plan.output_resolution} · ${plan.workflow_mode}`;
  } else if (canAutoStart) {
    elements.preflightLabel.textContent = "创意已就绪，提交时启动 ComfyUI";
    elements.preflightDetail.textContent = "系统会先使用稳定低内存参数启动本机服务，再执行完整门禁。";
  } else {
    const count = visibleBlockers.length || 1;
    elements.preflightLabel.textContent = `${count} 项尚未通过`;
    elements.preflightDetail.textContent = visibleBlockers[0] || "请检查当前创意与本机环境。";
  }
  elements.fixPlanButton.hidden = !creatorFixNeeded;
  elements.mobileReviewState.textContent = overallReady
    ? "可以生成"
    : canAutoStart
      ? "提交时启动"
      : `${visibleBlockers.length || 1} 项待处理`;

  if (!state.busy) {
    elements.generateButton.disabled = state.referenceUploading || (!overallReady && !canAutoStart);
    elements.generateText.textContent = canAutoStart ? "启动并生成" : `生成 ${plan.duration} 秒视频`;
    elements.exportButton.disabled = state.referenceUploading || creatorBlockers.length > 0;
  }
  elements.actionHint.textContent = adjusted
    ? `你选择了影院精修，本次会以 ${plan.output_resolution} 的安全档执行。`
    : "提交前会再次检查节点、模型、队列与显存档位。";
  updateStudioProgress();
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

function effectiveReferenceMode() {
  if (!state.reference) return "none";
  return state.referenceMode;
}

function assistantModeLabel() {
  const mode = effectiveReferenceMode();
  if (mode === "identity") return "Ref2VA 身份 / 风格参考";
  if (mode === "first_frame") return "I2VA 首帧图生视频";
  return "T2VA 文生视频";
}

function setAssistantProvider(provider) {
  for (const button of elements.assistantProviderSwitch.querySelectorAll("button[data-provider]")) {
    const selected = button.dataset.provider === provider;
    button.classList.toggle("is-selected", selected);
    button.setAttribute("aria-pressed", String(selected));
  }
  if (provider === "deepseek") {
    elements.assistantBaseUrl.value = "https://api.deepseek.com";
    elements.assistantModel.value = "deepseek-v4-flash";
  }
}

async function refreshPromptAssistantStatus() {
  try {
    state.assistantStatus = await api("/api/prompt-assistant");
    elements.assistantBaseUrl.value = state.assistantStatus.default_base_url;
    elements.assistantModel.value = state.assistantStatus.default_model;
    const isDeepSeek = state.assistantStatus.provider === "DeepSeek";
    setAssistantProvider(isDeepSeek ? "deepseek" : "custom");
    elements.assistantBaseUrl.value = state.assistantStatus.default_base_url;
    elements.assistantModel.value = state.assistantStatus.default_model;
    elements.assistantEnvironmentState.textContent = state.assistantStatus.environment_configured
      ? `${state.assistantStatus.provider} 已由启动环境配置`
      : "Key 由你填写，也可以改用其他兼容服务";
    elements.assistantKeyState.textContent = state.assistantStatus.environment_configured
      ? "启动环境已配置"
      : "仅保留到关闭页面";
    elements.assistantApiKey.placeholder = state.assistantStatus.environment_configured
      ? "留空即可使用启动环境中的 Key"
      : "由你自行填写，不写入项目";
    elements.assistantGuideState.textContent = `MiniMax H3 官方指引 · ${state.assistantStatus.guide_revision.slice(0, 8)}`;
  } catch (error) {
    elements.assistantEnvironmentState.textContent = "本地提示词编导状态读取失败";
    elements.assistantError.textContent = error.message;
  }
}

function openPromptAssistant() {
  const brief = elements.prompt.value.trim();
  elements.assistantContext.textContent = `${state.duration} 秒 · ${state.aspect} · ${assistantModeLabel()}`;
  elements.assistantBriefPreview.textContent = brief || "请先在主编辑器里写下画面创意。";
  elements.assistantBriefPreview.classList.toggle("is-empty", !brief);
  elements.assistantError.textContent = "";
  elements.promptAssistantGenerate.disabled = brief.length < 12;
  elements.promptAssistantDialog.showModal();
  document.body.style.overflow = "hidden";
  if (!state.assistantStatus) refreshPromptAssistantStatus();
}

function closePromptAssistant() {
  if (elements.promptAssistantDialog.open) elements.promptAssistantDialog.close();
  document.body.style.overflow = "";
  elements.assistantError.textContent = "";
}

function setAssistantBusy(busy) {
  state.assistantBusy = busy;
  elements.promptAssistantGenerate.disabled = busy;
  elements.promptAssistantClose.disabled = busy;
  elements.promptAssistantCancel.disabled = busy;
  elements.promptAssistantGenerate.classList.toggle("is-loading", busy);
  elements.promptAssistantGenerateText.textContent = busy ? "正在编排镜头与声轨" : "生成官方格式提示词";
}

async function generateOfficialPrompt() {
  const brief = elements.prompt.value.trim();
  if (brief.length < 12) {
    elements.assistantError.textContent = "请先在主编辑器里写至少 12 个字符的创意描述。";
    return;
  }
  const baseUrl = elements.assistantBaseUrl.value.trim();
  const model = elements.assistantModel.value.trim();
  let providerUrl;
  try {
    providerUrl = new URL(baseUrl);
  } catch {
    elements.assistantError.textContent = "请填写有效的模型服务地址。";
    return;
  }
  const loopbackHosts = new Set(["127.0.0.1", "localhost", "[::1]"]);
  const isLoopback = loopbackHosts.has(providerUrl.hostname);
  if (providerUrl.protocol === "http:" && !isLoopback) {
    elements.assistantError.textContent = "远程模型服务必须使用 HTTPS；HTTP 仅允许本机地址。";
    return;
  }
  if (!model) {
    elements.assistantError.textContent = "请填写模型名称。";
    return;
  }
  if (!elements.assistantApiKey.value.trim() && !state.assistantStatus?.environment_configured && !isLoopback) {
    elements.assistantError.textContent = "远程模型服务需要 API Key；Key 仅用于本次请求，不会写入项目。";
    return;
  }
  elements.assistantError.textContent = "";
  setAssistantBusy(true);
  try {
    const result = await post("/api/prompt-assistant", {
      brief,
      duration: state.duration,
      aspect: state.aspect,
      reference_mode: effectiveReferenceMode(),
      api_config: {
        base_url: baseUrl,
        model,
        api_key: elements.assistantApiKey.value.trim(),
      },
    });
    elements.prompt.value = result.prompt;
    elements.prompt.dispatchEvent(new Event("input", { bubbles: true }));
    closePromptAssistant();
    const tokens = result.usage?.total_tokens ? ` · ${result.usage.total_tokens} tokens` : "";
    showToast(`${result.provider} 已按 H3 官方结构完成改写${tokens}`);
  } catch (error) {
    elements.assistantError.textContent = error.message;
  } finally {
    setAssistantBusy(false);
  }
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
    updateBriefHealth();
    updateBeatProgress();
    updateStudioProgress();
    queueDraftSave();
    schedulePlan();
  });

  for (const button of $$('[data-template]')) {
    button.addEventListener("click", () => setPrompt(templates[button.dataset.template]));
  }
  elements.newDraftButton.addEventListener("click", resetCreatorDraft);

  elements.promptAssistantOpen.addEventListener("click", openPromptAssistant);
  elements.promptAssistantClose.addEventListener("click", closePromptAssistant);
  elements.promptAssistantCancel.addEventListener("click", closePromptAssistant);
  elements.promptAssistantGenerate.addEventListener("click", generateOfficialPrompt);
  elements.promptAssistantDialog.addEventListener("cancel", (event) => {
    if (state.assistantBusy) {
      event.preventDefault();
      return;
    }
    closePromptAssistant();
  });
  elements.assistantProviderSwitch.addEventListener("click", (event) => {
    const button = event.target.closest("button[data-provider]");
    if (!button) return;
    setAssistantProvider(button.dataset.provider);
    if (button.dataset.provider === "custom") {
      elements.assistantBaseUrl.focus();
      elements.assistantBaseUrl.select();
    }
  });

  elements.durationControl.addEventListener("click", (event) => {
    const button = event.target.closest("button[data-value]");
    if (!button) return;
    state.duration = Number(button.dataset.value);
    selectControl(elements.durationControl, state.duration);
    renderBeatBuilder();
    updateStudioProgress();
    queueDraftSave();
    schedulePlan();
  });

  elements.aspectControl.addEventListener("click", (event) => {
    const button = event.target.closest("button[data-value]");
    if (!button) return;
    state.aspect = button.dataset.value;
    selectControl(elements.aspectControl, state.aspect);
    updateFormatNote();
    queueDraftSave();
    schedulePlan();
  });

  elements.qualityControl.addEventListener("click", (event) => {
    const button = event.target.closest("button[data-value]");
    if (!button) return;
    state.quality = button.dataset.value;
    selectControl(elements.qualityControl, state.quality);
    updateStudioProgress();
    queueDraftSave();
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
    queueDraftSave();
    schedulePlan();
  });

  elements.seed.addEventListener("change", () => {
    queueDraftSave();
    schedulePlan();
  });
  elements.randomSeed.addEventListener("click", () => {
    const values = new Uint32Array(1);
    crypto.getRandomValues(values);
    elements.seed.value = values[0];
    queueDraftSave();
    schedulePlan();
  });

  elements.continuityBrief.addEventListener("input", queueDraftSave);
  elements.applyBeats.addEventListener("click", applyBeatDraft);
  elements.studioSteps.addEventListener("click", (event) => {
    const button = event.target.closest("button[data-scroll-target]");
    if (button) scrollToTarget(button.dataset.scrollTarget);
  });
  elements.fixPlanButton.addEventListener("click", jumpToFirstBlocker);
  elements.mobileReviewButton.addEventListener("click", () => scrollToTarget("planPanel"));

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
restoreDraft();
elements.promptCount.textContent = `${elements.prompt.value.length} / 12000`;
updateBriefHealth();
renderBeatBuilder();
updateFormatNote();
updateStudioProgress();
setupPlanObserver();
refreshStatus();
refreshPromptAssistantStatus();
