# Copyright (C) 2026 goohai <https://github.com/goohai/Goohai-MiniMax-H3_Integration>
# SPDX-License-Identifier: GPL-3.0-or-later
#
# 本文件基于上游 Goohai-MiniMax-H3_Integration 修改（2026-09-12）：
# 本地 GGUF 参考图降采样与上下文上限、模型目录解析层级、日志前缀、
# RunningHub App id 改为可用环境变量覆盖。
# 原始许可证声明见 third_party/LICENSE-Goohai-MiniMax-H3_Integration-GPL-3.0-or-later.txt

from __future__ import annotations

import asyncio
import base64
from difflib import SequenceMatcher
import gc
import json
import logging
import os
import platform
from pathlib import Path
import re
import shutil
import sys
import tempfile
import threading
import urllib.error
import urllib.parse
import urllib.request

import aiohttp
from aiohttp import web
import folder_paths
from server import PromptServer


PLUGIN_DIR = Path(__file__).resolve().parents[1]
SETTINGS_FILE = PLUGIN_DIR / "optimizer_settings.json"

DEFAULT_CONFIG = {
    "mode": "api",
    "provider": "runninghub",
    "api_url": "https://www.runninghub.cn/openapi/v2",
    "api_key": "",
    "model": "openai/gpt-5.6-sol",
    "protocol": "runninghub",
    "read_media": True,
    "output_language": "中文",
    "local_model": "",
    "local_mmproj": "",
    "local_device": "cuda",
    "auto_optimize": False,
}
PROVIDERS = {
    "openai": ("https://api.openai.com/v1", "gpt-4.1-mini", "openai"),
    "gemini": ("https://generativelanguage.googleapis.com/v1beta", "gemini-2.5-flash", "gemini"),
    "openrouter": ("https://openrouter.ai/api/v1", "google/gemini-2.5-flash", "openai"),
    "dashscope": ("https://dashscope.aliyuncs.com/compatible-mode/v1", "qwen-vl-max", "openai"),
    "siliconflow": ("https://api.siliconflow.cn/v1", "Qwen/Qwen2.5-VL-72B-Instruct", "openai"),
    "runninghub": ("https://www.runninghub.cn/openapi/v2", "openai/gpt-5.6-sol", "runninghub"),
}
# RunningHub 的 AI App id（继承自上游 Goohai-MiniMax-H3_Integration）。
# 想改用你自己在 RunningHub 上的 App，设置环境变量 AICG3D_RUNNINGHUB_APP_ID 即可，
# 不必改代码。
RUNNINGHUB_APP_ID = (
    os.environ.get("AICG3D_RUNNINGHUB_APP_ID") or "2089252473927196673"
).strip()
RUNNINGHUB_MODELS = (
    "openai/gpt-5.6-sol", "openai/gpt-5.6-sol-saver", "openai/gpt-5.6-terra",
    "openai/gpt-5.6-terra-saver", "openai/gpt-5.5", "openai/gpt-5.5-saver",
    "openai/gpt-5.6-luna", "openai/gpt-5.6-luna-saver", "google/gemini-3.1-flash-lite-preview",
    "google/gemini-3.5-flash", "openai/gpt-5.5-pro", "anthropic/claude-fable-5",
    "openai/gpt-5.4-pro", "anthropic/claude-opus-5", "anthropic/claude-opus-4.8",
    "anthropic/claude-opus-4.7", "glm-5.2", "anthropic/claude-opus-4.6", "openai/gpt-5.4",
    "openai/gpt-5.3-codex", "glm-5.1", "glm-5-turbo", "qwen/qwen3.8-max",
    "anthropic/claude-sonnet-4.6", "glm-5", "anthropic/claude-sonnet-5",
    "qwen/qwen3.7-max", "glm-5v-turbo", "qwen/qwen3.7-plus", "deepseek/deepseek-v4-pro",
    "xai/grok-4.6", "xai/grok-4.5", "xai/grok-4.3", "qwen/qwen3.6-plus",
    "google/gemini-3.1-pro-preview", "bytedance/doubao-seed-evolving",
    "bytedance/doubao-seed-2.1-pro", "anthropic/claude-sonnet-4.5",
    "bytedance/doubao-seed-2.1-turbo", "anthropic/claude-opus-4.5",
    "bytedance/doubao-seed-2.0-pro", "bytedance/doubao-seed-2.0-code",
    "deepseek/deepseek-v4-flash", "qwen/qwen3.6-flash", "openai/gpt-5.4-mini",
    "openai/gpt-5.4-nano", "google/gemini-3-flash-preview", "google/gemini-2.5-flash",
    "bytedance/doubao-seed-2.0-lite", "bytedance/doubao-seed-2.0-mini",
    "minimax/minimax-m2.7", "anthropic/claude-haiku-4.5", "qwen/qwen3.6-max-preview",
    "anthropic/claude-haiku-4.5-saver", "anthropic/claude-opus-4.6-saver",
    "anthropic/claude-opus-4.7-saver", "anthropic/claude-opus-4.8-saver",
    "anthropic/claude-sonnet-4.6-saver", "google/gemini-2.5-pro",
    "google/gemini-3.5-flash-lite", "google/gemini-3.6-flash",
)
RUNNINGHUB_DETAIL_URL = f"https://www.runninghub.cn/call-api/api-detail/{RUNNINGHUB_APP_ID}?apiType=4"
_RUNNINGHUB_MODELS_CACHE: tuple[str, ...] = RUNNINGHUB_MODELS
_RUNNINGHUB_MODELS_LOCK = asyncio.Lock()
_ROUTES_REGISTERED = False
_ACTIVE_REQUESTS: dict[str, asyncio.Task] = {}
_ACTIVE_CANCEL_EVENTS: dict[str, threading.Event] = {}
_ACTIVE_RH_TASKS: dict[str, tuple[str, str]] = {}
_GGUF_LOCK = threading.RLock()
_GGUF_MODEL = None
_GGUF_HANDLER = None
_GGUF_CONFIG: tuple[str, str, str] | None = None
_LOGGER = logging.getLogger("AICG3D.prompt_optimizer")
# Qwen3.5/Qwen3-VL place every reference image as one large multimodal batch. A
# single full-resolution screenshot already needs ~2000 tokens, so both the
# context window and the per-image resolution must stay bounded.
_GGUF_CONTEXT = 32768
_GGUF_CONTEXT_FALLBACK = 16384
IMAGE_MAX_SIDE = 512
_IMAGE_JPEG_QUALITY = 82
_MEDIA_IMAGE_LIMIT = 12
_MEDIA_FALLBACK_NOTE = (
    "\nThis request reached you without the reference pixels. Write the prompt from the user's text and the "
    "reference labels only, and never invent visual details that were not supplied."
)


def _llm_root() -> Path:
    # AICG3D：本模块位于 ComfyUI/custom_nodes/comfyui-AICG3D/h3goohai/，
    # 因此向上三层才是 ComfyUI 根目录。
    return Path(__file__).resolve().parents[3] / "models" / "llm"


