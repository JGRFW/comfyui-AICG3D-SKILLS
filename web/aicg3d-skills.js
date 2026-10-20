import { app } from "../../scripts/app.js";
import { api } from "../../scripts/api.js";

const styleHref = new URL("./aicg3d-skills.css", import.meta.url).href;
if (!document.querySelector(`link[data-aicg3d-skills-style="1"]`)) {
    const style = document.createElement("link");
    style.rel = "stylesheet";
    style.href = styleHref;
    style.dataset.aicg3dSkillsStyle = "1";
    document.head.append(style);
}

const SETTINGS_NODE = "AICG3D_SKILLS_Settings";
const EXPANDER_NODE = "AICG3D_SKILLS_PromptExpander";
const SKILL_MANAGER_NODE = "AICG3D_SKILLS_SkillManager";
const QUICK_TASK_WIDGET = "反推快捷任务";
const QUICK_TASK_UI_WIDGET = "快捷任务";
const QUICK_TASKS = ["普通创作", "图片反推提示词", "视频反推提示词"];
const QUICK_TASK_SKILL_IDS = {
    "图片反推提示词": "image-prompt-reverse",
    "视频反推提示词": "video-prompt-reverse",
};
const QUICK_TASK_PROMPTS = {
    "图片反推提示词": "分析 <Picture 1>，只生成一段可直接复制粘贴的图片生成提示词。",
    "视频反推提示词": "分析 <Video 1> 的镜头、动作、连续性和声音，只输出 MiniMax H3 Ref2VA 六段式正文。",
};
const QUICK_TASK_HIDDEN_FIELDS = [
    "任务模式",
    "输出画幅",
    "视频时长",
    "动作强度",
    "技能重点",
    "技能包",
    "无模型时生成模板",
];
const H3_STANDARD_MODE = "H3 六段式标准提示词";
const T2I_MODE = "文生图（T2I）";
const FL2I_MODE = "首尾帧生图（FL2I）";
const TASK_MODE_SKILL_IDS = {
    [H3_STANDARD_MODE]: "h3-six-segment-standard",
    [T2I_MODE]: "text-to-image-prompt",
    [FL2I_MODE]: "first-last-frame-image-prompt",
};
const TASK_MODE_PROMPTS = {
    [T2I_MODE]: "生成一幅主体明确、构图完整、光线清晰的图片。",
    [FL2I_MODE]: "以 <Picture 1> 为首帧、<Picture 2> 为尾帧，生成连续的首尾帧生图提示词。",
};
const API_BASE = "/aicg3d-skills/api";
const PROVIDERS = {
    runninghub: ["RunningHub", "https://www.runninghub.cn/openapi/v2", "openai/gpt-5.6-sol", "runninghub"],
    openai: ["OpenAI", "https://api.openai.com/v1", "gpt-4.1-mini", "openai"],
    gemini: ["Gemini", "https://generativelanguage.googleapis.com/v1beta", "gemini-2.5-flash", "gemini"],
    openrouter: ["OpenRouter", "https://openrouter.ai/api/v1", "google/gemini-2.5-flash", "openai"],
    dashscope: ["阿里云百炼", "https://dashscope.aliyuncs.com/compatible-mode/v1", "qwen-vl-max", "openai"],
    siliconflow: ["硅基流动", "https://api.siliconflow.cn/v1", "Qwen/Qwen2.5-VL-72B-Instruct", "openai"],
};

let activeDialog = null;
const skillPreviewCache = new Map();
let skillHoverPreview = null;
let skillHoverTimer = null;
let configCache = null;
let skillItemsCache = [];

function nodeClass(node) {
    return String(node?.comfyClass || node?.type || "");
}

function setWidget(node, names, value) {
    const list = node?.widgets || [];
    const widget = list.find((item) => names.includes(String(item?.name || "")));
    if (!widget) return;
    widget.value = value;
    if (typeof widget.callback === "function") {
        try {
            widget.callback(value, app.canvas, node, [0, 0], null);
        } catch {
            // Widget callbacks are optional and may be owned by another extension.
        }
    }
}

function field(label, control, hint = "") {
    const row = document.createElement("label");
    row.className = "aicg3d-skills-field";
    const title = document.createElement("span");
    title.className = "aicg3d-skills-field-label";
    title.textContent = label;
    row.append(title, control);
    if (hint) {
        const note = document.createElement("small");
        note.className = "aicg3d-skills-field-note";
        note.textContent = hint;
        row.append(note);
    }
    return row;
}

function textInput(value = "", type = "text") {
    const input = document.createElement("input");
    input.className = "aicg3d-skills-control";
    input.type = type;
    input.value = value || "";
    input.autocomplete = "off";
    input.spellcheck = false;
    return input;
}

function selectInput(options, value) {
    const select = document.createElement("select");
    select.className = "aicg3d-skills-control";
    const normalized = Array.isArray(options)
        ? options.map((item) => (typeof item === "string" ? [item, item] : item))
        : Object.entries(options || {});
    for (const [key, label] of normalized) {
        const option = document.createElement("option");
        option.value = String(key);
        option.textContent = String(label);
        select.append(option);
    }
    select.value = String(value ?? "");
    return select;
}

function toggleInput(value) {
    const wrapper = document.createElement("span");
    wrapper.className = "aicg3d-skills-switch";
    const input = document.createElement("input");
    input.type = "checkbox";
    input.checked = Boolean(value);
    const track = document.createElement("span");
    track.className = "aicg3d-skills-switch-track";
    wrapper.append(input, track);
    return { wrapper, input };
}

function errorBox() {
    const node = document.createElement("div");
    node.className = "aicg3d-skills-error";
    node.hidden = true;
    return node;
}

async function fetchJson(url, options = {}) {
    const response = await api.fetchApi(url, options);
    const text = await response.text();
    let payload = {};
    try {
        payload = text ? JSON.parse(text) : {};
    } catch {
        payload = { error: text };
    }
    if (!response.ok) {
        throw new Error(payload.error || `${response.status} ${response.statusText}`);
    }
    return payload;
}

function closeSettings() {
    document.body.classList.remove("aicg3d-skills-settings-open");
    if (!activeDialog) return;
    activeDialog.overlay.remove();
    activeDialog = null;
}

function syncSettingsFieldLayout(form) {
    const local = form.mode.value === "local";
    const fields = [
        [form.modeField, 1, 1],
        [form.deviceField, 1, 2],
        [form.localModelField, 2, 1],
        [form.languageField, 2, 2],
        [form.mmprojField, 3, 1],
        [form.readMediaField, 3, 2],
        [form.unloadField, 4, 2],
        [form.localHintField, 5, "1 / -1"],
    ];
    for (const [element, row, column] of fields) {
        if (!element?.style) continue;
        element.style.gridRow = local ? String(row) : "";
        element.style.gridColumn = local ? String(column) : "";
    }
}


function syncVisibility(form) {
    const isLocal = form.mode.value === "local";
    form.onlineRows.forEach((row) => {
        row.hidden = isLocal;
        row.style.display = isLocal ? "none" : "";
    });
    form.localRows.forEach((row) => {
        row.hidden = !isLocal;
        row.style.display = !isLocal ? "none" : "";
    });
    form.protocol.value = PROVIDERS[form.provider.value]?.[3] || "openai";
    syncSettingsFieldLayout(form);
}

async function hydrateLocalModels(config) {
    const payload = await fetchJson(`${API_BASE}/models`, { cache: "no-store" });
    config.models = Array.isArray(payload.models) ? payload.models : [];
    config.mmproj_files = Array.isArray(payload.mmproj_files) ? payload.mmproj_files : [];
    config.missing_dependencies = Array.isArray(payload.missing_dependencies) ? payload.missing_dependencies : [];
    config.gguf_dependency = payload.gguf_dependency || null;
    return config;
}


function fillLocalModels(form, config) {


    const selected = String(config.local_model || "");
    form.localModel.replaceChildren();
    const empty = document.createElement("option");
    empty.value = "";
    empty.textContent = config.models?.length ? "请选择本地视觉模型" : "未发现 models/llm 下的视觉模型";
    form.localModel.append(empty);
    for (const item of config.models || []) {
        const option = document.createElement("option");
        option.value = String(item.relative_path || item.name || "");
        option.textContent = `${item.name || option.value}${item.format === "gguf" ? " · GGUF" : ""}`;
        form.localModel.append(option);
    }
    form.localModel.value = selected;
    fillMmproj(form, config);
}

function fillMmproj(form, config) {
    const selectedModel = (config.models || []).find(
        (item) => String(item.relative_path || item.name || "") === form.localModel.value,
    );
    const selected = String(config.local_mmproj || "");
    form.mmproj.replaceChildren();
    const auto = document.createElement("option");
    auto.value = "";
    auto.textContent = "自动匹配（推荐）";
    form.mmproj.append(auto);
    const values = new Set([
        ...(selectedModel?.mmproj_candidates || []),
        ...(config.mmproj_files || []),
    ]);
    for (const value of values) {
        const option = document.createElement("option");
        option.value = String(value);
        option.textContent = String(value);
        form.mmproj.append(option);
    }
    form.mmproj.value = selected;
}

async function openSettings(node) {
    closeSettings();
    const overlay = document.createElement("dialog");
    overlay.className = "aicg3d-skills-overlay";
    const panel = document.createElement("section");
    panel.className = "aicg3d-skills-dialog";
    const header = document.createElement("header");
    header.className = "aicg3d-skills-header";
    const title = document.createElement("div");
    title.className = "aicg3d-skills-title";
    title.textContent = "AICG3D SKILLS · 提示词模型设置";
    const close = document.createElement("button");
    close.type = "button";
    close.className = "aicg3d-skills-close";
    close.textContent = "×";
    close.setAttribute("aria-label", "关闭");
    header.append(title, close);

    const body = document.createElement("div");
    body.className = "aicg3d-skills-body";
    const loading = document.createElement("div");
    loading.className = "aicg3d-skills-loading";
    loading.textContent = "正在读取设置……";
    body.append(loading);
    panel.append(header, body);
    overlay.append(panel);
    document.body.append(overlay);
    document.body.classList.add("aicg3d-skills-settings-open");
    activeDialog = { overlay };
    if (typeof overlay.showModal === "function") {
        try {
            overlay.showModal();
        } catch {
            // Browser fallback: the CSS overlay is already visible.
        }
    }
    close.addEventListener("click", closeSettings);
    overlay.addEventListener("cancel", (event) => {
        event.preventDefault();
        closeSettings();
    });
    overlay.addEventListener("pointerdown", (event) => {
        if (event.target === overlay) closeSettings();
    });

    let config;
    try {
        config = configCache || (await fetchJson(`${API_BASE}/config`, { cache: "no-store" }));
        await hydrateLocalModels(config).catch(() => config);
        configCache = config;
    } catch (error) {
        loading.textContent = `设置读取失败：${error.message}`;
        return;
    }

    const form = document.createElement("form");
    form.className = "aicg3d-skills-form";
    form.mode = selectInput({ api: "线上 API", local: "本地模型" }, config.mode);
    form.provider = selectInput(
        Object.fromEntries(Object.entries(PROVIDERS).map(([key, value]) => [key, value[0]])),
        config.provider || "runninghub",
    );
    form.protocol = selectInput(
        { openai: "OpenAI 兼容", responses: "OpenAI Responses", gemini: "Gemini", runninghub: "RunningHub" },
        config.protocol || "openai",
    );
    form.apiUrl = textInput(config.api_url || "");
    form.apiKey = textInput("", "password");
    form.apiKey.placeholder = config.has_api_key ? "已保存密钥；留空则保持不变" : "填写 API Key";
    form.model = textInput(config.model || "");
    form.localModel = selectInput({}, config.local_model || "");
    form.mmproj = selectInput({}, config.local_mmproj || "");
    fillLocalModels(form, config);
    form.device = selectInput({ cuda: "GPU · CUDA", cpu: "CPU" }, config.local_device || "cuda");
    form.language = selectInput({ "中文": "中文", English: "English" }, config.output_language || "中文");
    const readMedia = toggleInput(config.read_media);
    const unload = toggleInput(config.unload_ollama_after_optimize ?? true);

    const modeField = field("运行方式", form.mode, "API 适合云端高能力模型；本地模型适合离线、无密钥运行。");
    const onlineRows = [
        field("线上服务", form.provider),
        field("接口格式", form.protocol, "多数中转或云服务选 OpenAI 兼容；RunningHub 使用专用协议。"),
        field("API 地址", form.apiUrl),
        field("API Key", form.apiKey),
        field("线上模型名称", form.model),
    ];
    const localModelField = field("本地视觉模型", form.localModel, "扫描 ComfyUI/models/llm；GGUF 与 Transformers 模型都可选择。");
    const mmprojField = field("MMProj 文件", form.mmproj, "GGUF 视觉模型需要与主模型匹配的 mmproj。");
    const deviceField = field("运行设备", form.device);
    const languageField = field("输出语言", form.language, "对白仍保留原语言；这里控制提示词正文语言。");
    const readMediaField = field("读取参考图", readMedia.wrapper, "关闭后只使用素材标签和文字说明。");
    const unloadField = field("优化后卸载 Ollama", unload.wrapper, "仅 OpenAI 兼容的 Ollama 服务需要。");
    const localHint = document.createElement("div");
    localHint.className = "aicg3d-skills-local-hint";
    localHint.textContent = "本地模型需要安装 llama.cpp 轮子文件（llama-cpp-python）。如需有偿协助，请添加 QQ：623951782。";
    const localHintField = field("本地模型依赖提示", localHint);
    const localRows = [localModelField, mmprojField, deviceField, localHintField];
    form.localHintField = localHintField;
    form.onlineRows = onlineRows;
    form.localRows = localRows;
    form.modeField = modeField;
    form.localModelField = localModelField;
    form.mmprojField = mmprojField;
    form.deviceField = deviceField;
    form.languageField = languageField;
    form.readMediaField = readMediaField;
    form.unloadField = unloadField;
    form.append(
        modeField,
        ...onlineRows,
        localModelField,
        mmprojField,
        deviceField,
        languageField,
        readMediaField,
        unloadField,
        localHintField,
    );

    const error = errorBox();
    const actions = document.createElement("footer");
    actions.className = "aicg3d-skills-actions";
    const cancel = document.createElement("button");
    cancel.type = "button";
    cancel.className = "aicg3d-skills-button";
    cancel.textContent = "取消";
    const save = document.createElement("button");
    save.type = "submit";
    save.className = "aicg3d-skills-button is-primary";
    save.textContent = "保存并应用";
    actions.append(cancel, save);
    form.append(error, actions);
    body.replaceChildren(form);

    form.provider.addEventListener("change", () => {
        const preset = PROVIDERS[form.provider.value];
        if (!preset) return;
        form.apiUrl.value = preset[1];
        form.model.value = preset[2];
        form.protocol.value = preset[3];
    });
    form.localModel.addEventListener("change", () => fillMmproj(form, config));
    form.mode.addEventListener("change", async () => {
        syncVisibility(form);
        if (form.mode.value === "local") {
            await hydrateLocalModels(config).catch(() => config);
            fillLocalModels(form, config);
        }
    });
    syncVisibility(form);
    cancel.addEventListener("click", closeSettings);
    overlay.addEventListener("keydown", (event) => {
        if (event.key === "Escape") closeSettings();
    });
    form.addEventListener("submit", async (event) => {
        event.preventDefault();
        save.disabled = true;
        error.hidden = true;
        const payload = {
            mode: form.mode.value,
            provider: form.provider.value,
            protocol: form.protocol.value,
            api_url: form.apiUrl.value,
            api_key: form.apiKey.value,
            model: form.model.value,
            local_model: form.localModel.value,
            local_mmproj: form.mmproj.value,
            local_device: form.device.value,
            output_language: form.language.value,
            read_media: readMedia.input.checked,
            unload_ollama_after_optimize: unload.input.checked,
        };
        try {
            const saved = await fetchJson(`${API_BASE}/config`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(payload),
            });
            configCache = { ...config, ...saved, models: config.models, mmproj_files: config.mmproj_files };
            setWidget(node, ["运行方式"], configCache.mode);
            setWidget(node, ["线上服务"], configCache.provider);
            setWidget(node, ["API地址"], configCache.api_url);
            setWidget(node, ["模型名称"], configCache.model);
            setWidget(node, ["本地模型"], configCache.local_model);
            setWidget(node, ["GPU或CPU"], configCache.local_device);
            setWidget(node, ["输出语言"], configCache.output_language);
            setWidget(node, ["读取参考图"], configCache.read_media);
            closeSettings();
        } catch (saveError) {
            error.textContent = String(saveError.message || saveError);
            error.hidden = false;
            save.disabled = false;
        }
    });
}