def _is_visual_model(path: Path) -> bool:
    if not path.is_dir() or not (path / "config.json").is_file():
        return False
    try:
        config = json.loads((path / "config.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    text = json.dumps(config, ensure_ascii=False).lower()
    markers = (
        "qwen2-vl", "qwen2.5-vl", "qwen3-vl", "qwen-vl", "qwen2_vl", "qwen2_5_vl", "qwen3_vl",
        "vision", "visual", "gemma3", "gemma-3", "gemma4", "gemma-4", "minicpm-v", "internvl",
    )
    if not any(marker in text for marker in markers):
        return False
    return any((path / name).exists() for name in ("processor_config.json", "preprocessor_config.json", "tokenizer_config.json"))


def _is_auxiliary_gguf(path: Path) -> bool:
    name = path.name.lower()
    return any(marker in name for marker in ("mtp-", "draft-", "assistant-", "dflash-"))


def _is_mmproj(path: Path) -> bool:
    name = path.name.lower()
    return path.is_file() and path.suffix.lower() == ".gguf" and any(
        marker in name for marker in ("mmproj", "mm-projector", "projector")
    )


_GGUF_PRECISION_SUFFIX = re.compile(
    r"(?:[-_.](?:q\d+(?:[_-][a-z0-9]+)*|iq\d+(?:[_-][a-z0-9]+)*|f16|f32|fp16|fp32|bf16))+$",
    re.IGNORECASE,
)


def _gguf_identity(name: str, *, projector: bool = False) -> str:
    stem = Path(name).stem
    if projector:
        stem = re.sub(r"^(?:mmproj|mm-projector|projector)[-_. ]*", "", stem, flags=re.IGNORECASE)
    stem = _GGUF_PRECISION_SUFFIX.sub("", stem)
    return re.sub(r"[^a-z0-9]+", "", stem.lower())


def _gguf_model_signature(name: str) -> tuple[str, str] | None:
    """Return a stable model family/version and parameter size from loose filenames."""
    normalized = Path(name).stem.lower().replace("_", "-")
    family = re.search(r"(qwen\s*-?\s*3(?:[.\-]?\d+)?(?:\s*-?\s*vl)?)", normalized)
    if not family:
        family = re.search(r"(gemma\s*-?\s*[34](?:[.\-]?\d+)?)", normalized)
    size = re.search(r"(?<!\d)(\d+(?:\.\d+)?)\s*b(?![a-z])", normalized)
    if not family or not size:
        return None
    family_key = re.sub(r"[^a-z0-9]+", "", family.group(1))
    return family_key, f"{size.group(1)}b"


def _matching_mmproj(model_path: Path) -> list[Path]:
    root = _llm_root()
    identity = _gguf_identity(model_path.name)
    projectors = [path for path in root.rglob("*.gguf") if _is_mmproj(path)] if root.is_dir() else []
    exact = [path for path in projectors if _gguf_identity(path.name, projector=True) == identity]
    if exact:
        return sorted(exact, key=lambda path: path.name.lower())
    # Projectors are commonly named only by model generation and parameter
    # size, while the main model may add UD, publisher or quantization tokens.
    # First keep only the same model/version/size, then choose the closest name.
    signature = _gguf_model_signature(model_path.name)
    compatible = [path for path in projectors if signature and _gguf_model_signature(path.name) == signature]
    if compatible:
        return sorted(compatible, key=lambda path: path.name.lower())
    # Publisher bundles rename projectors by hand ("Qwe3.8-mmproj-BF16.gguf" for
    # "Qwen3.8-27B-UD-IQ4_XS.gguf"), which no name heuristic can match. A
    # projector stored next to the model is still the best guess, and the
    # settings dialog lets the user override the choice.
    sibling = [path for path in projectors if path.parent == model_path.parent]
    if sibling:
        ratios = {
            path: SequenceMatcher(None, identity, _gguf_identity(path.name, projector=True)).ratio()
            for path in sibling
        }
        best_ratio = max(ratios.values())
        return sorted(
            [path for path, ratio in ratios.items() if ratio == best_ratio],
            key=lambda path: path.name.lower(),
        )
    scored = []
    for path in projectors:
        candidate = _gguf_identity(path.name, projector=True)
        containment = 1 if identity in candidate or candidate in identity else 0
        ratio = SequenceMatcher(None, identity, candidate).ratio()
        scored.append(((containment, ratio), path))
    if not scored:
        return []
    best = max(score for score, _path in scored)
    # Stay conservative and reject weak names when nothing else matched.
    if best[0] == 0 and best[1] < 0.72:
        return []
    return sorted(
        [path for score, path in scored if score == best],
        key=lambda path: path.name.lower(),
    )


def _gguf_handler_name(path: Path) -> str | None:
    name = path.name.lower()
    if re.search(r"qwen[-_. ]?3[._-]?(?:5|6|8)", name):
        return "qwen35"
    if "qwen3-vl" in name or "qwen3vl" in name:
        return "qwen3vl"
    if re.search(r"gemma[-_. ]?4", name):
        return "gemma4"
    if re.search(r"gemma[-_. ]?3", name):
        return "gemma3"
    return None


def _mmproj_options() -> list[str]:
    """Every projector file under models/llm, for the manual picker in the settings dialog."""
    root = _llm_root()
    if not root.is_dir():
        return []
    return sorted(
        {path.relative_to(root).as_posix() for path in root.rglob("*.gguf") if _is_mmproj(path)},
        key=lambda item: item.lower(),
    )


def _scan_visual_models() -> list[dict]:
    root = _llm_root()
    if not root.is_dir():
        return []
    result = []
    for path in sorted(root.iterdir(), key=lambda item: item.name.lower()):
        if _is_visual_model(path):
            result.append({"name": path.name, "path": str(path), "relative_path": path.name, "format": "transformers"})
    for path in sorted(root.rglob("*.gguf"), key=lambda item: str(item).lower()):
        if _is_mmproj(path) or _is_auxiliary_gguf(path) or _gguf_handler_name(path) is None:
            continue
        relative = path.relative_to(root).as_posix()
        candidates = _matching_mmproj(path)
        result.append({
            "name": path.name,
            "path": str(path),
            "relative_path": relative,
            "format": "gguf",
            "mmproj_candidates": [candidate.relative_to(root).as_posix() for candidate in candidates],
        })
    return result


def _find_visual_model(selected: str) -> dict | None:
    return next((item for item in _scan_visual_models() if item["relative_path"] == selected), None)


def _normalize_config(data: dict | None) -> dict:
    current = DEFAULT_CONFIG
    data = data if isinstance(data, dict) else {}
    provider = str(data.get("provider") or current["provider"]).lower()
    preset = PROVIDERS.get(provider)
    config = {
        "mode": "local" if str(data.get("mode") or current.get("mode") or "api").lower() == "local" else "api",
        "provider": provider,
        "api_url": str(data.get("api_url") or (preset[0] if preset else current["api_url"])).strip(),
        "api_key": str(data.get("api_key") if "api_key" in data else current["api_key"]),
        "model": str(data.get("model") or (preset[1] if preset else current["model"])).strip(),
        "protocol": str(data.get("protocol") or (preset[2] if preset else current["protocol"])).lower(),
        "read_media": bool(data.get("read_media", current["read_media"])),
        "output_language": "中文" if str(data.get("output_language") or current.get("output_language") or "中文").lower() in {"中文", "chinese", "zh"} else "English",
        "local_model": str(data.get("local_model") or current.get("local_model") or "").strip(),
        "local_mmproj": str(data.get("local_mmproj") or current.get("local_mmproj") or "").strip(),
        "local_device": str(data.get("local_device") or current.get("local_device") or "cuda").lower(),
        "auto_optimize": bool(data.get("auto_optimize", current.get("auto_optimize", False))),
    }
    return config


def _read_saved_config() -> dict:
    try:
        payload = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else {}
    except (OSError, ValueError):
        return {}


def load_config() -> dict:
    """Return the persisted optimizer config merged over built-in defaults."""
    return _normalize_config({**DEFAULT_CONFIG, **_read_saved_config()})


def save_config(data: dict | None) -> dict:
    """Persist optimizer settings, preserving an existing API key when omitted."""
    incoming = dict(data or {})
    current = load_config()
    if not str(incoming.get("api_key") or "").strip() and current.get("api_key"):
        incoming["api_key"] = current["api_key"]
    config = _normalize_config({**current, **incoming})
    try:
        SETTINGS_FILE.write_text(
            json.dumps(config, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except OSError as error:
        _LOGGER.warning("无法保存提示词模型设置: %s", error)
    return config


def public_config(config: dict | None = None) -> dict:
    return _public_config(load_config() if config is None else _normalize_config(config))


def _public_config(config: dict) -> dict:
    return {
        **config,
        "api_key": "",
        "has_api_key": bool(config.get("api_key")),
        "runninghub_models": list(_RUNNINGHUB_MODELS_CACHE),
    }


def _runninghub_models_from_page(html: str) -> tuple[str, ...]:
    """Extract node 1 model choices from the public RunningHub Nuxt payload."""
    match = re.search(
        r'<script[^>]+id=["\']__NUXT_DATA__["\'][^>]*>([\s\S]*?)</script>',
        html,
        flags=re.IGNORECASE,
    )
    if not match:
        return ()
    try:
        payload = json.loads(match.group(1))
    except (TypeError, ValueError):
        return ()
    candidates = []
    for value in payload if isinstance(payload, list) else ():
        if not isinstance(value, str) or not value.startswith("[["):
            continue
        try:
            field_data = json.loads(value)
        except (TypeError, ValueError):
            continue
        if not isinstance(field_data, list) or not field_data or not isinstance(field_data[0], list):
            continue
        models = [str(item).strip() for item in field_data[0] if isinstance(item, str) and str(item).strip()]
        if len(models) >= 5 and sum("/" in item for item in models) >= 3:
            candidates.append(models)
    if not candidates:
        return ()
    return tuple(dict.fromkeys(max(candidates, key=len)))


async def _refresh_runninghub_models() -> tuple[str, ...]:
    global _RUNNINGHUB_MODELS_CACHE
    async with _RUNNINGHUB_MODELS_LOCK:
        timeout = aiohttp.ClientTimeout(total=15)
        async with aiohttp.ClientSession(timeout=timeout, trust_env=True) as session:
            async with session.get(RUNNINGHUB_DETAIL_URL) as response:
                if response.status != 200:
                    raise RuntimeError(f"RunningHub model list returned HTTP {response.status}")
                models = _runninghub_models_from_page(await response.text())
                if not models:
                    raise RuntimeError("RunningHub model list was not found in the application detail")
                _RUNNINGHUB_MODELS_CACHE = models
                return models


def _resolve_input_file(name: str) -> Path:
    value = str(name or "").strip()
    if not value:
        raise ValueError("参考素材文件名为空")
    annotated = folder_paths.get_annotated_filepath(value)
    if annotated and os.path.isfile(annotated):
        return Path(annotated)
    path = Path(folder_paths.get_input_directory()) / value
    if path.is_file():
        return path
    raise FileNotFoundError(f"找不到参考素材: {value}")


def _ffmpeg_path() -> str:
    found = shutil.which("ffmpeg")
    if found:
        return found
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception as error:
        raise RuntimeError("RunningHub 视频预处理需要 FFmpeg，但当前 ComfyUI 环境未找到 FFmpeg") from error


async def _runninghub_video(source_name: str, duration: float, output_path: Path) -> None:
    source = _resolve_input_file(source_name)
    limit = max(0.1, float(duration or 5))
    # fps=1 chooses one frame for every source second without changing source
    # playback speed. Audio is trimmed at the same point and copied at normal speed.
    command = [
        _ffmpeg_path(), "-hide_banner", "-loglevel", "error", "-y",
        "-i", str(source), "-t", f"{limit:.3f}",
        "-vf", "fps=1:start_time=0:round=down,scale=512:512:force_original_aspect_ratio=decrease:force_divisible_by=2",
        "-r", "1", "-c:v", "libx264", "-preset", "veryfast", "-crf", "25",
        "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "128k", "-shortest", str(output_path),
    ]
    process = await asyncio.create_subprocess_exec(
        *command, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )
    _stdout, stderr = await process.communicate()
    if process.returncode:
        raise RuntimeError("RunningHub 参考视频预处理失败: " + stderr.decode("utf-8", "replace")[-1000:])


async def _runninghub_upload(session: aiohttp.ClientSession, api_key: str, *, path: Path | None = None,
                             data_url: str | None = None, filename: str = "reference.jpg") -> str:
    form = aiohttp.FormData()
    if path is not None:
        form.add_field("file", path.read_bytes(), filename=path.name, content_type="video/mp4")
    else:
        try:
            header, encoded = str(data_url or "").split(",", 1)
            mime = header.split(";", 1)[0].split(":", 1)[1]
            form.add_field("file", base64.b64decode(encoded), filename=filename, content_type=mime)
        except Exception as error:
            raise ValueError("RunningHub 参考图片数据无效") from error
    async with session.post(
        "https://www.runninghub.cn/openapi/v2/media/upload/binary",
        headers={"Authorization": f"Bearer {api_key}"}, data=form,
    ) as response:
        body = await response.text()
        if response.status >= 400:
            raise RuntimeError(f"RunningHub 素材上传失败 ({response.status}): {body[:1000]}")
        data = json.loads(body)
    if data.get("code") not in (0, "0", None):
        raise RuntimeError(f"RunningHub 素材上传失败: {data.get('message') or data.get('msg') or data}")
    result = data.get("data") or {}
    value = result.get("fileName") or result.get("download_url")
    if not value:
        raise RuntimeError("RunningHub 素材上传响应缺少 fileName")
    return str(value)


async def _runninghub_cancel(api_key: str, task_id: str) -> None:
    if not api_key or not task_id:
        return
    timeout = aiohttp.ClientTimeout(total=20)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.post(
            "https://www.runninghub.cn/task/openapi/cancel",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={"apiKey": api_key, "taskId": task_id},
        ) as response:
            await response.read()


async def _runninghub_result_text(session: aiohttp.ClientSession, results: list) -> str:
    for item in results:
        if isinstance(item, dict) and str(item.get("text") or "").strip():
            return str(item["text"]).strip()
    for item in results:
        if not isinstance(item, dict):
            continue
        output_type = str(item.get("outputType") or item.get("fileType") or "").lower().lstrip(".")
        url = item.get("url") or item.get("fileUrl")
        if output_type not in {"txt", "text"} or not url:
            continue
        async with session.get(str(url)) as response:
            body = await response.read()
            if response.status >= 400:
                raise RuntimeError(f"RunningHub TXT 结果下载失败 ({response.status})")
        for encoding in ("utf-8-sig", "utf-8", "gb18030"):
            try:
                return body.decode(encoding).strip()
            except UnicodeDecodeError:
                continue
    raise RuntimeError("RunningHub 返回结果中没有文本或 TXT 文件")


def _local_model_path(config: dict) -> Path:
    selected = str(config.get("local_model") or "").strip()
    if not selected:
        raise ValueError("请先选择本地视觉模型")
    found = _find_visual_model(selected)
    if found is None:
        raise ValueError("所选本地模型不存在，或不是可识别的视觉模型")
    return Path(found["path"])


def _selected_local_model(config: dict) -> dict:
    selected = str(config.get("local_model") or "").strip()
    found = _find_visual_model(selected)
    if found is None:
        raise ValueError("所选本地模型不存在，或不是可识别的视觉模型")
    return found


def _selected_mmproj(config: dict, model: dict) -> Path:
    candidates = list(model.get("mmproj_candidates") or [])
    selected = str(config.get("local_mmproj") or "").strip()
    if selected:
        # 手动选择优先：文件名匹配（mmproj 自动识别）本来就常常靠不住，
        # 让用户自己指定的版本直接生效，只校验文件确实存在且是投影模型。
        root = _llm_root().resolve()
        path = (root / selected).resolve()
        if not path.is_file() or (path != root and root not in path.parents):
            raise ValueError("已选择的mmproj文件不存在")
        if not _is_mmproj(path):
            raise ValueError("已选择的文件不是mmproj视觉投影模型，请重新选择")
        return path
    if not candidates:
        raise ValueError("未找到与当前GGUF模型匹配的mmproj视觉模型，请在提示词优化设置里手动选择「视觉投影 (mmproj)」")
    if len(candidates) > 1:
        raise ValueError("检测到多个匹配的mmproj视觉模型，请在提示词优化设置里选择一个版本")
    return (_llm_root() / candidates[0]).resolve()


def _cuda_tag() -> str | None:
    try:
        import torch
        value = str(torch.version.cuda or "")
    except Exception:
        value = ""
    match = re.match(r"(\d+)\.(\d+)", value)
    return f"cu{match.group(1)}{match.group(2)}" if match else None


def _gguf_dependency_status() -> dict:
    system = platform.system().lower()
    machine = platform.machine().lower()
    python_tag = f"cp{sys.version_info.major}{sys.version_info.minor}"
    cuda_tag = _cuda_tag()
    platform_tag = "win_amd64" if system == "windows" and machine in {"amd64", "x86_64"} else (
        "linux_x86_64" if system == "linux" and machine in {"amd64", "x86_64"} else None
    )
    status = {
        "available": False,
        "reason": "",
        "system": platform.system(),
        "machine": platform.machine(),
        "python_tag": python_tag,
        "cuda_tag": cuda_tag or "",
        "release_url": "https://github.com/JamePeng/llama-cpp-python/releases",
        "wheel_url": "",
        "wheel_name": "",
    }
    try:
        import llama_cpp
        from llama_cpp.llama_chat_format import Qwen35ChatHandler  # noqa: F401
        status["available"] = True
        status["version"] = str(getattr(llama_cpp, "__version__", "unknown"))
        return status
    except Exception as error:
        status["reason"] = str(error)
    if system == "darwin":
        status["release_url"] = "https://github.com/JamePeng/llama-cpp-python/releases"
        return status
    if not cuda_tag or not platform_tag:
        return status
    # JamePeng release assets follow a stable version/cuda/python/platform
    # naming scheme. Resolve the current latest matching asset when online.
    try:
        request = urllib.request.Request(
            "https://api.github.com/repos/JamePeng/llama-cpp-python/releases?per_page=30",
            headers={"User-Agent": "Goohai-MiniMax-H3-Integration"},
        )
        with urllib.request.urlopen(request, timeout=8) as response:
            releases = json.load(response)
        marker = f"-{cuda_tag}-{'win' if system == 'windows' else 'linux'}-"
        for release in releases:
            if marker not in str(release.get("tag_name") or ""):
                continue
            for asset in release.get("assets") or []:
                name = str(asset.get("name") or "")
                if python_tag in name and platform_tag in name:
                    status["wheel_name"] = name
                    status["wheel_url"] = str(asset.get("browser_download_url") or "")
                    status["release_url"] = str(release.get("html_url") or status["release_url"])
                    return status
    except Exception:
        pass
    return status


def _unload_gguf_model() -> bool:
    global _GGUF_MODEL, _GGUF_HANDLER, _GGUF_CONFIG
    with _GGUF_LOCK:
        loaded = _GGUF_MODEL is not None or _GGUF_HANDLER is not None
        try:
            if _GGUF_MODEL is not None:
                _GGUF_MODEL.close()
        except Exception:
            pass
        try:
            stack = getattr(_GGUF_HANDLER, "_exit_stack", None)
            if stack is not None:
                stack.close()
        except Exception:
            pass
        _GGUF_MODEL = _GGUF_HANDLER = _GGUF_CONFIG = None
    gc.collect()
    try:
        import torch
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    except Exception:
        pass
    return loaded


def _data_url_image(data_url: str):
    from io import BytesIO
    from PIL import Image
    _header, encoded = str(data_url).split(",", 1)
    return Image.open(BytesIO(base64.b64decode(encoded))).convert("RGB")


def _downscaled_jpeg(image, max_side: int = IMAGE_MAX_SIDE) -> str:
    """Encode a decoded image as a data URL with its long edge capped."""
    from io import BytesIO
    from PIL import Image

    width, height = image.size
    scale = min(1.0, float(max_side) / float(max(width, height) or 1))
    if scale < 1.0:
        image = image.resize(
            (max(1, int(round(width * scale))), max(1, int(round(height * scale)))),
            Image.LANCZOS,
        )
    buffer = BytesIO()
    image.convert("RGB").save(buffer, "JPEG", quality=_IMAGE_JPEG_QUALITY, optimize=True)
    return "data:image/jpeg;base64," + base64.b64encode(buffer.getvalue()).decode("ascii")


def _shrink_data_url_image(data_url: str, max_side: int = IMAGE_MAX_SIDE) -> str:
    """Cap one inbound reference image; unusable input is forwarded untouched.

    Without this cap llama.cpp receives multi-thousand-token media chunks, fails to
    place them in the hybrid KV cache and aborts the request with
    "failed to find a memory slot for batch of size N" / "Media evaluation failed
    with error code 1". At IMAGE_MAX_SIDE each reference costs about 256 tokens.
    """
    text = str(data_url or "")
    if not text.startswith("data:") or "," not in text:
        return text
    header, encoded = text.split(",", 1)
    mime = header[5:].split(";", 1)[0].strip().lower()
    if not mime.startswith("image/"):
        return text
    try:
        from io import BytesIO
        from PIL import Image

        raw = base64.b64decode(encoded, validate=False)
        with Image.open(BytesIO(raw)) as source:
            width, height = source.size
            if max(width, height) <= max_side and mime in {"image/jpeg", "image/jpg"} and len(raw) <= 512 * 1024:
                return text
            return _downscaled_jpeg(source, max_side)
    except Exception:
        return text


def image_file_data_url(path, max_side: int = IMAGE_MAX_SIDE) -> str:
    """Encode a local reference image for the local engine at a bounded resolution."""
    from PIL import Image

    with Image.open(path) as source:
        return _downscaled_jpeg(source, max_side)


def _unload_comfy_models() -> None:
    """Release ComfyUI-managed models and cached allocations before/after local VLM use."""
    from comfy import model_management

    model_management.unload_all_models()
    gc.collect()
    model_management.soft_empty_cache()


def _local_generate(config: dict, payload: dict) -> str:
    """Run one local VLM request with ComfyUI models unloaded on both sides."""
    _unload_comfy_models()
    try:
        return _local_generate_impl(config, payload)
    finally:
        _unload_comfy_models()


def _local_generate_impl(config: dict, payload: dict) -> str:
    """Load one local VLM only for this request, then release its objects."""
    model_path = _local_model_path(config)
    if model_path.suffix.lower() == ".gguf":
        return _gguf_generate(config, payload)
    model = processor = inputs = output = generated = None
    try:
        import torch
        from transformers import AutoModelForImageTextToText, AutoProcessor, StoppingCriteria, StoppingCriteriaList
        cancel_event = payload.get("_cancel_event")

        class CancelledStoppingCriteria(StoppingCriteria):
            def __call__(self, input_ids, scores, **kwargs):
                return bool(cancel_event and cancel_event.is_set())
        device = config.get("local_device")
        if device not in {"cpu", "cuda"}:
            device = "cuda" if torch.cuda.is_available() else "cpu"
        dtype = torch.float16 if device == "cuda" else torch.float32
        processor = AutoProcessor.from_pretrained(str(model_path), trust_remote_code=True)
        model = AutoModelForImageTextToText.from_pretrained(
            str(model_path), torch_dtype=dtype, device_map="auto" if device == "cuda" else None,
            trust_remote_code=True,
        )
        if device == "cpu":
            model.to("cpu")
        user_prompt = str(payload.get("prompt") or "")
        media = payload.get("media") if isinstance(payload.get("media"), list) else []
        content = [{"type": "text", "text": "User prompt:\n" + user_prompt}]
        for item in media:
            label = str(item.get("label") or "")
            kind = str(item.get("kind") or "")
            if kind == "audio":
                content.append({"type": "text", "text": f"{label} is an uploaded audio reference; audio data is not transmitted."})
            else:
                for data_url in item.get("images") or []:
                    content.append({"type": "image", "image": _data_url_image(data_url)})
                    content.append({"type": "text", "text": f"This visual belongs to {label}; use the label, never a filename."})
        base_system = _system_prompt(
            str(payload.get("task") or "T2VA"), float(payload.get("duration") or 5),
            [str(item.get("label")) for item in media if item.get("label")],
            str(config.get("output_language") or "English"),
            payload.get("context") if isinstance(payload.get("context"), dict) else {}, user_prompt,
        )
        extra_system = str(payload.get("system") or "").strip()
        system = f"{base_system}\n\n{extra_system}" if extra_system else base_system
        messages = [{"role": "system", "content": [{"type": "text", "text": system}]}, {"role": "user", "content": content}]
        text = processor.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        images = [part["image"] for part in content if part.get("type") == "image"]
        inputs = processor(text=[text], images=images or None, padding=True, return_tensors="pt")
        input_device = next(model.parameters()).device
        inputs = {key: value.to(input_device) if hasattr(value, "to") else value for key, value in inputs.items()}
        with torch.inference_mode():
            output = model.generate(
                **inputs, max_new_tokens=4096, do_sample=False,
                stopping_criteria=StoppingCriteriaList([CancelledStoppingCriteria()]),
            )
        if cancel_event and cancel_event.is_set():
            raise RuntimeError("提示词优化已取消")
        generated = output[:, inputs["input_ids"].shape[1]:]
        return processor.batch_decode(generated, skip_special_tokens=True)[0].strip()
    finally:
        output = generated = inputs = model = processor = None
        gc.collect()
        try:
            import torch
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        except Exception:
            pass


def _create_gguf_model(model_path: Path, mmproj_path: Path, handler_name: str):
    """Load the local GGUF vision model, preferring the roomy context window.

    The larger window keeps multi-reference requests inside the KV cache; cards
    that cannot hold it fall back to the previous 16384 tokens.
    """
    from llama_cpp import Llama
    from llama_cpp.llama_chat_format import Gemma3ChatHandler, Gemma4ChatHandler, Qwen35ChatHandler, Qwen3VLChatHandler

    last_error: Exception | None = None
    for context_size in (_GGUF_CONTEXT, _GGUF_CONTEXT_FALLBACK):
        handler_cls = {
            "qwen35": Qwen35ChatHandler,
            "qwen3vl": Qwen3VLChatHandler,
            "gemma4": Gemma4ChatHandler,
            "gemma3": Gemma3ChatHandler,
        }.get(handler_name, Qwen3VLChatHandler)
        kwargs = {"clip_model_path": str(mmproj_path), "verbose": False}
        if handler_name in {"qwen35", "gemma4"}:
            kwargs["enable_thinking"] = False
        else:
            kwargs["force_reasoning"] = False
        handler = handler_cls(**kwargs)
        try:
            model = Llama(
                model_path=str(model_path), chat_handler=handler,
                n_gpu_layers=-1, n_ctx=context_size, verbose=False,
            )
        except Exception as error:
            last_error = error
            try:
                handler.close()
            except Exception:
                pass
            continue
        return model, handler
    raise last_error if last_error is not None else RuntimeError("本地GGUF视觉模型加载失败")


def _is_media_evaluation_error(error: Exception) -> bool:
    text = str(error).lower()
    return "media evaluation failed" in text or "memory slot" in text


def _gguf_generate(config: dict, payload: dict) -> str:
    global _GGUF_MODEL, _GGUF_HANDLER, _GGUF_CONFIG
    dependency = _gguf_dependency_status()
    if not dependency.get("available"):
        suffix = f"\n下载地址: {dependency['wheel_url']}" if dependency.get("wheel_url") else (
            f"\n发布页面: {dependency['release_url']}"
        )
        raise RuntimeError(
            "GGUF视觉模型依赖不可用。"
            f"当前环境: {dependency['system']} {dependency['machine']} / {dependency['python_tag']} / "
            f"{dependency.get('cuda_tag') or '无CUDA'}。{suffix}\n安装后请重启ComfyUI。"
        )
    model = _selected_local_model(config)
    model_path = Path(model["path"])
    mmproj_path = _selected_mmproj(config, model)
    handler_name = _gguf_handler_name(model_path)
    if handler_name not in {"qwen35", "qwen3vl", "gemma4", "gemma3"}:
        raise ValueError("当前GGUF视觉模型类型暂不支持")
    cancel_event = payload.get("_cancel_event")
    target_config = (str(model_path), str(mmproj_path), handler_name)
    try:
        with _GGUF_LOCK:
            if _GGUF_MODEL is None or _GGUF_CONFIG != target_config:
                _unload_gguf_model()
                _GGUF_MODEL, _GGUF_HANDLER = _create_gguf_model(model_path, mmproj_path, handler_name)
                _GGUF_CONFIG = target_config
        user_prompt = str(payload.get("prompt") or "")
        media = payload.get("media") if isinstance(payload.get("media"), list) else []
        labels = [str(item.get("label")) for item in media if item.get("label")]
        base_system = _system_prompt(
            str(payload.get("task") or "T2VA"), float(payload.get("duration") or 5), labels,
            str(config.get("output_language") or "English"),
            payload.get("context") if isinstance(payload.get("context"), dict) else {}, user_prompt,
        )
        extra_system = str(payload.get("system") or "").strip()
        system = f"{base_system}\n\n{extra_system}" if extra_system else base_system
        content = [{"type": "text", "text": "User prompt:\n" + user_prompt}]
        labels_only = [{"type": "text", "text": "User prompt:\n" + user_prompt}]
        attached_images = 0
        for item in media:
            label = str(item.get("label") or "")
            if str(item.get("kind") or "") == "audio":
                note = f"{label} is an uploaded audio reference; audio data is not transmitted."
                content.append({"type": "text", "text": note})
                labels_only.append({"type": "text", "text": note})
                continue
            for index, data_url in enumerate(item.get("images") or []):
                caption = f"{label} visual {index + 1}."
                labels_only.append({"type": "text", "text": caption})
                if attached_images >= _MEDIA_IMAGE_LIMIT:
                    continue
                attached_images += 1
                content.append({"type": "text", "text": caption})
                content.append({"type": "image_url", "image_url": {"url": _shrink_data_url_image(data_url)}})
        if cancel_event and cancel_event.is_set():
            raise RuntimeError("提示词优化已取消")
        try:
            with _GGUF_LOCK:
                result = _GGUF_MODEL.create_chat_completion(
                    messages=[{"role": "system", "content": system}, {"role": "user", "content": content}],
                    max_tokens=4096, temperature=0.2, top_p=0.9,
                )
        except Exception as error:
            if not attached_images or not _is_media_evaluation_error(error):
                raise
            # Even with bounded images an unusually heavy reference set can exhaust
            # the vision cache. Reload clean and retry without pixels so the user
            # still receives an optimized prompt instead of a hard failure.
            _LOGGER.warning("本地视觉模型无法评估参考媒体，改用纯文本重试: %s", error)
            with _GGUF_LOCK:
                _unload_gguf_model()
                _GGUF_MODEL, _GGUF_HANDLER = _create_gguf_model(model_path, mmproj_path, handler_name)
                _GGUF_CONFIG = target_config
                result = _GGUF_MODEL.create_chat_completion(
                    messages=[
                        {"role": "system", "content": system + _MEDIA_FALLBACK_NOTE},
                        {"role": "user", "content": labels_only},
                    ],
                    max_tokens=4096, temperature=0.2, top_p=0.9,
                )
        if cancel_event and cancel_event.is_set():
            raise RuntimeError("提示词优化已取消")
        return str(result["choices"][0]["message"]["content"] or "").removeprefix(": ").strip()
    finally:
        _unload_gguf_model()


def _endpoint(config: dict) -> str:
    base = config["api_url"].rstrip("/")
    if config["protocol"] == "gemini":
        if re.search(r":generateContent(?:\?|$)", base):
            return base
        return f"{base}/models/{urllib.parse.quote(config['model'], safe='-_.')}:generateContent"
    if config["protocol"] == "responses":
        return base if base.endswith("/responses") else f"{base}/responses"
    if base.endswith("/chat/completions"):
        return base
    return f"{base}/chat/completions"


def _system_prompt(
    task: str,
    duration: float,
    labels: list[str],
    output_language: str = "English",
    context: dict | None = None,
    user_prompt: str = "",
) -> str:
    task_upper = task.upper()
    language_rule = (
        "Write the final answer in Simplified Chinese."
        if str(output_language or "").lower().startswith(("zh", "chinese", "中文"))
        else f"Write the final answer in {output_language or 'English'}."
    )
    direct_rule = (
        "Return only the final prompt text that can be copied and pasted directly. "
        "Do not include introductions, summaries, analysis, explanations, notes, quality checks, usage advice, "
        "follow-up questions, markdown fences, bullet lists, or extra headings. "
        "Only MiniMax H3 tasks may use the required H3 section names. "
    )
    if task_upper == "IMAGE_REVERSE":
        return (
            "You are an expert visual prompt analyst. Follow the attached Skill instructions exactly. "
            "Analyze the supplied image evidence silently, then return only one complete natural-language image-generation prompt. "
            "Integrate the useful subject, appearance, action, environment, composition, camera, lighting, color, material, "
            "and style details into one directly pasteable paragraph. Do not output an introduction, reverse summary, "
            "structured breakdown, reference-role explanation, uncertainty list, exclusion list, analysis, or usage advice. "
            "Silently replace rights-sensitive identities, logos, protected characters, watermarks, and visible text with neutral "
            "descriptions. Do not invent unseen people, props, text, brands, or story events. "
            + direct_rule + language_rule
        )
    if task_upper == "VIDEO_REVERSE":
        return (
            "You are an expert audiovisual reverse-prompt analyst. Follow the attached Skill instructions exactly. "
            "Analyze the supplied video evidence silently and return only a copy-ready MiniMax H3 Ref2VA prompt "
            "containing exactly subject_definitions, summary, retention_analysis, detailed_description, "
            "overall_soundscape, and non_diegetic_music in that order. "
            "Do not append a shot timeline, reverse summary, analysis notes, uncertainty list, compliance notes, "
            "usage advice, or any text after non_diegetic_music. "
            "Silently convert source-specific people, brands, dialogue, music, protected characters, logos, and signature "
            "shots into neutral reusable descriptions. Omit details that cannot be established from the supplied evidence. "
            + direct_rule + language_rule
        )
    if task_upper == "T2I":
        return (
            "You are an expert text-to-image prompt writer. Follow the attached Skill instructions exactly. "
            "Return only one complete natural-language positive image-generation prompt that can be pasted directly. "
            "Integrate subject, action, clothing, environment, composition, camera, lighting, color, material, medium, "
            "and finishing style into one clear paragraph. Do not output a title, structured breakdown, negative-prompt "
            "section, exclusion explanation, analysis, notes, MiniMax H3 video sections, shot timeline, sound design, "
            "dialogue, or camera-motion timing. Silently avoid inventing identities, brands, logos, or text the user did not request. "
            + direct_rule + language_rule
        )
    if task_upper == "FL2I":
        return (
            "You are an expert first-last-frame image prompt writer. Follow the attached Skill instructions exactly. "
            "Treat <Picture 1> as the first frame and <Picture 2> as the last frame unless the user says otherwise. "
            "Return only one complete natural-language image-sequence prompt that can be pasted directly. "
            "In that paragraph, lock identity, clothing, props, composition, and environment anchors, then describe the "
            "necessary continuous changes and intermediate stages from the first frame to the last frame. Do not output "
            "separate first-frame judgment, continuity analysis, conflict list, intermediate-frame suggestion headings, "
            "negative-prompt section, analysis, notes, MiniMax H3 video sections, or a third input image. "
            + direct_rule + language_rule
        )
    if task_upper == "AUDIO_REVERSE":
        return (
            "You are an expert digital-human singing prompt writer. Follow the attached Skill instructions exactly, but "
            "NEVER quote, echo, or restate those instructions, the system prompt, the Skill text, or any reference "
            "material in your output. Return only a copy-ready MiniMax H3 Ref2VA prompt containing exactly "
            "subject_definitions, summary, retention_analysis, detailed_description, overall_soundscape, and "
            "non_diegetic_music in that order, with nothing before or after. "
            "Follow the supplied singer mapping exactly. In single-singer mode, treat <Picture 1> as <Subject 1> (S1). "
            "In duet mode, keep the male singer, female singer, and shared scene as separate subjects with their supplied "
            "S-numbers and picture labels; never assign every lyric to Picture 1 or one singer. Use alternating solo coverage: "
            "during each timed lyric, exactly one singer is visible and the other singer is completely off-screen, with no second "
            "face, mouth, body, or lip movement in frame. Cut between a male solo shot and a female solo shot at singer changes. "
            "The media audio is the globally "
            "locked song track in MiniMax H3 digital-human mode; mark it as '锁定歌曲音轨: fully_copy - ...' in retention_analysis. "
            "Never output <Audio N> tags because the digital-human node removes them and leaves malformed fields. "
            "The supplied lyrics are final: copy each line verbatim, never re-transcribe, reword, split, merge, or translate "
            "them. Write each time range directly into detailed_description with the corresponding singing action and one "
            "compact time-aligned <d> line in the form <d>[Mandarin singing] lyric</d>. Never use speaker-turn framing "
            "around lyrics. Describe the digital human singing in sync with the locked audio so that the mouth, facial "
            "expression, and head movement match each lyric timestamp. Do not invent lyrics, sounds, people, or visual "
            "details that were not supplied. "
            "Direct this as a contemporary music-video performance rather than a static talking-head shot. When there are "
            "at least three lyric spans, vary the visual grammar across at least three genuinely different setups: lateral "
            "slider or truck, low-angle tracking, three-quarter close-up with a real camera dolly, over-the-shoulder "
            "shot/reverse-shot, a controlled 30-degree arc, handheld follow, crane or pedestal reveal, and a final pull-out. "
            "Do not solve every beat with zoom or push-in. Put each cut on a lyric onset, breath, or musical accent, never "
            "in the middle of a word. Keep the active singer's mouth readable and preserve screen direction, identity, "
            "clothing, and the shared spatial relationship across cuts; the inactive duet singer keeps the mouth closed and "
            "reacts naturally. "
            + direct_rule + language_rule
        )
    fl2va = task_upper == "FL2VA"
    full_reference = task_upper in {"REF2VA", "HYBRID", "H3_STANDARD"}
    context = context if isinstance(context, dict) else {}
    label_rule = (
        "FL2VA picture labels must be bare lowercase: picture 1 and picture 2, never angle brackets. "
        "This is a mandatory content requirement, not merely a label-format example: the final prompt must explicitly "
        "contain both exact tokens 'picture 1' and 'picture 2'. The first line must state that picture 1 is the exact "
        f"opening-frame anchor at 0.00s and picture 2 is the exact ending-frame anchor at {duration:.2f}s. Never omit, "
        "rename, translate, capitalize, or replace either token, even when the requested output language is Chinese."
        if fl2va else
        "All media labels must use angle brackets exactly, for example <picture 1>, <video 1>, <audio 1>."
    )
    if full_reference:
        structure = (
            "Return exactly these six sections in this order, with each heading followed by a colon: "
            "subject_definitions, summary, retention_analysis, detailed_description, overall_soundscape, "
            "non_diegetic_music. Formatting is strict: every section heading must occupy its own line; put a newline "
            "immediately after the colon, write that section's content on the following line, and put one blank line "
            "between sections. Never place a heading and its content on the same line, and never join multiple sections "
            "into one paragraph. In subject_definitions, define reusable visible content as <Subject N> and cite "
            "its source label using one short sentence and no more than four identifying visual traits; define "
            "standalone <Picture N> only for a concrete frame anchor. In summary, use one sentence beginning "
            "with a square-bracketed combination of only the relationships that apply: keyframe completion, "
            "reference generation, video editing, video continuation, audio reuse, or audio reference. In "
            "retention_analysis, write one compact line per label and use fully_preserved, partially_preserved, "
            "attribute_transfer, or weak_reference for visual content, and fully_copy, partially_copy, reference, "
            "or weak_reference for audio. A relationship marker alone is never a complete entry. Every line must use "
            "the exact form '<label>: marker - explanation' and add a concise, concrete explanation after the hyphen. "
            "For fully_preserved, state which identity, appearance, scene, composition, or structural properties remain "
            "unchanged in the target. For attribute_transfer, state exactly which appearance, motion, scene, camera, "
            "timing, or structural attributes transfer from the reference and which target receives them. For audio, "
            "state whether the complete signal is copied unchanged, only selected portions or layers are copied, or "
            "only timbre, rhythm, delivery, or other specified attributes are referenced. Use enough information to "
            "make each reference relationship operational, normally one full sentence per label, but do not repeat an "
            "exhaustive appearance inventory already stated in subject_definitions. Never output bare entries such as "
            "'<picture 1>: fully_preserved', '<video 1>: attribute_transfer', or '<audio 1>: fully_copy'. "
            "Make detailed_description action-first, chronological, and production-ready. Give the scene a clear "
            "dramatic progression—establishment, development, a meaningful visual or emotional beat, and a resolved "
            "ending—without changing the user's intended event. Describe subject blocking, observable state changes, "
            "composition, camera movement, and the final visual landing. Use [Shot 1] and timed later shots only for "
            "motivated real cuts that reveal new information; otherwise design a fluid continuous shot. Normally allow "
            "about 350-700 Chinese characters or 220-450 English words for the complete six-section result, and use "
            "more when duration, dialogue, multiple subjects, or genuine shot complexity requires it."
        )
    else:
        structure = (
            "Return exactly these three sections in order: integrated_multimodal_description, overall_soundscape, "
            "non_diegetic_music. Formatting is strict: every section heading must occupy its own line; put a newline "
            "immediately after the colon, write that section's content on the following line, and put one blank line "
            "between sections. Never place a heading and its content on the same line. Build a complete audiovisual "
            "progression rather than merely paraphrasing the user's sentence. Use [Shot 1] for the opening and "
            "timestamps only for motivated real later cuts. For I2VA, "
            "anchor the supplied picture at 0.00s and develop forward. For L2VA, infer a plausible opening and "
            "converge exactly to the supplied picture at the end. For FL2VA, describe one continuous, observable "
            "motion path from picture 1 at 0.00s to picture 2 at the target end time. Give the main description enough "
            "detail to establish the opening composition, action onset, intermediate development, camera evolution, "
            "and a visually resolved ending within the supplied duration. In FL2VA, mention picture 1 again when "
            "establishing the opening state and picture 2 again when describing the final visual landing; both labels "
            "are compulsory and must not be replaced by generic phrases such as 'the first image' or 'the last image'."
        )

    keyframe_lines = []
    for item in context.get("keyframes") or []:
        if not isinstance(item, dict) or not item.get("label") or not item.get("role"):
            continue
        role_text = {
            "exact_first_frame": "is the exact first-frame anchor at 0.00s",
            "exact_last_frame": f"is the exact last-frame anchor at {duration:.2f}s",
            "keyframe": "is a concrete visual keyframe anchor",
        }.get(str(item["role"]), "is a visual reference")
        keyframe_lines.append(f"{item['label']} {role_text}")
    keyframe_rule = (
        "Keyframe roles supplied by the node: " + "; ".join(keyframe_lines) + ". Preserve these roles exactly."
        if keyframe_lines else
        "No concrete keyframe role was supplied by the node; do not invent one."
    )

    audio_mode = str(context.get("audio_mode") or "native")
    audio_rule = {
        "lock_source": (
            "Audio mode is original-audio output. State only that the source video's original audio is preserved "
            "unchanged as the complete target soundtrack and mark it fully_copy. Because the optimizer does not "
            "receive or hear the audio binary, do not identify, describe, classify, or invent any dialogue, music, "
            "ambience, sound effect, instrument, language, rhythm, or other audible content. In overall_soundscape, "
            "write only the selected-language equivalent of 'Preserve the source video's original audio unchanged.' "
            "Do not add any new sound, voice, animal vocalization, ambience, or music."
        ),
        "reference_only": (
            "Audio mode is reference-only: treat supplied audio as audio reference; do not claim its waveform "
            "is copied into the final soundtrack."
        ),
        "remix_source": (
            "Audio mode is source-audio remix: describe only partial copying or remixing of the supplied audio, "
            "never a 1:1 complete copy."
        ),
        "native": "Audio mode is automatic generation: do not claim any uploaded audio is copied into the final output.",
    }.get(audio_mode, "Describe the audio relationship conservatively and do not invent how it is used.")

    singing_rule = ""
    if re.search(
        r"唱|歌曲|歌词|歌唱|演唱|口型|嘴型|对口型|lip\s*sync|sing(?:ing|s)?|lyrics?|vocal",
        user_prompt,
        flags=re.IGNORECASE,
    ):
        singing_rule = (
            " The request involves singing or lip synchronization. Require accurate phoneme-level lip and jaw "
            "synchronization throughout the vocals: mouth movement should follow syllable onset and release, clear "
            "consonant closures, natural vowel shapes, pauses and breaths, and sustained notes; the mouth rests "
            "naturally during non-vocal spans. Also require stable facial identity and continuous mouth motion without "
            "generic loops, visible delay, frozen lips, or facial deformation. Do not reduce a singing performance "
            "to lip movement while the rest of the body remains still. Unless the user explicitly requests restrained "
            "or static performance, design evolving full-body or upper-body performance across the timeline: shifting "
            "weight, torso and shoulder rhythm, head movement, gaze changes, expressive but natural hand and arm "
            "phrasing, and transitions between distinct gestures. Make these movements non-repetitive and responsive "
            "to musical phrases, accents, pauses, intensity changes, and vocal emotion without inventing exact unheard "
            "beats. Coordinate purposeful camera motion and changing shot emphasis with the performance so the image "
            "does not feel like a static portrait with moving lips. Keep lip-sync requirements compact, but give the "
            "visible performance and camera progression enough concrete detail to guide a lively result. Because the audio binary is not "
            "transmitted to the optimizer, never invent exact lyrics, notes, beats, or timestamps and never claim "
            "to have analyzed or heard the file."
        )
    transfer_rule = ""
    if re.search(
        r"替换|置换|换成|变成|动作迁移|模仿.*动作|复刻.*动作|跟随.*动作|"
        r"replace|replacement|swap|motion\s*(?:transfer|reference)|imitate.*motion|copy.*motion",
        user_prompt,
        flags=re.IGNORECASE,
    ):
        transfer_rule = (
            " This is a subject-replacement or motion-transfer request. The following is a strict task-specific "
            "exception that overrides the general instructions to describe actions, timing, performance, camera, "
            "sound, and shot-by-shot events. Describe only the source-to-target relationship: which subject from "
            "<picture N> replaces which subject in <video N>, while the source video's complete motion, timing, "
            "scene, props, composition, camera movement, cuts, and temporal structure remain unchanged. Never name, "
            "infer, enumerate, paraphrase, or timestamp any concrete source-video action, gesture, pose change, facial "
            "expression, dialogue, object interaction, prop function, story event, sound, ambience, or music, even if "
            "it appears visible or inferable in the sampled frames. Use the sampled frames only to distinguish the "
            "subjects that must be replaced. Define replacement subjects only with official numbered labels such as "
            "<Subject 1> and <Subject 2>, never semantic labels such as <cat> or a Chinese name. Give each subject only "
            "the minimum clearly visible identity cues needed to avoid mismatch: subject type or gender, approximate "
            "age when reliable, main clothing and color, hairstyle or fur pattern, hat, and glasses. Do not infer an "
            "occupation or describe pose, expression, action, scene details, lighting, or unrelated appearance. Do not "
            "define the original subjects being removed as target <Subject N> entries unless needed only to make an "
            "unambiguous one-to-one replacement mapping. In detailed_description, keep a single [Shot 1] for the source "
            "timeline, but write a complete operational paragraph rather than a bare one-sentence relationship. State "
            "which source subject or scene is replaced by which referenced target, which target identity and major "
            "appearance or environment attributes remain stable, and which source-video properties remain unchanged: "
            "motion performance, facial-expression timing, blocking, screen direction, camera trajectory, framing, "
            "cuts, pacing, and duration when applicable. Explain how replaced subjects remain spatially integrated with "
            "preserved props and scene elements, but never invent or enumerate the source video's concrete actions, "
            "dialogue, props, events, or sounds; do not expand the source timeline or reconstruct it from sampled frames. Treat the three sampled images from one <video N> as observation "
            "frames of that single reference video, never as separate target shots or evidence of cuts."
        )
    language_rule = (
        "输出语言强制为中文：所有自然语言说明、主体描述、摘要、镜头描述、声音说明和音乐说明必须使用简体中文，"
        "不得输出英文句子。只有官方固定字段名 subject_definitions、summary、retention_analysis、"
        "detailed_description、integrated_multimodal_description、overall_soundscape、non_diegetic_music，"
        "媒体与主体标签、[Shot N]，以及 fully_preserved、partially_preserved、attribute_transfer、"
        "weak_reference、fully_copy、partially_copy、reference 等固定关系标记保留英文。返回前必须检查并将"
        "其他英文自然语言全部改写成中文。"
        if output_language == "中文" else
        "Output all natural-language content in English. Keep supplied dialogue, lyrics, and visible text in their "
        "original language."
    )
    dialogue_rule = (
        "Official dialogue formatting is mandatory in every task and is independent of the selected narration "
        "language. Put every user-supplied spoken line or lyric inside exactly one <d>[Language]...</d> block, using "
        "the dialogue's actual language name in English. In particular, Chinese speech must use the exact form "
        "<d>[Chinese]中文原文</d>; never write Chinese dialogue only inside quotation marks, and never omit [Chinese]. "
        "Keep the speaker description, stable speaker ID such as (S1), speaking action, and delivery outside the <d> "
        "block; inside it preserve only the user's exact words and punctuation without translation or rewriting. "
        "The output-language setting controls narration only: an English prompt must still retain supplied Chinese "
        "dialogue as <d>[Chinese]...</d>. Placement is as mandatory as formatting: every <d> block must be embedded "
        "inside integrated_multimodal_description or detailed_description at the exact chronological moment when the "
        "speaker speaks or sings, immediately after that speaker's speaking/singing action and delivery description. "
        "Never collect dialogue into a list, appendix, footer, or separate paragraph after the official sections. "
        "Never place a <d> block in subject_definitions, summary, retention_analysis, overall_soundscape, or "
        "non_diegetic_music. The final section is always non_diegetic_music, and absolutely no text or <d> block may "
        "follow that section's content. For multiple supplied lines, preserve their original order and place each line "
        "at its corresponding point in the shot timeline, with intervening actions and pauses described between lines "
        "when the user's request implies them. Before returning, verify that every supplied line appears exactly once "
        "inside the main shot timeline and nowhere else. Do not wrap paraphrased soundscape descriptions, ambient "
        "sounds, or dialogue that the user did not explicitly supply in <d> tags."
    )
    subject_shorthand_rule = (
        "Subject shorthand formatting is mandatory and globally consistent. If a stable short subject ID is used, "
        "it must always be written with parentheses as (S1), (S2), ... through (S20). Never output a bare S1, S2, "
        "or any other unparenthesized S-number in narration, shot descriptions, actions, dialogue attribution, or "
        "sound descriptions. <Subject N> definitions remain unchanged; (S1) is only the shorthand used to refer back "
        "to a defined subject. Before returning, scan the complete result and replace every standalone bare S1-S20 "
        "with its exact parenthesized form."
    )
    return (
        "You are a professional prompt writer for the open-source MiniMax H3 audiovisual model. Return only the "
        "final production-ready prompt without explanations, markdown fences, filenames, or invented media. "
        "Preserve the user's intent and every supplied dialogue, lyric, and visible-text word verbatim; do not "
        "invent dialogue or lyrics that were not provided. This is a video-generation prompt, not image captioning "
        "or visual reverse-prompting. Reference images are already passed into model conditioning, so identify each "
        "visual subject only with the minimum distinctive cues needed to disambiguate it: usually gender or subject "
        "type, main clothing, main hairstyle, and scene. Do not describe facial features, lighting, pose, background "
        "objects, or composition exhaustively unless they are essential to the requested motion or must change over "
        "time. Spend most words on what happens after the reference frame: causally connected actions, reactions, "
        "story progression, timing, performance, camera behavior, and audio-visual synchronization. Develop the "
        "user's idea into concrete visible beats that fit the duration: establish the situation, let the central "
        "action evolve through meaningful intermediate changes, add a restrained climax or reveal when appropriate, "
        "and finish on a clear visual result rather than an abrupt stop. Do not introduce unrelated characters, props, "
        "locations, conflicts, or plot twists. Avoid repeating the same static trait across sections, avoid decorative "
        "adjectives, and never turn quality requirements into a long negative-prompt checklist. Use professional but "
        "executable cinematography with dynamic video direction by default. Unless the user explicitly requests a static pose, locked-off camera, "
        "minimal movement, or a specific fixed composition, do not let the subject remain nearly motionless after the "
        "opening frame. Build visible motion in successive phases with clear variation and continuity: changes in body "
        "weight, posture, orientation, gesture, interaction, expression, spatial position, or object state. Avoid one "
        "gesture repeated mechanically throughout the clip. For music, singing, dance, performance, fashion, or other "
        "rhythmic scenes, let the body express phrase changes through varied natural gestures and coordinated torso, "
        "shoulder, head, hand, and footwork where framing permits; align movement energy and camera emphasis with broad "
        "musical progression without fabricating unheard exact beats. Treat the reference image as a starting anchor, "
        "not the main subject of the description: spend only enough text to identify it, then prioritize motion design, "
        "performance evolution, kinetic atmosphere, and a visually active ending. For each shot, integrate the useful framing or shot scale, subject blocking, and "
        "camera path into the action. When motion benefits the scene, choose a motivated Push In, Pull Out, Pan, Tilt, "
        "Truck, Pedestal, Arc Shot, Tracking Shot, or controlled Zoom, and specify subtle/large amplitude and slow/fast "
        "speed only when meaningful. Let camera movement reveal information, follow motion, emphasize a transformation, "
        "or land on the final state; do not stack random camera terms or use constant movement without purpose. Vary "
        "composition and visual emphasis over time so the video feels directed rather than static, while preserving "
        "spatial continuity, screen direction, subject identity, and reference constraints. Expand into continuous "
        "actions, camera choreography, synchronized audible events, ambience, and music with enough detail to guide "
        "generation effectively. Prefer a well-designed continuous shot when it can express the event clearly, but "
        "allow a small number of motivated cuts when they materially improve narrative clarity or reveal new visual "
        "information. Do not create labels outside the supplied label list, renumber labels, "
        "or replace labels with filenames. "
        f"Task={task}; duration={duration:.2f}s; available labels={', '.join(labels) or 'none'}. "
        f"{label_rule} {keyframe_rule} {audio_rule} {structure}{singing_rule}{transfer_rule} {dialogue_rule} "
        f"{subject_shorthand_rule} "
        "Audio items are label-only references; never claim you listened to them. Before returning, silently check "
        "that every required section is present in the correct order, every used label exists, no filename appears, "
        "no audio content was fabricated, all timing fits the target duration, and the audio relationship matches "
        f"the supplied mode. {direct_rule} {language_rule}"
    )


def _user_parts(prompt: str, media: list[dict], read_media: bool) -> list[dict]:
    parts = [{"type": "text", "text": "User prompt:\n" + prompt}]
    for item in media:
        label = str(item.get("label") or "")
        kind = str(item.get("kind") or "")
        if kind == "audio":
            parts.append({"type": "text", "text": f"{label} is an uploaded audio reference (content not transmitted)."})
        elif read_media:
            for index, data_url in enumerate(item.get("images") or []):
                parts.append({"type": "text", "text": f"{label} visual {index + 1}."})
                parts.append({"type": "image_url", "image_url": {"url": data_url, "detail": "low"}})
        else:
            parts.append({"type": "text", "text": f"{label} is an uploaded {kind} reference."})
    return parts


def _strip_filenames(text: str) -> str:
    return re.sub(
        r"(?<![\w/\\])[\w .()\-\u4e00-\u9fff]+\.(?:png|jpe?g|webp|bmp|gif|mp4|mov|webm|mkv|avi|mp3|wav|flac|m4a|ogg|aac)(?!\w)",
        "",
        text,
        flags=re.IGNORECASE,
    ).strip()


_META_HEADING_RE = re.compile(
    r"^\s*(?:\d+[.、]\s*)?(?:"
    r"反推摘要|结构化拆解|结构化视觉拆解|视觉拆解|H3\s*参考用法|参考用途|素材用途|"
    r"首尾帧判断|连续性|冲突(?:或|与)不确定项|中间帧建议|负面约束|规避项|合规(?:说明|提示)?|"
    r"说明|注意|备注|使用说明|质量要求|分析|技术说明|镜头时间线|时间线表|"
    r"保留项|替换建议|禁止复制|negative\s*prompt|notes?|explanation|analysis|timeline|"
    r"quality\s*check|output\s*format"
    r")\s*(?:[:：].*)?$",
    flags=re.IGNORECASE,
)

_IMAGE_PROMPT_HEADING_RE = re.compile(
    r"^\s*(?:\d+[.、]\s*)?(?:"
    r"可复用生成提示词|可复用图片提示词|生图主提示词|主提示词|图片提示词|最终提示词|正向提示词|"
    r"positive\s*prompt|image\s*prompt|prompt"
    r")\s*[:：]?\s*$",
    flags=re.IGNORECASE,
)


def _markdown_plain_text(text: str) -> str:
    value = _unescape_model_text(text)
    value = re.sub(r"```(?:json|text)?", "", value, flags=re.IGNORECASE).replace("```", "")
    value = re.sub(r"(?m)^\s{0,3}#{1,6}\s*", "", value)
    value = value.replace("**", "").replace("__", "")
    value = re.sub(r"(?m)^\s*(?:[-*•·]|\d+[.、])\s*", "", value)
    return re.sub(r"\n{3,}", "\n\n", value).strip()


def _sanitize_direct_image_output(text: str) -> str:
    """Return only the positive image prompt, without analysis or instructional scaffolding."""
    value = _markdown_plain_text(text)
    inline = re.search(
        r"(?im)^\s*(?:\d+[.、]\s*)?(?:可复用生成提示词|可复用图片提示词|生图主提示词|主提示词|"
        r"图片提示词|最终提示词|正向提示词|positive\s*prompt|image\s*prompt|prompt)\s*[:：]\s*(.+)$",
        value,
    )
    if inline and inline.group(1).strip():
        prompt = re.sub(r"\s+", " ", inline.group(1)).strip().strip("“”\"'")
        prompt = re.sub(r"^(?:以下是|下面是|这是)[^。！？\n]{0,24}(?:提示词|描述|内容)?\s*[:：]\s*", "", prompt)
        prompt = re.sub(r"^(?:这张|这幅|该)?(?:图片|图像|画面)(?:显示|展示|呈现)[，,:：]?\s*", "", prompt)
        return prompt
    lines = [line.rstrip() for line in value.splitlines()]
    selected: list[str] = []
    collecting = False
    for line in lines:
        stripped = line.strip()
        if not stripped:
            if collecting and selected and selected[-1] != "":
                selected.append("")
            continue
        if not collecting:
            if _IMAGE_PROMPT_HEADING_RE.match(stripped):
                collecting = True
            continue
        if _META_HEADING_RE.match(stripped) or _IMAGE_PROMPT_HEADING_RE.match(stripped):
            break
        if re.match(r"^(?:主体|动作与表情|服装与道具|环境与空间|构图与镜头|光影与色彩|材质与风格|画面文字|不确定项|首帧|尾帧|连续性|冲突或不确定项|中间帧)\s*[:：<]", stripped):
            break
        selected.append(stripped)
    prompt = " ".join(part for part in selected if part).strip()
    if not prompt:
        paragraphs = [part.strip() for part in re.split(r"\n\s*\n", value) if part.strip()]
        candidates = []
        for part in paragraphs:
            first = part.splitlines()[0].strip()
            if _META_HEADING_RE.match(first) or _IMAGE_PROMPT_HEADING_RE.match(first):
                continue
            if re.match(r"^(?:主体|动作与表情|服装与道具|环境与空间|构图与镜头|光影与色彩|材质与风格|画面文字|不确定项|首帧|尾帧|连续性|冲突或不确定项|中间帧)\s*[:：<]", first):
                continue
            candidates.append(part.replace("\n", " "))
        prompt = max(candidates, key=len, default=value.replace("\n", " "))
    prompt = re.sub(r"^(?:可复用生成提示词|可复用图片提示词|生图主提示词|主提示词|图片提示词|最终提示词|正向提示词|prompt)\s*[:：]\s*", "", prompt, flags=re.IGNORECASE)
    prompt = re.sub(r"^(?:以下是|下面是|这是)[^。！？\n]{0,24}(?:提示词|描述|内容)?\s*[:：]\s*", "", prompt)
    prompt = re.sub(r"^(?:这张|这幅|该)?(?:图片|图像|画面)(?:显示|展示|呈现)[，,:：]?\s*", "", prompt)
    prompt = re.sub(r"\s+", " ", prompt).strip().strip("“”\"'")
    return prompt

def _format_prompt_sections(text: str) -> str:
    """Force official section headings onto separate lines without rewriting content."""
    headings = (
        "subject_definitions",
        "summary",
        "retention_analysis",
        "detailed_description",
        "integrated_multimodal_description",
        "overall_soundscape",
        "non_diegetic_music",
    )
    pattern = r"\s*(" + "|".join(map(re.escape, headings)) + r")\s*:\s*"
    formatted = re.sub(pattern, lambda match: f"\n\n{match.group(1).lower()}:\n", str(text), flags=re.IGNORECASE)
    return formatted.strip()


def _clean_dialogue_tags(text: str) -> str:
    value = re.sub(r"\\+(</?d\s*>)", r"\1", str(text or ""), flags=re.IGNORECASE)
    for _ in range(4):
        value = re.sub(r"<d>\s*<d>", "<d>", value, flags=re.IGNORECASE)
        value = re.sub(r"</d>\s*</d>", "</d>", value, flags=re.IGNORECASE)
        value = re.sub(r"<d>\s*(\[[^\]]+\])?\s*<d>", lambda m: f"<d>{m.group(1) or ''}", value, flags=re.IGNORECASE)
        value = re.sub(r"</d>[\s`'\"]*</d>", "</d>", value, flags=re.IGNORECASE)
    value = re.sub(r"</d>\s*[`'\"]+", "</d>", value, flags=re.IGNORECASE)

    def normalize(match):
        body = match.group(1).strip()
        if not body:
            return ""
        if not body.startswith("["):
            language = "Chinese" if re.search(r"[\u3400-\u9fff]", body) else "English"
            body = f"[{language}]{body}"
        return f"<d>{body}</d>"

    value = re.sub(r"<d>(.*?)</d>", normalize, value, flags=re.IGNORECASE | re.DOTALL)
    return re.sub(r"\[([A-Za-z]+)\]\[([A-Za-z]+)\]", lambda match: f"[{match.group(2)}]", value)


def _clean_section_content(name: str, content: str) -> str:
    value = _markdown_plain_text(_clean_dialogue_tags(content))
    lines = []
    repeats: dict[str, int] = {}
    for line in value.splitlines():
        stripped = line.strip()
        if _META_HEADING_RE.match(stripped):
            break
        if not stripped:
            if lines and lines[-1] != "":
                lines.append("")
            continue
        if re.match(r'^"?(?:task|prompt|system|config|skill_id|media|reference|duration|aspect_ratio)"?\s*[:=]', stripped, re.IGNORECASE):
            continue
        if stripped in {"{", "}", "[", "]", "```", "```json", "text"}:
            continue
        if len(stripped) > 24:
            count = repeats.get(stripped, 0) + 1
            repeats[stripped] = count
            if count > 2:
                continue
        lines.append(line.rstrip())
    value = re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()
    value = value.replace("。。", "。").replace("；。", "。").replace("，。", "。")
    return value.strip("逗号：:;,， \t\r\n")


def _sanitize_h3_output(text: str) -> str:
    """Remove JSON wrappers, escaped strings, duplicate lines, and nested dialogue tags."""
    value = _unescape_model_text(text)
    value = re.sub(r"```(?:json|text)?", "", value, flags=re.IGNORECASE).replace("```", "")
    heading_re = re.compile(
        r"(?im)^\s*(subject_definitions|summary|retention_analysis|detailed_description|"
        r"overall_soundscape|non_diegetic_music|integrated_multimodal_description)\s*[:：]\s*"
    )
    matches = list(heading_re.finditer(value))
    if len(matches) >= 2:
        sections: dict[str, str] = {}
        for index, match in enumerate(matches):
            name = match.group(1).lower()
            end = matches[index + 1].start() if index + 1 < len(matches) else len(value)
            sections[name] = _clean_section_content(name, value[match.end():end])
        order = _H3_SECTION_ORDER if "subject_definitions" in sections else (
            "integrated_multimodal_description", "overall_soundscape", "non_diegetic_music"
        )
        kept = [f"{name}:\n{sections[name]}" for name in order if sections.get(name)]
        if kept:
            return "\n\n".join(kept).strip()
    return _clean_section_content("full", value)
_H3_SECTION_ORDER = (
    "subject_definitions",
    "summary",
    "retention_analysis",
    "detailed_description",
    "overall_soundscape",
    "non_diegetic_music",
    "integrated_multimodal_description",
)


def _unescape_model_text(text: str) -> str:
    value = str(text or "").strip()
    value = re.sub(r"^\s*```(?:json|text)?\s*", "", value, flags=re.IGNORECASE)
    value = re.sub(r"\s*```\s*$", "", value)
    quoted = re.search(r'"(?:prompt|text|result|content)"\s*:\s*"(.*)"\s*}\s*$', value, flags=re.DOTALL)
    if quoted:
        value = quoted.group(1)
    try:
        parsed = json.loads(value)
        if isinstance(parsed, dict):
            for key in ("prompt", "text", "result", "content"):
                if isinstance(parsed.get(key), str):
                    value = parsed[key]
                    break
    except (TypeError, ValueError):
        pass
    value = value.replace("\\r\\n", "\n").replace("\\n", "\n").replace("\\r", "\n")
    value = value.replace('\\"', '"').replace("\\'", "'")
    value = re.sub(r"\\u([0-9a-fA-F]{4})", lambda match: chr(int(match.group(1), 16)), value)
    value = re.sub(r"\\([<>/])", r"\1", value)
    value = value.replace("\\_", "_")
    return value


def _sanitize_audio_reverse_output(text: str) -> str:
    """Strip instruction/skill leakage and speaker-turn framing from audio-reverse prompts."""
    leak_re = re.compile(
        r"(?im)^\s*(?:#|##|###|----?|--|>\s|\*\*\s|"
        r"Skill 主说明|SKILL\.md|references?/|工作步骤|输入约定|最终输出|负面约束|硬性纪律|"
        r"name\s*:|description\s*:|以下|如下)"
    )
    frame_re = re.compile(
        r"(?:The\s+)?(?:on-screen\s+)?speaker\s*\(?S?\d+\)?\s*(?:then\s+)?continues?\s*:\s*",
        re.IGNORECASE,
    )
    value = str(text or "").strip()
    lines = []
    for raw in value.splitlines():
        line = raw.rstrip()
        stripped = line.strip()
        if not stripped:
            if lines and lines[-1] != "":
                lines.append("")
            continue
        if leak_re.match(stripped):
            continue
        if frame_re.search(stripped):
            stripped = frame_re.sub("", stripped, count=1).strip()
        if stripped in {"<d>", "</d>", "<d></d>"}:
            continue
        if stripped.startswith("<d>") and not stripped.endswith("</d>"):
            stripped = f"{stripped}</d>"
        lines.append(stripped)
    value = re.sub(r"\n{3,}", "\n\n", "\n".join(lines))
    return value.strip()


# ---------------------------------------------------------------------------
# 音频反推：程序化注入带时间码歌词（不依赖弱量化模型去“重写歌词”）
# ---------------------------------------------------------------------------
_AUDIO_REVERSE_LEAK_MARKERS = (
    "禁止重新转写",
    "每句只输出一条",
    "重写、改写、翻译",
    "说话适合",
    "对白行",
    "on-screen speaker",
    "speaker (S",
    "Skill 主说明",
    "Skill 参考",
    "references/template",
    "references/digital-human-singing",
    "SKILL.md",
    "name: audio-prompt-reverse",
    "description: 上传歌曲",
    "工作步骤",
    "输入约定",
    "最终输出",
    "负面约束",
    "硬性纪律",
    "识别歌词按时间码",
    "识别歌词的歌曲音频",
    "这是音频反推任务",
    "这是 MiniMax H3 数字人提示词生成任务",
    "最终提示词中禁止出现",
    "歌曲音频由 11 号工作流",
    "既是数字人主体",
    "把<Picture 1>中的人物",
    "运镜必须按创意 MV 设计",
    "三个以上歌词段时",
    "每个镜头只承担一个主要机位动作",
    "不要全片只靠 Zoom",
)


def _fmt_h3_ts(seconds: float) -> str:
    """秒数 → mm:ss.mmm，如 3.56 → '00:03.560'。"""
    sec = max(0.0, float(seconds))
    minutes = int(sec // 60)
    remainder = sec - minutes * 60
    return f"{minutes:02d}:{remainder:06.3f}"


def _build_timed_lyrics_block(lyric_timeline: str) -> str:
    """把 whisper 时间线转成 H3 数字人演唱的标准时间码歌词块。

    输入格式（_format_timeline singing=True 输出）：
        0.00-3.56 秒 | S1 | <Picture 1> | <Subject 1>
        <d>[Mandarin singing]我悄悄地爱上你</d>
    输出格式（对齐 11 号数字人工作流）：
        00:00.000-00:03.560, <Subject 1> (S1) sings:
        <d>[Mandarin singing] 我悄悄地爱上你</d>
    """
    blocks: list[str] = []
    subject = "<Subject 1>"
    speaker = "S1"
    pending_time: tuple[float, float] | None = None
    for raw in str(lyric_timeline or "").splitlines():
        line = raw.strip()
        time_m = re.search(r"([\d.]+)\s*[-–]\s*([\d.]+)\s*秒", line)
        if time_m:
            pending_time = (float(time_m.group(1)), float(time_m.group(2)))
        speaker_m = re.search(r"\|\s*(S\d+)\s*\|", line, re.I)
        if speaker_m:
            speaker = speaker_m.group(1).upper()
        subj_m = re.search(r"<Subject\s+\d+>", line)
        if subj_m:
            subject = subj_m.group(0)
        d_m = re.search(r"<d>\s*\[([^\]]+)\]\s*(.*?)</d>", line, re.DOTALL)
        if d_m and pending_time:
            lang = d_m.group(1).strip()
            if "singing" not in lang.lower():
                lang = {
                    "chinese": "Mandarin singing",
                    "mandarin": "Mandarin singing",
                    "中文": "Mandarin singing",
                    "english": "English singing",
                    "japanese": "Japanese singing",
                    "korean": "Korean singing",
                }.get(lang.lower(), f"{lang} singing")
            lyric = re.sub(r"\s+", " ", d_m.group(2)).strip()
            start_s, end_s = pending_time
            blocks.append(
                f"{_fmt_h3_ts(start_s)}-{_fmt_h3_ts(end_s)}, {subject} ({speaker}) sings:\n"
                f"<d>[{lang}] {lyric}</d>"
            )
    return "\n\n".join(blocks)


def _strip_audio_reverse_leak(text: str) -> str:
    """清洗 detailed_description：去掉模型泄漏的技能/指令文本与模型自写的乱歌词。

    先按句切分再做清理，避免“泄漏句粘连好句”导致整句误删。
    """
    value = str(text or "")
    sentences = re.split(r"(?<=[。；;.!？?\n])", value)
    kept: list[str] = []
    for sentence in sentences:
        s = re.sub(r"<d>\s*\[[^\]]*\]\s*.*?</d>", "", sentence, flags=re.IGNORECASE | re.DOTALL)
        s = re.sub(
            r"(?im)^\s*(?:from\s+approximately\s+)?\d{1,2}:\d{2}\.\d{3}\s*(?:to|-)\s*"
            r"\d{1,2}:\d{2}\.\d{3},.*$",
            "",
            s,
        )
        s = re.sub(
            r"(?i)\s+(?:and\s+)?(?:sings?|sang|says?|saying)\s*[:：]?\s*$",
            "",
            s,
        )
        s = re.sub(
            r"(?i)\s+with\s+(?:the\s+|model\s+)?(?:lyrics?|line)\s*[.:：]?\s*$",
            "",
            s,
        )
        s = re.sub(r"(?:演唱|唱道|歌词)\s*[:：]?\s*$", "", s)
        if any(marker.lower() in s.lower() for marker in _AUDIO_REVERSE_LEAK_MARKERS):
            continue
        s = re.sub(r"</?d\s*>", "", s, flags=re.IGNORECASE)
        s = re.sub(r"\s+", " ", s).strip()
        if s.strip(" \n\t,，;；"):
            kept.append(s.strip(" \n\t,，;；"))
    return re.sub(r"\n{3,}", "\n\n", "".join(kept)).strip(" \n\t,，;；")


def _split_audio_reverse_sections(prompt: str) -> dict[str, str]:
    heading_re = re.compile(
        r"(?im)^\s*(subject_definitions|summary|retention_analysis|detailed_description|"
        r"overall_soundscape|non_diegetic_music)\s*[:：]\s*"
    )
    matches = list(heading_re.finditer(prompt))
    sections: dict[str, str] = {}
    for index, match in enumerate(matches):
        name = match.group(1).lower()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(prompt)
        sections[name] = prompt[match.end():end].strip()
    return sections


def _audio_track_label(output_language: str) -> str:
    return "锁定歌曲音轨" if str(output_language).lower().startswith(("zh", "chinese", "中文")) else "locked song audio track"


def _replace_audio_tags(text: str, output_language: str) -> str:
    """Replace standard audio labels before H3 digital-human mode strips angle-bracket tags."""
    label = _audio_track_label(output_language)
    value = re.sub(r"<Audio\s+\d+>\s*(?=[:：])", label, str(text or ""), flags=re.IGNORECASE)
    return re.sub(r"<Audio\s+\d+>", label, value, flags=re.IGNORECASE)


def _ensure_audio_reverse_sections(prompt: str, output_language: str, context: dict | None = None) -> str:
    """Guarantee the six H3 fields expected by the digital-human renderer."""
    context = context if isinstance(context, dict) else {}
    if context.get("duet"):
        male = context.get("male") if isinstance(context.get("male"), dict) else {}
        female = context.get("female") if isinstance(context.get("female"), dict) else {}
        scene = context.get("scene") if isinstance(context.get("scene"), dict) else {}
        male_subject = str(male.get("subject") or "<Subject 1>")
        male_picture = str(male.get("picture") or "<Picture 1>")
        male_speaker = str(male.get("speaker") or "S1")
        female_subject = str(female.get("subject") or "<Subject 2>")
        female_picture = str(female.get("picture") or "<Picture 2>")
        female_speaker = str(female.get("speaker") or "S2")
        scene_subject = str(scene.get("subject") or "").strip()
        scene_picture = str(scene.get("picture") or "").strip()
        chinese = str(output_language).lower().startswith(("zh", "chinese", "中文"))
        audio_label = _audio_track_label(output_language)
        if chinese:
            scene_definition = (
                f"{scene_subject} 是 {scene_picture} 中的共同场景，保持背景、光线和两人原有站位，但按歌词段只让当前歌手入画。"
                if scene_subject and scene_picture else
                "两人处于参考素材中一致的共享环境，保持背景、光线和原有站位，但按歌词段只让当前歌手入画。"
            )
            subject = (
                f"{male_subject} 是 {male_picture} 中的男子，只负责男声（{male_speaker}）；{female_subject} 是 "
                f"{female_picture} 中的女子，只负责女声（{female_speaker}）。{scene_definition}"
                "对唱采用交替单人镜头：男声时间段画面中有且只有男子，女子完全在画外；女声时间段画面中有且只有女子，男子完全在画外。每个时间段只出现一张演唱的嘴，不生成第二人的正脸、嘴部、身体或口型。"
            )
            summary = "[reference generation + digital human duet + audio reuse] 男女两位歌手在同一场景中按照锁定歌曲音轨交替独唱；每个时间段只出现当前歌手一个人，另一人完全在画外，从不同时出现两张演唱的嘴。"
            retention_lines = [
                f"{male_picture}: fully_preserved - 男子的身份、脸型、发型、服装、配饰和体型完整保留。",
                f"{female_picture}: fully_preserved - 女子的身份、脸型、发型、服装、配饰和体型完整保留。",
            ]
            if scene_subject and scene_picture:
                retention_lines.append(
                    f"{scene_picture}: fully_preserved - 两人的共同场景、空间位置、光线和构图保持稳定。"
                )
            retention_lines.append(
                f"{audio_label}: fully_copy - 原歌曲、男女声、伴奏、节奏、停顿、音色和时长作为完整最终音轨原样复用。"
            )
            retention = "\n".join(retention_lines)
            scene_reference = (
                f"{scene_subject} 的共同环境中"
                if scene_subject else "与参考素材一致的共享环境中"
            )
            detail = (
                f"[Shot 1] 写实 MV 风格，{male_subject}（{male_speaker}）和 {female_subject}（{female_speaker}）位于 "
                f"{scene_reference}，分别保持 {male_picture} 与 {female_picture} 中的人物身份、服装和外观。"
                "采用 MV 交替单人镜头：男声段只拍男子，女声段只拍女子；切点落在歌词起唱而不是咬字中间。"
                "每个镜头画面中有且只有当前歌手一个人，另一人完全在画外，不出现第二张脸、第二张嘴或第二套口型。"
                "当前歌手完成口型、下颌、呼吸、眼神和头肩律动，镜头运动与共享场景的空间关系跨镜头连续。"
            )
        else:
            scene_definition = (
                f"{scene_subject} is the shared scene from {scene_picture}, preserving both singers' blocking, background, lighting, and composition."
                if scene_subject and scene_picture else
                "Both singers remain in one consistent shared environment, preserving blocking, background, lighting, and eyelines."
            )
            subject = (
                f"{male_subject} is the man from {male_picture}, responsible only for the male vocal ({male_speaker}). "
                f"{female_subject} is the woman from {female_picture}, responsible only for the female vocal ({female_speaker}). "
                f"{scene_definition} Use alternating solo coverage: a male lyric shows only the man while the woman is completely "
                "off-screen; a female lyric shows only the woman while the man is completely off-screen. Each timed lyric contains "
                "exactly one visible singing mouth and never shows a second face, mouth, body, or lip movement."
            )
            summary = "[reference generation + digital human duet + audio reuse] The male and female singers alternate solo coverage in the same scene from the locked source song track; each timed lyric shows only its assigned singer, while the other singer remains completely off-screen."
            retention_lines = [
                f"{male_picture}: fully_preserved - the man's identity, face, hairstyle, clothing, accessories, and body shape remain stable.",
                f"{female_picture}: fully_preserved - the woman's identity, face, hairstyle, clothing, accessories, and body shape remain stable.",
            ]
            if scene_subject and scene_picture:
                retention_lines.append(
                    f"{scene_picture}: fully_preserved - the shared scene, blocking, lighting, and composition remain stable."
                )
            retention_lines.append(
                f"{audio_label}: fully_copy - the original song, both vocal parts, accompaniment, rhythm, pauses, timbre, and duration are reused unchanged as the final soundtrack."
            )
            retention = "\n".join(retention_lines)
            scene_reference = (
                f"the shared environment of {scene_subject}"
                if scene_subject else "one consistent shared environment from the references"
            )
            detail = (
                f"[Shot 1] Realistic music-video style. {male_subject} ({male_speaker}) and {female_subject} ({female_speaker}) perform in "
                f"{scene_reference}, preserving the identities, clothing, and appearance from {male_picture} and {female_picture}. "
                "Build the duet from alternating solo coverage: male lyrics show only the man, female lyrics show only the woman, "
                "and cuts land on lyric onsets. Each shot contains exactly one singer; the other is completely off-screen with no "
                "second face, mouth, body, or lip movement. The active singer performs synchronized lip, jaw, breathing, gaze, "
                "head, and shoulder motion while the shared scene and screen direction remain continuous across cuts."
            )
        ensured = {
            "subject_definitions": subject,
            "summary": summary,
            "retention_analysis": retention,
            "detailed_description": detail,
            "overall_soundscape": "N/A",
            "non_diegetic_music": "N/A",
        }
        return "\n\n".join(f"{name}:\n{ensured[name]}" for name in _H3_SECTION_ORDER if name in ensured).strip()
    chinese = str(output_language).lower().startswith(("zh", "chinese", "中文"))
    audio_label = _audio_track_label(output_language)
    single = context.get("single") if isinstance(context.get("single"), dict) else {}
    forced_single = bool(single)
    single_picture = str(single.get("picture") or "<Picture 1>")
    single_subject = str(single.get("subject") or "<Subject 1>")
    single_speaker = str(single.get("speaker") or "S1")
    sections = _split_audio_reverse_sections(prompt)
    plain = "" if sections else _strip_audio_reverse_leak(prompt)
    defaults = (
        {
            "subject": f"{single_subject} 是 {single_picture} 中的人物，保持脸型、五官、发型、服装、配饰、体型和整体构图稳定。人物是目标视频中的歌手（{single_speaker}）。",
            "summary": f"[reference generation + digital human audio reuse] 人物保持 {single_picture} 中的身份与外观，按照数字人模式锁定的原歌曲音轨完成逐字演唱、口型和表情同步。",
            "retention": f"{single_picture}: fully_preserved - 人物身份、脸型、发型、服装、配饰、体型和构图完整保留。\n{audio_label}: fully_copy - 原歌曲音轨作为目标视频的完整最终音轨按原样复用。",
            "detail": f"[Shot 1] 写实 MV 风格，{single_subject}（{single_speaker}）保持 {single_picture} 中的人物身份、服装和场景关系。用“前景横移揭示 → 低机位侧向 Truck → 三分之四近景 Dolly → 30° 小弧线 → Crane Up 拉远”的有目的切镜组成演唱段落，每句只在起唱、换气或重音处切换，始终保留正在演唱者的完整嘴部。人物按照锁定歌曲音轨的节拍、旋律、咬字、换气和重音完成准确口型同步，身体随乐句改变重心和手势，不做机械重复摆动。",
        }
        if chinese else
        {
            "subject": f"{single_subject} is the person from {single_picture}. Preserve the face, features, hairstyle, clothing, accessories, body shape, and overall composition. The person is the singer ({single_speaker}) in the target video.",
            "summary": f"[reference generation + digital human audio reuse] The person preserves the identity and appearance from {single_picture} and sings every supplied lyric on the locked source song track with synchronized mouth, facial expression, and breathing.",
            "retention": f"{single_picture}: fully_preserved - the person's identity, face, hairstyle, clothing, accessories, body shape, and composition remain stable.\n{audio_label}: fully_copy - the original song audio is reused unchanged as the complete final soundtrack.",
            "detail": f"[Shot 1] Realistic music-video style. {single_subject} ({single_speaker}) preserves the identity, clothing, and scene relationship from {single_picture}. Build the vocal section from motivated setups: a foreground lateral reveal, low-angle tracking, a three-quarter dolly close-up, a controlled 30-degree arc, and a final crane pull-out. Cut only on lyric onsets, breaths, or accents and keep the active singer's mouth fully readable. The mouth, jaw, lips, breathing, gaze, head, and shoulders follow the locked song track with accurate lip sync while identity remains stable.",
        }
    )
    subject_source = defaults["subject"] if forced_single else (sections.get("subject_definitions") or plain or defaults["subject"])
    subject = _replace_audio_tags(subject_source, output_language)
    if single_subject not in subject or single_picture not in subject:
        subject = f"{defaults['subject']}\n{subject}".strip()
    retention_source = defaults["retention"] if forced_single else (sections.get("retention_analysis") or defaults["retention"])
    retention = _replace_audio_tags(retention_source, output_language)
    if single_picture not in retention or "fully_preserved" not in retention.lower():
        picture_retention = (
            f"{single_picture}: fully_preserved - 人物身份、脸型、发型、服装、配饰、体型和构图完整保留。"
            if chinese else
            f"{single_picture}: fully_preserved - the person's identity, face, hairstyle, clothing, accessories, body shape, and composition remain unchanged."
        )
        retention = f"{picture_retention}\n{retention}".strip()
    if "fully_copy" not in retention.lower():
        retention = f"{retention}\n{audio_label}: fully_copy - the complete original song audio is reused as the final soundtrack.".strip()
    detail = _replace_audio_tags(sections.get("detailed_description") or plain or defaults["detail"], output_language)
    if "[Shot 1]" not in detail:
        detail = f"[Shot 1] {detail}".strip()
    ensured = {
        "subject_definitions": subject,
        "summary": _replace_audio_tags(defaults["summary"] if forced_single else (sections.get("summary") or defaults["summary"]), output_language),
        "retention_analysis": retention,
        "detailed_description": detail,
        "overall_soundscape": "N/A",
        "non_diegetic_music": "N/A",
    }
    return "\n\n".join(f"{name}:\n{ensured[name]}" for name in _H3_SECTION_ORDER if name in ensured).strip()


def _parse_lyric_timeline(lyric_timeline: str) -> list[dict[str, Any]]:
    entries = []
    pending_time = None
    pending_speaker = "S1"
    pending_picture = "<Picture 1>"
    pending_subject = "<Subject 1>"
    for raw in str(lyric_timeline or "").splitlines():
        line = raw.strip()
        time_match = re.search(r"([\d.]+)\s*[-–]\s*([\d.]+)\s*秒", line)
        if time_match:
            pending_time = (float(time_match.group(1)), float(time_match.group(2)))
            speaker_match = re.search(r"\|\s*(S\d+)\s*\|", line, re.I)
            picture_match = re.search(r"<Picture\s+\d+>", line, re.I)
            subject_match = re.search(r"<Subject\s+\d+>", line, re.I)
            if speaker_match:
                pending_speaker = speaker_match.group(1).upper()
            if picture_match:
                pending_picture = picture_match.group(0)
            if subject_match:
                pending_subject = subject_match.group(0)
            continue
        dialogue_match = re.search(r"<d>\s*\[([^\]]+)\]\s*(.*?)</d>", line, re.DOTALL)
        if dialogue_match and pending_time:
            entries.append({
                "start": pending_time[0],
                "end": pending_time[1],
                "speaker": pending_speaker,
                "picture": pending_picture,
                "subject": pending_subject,
                "language": dialogue_match.group(1).strip(),
                "lyric": re.sub(r"\s+", " ", dialogue_match.group(2)).strip(),
            })
            pending_time = None
    return entries


def _mv_shot_style(index: int, count: int, duet: bool, chinese: bool, duration: float = 0.0) -> str:
    """Return a distinct MV camera setup without relying on zoom."""
    if chinese:
        if count <= 1:
            return (
                "用一个连续复合长镜头完成整段：低机位广角横移借现场前景揭示歌手，随后以约 30° 受控小弧线转到三分之四近景，"
                "最后 Crane Up 轻微拉远留出环境；所有变化由机位位移和景别转换完成，运动方向清楚"
            )
        if duet:
            opening = (
                "镜头从共享场景的背景线条横移到当前歌手的单人中景，人物保持原场景位置，画面中只有当前歌手一个人"
            )
            middle = (
                "单人低机位中近景，沿当前歌手肩线做平行 Truck，背景产生视差，画面不安排第二张脸",
                "当前歌手三分之四近景，用真实 Dolly In 靠近眼睛，前景只使用场景遮挡，不用另一位歌手当前景",
                "从场景侧后方起幅，围绕当前歌手做约 30° 受控 Arc，让背景层次展开，下一句起唱前切出",
                "手持中近景跟随当前歌手的重心和手势，以肩部转向做动作匹配，再切入新的单人机位",
                "高机位 Crane/Pedestal 小幅下降，越过现场固定前景落到当前歌手的三分之四近景",
            )
            ending = (
                "结尾用 Crane Up 配合 Dolly Out 从当前歌手单人近景拉回共享场景，画面仍只有当前歌手一个人"
            )
        else:
            opening = (
                "低机位三分之二广角横移开场，镜头先读环境再借现场前景视差揭示歌手，首句落下时落到完整面部"
            )
            middle = (
                "低机位中近景，沿肩线做平行 Truck，背景空间线产生速度差，歌手随重音改变重心并转向镜头",
                "三分之四侧面近景用真实 Dolly In 靠近眼睛，焦点从前景边缘拉到眼神，同时保留完整嘴部",
                "从肩后斜角起幅，围绕歌手做约 30° 受控 Arc，在下一句前切到正面反打，避免绕到全侧面",
                "手持中近景跟随身体重心，先跟肩部再抬到眼神；歌手向前半步时用动作匹配硬切到新角度",
                "高机位 Crane/Pedestal 小幅下降，越过现场前景轮廓落到三分之四近景，背景层次向下压缩",
                "侧向滑轨从暗部滑入亮部，利用现场光线变化形成擦镜转场，机位完成半身到近景的自然推进",
            )
            ending = (
                "结尾用 Crane Up 配合 Dolly Out 拉回完整空间，先保留近景再逐渐露出场景，最后停在人物仍演唱的开放构图"
            )
        style = opening if index == 0 else ending if index == count - 1 else middle[(index - 1) % len(middle)]
        if 0 < index < count - 1:
            if duration >= 3.2:
                long_rhythm = (
                    "长句内部让机位连续完成一次明确变化，但不在咬字中间切换",
                    "长音段落把运动拆成前后两拍，先跟动作再落到眼神",
                    "句尾保留短暂稳定落点，让下一次切镜有呼吸空间",
                )
                style += "；" + long_rhythm[index % len(long_rhythm)]
            elif duration <= 1.1:
                short_rhythm = (
                    "短句采用干脆入点和一次轻微机位惯性",
                    "这一句用短促切点和克制的机身运动",
                    "短句以轻快换景推进，画面节奏利落",
                    "句尾不做多余运动，给下一句保留切点",
                )
                style += "；" + short_rhythm[index % len(short_rhythm)]
        return style
    if count <= 1:
        return (
            "Use one continuous compound take: a low-angle wide lateral slider reveals the singer through existing foreground, "
            "then a controlled 30-degree arc settles into a three-quarter close-up, followed by a small crane-up pull-out; "
            "all emphasis comes from camera position and a clear change in shot scale"
        )
    if duet:
        opening = (
            "Lateral slide from the shared background into a solo medium shot of the current singer, keeping the original scene position and only one person in frame"
        )
        middle = (
            "Solo low-angle medium close-up with a parallel shoulder truck, using background parallax and no second face in frame",
            "Three-quarter solo close-up with a real dolly toward the eyes; use only scene foreground, never the other singer, as an occluder",
            "Start from a side-back scene angle and make a controlled 30-degree arc around the current singer, then cut before the next lyric onset",
            "Handheld solo medium follow of the current singer's weight shift and gesture, using the shoulder turn as an action-matched cut",
            "Small high-angle crane or pedestal descent past fixed set foreground onto a three-quarter close-up of the current singer",
        )
        ending = (
            "Finish with a crane-up and dolly-out from the solo close-up back into the shared scene while exactly one singer remains in frame"
        )
    else:
        opening = (
            "Open on a low-angle three-quarter wide lateral slider that reads the environment first and reveals the singer through existing foreground parallax on the first lyric"
        )
        middle = (
            "Low-angle medium close-up with a parallel shoulder truck, using background parallax while the singer shifts weight and turns toward the lens on the accent",
            "Use a three-quarter profile close-up with a real dolly in; rack focus from a foreground edge to the eyes while keeping the entire mouth readable",
            "Start behind the shoulder and make a controlled 30-degree arc onto the face, then cut back to a frontal reverse before a full profile can destabilize identity",
            "Follow the body's weight shift in a handheld medium close-up, move from shoulder to eyeline, and use the half-step toward camera as an action-matched cut",
            "Use a small high-angle crane or pedestal descent past existing foreground onto a three-quarter close-up, compressing the background layers",
            "Slide laterally from shadow into the existing light, using the light change as a wipe-like transition while moving from waist-up framing to a close-up",
        )
        ending = (
            "Finish with a crane-up and dolly-out that reveals the full space, holding the singer in close-up before opening to the environment and ending while the performance continues"
        )
    style = opening if index == 0 else ending if index == count - 1 else middle[(index - 1) % len(middle)]
    if 0 < index < count - 1:
        if duration >= 3.2:
            long_rhythm = (
                "make one clear camera adjustment inside the long lyric span without cutting mid-word",
                "split the sustained phrase into two visual beats, following the body first and landing on the eyes",
                "leave a brief settled landing at the phrase end so the next cut can breathe",
            )
            style += "; " + long_rhythm[index % len(long_rhythm)]
        elif duration <= 1.1:
            short_rhythm = (
                "use a crisp entry and one light camera follow-through",
                "keep the cut short and the camera motion restrained",
                "use a nimble change of setup for this short phrase",
                "settle at the phrase end and preserve a clean cut point",
            )
            style += "; " + short_rhythm[index % len(short_rhythm)]
    return style


def _mv_transition(index: int, count: int, previous: dict[str, Any] | None, current: dict[str, Any], chinese: bool) -> str:
    if index <= 0:
        return "开场" if chinese else "Opening"
    speaker_changed = bool(previous and previous.get("speaker") != current.get("speaker"))
    is_ending = index == count - 1
    if chinese:
        if is_ending:
            return "最后一句起唱时硬切到当前歌手的收束单人机位，上一歌手在切点前闭唇并完全离开画面"
        if speaker_changed:
            return "下一句第一个字硬切到另一位歌手的单人镜头，上一歌手在切点前闭唇并完全离开画面"
        transitions = (
            "句首硬切到新的景别，切点压在歌词起音",
            "顺着手势或转头做动作匹配切，不切在咬字中间",
            "借现场前景边缘擦镜切入新机位，保持人物位置不变",
            "乐句重音处直切近景，用明显的景别跳变加强力度",
        )
        return transitions[(index - 1) % len(transitions)]
    if is_ending:
        return "Hard cut to the current singer's solo closing setup on the final lyric onset; the previous singer closes the lips and leaves frame before the cut"
    if speaker_changed:
        return "Hard cut to the other singer's solo setup on the first syllable; the previous singer closes the lips and leaves frame before the cut"
    transitions = (
        "Hard cut to a new shot scale on the lyric onset, never mid-word",
        "Use a gesture or head turn as an action-matched cut",
        "Wipe through the edge of existing foreground into a new camera position while the singer stays put",
        "Cut directly to a close-up on the musical accent to add emphasis through a clear change of shot scale",
    )
    return transitions[(index - 1) % len(transitions)]


def _mv_performance(index: int, count: int, chinese: bool) -> str:
    if chinese:
        if count <= 1:
            return "表演从自然呼吸和克制的重心变化开始，唱到长音时抬眼，结尾减小动作并把视线留在场景里"
        if index == 0:
            return "表演从自然呼吸起，第一句后半抬眼看向镜头，肩颈随旋律松沉，不做重复机械摆手"
        if index == count - 1:
            return "最后一句收小动作，眼神从镜头移向共享场景，保留余韵"
        if index % 3 == 1:
            return "随重音改变重心，只做一次明确的抬手或落肩，胸口呼吸和下颌动作连续"
        if index % 3 == 2:
            return "在长音处略微侧身再回到镜头，眼神先移动、身体随后跟上，避免僵硬站桩"
        return "动作幅度随乐句提升，向前半步并抬眸，嘴部始终完整可见"
    if count <= 1:
        return "Start with natural breathing and a restrained weight shift, lift the eyes on a sustained note, then reduce the gesture at the end and leave the gaze in the scene"
    if index == 0:
        return "Start from natural breathing, lift the eyes toward the lens in the second half of the first line, and release the shoulders with the melody instead of repeating a mechanical hand wave"
    if index == count - 1:
        return "Reduce the gesture on the final line, move the gaze from the lens toward the shared scene, and leave a quiet afterbeat"
    if index % 3 == 1:
        return "Shift weight on the accent, make one clear hand lift or shoulder release, and keep breathing and jaw motion continuous"
    if index % 3 == 2:
        return "Turn slightly away on the sustained note and return to the lens, leading with the eyes and letting the body follow without freezing"
    return "Increase the physical commitment with the phrase, take half a step toward camera, lift the eyes, and keep the whole mouth visible"


def _mv_duet_singer_labels(entry: dict[str, Any], context: dict, chinese: bool) -> tuple[str, str]:
    male = context.get("male") if isinstance(context.get("male"), dict) else {}
    female = context.get("female") if isinstance(context.get("female"), dict) else {}
    speaker = str(entry.get("speaker") or "").upper()
    active_mapping = None
    active_role = ""
    inactive_mapping = None
    inactive_role = ""
    if speaker and speaker == str(male.get("speaker") or "").upper():
        active_mapping, active_role = male, ("男声歌手" if chinese else "male singer")
        inactive_mapping, inactive_role = female, ("女声歌手" if chinese else "female singer")
    elif speaker and speaker == str(female.get("speaker") or "").upper():
        active_mapping, active_role = female, ("女声歌手" if chinese else "female singer")
        inactive_mapping, inactive_role = male, ("男声歌手" if chinese else "male singer")
    if not active_mapping or not inactive_mapping:
        active = f"{entry['subject']} ({entry['speaker']})"
        inactive = "另一位歌手" if chinese else "the other singer"
        return active, inactive
    active = f"{active_role} {entry['subject']} ({entry['speaker']})"
    inactive = (
        f"{inactive_role} {inactive_mapping.get('subject') or '<Subject>'} "
        f"({inactive_mapping.get('speaker') or 'S?'})"
    )
    return active, inactive


def _build_mv_shot_timeline(lyric_timeline: str, output_language: str, context: dict) -> str:
    entries = _parse_lyric_timeline(lyric_timeline)
    if not entries:
        return ""
    chinese = str(output_language).lower().startswith(("zh", "chinese", "中文"))
    duet = bool(context.get("duet"))
    scene_subject = str((context.get("scene") or {}).get("subject") or "").strip()
    lines = []
    for index, entry in enumerate(entries):
        previous = entries[index - 1] if index else None
        next_entry = entries[index + 1] if index + 1 < len(entries) else None
        duration = max(0.0, float(entry.get("end", 0.0)) - float(entry.get("start", 0.0)))
        style = _mv_shot_style(index, len(entries), duet, chinese, duration)
        transition = _mv_transition(index, len(entries), previous, entry, chinese)
        performance = _mv_performance(index, len(entries), chinese)
        if duet:
            active, inactive = _mv_duet_singer_labels(entry, context, chinese)
        else:
            single = context.get("single") if isinstance(context.get("single"), dict) else {}
            single_gender = str(single.get("gender") or "").lower()
            voice_role = (
                ("女声歌手" if chinese else "female singer")
                if single_gender == "female" else
                ("男声歌手" if chinese else "male singer")
                if single_gender == "male" else ""
            )
            active = f"{voice_role} {entry['subject']} ({entry['speaker']})".strip()
            inactive = ""
        time_range = f"{_fmt_h3_ts(entry['start'])}-{_fmt_h3_ts(entry['end'])}"
        speaker_change_next = bool(next_entry and next_entry.get("speaker") != entry.get("speaker"))
        if chinese:
            scene_continuity = (
                f"人物始终位于 {scene_subject} 的同一空间，" if scene_subject else "人物始终处于同一共享场景，"
            )
            if duet:
                solo_visibility = (
                    f"本镜为单人演唱镜头：画面中有且只有 {active} 一个人；{inactive} 完全在画外，"
                    "不出现第二张脸、第二张嘴、第二具身体、第二个人影或任何口型动作。"
                )
                handoff = (
                    "本段结束处嘴唇自然闭合；下一镜只切到另一位歌手。"
                    if speaker_change_next else
                    "本段结束处嘴唇自然闭合；下一镜仍只保留当前歌手。"
                )
            else:
                solo_visibility = ""
                handoff = "人物身份、服装和空间关系保持连续。"
            shot_header = (
                f"[Shot {index + 1}] {transition}。{style}。"
                if index == 0 else
                f"[Shot {index + 1}] 在 {_fmt_h3_ts(entry['start'])} 处，{transition}。{style}。"
            )
            block = (
                f"{shot_header}\n{solo_visibility}{scene_continuity}{active} 是当前唯一开口演唱者；"
                "以锁定歌曲音轨中的原声音色、语速、咬字和气息演唱，嘴唇、下颌、呼吸、眼神和头肩律动严格同步。"
                f"{performance}。{handoff}\n{time_range}，{active} 演唱："
            )
        else:
            scene_continuity = (
                f"Stay inside one continuous space in {scene_subject}. "
                if scene_subject else "Stay inside one continuous shared environment. "
            )
            if duet:
                solo_visibility = (
                    f"This is a solo-singer shot: exactly one person, {active}, is in frame. {inactive} is completely off-screen, "
                    "with no second face, mouth, body, silhouette, or lip movement."
                )
                handoff = (
                    "Close the lips naturally at the end of this lyric; the next cut shows only the other singer."
                    if speaker_change_next else
                    "Close the lips naturally at the end of this lyric; the next shot still keeps only the current singer."
                )
            else:
                solo_visibility = ""
                handoff = "Identity, clothing, and spatial relationships remain continuous."
            shot_header = (
                f"[Shot {index + 1}] {transition}. {style}."
                if index == 0 else
                f"[Shot {index + 1}] At {_fmt_h3_ts(entry['start'])}, {transition}. {style}."
            )
            block = (
                f"{shot_header}\n{solo_visibility}{scene_continuity}{active} is the only singer opening the mouth, "
                "using the exact timbre, pacing, articulation, and breath from the locked song track; lips, jaw, breathing, gaze, "
                f"head, and shoulder motion stay synchronized. {performance}. {handoff}\n{time_range}, {active} sings:"
            )
        lines.append(f"{block}\n<d>[{entry['language']}] {entry['lyric']}</d>")
    return "\n\n".join(lines)


def _inject_audio_reverse_lyrics(prompt: str, lyric_timeline: str, output_language: str = "中文", context: dict | None = None) -> str:
    context = context if isinstance(context, dict) else {}
    """Insert exact timed lyrics into detailed_description after cleaning model-generated lyrics."""
    sections = _split_audio_reverse_sections(prompt)
    if not sections:
        return prompt
    mv_timeline = _build_mv_shot_timeline(lyric_timeline, output_language, context)
    if not mv_timeline:
        return prompt
    sections["detailed_description"] = mv_timeline
    kept = [f"{name}:\n{sections[name]}" for name in _H3_SECTION_ORDER if sections.get(name)]
    return "\n\n".join(kept).strip()


def _finalize_audio_reverse_output(text: str, lyric_timeline: str, output_language: str, context: dict | None = None) -> str:
    value = _sanitize_audio_reverse_output(text)
    value = _replace_audio_tags(value, output_language)
    value = _ensure_audio_reverse_sections(value, output_language, context)
    value = _inject_audio_reverse_lyrics(value, lyric_timeline, output_language, context)
    return _replace_audio_tags(value, output_language).strip()


def _normalize_subject_shorthand(text: str) -> str:
    """Guarantee that standalone S1-S20 references use official parentheses."""
    return re.sub(
        r"(?<![A-Za-z0-9_(<（])S([1-9]|1\d|20)(?![A-Za-z0-9_)>）])",
        lambda match: f"(S{match.group(1)})",
        str(text),
        flags=re.IGNORECASE,
    )


def _extract_explicit_dialogues(prompt: str) -> list[tuple[str, str]]:
    """Extract only dialogue that the user explicitly supplied, preserving its exact text."""
    source = str(prompt or "")
    candidates = []
    for match in re.finditer(
        r"<d>\s*(?:\[([^\]]+)\]\s*)?(.*?)\s*</d>",
        source,
        flags=re.IGNORECASE | re.DOTALL,
    ):
        value = re.sub(r"\s+", " ", match.group(2) or "").strip().strip("“”‘’\"'").strip()
        if not value:
            continue
        language = (match.group(1) or "").strip() or (
            "Chinese" if re.search(r"[\u3400-\u9fff]", value) else "English"
        )
        candidates.append((value, language))
    speech_marker = r"(?:说|说道|说着|喊|喊道|问|问道|回答|答道|台词|对白|says?|speaks?|shouts?|asks?|replies?)"
    patterns = (
        rf"{speech_marker}[^\n“”‘’\"']{{0,20}}[：:]?\s*[“\"]([^”\"\n]+)[”\"]",
        rf"{speech_marker}[^\n“”‘’\"']{{0,20}}[：:]?\s*[‘']([^’'\n]+)[’']",
        rf"{speech_marker}\s*[：:]\s*([^\n；;]+)",
    )
    for pattern in patterns:
        for match in re.finditer(pattern, source, flags=re.IGNORECASE):
            value = match.group(1).strip().strip("“”‘’\"'").strip()
            existing = {item[0] for item in candidates}
            if not value or value in existing or any(value in item or item in value for item in existing):
                continue
            language = "Chinese" if re.search(r"[\u3400-\u9fff]", value) else "English"
            candidates.append((value, language))
    return candidates


def _remove_unsupplied_dialogues(text: str, user_prompt: str) -> str:
    """Drop model-invented <d> blocks while preserving user-supplied dialogue."""
    def canonical(value: str) -> str:
        return re.sub(r"\s+", "", str(value or "")).strip().strip("“”‘’\"'")

    supplied_keys = {
        canonical(value)
        for value, _language in _extract_explicit_dialogues(user_prompt)
        if canonical(value)
    }
    value = str(text or "")

    def replace(match):
        body = match.group(1)
        plain = re.sub(r"^\s*\[[^\]]+\]\s*", "", body).strip()
        if plain and canonical(plain) in supplied_keys:
            return match.group(0)
        return ""

    value = re.sub(r"<d>(.*?)</d>", replace, value, flags=re.IGNORECASE | re.DOTALL)
    value = re.sub(
        r"(?i)(?:the\s+)?(?:on-screen\s+speaker|speaker|character)?\s*\(S\d+\)?\s*"
        r"(?:says?|speaks?|shouts?|asks?|replies?|说|说道|开口说)\s*[:：]?\s*",
        " maintains the original speaking motion, lip-sync, and mouth timing. ",
        value,
    )
    value = re.sub(r"[ \t]{2,}", " ", value)
    return value

def _ensure_supplied_dialogues(text: str, user_prompt: str, output_language: str) -> str:
    """Keep supplied dialogue exactly once and inside the main shot timeline."""
    result = str(text)
    dialogues_to_insert = []
    for index, (dialogue, language) in enumerate(_extract_explicit_dialogues(user_prompt), start=1):
        tag = f"<d>[{language}]{dialogue}</d>"
        main_heading = re.search(
            r"(?:integrated_multimodal_description|detailed_description)\s*:\s*",
            result,
            flags=re.IGNORECASE,
        )
        main_start = main_heading.end() if main_heading else 0
        main_end_match = re.search(
            r"(?:overall_soundscape|non_diegetic_music)\s*:\s*",
            result[main_start:],
            flags=re.IGNORECASE,
        )
        main_end = main_start + main_end_match.start() if main_end_match else len(result)
        timeline = result[main_start:main_end]
        if tag in timeline:
            # Remove accidental duplicates outside the timeline while preserving the valid occurrence.
            prefix = result[:main_start].replace(tag, "")
            suffix = result[main_end:].replace(tag, "")
            result = prefix + timeline + suffix
            continue
        # A correctly tagged line outside the shot timeline is structurally invalid; move rather than duplicate it.
        result = result.replace(tag, "")
        main_heading = re.search(
            r"(?:integrated_multimodal_description|detailed_description)\s*:\s*",
            result,
            flags=re.IGNORECASE,
        )
        main_start = main_heading.end() if main_heading else 0
        main_end_match = re.search(
            r"(?:overall_soundscape|non_diegetic_music)\s*:\s*",
            result[main_start:],
            flags=re.IGNORECASE,
        )
        main_end = main_start + main_end_match.start() if main_end_match else len(result)
        timeline = result[main_start:main_end]
        if dialogue in timeline:
            replaced = False
            for quoted in (f"“{dialogue}”", f"‘{dialogue}’", f'"{dialogue}"', f"'{dialogue}'"):
                if quoted in timeline:
                    timeline = timeline.replace(quoted, tag, 1)
                    replaced = True
                    break
            if not replaced:
                timeline = timeline.replace(dialogue, tag, 1)
            result = result[:main_start] + timeline + result[main_end:]
            continue
        dialogues_to_insert.append((index, tag))

    if dialogues_to_insert:
        main_heading = re.search(
            r"(?:integrated_multimodal_description|detailed_description)\s*:\s*",
            result,
            flags=re.IGNORECASE,
        )
        main_start = main_heading.end() if main_heading else 0
        main_end_match = re.search(
            r"(?:overall_soundscape|non_diegetic_music)\s*:\s*",
            result[main_start:],
            flags=re.IGNORECASE,
        )
        main_end = main_start + main_end_match.start() if main_end_match else len(result)
        timeline = result[main_start:main_end]
        cue = re.search(
            r"(?:开口说话|开始说话|随后说|继续说|说话|演唱|唱着|begins? speaking|starts? speaking|speaks?|says?|sings?)",
            timeline,
            flags=re.IGNORECASE,
        )
        if cue:
            boundary = re.search(r"[。！？.!?](?:\s|$)", timeline[cue.end():])
            insert_at = cue.end() + boundary.end() if boundary else cue.end()
        else:
            shot = re.search(r"\[Shot 1\]\s*", timeline, flags=re.IGNORECASE)
            insert_at = shot.end() if shot else 0
        sentences = []
        for order, (index, tag) in enumerate(dialogues_to_insert):
            if str(output_language).lower() in {"中文", "chinese", "zh", "zh-cn"}:
                action = "说" if order == 0 else "随后继续说"
                sentences.append(f"画面中的说话者 (S{index}) {action}：{tag}")
            else:
                action = "says" if order == 0 else "then continues"
                sentences.append(f"The on-screen speaker (S{index}) {action}: {tag}")
        insertion = " " + " ".join(sentences) + " "
        timeline = timeline[:insert_at] + insertion + timeline[insert_at:]
        result = result[:main_start] + timeline + result[main_end:]
    return re.sub(r"[ \t]+\n", "\n", result).strip()


def _ensure_fl2va_picture_labels(text: str, task: str, duration: float, output_language: str) -> str:
    """Guarantee that an FL2VA result retains both official bare picture labels."""
    if str(task).upper() != "FL2VA":
        return text
    lowered = str(text).lower()
    if "picture 1" in lowered and "picture 2" in lowered:
        return text
    if str(output_language).lower() in {"中文", "chinese", "zh", "zh-cn"}:
        alignment = (
            f"参考图像与目标视频对齐关系：picture 1 对齐目标视频的 0.00 秒首帧；"
            f"picture 2 对齐目标视频的 {duration:.2f} 秒尾帧。"
        )
    else:
        alignment = (
            "Reference-picture alignment: picture 1 is the target video's exact opening frame at 0.00s; "
            f"picture 2 is its exact ending frame at {duration:.2f}s."
        )
    return f"{alignment}\n\n{text}".strip()


def _extract_openai(data: dict) -> str:
    try:
        content = data["choices"][0]["message"]["content"]
        if isinstance(content, list):
            return "".join(str(item.get("text") or "") for item in content if isinstance(item, dict)).strip()
        return str(content).strip()
    except (KeyError, IndexError, TypeError):
        raise RuntimeError("The API returned no optimized prompt")


def _extract_openai_responses(data: dict) -> str:
    direct = data.get("output_text")
    if isinstance(direct, str) and direct.strip():
        return direct.strip()
    texts = []
    for output in data.get("output") or []:
        if not isinstance(output, dict):
            continue
        for content in output.get("content") or []:
            if not isinstance(content, dict) or content.get("type") not in {"output_text", "text"}:
                continue
            value = content.get("text")
            if isinstance(value, dict):
                value = value.get("value")
            if value:
                texts.append(str(value))
    if texts:
        return "".join(texts).strip()
    raise RuntimeError("OpenAI Responses returned no optimized prompt")


def _request_parts(config: dict, payload: dict):
    task = str(payload.get("task") or "T2VA")
    duration = float(payload.get("duration") or 5)
    media = payload.get("media") if isinstance(payload.get("media"), list) else []
    labels = [str(item.get("label")) for item in media if item.get("label")]
    user_prompt = str(payload.get("prompt") or "")
    context = payload.get("context") if isinstance(payload.get("context"), dict) else {}
    system = _system_prompt(
        task,
        duration,
        labels,
        str(config.get("output_language") or "English"),
        context,
        user_prompt,
    )
    extra_system = str(payload.get("system") or "").strip()
    if extra_system:
        system = f"{system}\n\n{extra_system}"
    parts = _user_parts(user_prompt, media, bool(config.get("read_media")))
    headers = {"Content-Type": "application/json"}
    if config["protocol"] == "gemini":
        gemini_parts = []
        for part in parts:
            if part["type"] == "text":
                gemini_parts.append({"text": part["text"]})
            else:
                url = part["image_url"]["url"]
                header, encoded = url.split(",", 1)
                mime = header.split(";")[0].split(":", 1)[1]
                gemini_parts.append({"inline_data": {"mime_type": mime, "data": encoded}})
        body = {
            "system_instruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": gemini_parts}],
            "generationConfig": {"temperature": 0.35, "maxOutputTokens": 2048},
        }
        url = _endpoint(config)
        separator = "&" if "?" in url else "?"
        url += separator + "key=" + urllib.parse.quote(config["api_key"])
    elif config["protocol"] == "responses":
        response_parts = []
        for part in parts:
            if part["type"] == "text":
                response_parts.append({"type": "input_text", "text": part["text"]})
            else:
                response_parts.append({
                    "type": "input_image",
                    "image_url": part["image_url"]["url"],
                    "detail": part["image_url"].get("detail", "low"),
                })
        body = {
            "model": config["model"],
            "instructions": system,
            "input": [{"role": "user", "content": response_parts}],
            "temperature": 0.35,
            "max_output_tokens": 2048,
        }
        headers["Authorization"] = f"Bearer {config['api_key']}"
        url = _endpoint(config)
    else:
        body = {
            "model": config["model"],
            "temperature": 0.35,
            "max_tokens": 2048,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": parts},
            ],
        }
        headers["Authorization"] = f"Bearer {config['api_key']}"
        url = _endpoint(config)
    return url, headers, body


async def _request_runninghub(config: dict, payload: dict) -> str:
    api_key = str(config.get("api_key") or "")
    request_id = str(payload.get("request_id") or "")
    media = payload.get("media") if isinstance(payload.get("media"), list) else []
    task = str(payload.get("task") or "T2VA")
    duration = float(payload.get("duration") or 5)
    labels = [str(item.get("label")) for item in media if item.get("label")]
    system_prompt = _system_prompt(
        task, duration, labels, str(config.get("output_language") or "English"),
        payload.get("context") if isinstance(payload.get("context"), dict) else {},
        str(payload.get("prompt") or ""),
    )
    extra_system = str(payload.get("system") or "").strip()
    if extra_system:
        system_prompt = f"{system_prompt}\n\n{extra_system}"
    mapping_notes = []
    node_values = {
        "11": "None", "2": "None", "12": "None", "13": "None", "14": "None",
        "15": "None", "16": "None", "17": "None", "18": "None",
    }
    image_nodes = ("2", "12", "13", "14", "15", "16", "17", "18")
    timeout = aiohttp.ClientTimeout(total=200)
    temp_dir = Path(tempfile.mkdtemp(prefix="gh_h3_rh_"))
    task_id = ""
    try:
        async with aiohttp.ClientSession(timeout=timeout) as session:
            image_index = 0
            video_uploaded = False
            for item in media:
                kind = str(item.get("kind") or "")
                label = str(item.get("label") or "")
                if kind == "image":
                    images = item.get("images") or []
                    if image_index < len(image_nodes) and images:
                        node_id = image_nodes[image_index]
                        node_values[node_id] = await _runninghub_upload(
                            session, api_key, data_url=images[0], filename=f"reference_{image_index + 1}.jpg"
                        )
                        mapping_notes.append(f"{label} corresponds to uploaded image {image_index + 1}.")
                        image_index += 1
                    else:
                        mapping_notes.append(f"{label} exists as an image reference label, but its visual file was not transmitted.")
                elif kind == "video" and not item.get("labelOnly"):
                    if not video_uploaded and item.get("source_name"):
                        processed = temp_dir / "reference_1fps.mp4"
                        await _runninghub_video(str(item["source_name"]), duration, processed)
                        node_values["11"] = await _runninghub_upload(session, api_key, path=processed)
                        mapping_notes.append(f"{label} corresponds to the uploaded 1 FPS reference video.")
                        video_uploaded = True
                    else:
                        mapping_notes.append(f"{label} exists as a video reference label, but its visual file was not transmitted.")
                elif kind == "audio":
                    mapping_notes.append(f"{label} is an audio reference label; audio data is not separately transmitted.")

            user_prompt = "User prompt:\n" + str(payload.get("prompt") or "")
            if mapping_notes:
                user_prompt += "\n\nReference mapping:\n" + "\n".join(mapping_notes)
            node_info = [
                {"nodeId": "11", "fieldName": "file", "fieldValue": node_values["11"]},
                *[
                    {"nodeId": node_id, "fieldName": "image", "fieldValue": node_values[node_id]}
                    for node_id in image_nodes
                ],
                {"nodeId": "1", "fieldName": "model", "fieldValue": str(config.get("model") or RUNNINGHUB_MODELS[0])},
                {"nodeId": "9", "fieldName": "Text", "fieldValue": system_prompt},
                {"nodeId": "10", "fieldName": "Text", "fieldValue": user_prompt},
            ]
            async with session.post(
                f"https://www.runninghub.cn/openapi/v2/run/ai-app/{RUNNINGHUB_APP_ID}",
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json={"nodeInfoList": node_info, "instanceType": "default", "usePersonalQueue": False},
            ) as response:
                body = await response.text()
                if response.status >= 400:
                    raise RuntimeError(f"RunningHub 应用启动失败 ({response.status}): {body[:1000]}")
                started = json.loads(body)
            if started.get("code") not in (0, "0", None):
                raise RuntimeError(f"RunningHub 应用启动失败: {started.get('msg') or started}")
            start_data = started.get("data") if isinstance(started.get("data"), dict) else started
            task_id = str(start_data.get("taskId") or "")
            if not task_id:
                raise RuntimeError("RunningHub 应用启动响应缺少 taskId")
            if request_id:
                _ACTIVE_RH_TASKS[request_id] = (api_key, task_id)

            while True:
                cancel_event = payload.get("_cancel_event")
                if cancel_event is not None and cancel_event.is_set():
                    await _runninghub_cancel(api_key, task_id)
                    raise asyncio.CancelledError
                await asyncio.sleep(2)
                async with session.post(
                    "https://www.runninghub.cn/openapi/v2/query",
                    headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                    json={"taskId": task_id},
                ) as response:
                    body = await response.text()
                    if response.status >= 400:
                        raise RuntimeError(f"RunningHub 任务查询失败 ({response.status}): {body[:1000]}")
                    queried = json.loads(body)
                if queried.get("code") not in (0, "0", None):
                    raise RuntimeError(f"RunningHub 任务查询失败: {queried.get('msg') or queried}")
                query_data = queried.get("data") if isinstance(queried.get("data"), dict) else queried
                status = str(query_data.get("status") or query_data.get("taskStatus") or "").upper()
                if status == "SUCCESS":
                    return await _runninghub_result_text(session, query_data.get("results") or [])
                if status in {"FAILED", "CANCELLED", "CANCELED"}:
                    message = query_data.get("errorMessage") or query_data.get("failedReason") or status
                    raise RuntimeError(f"RunningHub 提示词优化失败: {message}")
    except asyncio.CancelledError:
        active = _ACTIVE_RH_TASKS.get(request_id)
        if active:
            await _runninghub_cancel(*active)
        elif task_id:
            await _runninghub_cancel(api_key, task_id)
        raise
    except asyncio.TimeoutError as error:
        if task_id:
            await _runninghub_cancel(api_key, task_id)
        raise RuntimeError("RunningHub 提示词优化超过200秒，云端任务已取消") from error
    finally:
        if request_id:
            _ACTIVE_RH_TASKS.pop(request_id, None)
        shutil.rmtree(temp_dir, ignore_errors=True)


async def _request_async(config: dict, payload: dict) -> str:
    if config.get("mode") == "local":
        model_path = _local_model_path(config)
        if model_path.suffix.lower() != ".gguf" and _local_missing_dependencies():
            raise RuntimeError("本地视觉模型依赖缺失: " + ", ".join(_local_missing_dependencies()))
        try:
            return await asyncio.wait_for(asyncio.to_thread(_local_generate, config, payload), timeout=200)
        except (asyncio.TimeoutError, asyncio.CancelledError):
            cancel_event = payload.get("_cancel_event")
            if cancel_event:
                cancel_event.set()
            raise
    if config.get("provider") == "runninghub" or config.get("protocol") == "runninghub":
        return await _request_runninghub(config, payload)
    url, headers, body = _request_parts(config, payload)
    try:
        timeout = aiohttp.ClientTimeout(total=200)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(url, headers=headers, json=body) as response:
                text = await response.text()
                if response.status >= 400:
                    raise RuntimeError(f"API request failed ({response.status}): {text[:1000]}")
                data = json.loads(text)
    except asyncio.CancelledError:
        raise
    except (aiohttp.ClientError, asyncio.TimeoutError, ValueError) as error:
        raise RuntimeError(f"API request failed: {error}") from error
    if config["protocol"] == "gemini":
        try:
            return "".join(part.get("text", "") for part in data["candidates"][0]["content"]["parts"]).strip()
        except (KeyError, IndexError, TypeError):
            raise RuntimeError("Gemini returned no optimized prompt")
    if config["protocol"] == "responses":
        return _extract_openai_responses(data)
    return _extract_openai(data)


def generate_local_prompt(config: dict, payload: dict) -> str:
    """AICG3D 公共入口：供插件内其他节点复用本地视觉模型引擎。

    config 需要 local_model / local_mmproj / local_device / output_language；
    payload 支持 prompt / system / media / task / duration / context / _cancel_event，
    其中 system 由调用方提供时会覆盖内置的通用系统提示词。
    """
    return _local_generate(_normalize_config(config), payload)


def generate_prompt_sync(config: dict | None, payload: dict) -> str:
    """Synchronous workflow-node entry point for local and online models."""
    normalized = _normalize_config({**load_config(), **(config or {})})
    if normalized.get("mode") == "local":
        result = generate_local_prompt(normalized, payload)
    else:
        result_box: dict[str, object] = {}

        def _worker() -> None:
            try:
                result_box["value"] = asyncio.run(_request_async(normalized, payload))
            except BaseException as error:  # forwarded to the caller
                result_box["error"] = error

        worker = threading.Thread(target=_worker, name="AICG3DSkillPrompt", daemon=True)
        worker.start()
        worker.join()
        if "error" in result_box:
            raise result_box["error"]
        result = str(result_box.get("value") or "")
    if not result:
        raise RuntimeError("提示词模型返回了空内容")
    task_upper = str(payload.get("task") or "").upper()
    if task_upper in {"IMAGE_REVERSE", "T2I", "FL2I"}:
        return _sanitize_direct_image_output(_strip_filenames(str(result)))
    if task_upper == "VIDEO_REVERSE":
        formatted = _format_prompt_sections(_strip_filenames(result))
        return _sanitize_h3_output(_normalize_subject_shorthand(formatted))
    formatted = _format_prompt_sections(_strip_filenames(result))
    formatted = _ensure_fl2va_picture_labels(
        formatted,
        str(payload.get("task") or "T2VA"),
        float(payload.get("duration") or 5),
        str(normalized.get("output_language") or "English"),
    )
    formatted = _ensure_supplied_dialogues(
        formatted,
        str(payload.get("prompt") or ""),
        str(normalized.get("output_language") or "English"),
    )
    formatted = _remove_unsupplied_dialogues(formatted, str(payload.get("prompt") or ""))
    result_clean = _sanitize_h3_output(_normalize_subject_shorthand(formatted))
    if task_upper == "AUDIO_REVERSE":
        result_clean = _finalize_audio_reverse_output(
            result_clean,
            str(payload.get("lyric_timeline") or ""),
            str(normalized.get("output_language") or "English"),
            payload.get("audio_reverse_context") if isinstance(payload.get("audio_reverse_context"), dict) else {},
        )
    return result_clean


def scan_local_models() -> list[dict]:
    return _scan_visual_models()


def missing_local_dependencies() -> list[str]:
    return _local_missing_dependencies()


def gguf_dependency_status() -> dict:
    return _gguf_dependency_status()


async def get_prompt_optimizer_config(_request):
    config = _public_config(load_config())
    config["models"] = _scan_visual_models()
    config["mmproj_files"] = _mmproj_options()
    config["missing_dependencies"] = _local_missing_dependencies()
    config["gguf_dependency"] = _gguf_dependency_status()
    return web.json_response(config)


def _local_missing_dependencies() -> list[str]:
    import importlib.util
    required = ("torch", "transformers", "PIL", "accelerate", "safetensors")
    return [name for name in required if importlib.util.find_spec(name) is None]


async def list_prompt_optimizer_models(_request):
    return web.json_response({
        "models": _scan_visual_models(),
        "mmproj_files": _mmproj_options(),
        "missing_dependencies": _local_missing_dependencies(),
        "gguf_dependency": _gguf_dependency_status(),
    })


async def refresh_runninghub_models(_request):
    try:
        models = await _refresh_runninghub_models()
        return web.json_response({"runninghub_models": list(models)})
    except Exception as error:
        return web.json_response({"error": str(error)}, status=502)


async def save_prompt_optimizer_config(request):
    config = save_config(await request.json())
    return web.json_response(_public_config(config))


async def optimize_prompt(request):
    request_id = ""
    try:
        payload = await request.json()
        request_id = str(payload.get("request_id") or "")
        cancel_event = threading.Event()
        payload["_cancel_event"] = cancel_event
        if request_id:
            previous_cancel_event = _ACTIVE_CANCEL_EVENTS.pop(request_id, None)
            if previous_cancel_event is not None:
                previous_cancel_event.set()
            _ACTIVE_CANCEL_EVENTS[request_id] = cancel_event
        node_config = payload.get("config") if isinstance(payload.get("config"), dict) else {}
        config = _normalize_config({**load_config(), **node_config})
        if config.get("mode") == "local":
            model_path = _local_model_path(config)
            if model_path.suffix.lower() == ".gguf":
                _selected_mmproj(config, _selected_local_model(config))
            elif _local_missing_dependencies():
                raise RuntimeError("本地视觉模型依赖缺失: " + ", ".join(_local_missing_dependencies()))
        elif not config.get("api_url") or not config.get("model") or not config.get("api_key"):
            raise ValueError("请先配置提示词优化 API")
        task = asyncio.create_task(_request_async(config, payload))
        if request_id:
            previous = _ACTIVE_REQUESTS.pop(request_id, None)
            if previous is not None:
                previous.cancel()
            _ACTIVE_REQUESTS[request_id] = task
        result = await task
        if not result:
            raise RuntimeError("API 返回了空提示词")
        task_name = str(payload.get("task") or "").upper()
        cleaned = _strip_filenames(result)
        if task_name in {"IMAGE_REVERSE", "T2I", "FL2I"}:
            return web.json_response({"prompt": _sanitize_direct_image_output(cleaned)})
        formatted = _format_prompt_sections(cleaned)
        if task_name == "AUDIO_REVERSE":
            formatted = _sanitize_h3_output(_normalize_subject_shorthand(formatted))
            formatted = _finalize_audio_reverse_output(
                formatted,
                str(payload.get("lyric_timeline") or ""),
                str(config.get("output_language") or "English"),
                payload.get("audio_reverse_context") if isinstance(payload.get("audio_reverse_context"), dict) else {},
            )
            return web.json_response({"prompt": formatted})
        if task_name != "VIDEO_REVERSE":
            formatted = _ensure_fl2va_picture_labels(
                formatted,
                str(payload.get("task") or "T2VA"),
                float(payload.get("duration") or 5),
                str(config.get("output_language") or "English"),
            )
        formatted = _ensure_supplied_dialogues(
            formatted,
            str(payload.get("prompt") or ""),
            str(config.get("output_language") or "English"),
        )
        formatted = _remove_unsupplied_dialogues(formatted, str(payload.get("prompt") or ""))
        formatted = _sanitize_h3_output(_normalize_subject_shorthand(formatted))
        return web.json_response({"prompt": formatted})
    except asyncio.CancelledError:
        return web.json_response({"error": "提示词优化已取消"}, status=499)
    except Exception as error:
        return web.json_response({"error": str(error)}, status=400)
    finally:
        if request_id:
            _ACTIVE_REQUESTS.pop(request_id, None)
            _ACTIVE_CANCEL_EVENTS.pop(request_id, None)


async def cancel_prompt_optimization(request):
    payload = await request.json()
    request_id = str(payload.get("request_id") or "")
    task = _ACTIVE_REQUESTS.pop(request_id, None)
    cancel_event = _ACTIVE_CANCEL_EVENTS.pop(request_id, None)
    if cancel_event is not None:
        cancel_event.set()
    if task is not None:
        task.cancel()
    runninghub_task = _ACTIVE_RH_TASKS.pop(request_id, None)
    if runninghub_task is not None:
        try:
            await _runninghub_cancel(*runninghub_task)
        except Exception:
            pass
    return web.json_response({"cancelled": task is not None or cancel_event is not None or runninghub_task is not None})


def register_prompt_optimizer_routes() -> bool:
    global _ROUTES_REGISTERED
    if _ROUTES_REGISTERED:
        return True
    instance = getattr(PromptServer, "instance", None)
    if instance is None:
        return False
    routes = instance.routes
    routes.get("/aicg3d-skills/api/config")(get_prompt_optimizer_config)
    routes.get("/aicg3d-skills/api/models")(list_prompt_optimizer_models)
    routes.get("/aicg3d-skills/api/runninghub-models")(refresh_runninghub_models)
    routes.post("/aicg3d-skills/api/config")(save_prompt_optimizer_config)
    routes.post("/aicg3d-skills/api/optimize")(optimize_prompt)
    routes.post("/aicg3d-skills/api/cancel")(cancel_prompt_optimization)
    _ROUTES_REGISTERED = True
    return True


register_prompt_optimizer_routes()