function widgetByName(node, name) {
    return (node?.widgets || []).find((widget) => String(widget?.name || "") === name) || null;
}

function setWidgetOption(widget, key, value) {
    widget.options = widget.options || {};
    widget.options[key] = value;
    if (widget._state?.options) widget._state.options[key] = value;
}

function hideNodeWidget(widget) {
    if (!widget || widget.__aicg3dNodeHidden) return;
    if (!widget.__aicg3dNodeOriginal) {
        widget.__aicg3dNodeOriginal = {
            type: widget.type,
            hidden: widget.hidden,
            optionsHidden: widget.options?.hidden,
            optionsCanvasOnly: widget.options?.canvasOnly,
            computeSize: widget.computeSize,
            hadComputeSize: Object.prototype.hasOwnProperty.call(widget, "computeSize"),
            computedHeight: widget.computedHeight,
            hadComputedHeight: Object.prototype.hasOwnProperty.call(widget, "computedHeight"),
        };
    }
    widget.__aicg3dNodeHidden = true;
    widget.hidden = true;
    if (widget.inputEl) widget.inputEl.style.display = "none";
    if (widget.element) widget.element.style.display = "none";
    widget.type = "hidden";
    widget.computeSize = () => [0, -4];
    widget.computedHeight = 0;
    setWidgetOption(widget, "hidden", true);
    setWidgetOption(widget, "canvasOnly", true);
    if (widget._state) {
        widget._state.hidden = true;
        widget._state.type = "hidden";
        widget._state.computedHeight = 0;
    }
}

function showNodeWidget(widget) {
    if (!widget || !widget.__aicg3dNodeHidden) return;
    const original = widget.__aicg3dNodeOriginal || {};
    widget.__aicg3dNodeHidden = false;
    widget.hidden = original.hidden ?? false;
    if (widget.inputEl) widget.inputEl.style.display = "";
    if (widget.element) widget.element.style.display = "";
    widget.type = original.type || "combo";
    if (original.hadComputeSize) widget.computeSize = original.computeSize;
    else delete widget.computeSize;
    if (original.hadComputedHeight) widget.computedHeight = original.computedHeight;
    else delete widget.computedHeight;
    setWidgetOption(widget, "hidden", original.optionsHidden ?? false);
    setWidgetOption(widget, "canvasOnly", original.optionsCanvasOnly ?? false);
    if (widget._state) {
        widget._state.hidden = widget.hidden;
        widget._state.type = widget.type;
        if (original.hadComputedHeight) widget._state.computedHeight = widget.computedHeight;
        else delete widget._state.computedHeight;
    }
}

function syncSettingsNodeWidgetVisibility(node) {
    if (!node) return;
    const mode = widgetByName(node, "运行方式");
    const local = String(mode?.value || "").toLowerCase() === "local";
    const onlineNames = ["线上服务", "API地址", "模型名称"];
    const localNames = ["本地模型", "GPU或CPU"];
    for (const name of onlineNames) {
        const widget = widgetByName(node, name);
        if (local) hideNodeWidget(widget);
        else showNodeWidget(widget);
    }
    for (const name of localNames) {
        const widget = widgetByName(node, name);
        if (local) showNodeWidget(widget);
        else hideNodeWidget(widget);
    }
    try {
        node.setSize([node.size?.[0] || 320, node.computeSize?.()[1] || node.size?.[1] || 220]);
    } catch {
        // Some renderers do not expose computeSize during node construction.
    }
    node.setDirtyCanvas?.(true, true);
    node.graph?.setDirtyCanvas?.(true, true);
}

function configureSettingsNodeWidgets(node) {
    const mode = widgetByName(node, "运行方式");
    if (!mode) {
        const attempt = Number(node.__aicg3dVisibilityAttempt || 0);
        if (attempt < 40) {
            node.__aicg3dVisibilityAttempt = attempt + 1;
            setTimeout(() => configureSettingsNodeWidgets(node), 50);
        }
        return;
    }
    node.__aicg3dVisibilityAttempt = 0;
    if (!mode.__aicg3dVisibilityCallbackBound) {
        mode.__aicg3dVisibilityCallbackBound = true;
        const originalCallback = mode.callback;
        mode.callback = function () {
            const result = typeof originalCallback === "function" ? originalCallback.apply(this, arguments) : undefined;
            syncSettingsNodeWidgetVisibility(node);
            return result;
        };
    }
    requestAnimationFrame(() => syncSettingsNodeWidgetVisibility(node));
}

function quickTaskValue(node) {
    return String(widgetByName(node, QUICK_TASK_WIDGET)?.value || "普通创作");
}

function skillItemForId(skillId) {
    return skillItemsCache.find((item) => String(item?.id || "") === String(skillId || "")) || null;
}

function setQuickTaskSkill(node, task) {
    const item = skillItemForId(QUICK_TASK_SKILL_IDS[task]);
    if (item) setWidget(node, ["技能包"], skillLabel(item));
}

function setTaskModeSkill(node, mode) {
    const item = skillItemForId(TASK_MODE_SKILL_IDS[mode]);
    if (item) setWidget(node, ["技能包"], skillLabel(item));
}

function applyTaskModeBehavior(node, value = "") {
    if (!node || quickTaskValue(node) !== "普通创作") return;
    const mode = String(value || widgetByName(node, "任务模式")?.value || "Ref2VA 全能参考（推荐）");
    const specialSkillId = TASK_MODE_SKILL_IDS[mode];
    const special = Boolean(specialSkillId);
    const imageMode = mode === T2I_MODE || mode === FL2I_MODE;
    const promptWidget = widgetByName(node, "创意描述");
    const currentPrompt = String(promptWidget?.value || "");
    const previousDefault = String(node.__aicg3dTaskModePrompt || "");
    const nextDefault = String(TASK_MODE_PROMPTS[mode] || "");
    const previous = node.__aicg3dTaskModePrevious;
    const replaceablePrompt = !currentPrompt.trim()
        || currentPrompt === previousDefault
        || currentPrompt === "图1和图2在图3场景打斗"
        || currentPrompt === "人物在同一空间中展开行动"
        || Object.values(QUICK_TASK_PROMPTS).includes(currentPrompt);

    if (promptWidget && special && nextDefault && replaceablePrompt) {
        promptWidget.value = nextDefault;
        if (promptWidget._state) promptWidget._state.value = nextDefault;
    } else if (promptWidget && !special && previousDefault && currentPrompt === previousDefault) {
        promptWidget.value = String(previous?.prompt || "");
        if (promptWidget._state) promptWidget._state.value = promptWidget.value;
    }
    node.__aicg3dTaskModePrompt = nextDefault;

    for (const field of ["视频时长", "动作强度", "技能重点", "技能包"]) {
        const widget = widgetByName(node, field);
        const hide = special && (imageMode || field === "技能重点" || field === "技能包");
        if (hide) hideNodeWidget(widget);
        else showNodeWidget(widget);
    }

    if (special) {
        const currentSkill = String(widgetByName(node, "技能包")?.value || "");
        const currentItem = skillItemsCache.find((item) => skillLabel(item) === currentSkill);
        const isTaskModeSkill = Object.values(TASK_MODE_SKILL_IDS).includes(String(currentItem?.id || ""));
        if (!previous && !isTaskModeSkill) {
            node.__aicg3dTaskModePrevious = {
                skill: currentSkill,
                focus: String(widgetByName(node, "技能重点")?.value || "自动选择"),
                prompt: currentPrompt,
            };
        }
        setTaskModeSkill(node, mode);
        setWidget(node, ["技能重点"], imageMode ? "自动选择" : "全流程导演");
    } else if (previous) {
        if (previous.skill) setWidget(node, ["技能包"], previous.skill);
        if (previous.focus) setWidget(node, ["技能重点"], previous.focus);
        node.__aicg3dTaskModePrevious = null;
    }

    node._widgetSlotsDirty = true;
    node.setDirtyCanvas?.(true, true);
    node.graph?.setDirtyCanvas?.(true, true);
}

function configureTaskModeBehavior(node) {
    const modeWidget = widgetByName(node, "任务模式");
    if (!modeWidget || modeWidget.__aicg3dTaskModeBound) return;
    modeWidget.__aicg3dTaskModeBound = true;
    const originalCallback = modeWidget.callback;
    modeWidget.callback = function (value) {
        const result = typeof originalCallback === "function" ? originalCallback.apply(this, arguments) : undefined;
        applyTaskModeBehavior(node, String(value || ""));
        return result;
    };
    requestAnimationFrame(() => applyTaskModeBehavior(node, String(modeWidget.value || "")));
}

function applyQuickTaskMode(node, value = quickTaskValue(node)) {
    if (!node) return;
    const task = QUICK_TASKS.includes(value) ? value : "普通创作";
    const reverse = task !== "普通创作";
    const promptWidget = widgetByName(node, "创意描述");
    const previousDefault = String(node.__aicg3dQuickTaskPrompt || "");
    const currentPrompt = String(promptWidget?.value || "");
    const nextDefault = String(QUICK_TASK_PROMPTS[task] || "");
    const replaceablePrompt = !currentPrompt.trim()
        || currentPrompt === previousDefault
        || currentPrompt === "图1和图2在图3场景打斗"
        || currentPrompt === "人物在同一空间中展开行动";
    const previousState = node.__aicg3dQuickTaskPrevious;
    if (promptWidget && reverse && replaceablePrompt) {
        promptWidget.value = nextDefault;
        if (promptWidget._state) promptWidget._state.value = nextDefault;
    } else if (promptWidget && !reverse && previousDefault && currentPrompt === previousDefault) {
        promptWidget.value = String(previousState?.prompt || "");
        if (promptWidget._state) promptWidget._state.value = promptWidget.value;
    }
    node.__aicg3dQuickTaskPrompt = nextDefault;

    for (const field of QUICK_TASK_HIDDEN_FIELDS) {
        const widget = widgetByName(node, field);
        if (reverse) hideNodeWidget(widget);
        else showNodeWidget(widget);
    }

    if (reverse) {
        const previous = node.__aicg3dQuickTaskPrevious;
        const currentSkill = String(widgetByName(node, "技能包")?.value || "");
        const currentItem = skillItemsCache.find((item) => skillLabel(item) === currentSkill);
        const isReverseSkill = Object.values(QUICK_TASK_SKILL_IDS).includes(String(currentItem?.id || ""));
        if (!previous && !isReverseSkill) {
            node.__aicg3dQuickTaskPrevious = {
                skill: currentSkill,
                focus: String(widgetByName(node, "技能重点")?.value || "自动选择"),
                prompt: currentPrompt,
                taskMode: String(widgetByName(node, "任务模式")?.value || "Ref2VA 全能参考（推荐）"),
            };
        }
        setWidget(node, ["任务模式"], "Ref2VA 全能参考（推荐）");
        setWidget(node, ["技能重点"], task === "视频反推提示词" ? "镜头与分镜" : "自动选择");
        setQuickTaskSkill(node, task);
    } else if (node.__aicg3dQuickTaskPrevious) {
        const previous = node.__aicg3dQuickTaskPrevious;
        if (previous.skill) setWidget(node, ["技能包"], previous.skill);
        if (previous.focus) setWidget(node, ["技能重点"], previous.focus);
        if (previous.taskMode) {
            const taskModeWidget = widgetByName(node, "任务模式");
            if (taskModeWidget) {
                taskModeWidget.value = previous.taskMode;
                if (taskModeWidget._state) taskModeWidget._state.value = previous.taskMode;
            }
        }
        node.__aicg3dQuickTaskPrevious = null;
    }

    const ui = widgetByName(node, QUICK_TASK_UI_WIDGET);
    if (ui && ui.value !== task) ui.value = task;
    if (!reverse) applyTaskModeBehavior(node, String(widgetByName(node, "任务模式")?.value || ""));
    node._widgetSlotsDirty = true;
    node.setDirtyCanvas?.(true, true);
    node.graph?.setDirtyCanvas?.(true, true);
}

function configureQuickTaskMode(node) {
    if (!node || node.__aicg3dQuickTaskConfigured) return;
    const hidden = widgetByName(node, QUICK_TASK_WIDGET);
    if (!hidden) {
        const attempt = Number(node.__aicg3dQuickTaskAttempt || 0);
        if (attempt < 30) {
            node.__aicg3dQuickTaskAttempt = attempt + 1;
            setTimeout(() => configureQuickTaskMode(node), 80);
        }
        return;
    }
    node.__aicg3dQuickTaskConfigured = true;
    hideNodeWidget(hidden);

    let ui = widgetByName(node, QUICK_TASK_UI_WIDGET);
    if (!ui) {
        ui = node.addWidget("combo", QUICK_TASK_UI_WIDGET, quickTaskValue(node), (value) => {
            setWidget(node, [QUICK_TASK_WIDGET], value);
        }, {
            values: QUICK_TASKS,
            tooltip: "普通创作保留完整参数；图片/视频反推会自动加载专用 Skill，并隐藏无关参数。",
        });
    }
    if (!ui) {
        showNodeWidget(hidden);
        node.__aicg3dQuickTaskConfigured = false;
        return;
    }
    if (ui) {
        ui.serialize = false;
        setWidgetOption(ui, "serialize", false);
        if (ui._state) ui._state.serialize = false;
    }

    const promptWidget = widgetByName(node, "创意描述");
    if (ui && promptWidget && Array.isArray(node.widgets)) {
        const uiIndex = node.widgets.indexOf(ui);
        const promptIndex = node.widgets.indexOf(promptWidget);
        if (uiIndex >= 0 && promptIndex >= 0 && uiIndex !== promptIndex + 1) {
            node.widgets.splice(uiIndex, 1);
            const nextPromptIndex = node.widgets.indexOf(promptWidget);
            node.widgets.splice(nextPromptIndex + 1, 0, ui);
        }
    }

    if (!hidden.__aicg3dQuickTaskCallbackBound) {
        hidden.__aicg3dQuickTaskCallbackBound = true;
        const originalCallback = hidden.callback;
        hidden.callback = function (value) {
            const result = typeof originalCallback === "function" ? originalCallback.apply(this, arguments) : undefined;
            applyQuickTaskMode(node, String(value || "普通创作"));
            return result;
        };
    }

    const sync = () => applyQuickTaskMode(node, quickTaskValue(node));
    if (!node.__aicg3dQuickTaskConfigureHooked) {
        node.__aicg3dQuickTaskConfigureHooked = true;
        const originalConfigure = node.onConfigure;
        node.onConfigure = function (...args) {
            const result = originalConfigure?.apply(this, args);
            requestAnimationFrame(sync);
            return result;
        };
    }
    requestAnimationFrame(sync);
    setTimeout(sync, 100);
    loadSkills().then(sync).catch(() => {});
}

function configureCompactExpanderWidgets(node) {
    if (!node) return;
    for (const name of ["参考素材JSON", "技能重点输入", "技能包输入", "模型设置JSON", QUICK_TASK_WIDGET]) {
        hideNodeWidget(widgetByName(node, name));
    }
    node.setDirtyCanvas?.(true, true);
    node.graph?.setDirtyCanvas?.(true, true);
}


function addSettingsButton(node) {
    if (!node || node.__aicg3dSkillsButtonAdded) return;
    node.__aicg3dSkillsButtonAdded = true;
    node.addWidget("button", "模型设置", null, () => openSettings(node));
    node.setSize([Math.max(node.size?.[0] || 280, 300), Math.max(node.size?.[1] || 120, 150)]);
}

function setComboOptions(widget, values, preferred) {
    if (!widget) return;
    const next = Array.from(new Set(values.filter(Boolean).map(String)));
    if (!next.length) return;
    widget.options = widget.options || {};
    widget.options.values = next;
    const wanted = String(preferred || widget.value || "");
    widget.value = next.includes(wanted) ? wanted : next[0];
}

function allSkillNodes() {
    const graph = app.graph || app.rootGraph;
    return graph?._nodes || graph?.nodes || [];
}

function skillLabel(item) {
    return String(item?.name || item?.id || "");
}


function normalizeSkillPreviewKey(value) {
    return String(value || "")
        .trim()
        .toLowerCase()
        .replace(/[\s｜|·,，。:：;；()（）\[\]【】_\-✓✔]+/g, "");
}


function registerSkillPreviewItems(skills) {
    for (const item of skills) {
        const keys = [item.id, item.name, item.original_name, item.preview_title]
            .map(normalizeSkillPreviewKey)
            .filter(Boolean);
        for (const key of keys) skillPreviewCache.set(key, item);
    }
}


function findSkillPreviewItem(label) {
    const raw = String(label || "").trim();
    return skillPreviewCache.get(normalizeSkillPreviewKey(raw)) || null;
}


function positionSkillHoverPreview(element, option) {
    const rect = option.getBoundingClientRect();
    const width = 360;
    let left = rect.right + 12;
    if (left + width > window.innerWidth - 8) left = rect.left - width - 12;
    left = Math.max(8, Math.min(left, window.innerWidth - width - 8));
    const top = Math.max(8, Math.min(rect.top, window.innerHeight - 220));
    element.style.left = `${left}px`;
    element.style.top = `${top}px`;
}


function showSkillHoverPreview(item, option) {
    if (!item || window.matchMedia?.("(hover: none)")?.matches) return;
    hideSkillHoverPreview();
    const panel = document.createElement("div");
    panel.className = "aicg3d-skills-hover-preview";
    panel.dataset.skillId = String(item.id || "");
    const visual = document.createElement("div");
    visual.className = "aicg3d-skills-hover-visual";
    const fallback = document.createElement("div");
    fallback.className = "aicg3d-skills-hover-fallback";
    fallback.textContent = "预览加载中";
    visual.append(fallback);
    const source = item.preview_poster || item.preview_gif;
    if (source) {
        const image = document.createElement("img");
        image.alt = "";
        image.loading = "eager";
        image.decoding = "async";
        image.addEventListener("load", () => fallback.remove());
        image.addEventListener("error", () => {
            if (item.preview_poster && item.preview_gif && image.dataset.usedGif !== "1") {
                image.dataset.usedGif = "1";
                image.src = item.preview_gif;
                return;
            }
            image.remove();
            fallback.textContent = "暂无预览图";
        });
        image.src = source;
        visual.append(image);
        if (item.preview_poster && item.preview_gif) {
            skillHoverTimer = window.setTimeout(() => {
                if (panel.isConnected && image.isConnected) {
                    image.dataset.usedGif = "1";
                    image.src = item.preview_gif;
                }
            }, 600);
        }
    }
    const content = document.createElement("div");
    content.className = "aicg3d-skills-hover-content";
    const title = document.createElement("strong");
    title.textContent = skillLabel(item);
    const description = document.createElement("span");
    description.textContent = item.preview_summary || item.description || item.full_description || "暂无说明";
    content.append(title, description);
    panel.append(visual, content);
    document.body.append(panel);
    positionSkillHoverPreview(panel, option);
    skillHoverPreview = panel;
}


function hideSkillHoverPreview() {
    if (skillHoverTimer) {
        window.clearTimeout(skillHoverTimer);
        skillHoverTimer = null;
    }
    skillHoverPreview?.remove();
    skillHoverPreview = null;
}


function installSkillHoverPreview() {
    if (window.__aicg3dSkillHoverPreviewInstalled) return;
    window.__aicg3dSkillHoverPreviewInstalled = true;
    const optionSelector = '[role="option"], .p-select-option, .p-listbox-option, .litecontextmenu .litemenu-entry, .comfyui-menu-item';
    const optionFromEvent = (event) => {
        const path = event.composedPath?.() || [];
        return path.find((element) => element?.matches?.(optionSelector)) || null;
    };
    document.addEventListener("pointerover", (event) => {
        const option = optionFromEvent(event);
        if (!option) return;
        const item = findSkillPreviewItem(option.textContent || "");
        if (!item) {
            hideSkillHoverPreview();
            return;
        }
        if (skillHoverPreview?.dataset.skillId === String(item.id || "")) return;
        hideSkillHoverPreview();
        skillHoverTimer = window.setTimeout(() => showSkillHoverPreview(item, option), 180);
    }, true);
    document.addEventListener("pointerout", (event) => {
        const option = optionFromEvent(event);
        if (!option) return;
        const next = event.relatedTarget;
        if (next && option.contains(next)) return;
        hideSkillHoverPreview();
    }, true);
    window.addEventListener("scroll", hideSkillHoverPreview, true);
    document.addEventListener("pointerdown", hideSkillHoverPreview, true);
}


function syncSkillChoices(skills) {
    const labels = skills.map(skillLabel).filter(Boolean);
    for (const node of allSkillNodes()) {
        const name = nodeClass(node);
        if (![EXPANDER_NODE, "AICG3D_SKILLS_SkillSelector", SKILL_MANAGER_NODE].includes(name)) continue;
        const widget = (node.widgets || []).find((item) => ["技能包", "当前技能"].includes(String(item?.name || "")));
        const current = String(widget?.value || "");
        const selected = skills.find((item) => [item.id, item.name, item.original_name].includes(current));
        setComboOptions(widget, labels, selected ? skillLabel(selected) : current);
    }
}

async function loadSkills() {
    const payload = await fetchJson(`${API_BASE}/skills`, { cache: "no-store" });
    const skills = Array.isArray(payload.skills) ? payload.skills : [];
    skillItemsCache = skills;
    registerSkillPreviewItems(skills);
    syncSkillChoices(skills);
    return skills;
}

function skillRows(skills, onChanged, options = {}) {
    const list = document.createElement("div");
    list.className = "aicg3d-skills-list";
    if (!skills.length) {
        const empty = document.createElement("div");
        empty.className = "aicg3d-skills-empty";
        empty.textContent = "没有找到匹配的 Skill，请换一个关键词。";
        list.append(empty);
        return list;
    }
    for (const item of skills) {
        const row = document.createElement("div");
        row.className = "aicg3d-skills-skill-row";
        const main = document.createElement("div");
        main.className = "aicg3d-skills-skill-main";
        const name = document.createElement("div");
        name.className = "aicg3d-skills-skill-name";
        const badges = [item.bundled ? "内置" : "", item.category || ""].filter(Boolean);
        name.textContent = `${item.name || item.id}${badges.length ? ` · ${badges.join(" · ")}` : ""}`;
        const meta = document.createElement("div");
        meta.className = "aicg3d-skills-skill-meta";
        meta.textContent = `${item.id} · ${item.source || "本地"} · ${item.reference_count || 0} 个参考文件`;
        const description = document.createElement("div");
        description.className = "aicg3d-skills-skill-description";
        description.textContent = item.description || item.full_description || "没有描述。";
        main.append(name, meta, description);
        const actions = document.createElement("div");
        actions.className = "aicg3d-skills-skill-actions";
        const preview = document.createElement("button");
        preview.type = "button";
        preview.className = "aicg3d-skills-button";
        preview.textContent = "预览";
        preview.addEventListener("click", () => (options.onPreview || openSkillPreview)(item));
        actions.append(preview);
        if (typeof options.onUse === "function") {
            const use = document.createElement("button");
            use.type = "button";
            use.className = "aicg3d-skills-button is-primary";
            use.textContent = skillLabel(item) === options.selectedLabel ? "已选择" : "使用";
            use.disabled = skillLabel(item) === options.selectedLabel;
            use.addEventListener("click", () => options.onUse(item));
            actions.append(use);
        }
        const remove = document.createElement("button");
        remove.type = "button";
        remove.className = "aicg3d-skills-button is-danger";
        remove.textContent = "删除";
        remove.disabled = Boolean(item.bundled);
        if (item.bundled) remove.title = "内置 Skill 不允许删除";
        remove.addEventListener("click", async () => {
            if (!window.confirm(`确定删除 Skill「${item.name || item.id}」吗？`)) return;
            remove.disabled = true;
            try {
                await fetchJson(`${API_BASE}/skills/${encodeURIComponent(item.id)}`, { method: "DELETE" });
                await onChanged();
            } catch (error) {
                window.alert(String(error.message || error));
                remove.disabled = false;
            }
        });
        actions.append(remove);
        row.append(main, actions);
        list.append(row);
    }
    return list;
}

async function openSkillPreview(item, node = null) {
    closeSettings();
    const overlay = document.createElement("dialog");
    overlay.className = "aicg3d-skills-overlay";
    const panel = document.createElement("section");
    panel.className = "aicg3d-skills-dialog";
    const header = document.createElement("header");
    header.className = "aicg3d-skills-header";
    const title = document.createElement("div");
    title.className = "aicg3d-skills-title";
    title.textContent = `技能演示 · ${skillLabel(item)}`;
    const close = document.createElement("button");
    close.type = "button";
    close.className = "aicg3d-skills-close";
    close.textContent = "×";
    header.append(title, close);
    const body = document.createElement("div");
    body.className = "aicg3d-skills-body";
    const loading = document.createElement("div");
    loading.className = "aicg3d-skills-loading";
    loading.textContent = "正在生成技能演示……";
    body.append(loading);
    const footer = document.createElement("footer");
    footer.className = "aicg3d-skills-actions";
    const use = document.createElement("button");
    use.type = "button";
    use.className = "aicg3d-skills-button is-primary";
    use.textContent = "使用此技能";
    use.disabled = !node;
    const done = document.createElement("button");
    done.type = "button";
    done.className = "aicg3d-skills-button";
    done.textContent = "关闭";
    footer.append(use, done);
    panel.append(header, body, footer);
    overlay.append(panel);
    document.body.append(overlay);
    activeDialog = { overlay, node };
    if (typeof overlay.showModal === "function") {
        try {
            overlay.showModal();
        } catch {
            // Browser fallback: the CSS overlay is already visible.
        }
    }
    close.addEventListener("click", closeSettings);
    done.addEventListener("click", closeSettings);
    use.addEventListener("click", () => {
        if (!node) return;
        setWidget(node, ["技能包", "当前技能"], skillLabel(item));
        closeSettings();
    });
    overlay.addEventListener("cancel", (event) => {
        event.preventDefault();
        closeSettings();
    });
    overlay.addEventListener("pointerdown", (event) => {
        if (event.target === overlay) closeSettings();
    });
    try {
        const payload = await fetchJson(`${API_BASE}/skills/${encodeURIComponent(item.id)}`, { cache: "no-store" });
        const skill = payload.skill || item;
        const intro = document.createElement("section");
        intro.className = "aicg3d-skills-preview";
        const name = document.createElement("h3");
        name.textContent = skillLabel(skill);
        const previewSource = skill.preview_gif || skill.preview_poster;
        if (previewSource) {
            const preview = document.createElement("img");
            preview.className = "aicg3d-skills-preview-media";
            preview.alt = skill.preview_title || skillLabel(skill);
            preview.loading = "eager";
            preview.decoding = "async";
            preview.addEventListener("error", () => preview.remove());
            preview.src = previewSource;
            intro.append(name, preview);
        } else {
            intro.append(name);
        }
        const description = document.createElement("p");
        description.textContent = skill.description || skill.full_description || "暂无中文说明。";
        const demo = document.createElement("div");
        demo.className = "aicg3d-skills-demo";
        for (const [index, label] of ["素材 / 创意", "加载 Skill 规则", "生成 H3 提示词"].entries()) {
            const step = document.createElement("div");
            step.className = "aicg3d-skills-demo-step";
            step.style.animationDelay = `${index * 0.45}s`;
            step.textContent = label;
            demo.append(step);
        }
        const summaryTitle = document.createElement("h4");
        summaryTitle.textContent = "这个 Skill 会怎么工作";
        const summary = document.createElement("pre");
        summary.className = "aicg3d-skills-preview-text";
        summary.textContent = skill.summary || skill.full_description || "暂无演示内容。";
        intro.append(description, demo, summaryTitle, summary);
        if (skill.demo_prompt && skill.demo_prompt !== skill.summary) {
            const demoTip = document.createElement("h4");
            demoTip.textContent = "可直接参考的演示输入";
            const demoText = document.createElement("pre");
            demoText.className = "aicg3d-skills-preview-text";
            demoText.textContent = skill.demo_prompt;
            intro.append(demoTip, demoText);
        }
        body.replaceChildren(intro);
    } catch (error) {
        const failure = document.createElement("div");
        failure.className = "aicg3d-skills-error";
        failure.textContent = String(error.message || error);
        body.replaceChildren(failure);
    }
}


async function openSkillManager(node) {
    closeSettings();
    const overlay = document.createElement("dialog");
    overlay.className = "aicg3d-skills-overlay";
    const panel = document.createElement("section");
    panel.className = "aicg3d-skills-dialog";
    const header = document.createElement("header");
    header.className = "aicg3d-skills-header";
    const title = document.createElement("div");
    title.className = "aicg3d-skills-title";
    title.textContent = "AICG3D SKILLS · 技能库";
    const close = document.createElement("button");
    close.type = "button";
    close.className = "aicg3d-skills-close";
    close.textContent = "×";
    header.append(title, close);
    const body = document.createElement("div");
    body.className = "aicg3d-skills-body";
    const loading = document.createElement("div");
    loading.className = "aicg3d-skills-loading";
    loading.textContent = "正在读取 Skill 列表……";
    const searchInput = textInput("", "search");
    searchInput.placeholder = "搜索中文用途、英文 ID 或关键词";
    const searchField = field("搜索技能", searchInput, "例如“产品广告”“连续追逐”“微表情”“品牌宣传”。列表会立即筛选。");
    searchField.classList.add("aicg3d-skills-toolbar");
    const listHost = document.createElement("div");
    listHost.append(loading);
    body.append(searchField, listHost);
    const footer = document.createElement("footer");
    footer.className = "aicg3d-skills-actions";
    panel.append(header, body, footer);
    overlay.append(panel);
    document.body.append(overlay);
    activeDialog = { overlay };
    if (typeof overlay.showModal === "function") overlay.showModal();
    close.addEventListener("click", closeSettings);
    overlay.addEventListener("cancel", (event) => {
        event.preventDefault();
        closeSettings();
    });
    const importInput = document.createElement("input");
    importInput.type = "file";
    importInput.accept = ".zip,application/zip";
    importInput.hidden = true;
    const importButton = document.createElement("button");
    importButton.type = "button";
    importButton.className = "aicg3d-skills-button is-primary";
    importButton.textContent = "导入 Skill ZIP";
    const refreshButton = document.createElement("button");
    refreshButton.type = "button";
    refreshButton.className = "aicg3d-skills-button";
    refreshButton.textContent = "刷新列表";
    footer.append(importInput, refreshButton, importButton);
    let allSkills = [];
    const skillWidget = () => (node?.widgets || []).find((item) => ["技能包", "当前技能"].includes(String(item?.name || "")));
    const renderList = () => {
        const query = String(searchInput.value || "").trim().toLowerCase();
        const filtered = !query
            ? allSkills
            : allSkills.filter((item) => [
                item.name,
                item.id,
                item.original_name,
                item.description,
                item.full_description,
                item.source,
                item.category,
            ].some((value) => String(value || "").toLowerCase().includes(query)));
        listHost.replaceChildren(skillRows(filtered, render, {
            onPreview: (item) => openSkillPreview(item, node),
            selectedLabel: (() => {
                const current = String(skillWidget()?.value || "");
                const selected = allSkills.find((item) => [item.id, item.name, item.original_name].includes(current));
                return selected ? skillLabel(selected) : current;
            })(),
            onUse: (item) => {
                if (!node) return;
                setWidget(node, ["技能包", "当前技能"], skillLabel(item));
                closeSettings();
            },
        }));
    };
    const render = async () => {
        listHost.replaceChildren(loading);
        try {
            allSkills = await loadSkills();
            const widget = skillWidget();
            setComboOptions(widget, allSkills.map(skillLabel), widget?.value);
            renderList();
        } catch (error) {
            const failure = document.createElement("div");
            failure.className = "aicg3d-skills-error";
            failure.textContent = String(error.message || error);
            listHost.replaceChildren(failure);
        }
    };
    searchInput.addEventListener("input", renderList);
    refreshButton.addEventListener("click", render);
    importButton.addEventListener("click", () => importInput.click());
    importInput.addEventListener("change", async () => {
        const file = importInput.files?.[0];
        if (!file) return;
        const form = new FormData();
        form.append("file", file, file.name);
        try {
            const response = await api.fetchApi(`${API_BASE}/skills/import`, { method: "POST", body: form });
            const payload = await response.json().catch(() => ({}));
            if (!response.ok) {
                if (payload.code === "exists" && window.confirm(`${payload.error}\n是否覆盖已有 Skill？`)) {
                    const retry = await api.fetchApi(`${API_BASE}/skills/import?replace=1`, { method: "POST", body: form });
                    if (!retry.ok) throw new Error((await retry.json()).error || "导入失败");
                } else {
                    throw new Error(payload.error || "导入失败");
                }
            }
            importInput.value = "";
            await render();
        } catch (error) {
            window.alert(String(error.message || error));
        }
    });
    await render();
}

function helpRow(term, copy) {
    const row = document.createElement("div");
    row.className = "aicg3d-skills-help-row";
    const label = document.createElement("div");
    label.className = "aicg3d-skills-help-term";
    label.textContent = term;
    const description = document.createElement("div");
    description.className = "aicg3d-skills-help-copy";
    description.textContent = copy;
    row.append(label, description);
    return row;
}


function helpSection(title, rows) {
    const section = document.createElement("section");
    section.className = "aicg3d-skills-help-section";
    const heading = document.createElement("h3");
    heading.textContent = title;
    section.append(heading, ...rows);
    return section;
}


function openSkillHelp(node) {
    closeSettings();
    const overlay = document.createElement("dialog");
    overlay.className = "aicg3d-skills-overlay";
    const panel = document.createElement("section");
    panel.className = "aicg3d-skills-dialog";
    const header = document.createElement("header");
    header.className = "aicg3d-skills-header";
    const title = document.createElement("div");
    title.className = "aicg3d-skills-title";
    title.textContent = "AICG3D SKILLS · 使用说明";
    const close = document.createElement("button");
    close.type = "button";
    close.className = "aicg3d-skills-close";
    close.textContent = "×";
    close.setAttribute("aria-label", "关闭");
    header.append(title, close);
    const body = document.createElement("div");
    body.className = "aicg3d-skills-body aicg3d-skills-help";
    const lead = document.createElement("p");
    lead.className = "aicg3d-skills-help-lead";
    lead.textContent = "普通创作只需填写“创意描述”并选择 Skill；如果要分析现成图片或视频，直接在“快捷任务”里选“图片反推提示词”或“视频反推提示词”，插件会自动加载专用 Skill 并隐藏无关参数。";
    body.append(
        lead,
        helpSection("截图里的五个字段", [
            helpRow("参考素材JSON", "高级连线项，来自“参考素材整理”。作用是告诉模型每张图、视频、音频分别锁定主体、场景、动作或音色。不接也能运行，插件会识别创意中的图1、图2、图3。"),
            helpRow("技能重点输入", "高级连线项，来自“技能选择器”。它覆盖节点上的“技能重点”；直接用节点下拉框时不要接。"),
            helpRow("技能包输入", "高级连线项，来自“技能选择器”或“技能库”。它覆盖节点上的“技能包”；最方便的做法是直接用“选择 / 管理技能”弹窗。"),
            helpRow("额外要求", "可以直接输入自然语言限制，例如“不要添加新人物”“结尾停在对手拔枪的瞬间”“保持角色沉默”。可留空。"),
            helpRow("模型设置JSON", "高级连线项，来自“模型设置”。通常不接，插件会使用已经保存的全局 API 或本地模型设置。"),
        ]),
        helpSection("任务模式新增项", [
            helpRow("H3 六段式标准提示词", "无论参考素材数量多少，都强制输出 MiniMax H3 的六个标准字段，适合需要严格结构校验的任务。"),
            helpRow("文生图（T2I）", "只输出一段可直接复制的图片提示词，不再附加结构拆解、负面约束标题、分析或视频字段。"),
            helpRow("首尾帧生图（FL2I）", "默认把 <Picture 1> 当首帧、<Picture 2> 当尾帧；必须接入两张实际图片，只输出一段连续生图提示词。"),
        ]),
        helpSection("如何选 Skill", [
        helpSection("快捷任务（推荐）", [
            helpRow("图片反推提示词", "把图片接到“参考图片”或 AICG3D 资源库。选择后只输出一段可直接复制粘贴的图片生成提示词，不附带摘要、拆解或参考用法。"),
            helpRow("视频反推提示词", "把视频接到 AICG3D 资源库。选择后只输出 MiniMax H3 Ref2VA 六个正式字段，不附加镜头时间线、分析、合规说明或操作建议。"),
            helpRow("普通创作", "恢复任务模式、画幅、时长、动作强度、技能重点和技能包等完整参数；之前手动选择的技能会自动恢复。"),
            helpRow("模型要求", "图片和视频反推必须配置支持视觉的线上模型或本地视觉模型；不能用“无模型时生成模板”代替真实分析。"),
        ]),
            helpRow("默认导演", "保留“minimax-h3-short-drama-director”适合大多数短剧、打斗、对白和多段连续性任务。"),
            helpRow("创意 DNA", "技能库新增了 284 个 T8 机制 Skill，包括产品广告、连续追逐、品牌宣传、微表情、材质变身、角色登场等。搜索中文用途后点“使用”即可套到当前节点。"),
        ]),
    );
    const footer = document.createElement("footer");
    footer.className = "aicg3d-skills-actions";
    const settingsButton = document.createElement("button");
    settingsButton.type = "button";
    settingsButton.className = "aicg3d-skills-button";
    settingsButton.textContent = "打开模型设置";
    const pickerButton = document.createElement("button");
    pickerButton.type = "button";
    pickerButton.className = "aicg3d-skills-button is-primary";
    pickerButton.textContent = "选择 / 管理技能";
    pickerButton.disabled = !node;
    const done = document.createElement("button");
    done.type = "button";
    done.className = "aicg3d-skills-button";
    done.textContent = "关闭";
    footer.append(settingsButton, pickerButton, done);
    panel.append(header, body, footer);
    overlay.append(panel);
    document.body.append(overlay);
    activeDialog = { overlay };
    if (typeof overlay.showModal === "function") {
        try {
            overlay.showModal();
        } catch {
            // Browser fallback: the CSS overlay is already visible.
        }
    }
    close.addEventListener("click", closeSettings);
    done.addEventListener("click", closeSettings);
    settingsButton.addEventListener("click", () => openSettings(node));
    pickerButton.addEventListener("click", () => openSkillManager(node));
    overlay.addEventListener("cancel", (event) => {
        event.preventDefault();
        closeSettings();
    });
    overlay.addEventListener("pointerdown", (event) => {
        if (event.target === overlay) closeSettings();
    });
}


async function openSelectedSkillPreview(node) {
    if (!node) return;
    try {
        const skills = await loadSkills();
        const widget = (node.widgets || []).find((item) => ["技能包", "当前技能"].includes(String(item?.name || "")));
        const current = String(widget?.value || "");
        const selected = skills.find((item) => [item.id, item.name, item.original_name].includes(current));
        await openSkillPreview(selected || skills[0] || { id: current, name: current || "技能" }, node);
    } catch (error) {
        window.alert(String(error.message || error));
    }
}


function addHelpButton(node) {
    if (!node || node.__aicg3dHelpButtonAdded) return;
    node.__aicg3dHelpButtonAdded = true;
    node.addWidget("button", "使用说明", null, () => openSkillHelp(node));
    node.setSize([Math.max(node.size?.[0] || 300, 330), Math.max(node.size?.[1] || 180, 220)]);
}


function addSkillPreviewButton(node) {
    if (!node || node.__aicg3dSkillPreviewButtonAdded) return;
    node.__aicg3dSkillPreviewButtonAdded = true;
    node.addWidget("button", "技能演示", null, () => openSelectedSkillPreview(node));
}


function addSkillManagerButton(node) {
    if (!node || node.__aicg3dSkillManagerButtonAdded) return;
    node.__aicg3dSkillManagerButtonAdded = true;
    node.addWidget("button", "选择 / 管理技能", null, () => openSkillManager(node));
    node.setSize([Math.max(node.size?.[0] || 300, 320), Math.max(node.size?.[1] || 130, 170)]);
}

installSkillHoverPreview();

app.registerExtension({
    name: "AICG3D.SKILLS.Settings",
    async setup() {
        await loadSkills().catch(() => {});
    },
    async nodeCreated(node) {
        const name = nodeClass(node);
        if (name === SETTINGS_NODE || name === EXPANDER_NODE) {
            addSettingsButton(node);
        }
        if (name === SETTINGS_NODE) {
            configureSettingsNodeWidgets(node);
        }
        if (name === EXPANDER_NODE) {
            configureCompactExpanderWidgets(node);
            configureQuickTaskMode(node);
            configureTaskModeBehavior(node);
        }
        if (name === EXPANDER_NODE || name === "AICG3D_SKILLS_SkillSelector" || name === SKILL_MANAGER_NODE) {
            addSkillManagerButton(node);
        }
        if (name === EXPANDER_NODE || name === "AICG3D_SKILLS_SkillSelector") {
            addSkillPreviewButton(node);
        }
        if (name === EXPANDER_NODE || name === "AICG3D_SKILLS_SkillSelector") {
            addHelpButton(node);
        }
    },
});

if (typeof window !== "undefined") {
    window.AICG3DSkills = {
        openSettings,
        reload: () => {
            configCache = null;
        },
    };
}
