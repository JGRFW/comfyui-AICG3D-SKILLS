# Copyright (C) 2026 AICG3D
# SPDX-License-Identifier: GPL-3.0-or-later
"""User-facing ComfyUI nodes for comfyui-AICG3D-SKILLS."""

from __future__ import annotations

import base64
import hashlib
import io
import json
import re
from typing import Any

from engine import composer, dialogue, optimizer, skills, validator

CATEGORY = "AICG3D SKILLS"
MEDIA_BUNDLE_TYPE = "MINIMAX_H3_MEDIA_BUNDLE"
MODES = tuple(composer.MODE_TO_TASK)
ASPECTS = tuple(composer.RATIO_VALUES)
INTENSITIES = tuple(composer.INTENSITY_TEXT)
OUTPUT_LANGUAGES = ("中文", "English")
DIGITAL_HUMAN_PROMPT_TASK = "数字人提示词生成"
LEGACY_AUDIO_REVERSE_TASK = "音频反推提示词"
QUICK_TASKS = ("普通创作", "图片反推提示词", "视频反推提示词", DIGITAL_HUMAN_PROMPT_TASK, LEGACY_AUDIO_REVERSE_TASK)
LOCAL_DEVICES = ("cuda", "cpu")
PROVIDERS = tuple(optimizer.PROVIDERS)


def _as_text(value: Any) -> str:
    return str(value or "").strip()


def _content_fingerprint(value: Any) -> str:
    """Stable cache key for AUDIO/IMAGE tensors and ComfyUI audio mappings."""
    if value is None:
        return "none"
    if isinstance(value, dict):
        waveform = value.get("waveform")
        if waveform is not None:
            return f"{_content_fingerprint(waveform)}|rate={value.get('sample_rate')}"
        images = value.get("images")
        if images is not None:
            return _content_fingerprint(images)
    if hasattr(value, "detach") and hasattr(value, "shape"):
        try:
            tensor = value.detach().to("cpu").contiguous()
            digest = hashlib.sha256(tensor.numpy().tobytes()).hexdigest()
            return f"{tuple(tensor.shape)}|{tensor.dtype}|{digest}"
        except Exception:
            return repr(value)
    return repr(value)


def _decode_json(value: Any) -> dict[str, Any]:
    text = _as_text(value)
    if not text:
        return {}
    try:
        payload = json.loads(text)
        return payload if isinstance(payload, dict) else {}
    except ValueError:
        return {}


def _image_batch_tensor(images: Any, image_index: int = 0) -> Any:
    if images is None:
        return None
    try:
        if getattr(images, "ndim", 0) == 4:
            return images[image_index : image_index + 1]
        if getattr(images, "ndim", 0) == 3:
            return images.unsqueeze(0)
    except Exception:
        return None
    return None


def _image_batch_size(images: Any) -> int:
    if images is None:
        return 0
    try:
        if getattr(images, "ndim", 0) == 4:
            return int(images.shape[0])
        if getattr(images, "ndim", 0) == 3:
            return 1
    except Exception:
        return 0
    return 0


def _tensor_to_data_url(image: Any) -> str:
    from PIL import Image
    import numpy as np

    array = image.detach().cpu().float().numpy()
    while array.ndim > 3 and array.shape[0] == 1:
        array = array[0]
    array = np.clip(array * 255.0, 0, 255).astype("uint8")
    if array.ndim == 3 and array.shape[-1] == 1:
        array = array[..., 0]
    buffer = io.BytesIO()
    Image.fromarray(array).save(buffer, format="PNG")
    encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
    return "data:image/png;base64," + encoded


def _attach_images(references: list[dict[str, Any]], images: Any) -> list[dict[str, Any]]:
    count = _image_batch_size(images)
    if not count:
        return references
    image_refs = [
        item
        for item in references
        if str(item.get("kind") or "image").lower() == "image"
    ]
    while len(references) < count:
        references.append(
            {
                "label": f"<Picture {len(references) + 1}>",
                "kind": "image",
                "role": "subject_reference",
                "description": "由 ComfyUI 图片输入自动映射。",
            }
        )
    for index in range(count):
        target = image_refs[index] if index < len(image_refs) else None
        if target is None:
            target = next(
                (
                    item
                    for item in references
                    if str(item.get("kind") or "image").lower() == "image"
                    and not item.get("images")
                ),
                None,
            )
        if target is None:
            continue
        target.setdefault("label", f"<Picture {index + 1}>")
        target["images"] = [_tensor_to_data_url(_image_batch_tensor(images, index))]
    return references
def _bundle_items(bundle: Any) -> list[Any]:
    items = getattr(bundle, "items", None)
    if isinstance(items, (list, tuple)):
        return list(items)
    if isinstance(bundle, (list, tuple)):
        return list(bundle)
    return []


def _bundle_fields(item: Any) -> tuple[str, Any]:
    if isinstance(item, dict):
        return str(item.get("media_type") or item.get("type") or "").lower(), item.get("value")
    return str(getattr(item, "media_type", "") or "").lower(), getattr(item, "value", None)


def _media_value(value: Any, key: str) -> Any:
    if isinstance(value, dict):
        return value.get(key)
    return getattr(value, key, None)


def _image_data_urls(value: Any, limit: int = 12) -> list[str]:
    count = _image_batch_size(value)
    result = []
    for index in range(min(count, max(1, limit))):
        image = _image_batch_tensor(value, index)
        if image is not None:
            result.append(_tensor_to_data_url(image))
    return result


def _video_sample_urls(value: Any) -> list[str]:
    frames = _media_value(value, "images")
    count = _image_batch_size(frames)
    if not count:
        return []
    result = []
    for index in list(dict.fromkeys([0, count // 2, count - 1])):
        image = _image_batch_tensor(frames, index)
        if image is not None:
            result.append(_tensor_to_data_url(image))
    return result


def _audio_description(value: Any) -> str:
    waveform = _media_value(value, "waveform")
    sample_rate = _media_value(value, "sample_rate")
    try:
        samples = int(waveform.shape[-1])
        duration = samples / max(1, int(sample_rate))
        return f"音频参考，约 {duration:.2f} 秒，采样率 {int(sample_rate)} Hz；用于参考音色、节奏或声音氛围。"
    except Exception:
        return "音频参考，用于参考音色、节奏或声音氛围。"


def _bundle_audio(bundle: Any) -> Any:
    """Extract the first audio value from a MiniMaxH3MediaBundle-like object."""
    for item in _bundle_items(bundle):
        media_type, value = _bundle_fields(item)
        if media_type == "audio" and value is not None:
            return value
    return None


def _bundle_content_fingerprint(bundle: Any) -> str:
    parts = []
    for item in _bundle_items(bundle):
        media_type, value = _bundle_fields(item)
        parts.append(f"{media_type}:{_content_fingerprint(value)}")
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest() if parts else "empty"


def _infer_digital_human_roles(idea: str, references: list[dict[str, Any]]) -> dict[str, Any]:
    """Infer male/female singer pictures and a shared scene from the user's text."""
    text = str(idea or "")
    image_numbers = []
    for item in references:
        match = re.search(r"<(?:Picture|Image)\s+(\d+)>|(?:图片|图)\s*(\d+)", str(item.get("label") or ""), re.I)
        if match:
            number = int(match.group(1) or match.group(2))
            if number not in image_numbers:
                image_numbers.append(number)
    mentions = list(re.finditer(r"<(?:Picture|Image)\s+(\d+)>|(?:图片|图)\s*(\d+)", text, re.I))
    male_picture = female_picture = scene_picture = ""
    for index, match in enumerate(mentions):
        number = int(match.group(1) or match.group(2))
        end = mentions[index + 1].start() if index + 1 < len(mentions) else min(len(text), match.end() + 40)
        context = text[match.end():max(match.end(), end)]
        label = f"<Picture {number}>"
        if re.search(r"男|male|man|boy|先生", context, re.I):
            male_picture = label
        if re.search(r"女|female|woman|girl|女士", context, re.I):
            female_picture = label
        if re.search(r"场景|背景|环境|舞台|scene|background|environment", context, re.I):
            scene_picture = label
    duet_words = bool(re.search(r"男声|女声|男女|男生|女生|男子|女子|合唱|对唱|duet", text, re.I))
    if len(image_numbers) >= 2 and duet_words:
        if not male_picture:
            male_picture = f"<Picture {image_numbers[0]}>"
        if not female_picture:
            remaining = [number for number in image_numbers if f"<Picture {number}>" != male_picture]
            if remaining:
                female_picture = f"<Picture {remaining[0]}>"
    if duet_words and len(image_numbers) >= 3 and not scene_picture:
        remaining = [
            number for number in image_numbers
            if f"<Picture {number}>" not in {male_picture, female_picture}
        ]
        if remaining:
            scene_picture = f"<Picture {remaining[0]}>"
    duet = bool(male_picture and female_picture and male_picture != female_picture)

    def mapping(label: str, gender: str) -> dict[str, str]:
        number = int(re.search(r"\d+", label).group(0))
        return {
            "speaker": f"S{number}",
            "picture": label,
            "subject": f"<Subject {number}>",
            "gender": gender,
        }

    result: dict[str, Any] = {"duet": duet}
    if male_picture:
        result["male"] = mapping(male_picture, "male")
    if female_picture:
        result["female"] = mapping(female_picture, "female")
    if scene_picture:
        scene_number = int(re.search(r"\d+", scene_picture).group(0))
        result["scene"] = {
            "picture": scene_picture,
            "subject": f"<Subject {scene_number}>",
        }
    return result


def _references_from_media_bundle(bundle: Any) -> list[dict[str, Any]]:
    """Adapt MiniMaxH3MediaBundle-like objects to the Skill reference schema."""
    references: list[dict[str, Any]] = []
    image_count = 0
    video_count = 0
    audio_count = 0
    total = 0
    for item in _bundle_items(bundle):
        media_type, value = _bundle_fields(item)
        if total >= 12:
            break
        if media_type == "image" and image_count < 9:
            urls = _image_data_urls(value, limit=9 - image_count)
            for url in urls:
                image_count += 1
                total += 1
                references.append(
                    {
                        "label": f"<Picture {image_count}>",
                        "kind": "image",
                        "role": "subject_reference" if image_count < 3 else ("scene_reference" if image_count == 3 else "reference"),
                        "description": (
                            f"AICG3D 资源库图片 {image_count}，作为主体参考，用于锁定形象、服装、姿态或动作状态。"
                            if image_count < 3 else (
                                f"AICG3D 资源库图片 {image_count}，作为场景参考，用于锁定空间与构图。"
                                if image_count == 3 else f"AICG3D 资源库图片 {image_count}，作为补充参考。"
                            )
                        ),
                        "images": [url],
                    }
                )
                if total >= 12:
                    break
        elif media_type == "video" and video_count < 3:
            video_count += 1
            total += 1
            fps = _media_value(value, "fps")
            frames = _media_value(value, "images")
            frame_count = _image_batch_size(frames)
            duration = frame_count / float(fps) if fps and frame_count else 0
            references.append(
                {
                    "label": f"<Video {video_count}>",
                    "kind": "video",
                    "role": "motion_reference",
                    "description": f"AICG3D 资源库视频 {video_count}，约 {duration:.2f} 秒，用于锁动作、节奏、运镜或视频续写；不复制原视频中的对白与音乐。",
                    "images": _video_sample_urls(value),
                }
            )
        elif media_type == "audio" and audio_count < 3:
            audio_count += 1
            total += 1
            references.append(
                {
                    "label": f"<Audio {audio_count}>",
                    "kind": "audio",
                    "role": "audio_reference",
                    "description": _audio_description(value),
                    "labelOnly": True,
                }
            )
    return references


def _reference_media(references: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for index, item in enumerate(references, start=1):
        kind = str(item.get("kind") or "image").lower()
        label = str(item.get("label") or f"<Picture {index}>")
        entry: dict[str, Any] = {
            "label": label,
            "kind": kind,
            "role": item.get("role") or "reference",
            "description": item.get("description") or "",
        }
        if kind == "image":
            entry["images"] = list(item.get("images") or [])
            if not entry["images"]:
                entry["labelOnly"] = True
        elif kind == "video":
            entry["images"] = list(item.get("images") or [])
            path = str(item.get("path") or item.get("filename") or "").strip()
            if path:
                entry["source_name"] = path
            else:
                entry["labelOnly"] = not entry["images"]
        elif kind == "audio":
            entry["labelOnly"] = True
        result.append(entry)
    return result


def _strip_media_binary(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result = []
    for item in items:
        clean = {key: value for key, value in item.items() if key not in {"images", "image"}}
        if item.get("images"):
            clean["image_count"] = len(item["images"])
        result.append(clean)
    return result


def _config_ready(config: dict[str, Any]) -> bool:


    if config.get("mode") == "local":
        return bool(str(config.get("local_model") or "").strip())
    if str(config.get("provider") or "") == "runninghub":
        return bool(str(config.get("api_key") or "").strip())
    return bool(
        str(config.get("api_url") or "").strip()
        and str(config.get("model") or "").strip()
        and str(config.get("api_key") or "").strip()
    )


class AICG3DSkillSettings:
    CATEGORY = CATEGORY
    FUNCTION = "run"
    RETURN_TYPES = ("STRING", "STRING", "STRING")
    RETURN_NAMES = ("设置JSON", "模型列表JSON", "状态")
    DESCRIPTION = "集中设置线上 API 或本地模型。保存后整个 AICG3D SKILLS 插件共用，无需每个节点重复填写。"

    @classmethod
    def INPUT_TYPES(cls):
        current = optimizer.load_config()
        return {
            "required": {
                "运行方式": (
                    ["api", "local"],
                    {
                        "default": current.get("mode", "api"),
                        "tooltip": "api：调用 OpenAI 兼容接口、Gemini 或 RunningHub；local：读取 ComfyUI/models/llm 下的本地视觉模型。",
                    },
                ),
                "线上服务": (
                    list(PROVIDERS),
                    {
                        "default": current.get("provider", "runninghub"),
                        "tooltip": "选择后会自动填入常用 API 地址和默认模型；仍可在右键设置面板中覆盖。",
                    },
                ),
                "API地址": (
                    "STRING",
                    {"default": current.get("api_url", ""), "tooltip": "OpenAI 兼容服务填写到 /v1，插件自动拼接 /chat/completions。"},
                ),
                "模型名称": (
                    "STRING",
                    {"default": current.get("model", ""), "tooltip": "线上模型 ID，例如 qwen-vl-max、gpt-4.1-mini 或 RunningHub 模型名。"},
                ),
                "本地模型": (
                    "STRING",
                    {"default": current.get("local_model", ""), "tooltip": "models/llm 下的相对路径；留空则使用设置面板选择。"},
                ),
                "GPU或CPU": (
                    list(LOCAL_DEVICES),
                    {"default": current.get("local_device", "cuda"), "tooltip": "本地 Transformers 模型的运行设备；GGUF 由 llama.cpp 自行分配。"},
                ),
                "输出语言": (
                    list(OUTPUT_LANGUAGES),
                    {"default": current.get("output_language", "中文"), "tooltip": "提示词自然语言输出语言；对白仍保留用户原文和原语言。"},
                ),
                "读取参考图": (
                    "BOOLEAN",
                    {"default": bool(current.get("read_media", True)), "tooltip": "开启后，线上或本地视觉模型会读取已连接的参考图。"},
                ),
            },
            "optional": {
                "模型设置JSON": (
                    "STRING",
                    {
                        "multiline": True,
                        "default": "",
                        "tooltip": "可由上游节点覆盖设置；留空使用保存的全局设置。",
                    },
                ),
            },
        }

    def run(self, **kwargs):
        incoming = _decode_json(kwargs.get("模型设置JSON"))
        if not incoming:
            current = optimizer.load_config()
            incoming = {
                **current,
                "mode": kwargs.get("运行方式") or current.get("mode", "api"),
                "provider": kwargs.get("线上服务") or current.get("provider", "runninghub"),
                "api_url": kwargs.get("API地址") or current.get("api_url", ""),
                "model": kwargs.get("模型名称") or current.get("model", ""),
                "local_model": kwargs.get("本地模型") or current.get("local_model", ""),
                "local_device": kwargs.get("GPU或CPU") or current.get("local_device", "cuda"),
                "output_language": kwargs.get("输出语言") or current.get("output_language", "中文"),
                "read_media": bool(kwargs.get("读取参考图", current.get("read_media", True))),
            }
        provider = str(incoming.get("provider") or "runninghub")
        preset = optimizer.PROVIDERS.get(provider)
        if preset:
            incoming.setdefault("api_url", preset[0])
            incoming.setdefault("model", preset[1])
            incoming.setdefault("protocol", preset[2])
        saved = optimizer.save_config(incoming)
        public = optimizer.public_config(saved)
        models = {
            "models": optimizer.scan_local_models(),
            "missing_dependencies": optimizer.missing_local_dependencies(),
            "gguf_dependency": optimizer.gguf_dependency_status(),
        }
        return (
            json.dumps(public, ensure_ascii=False, indent=2),
            json.dumps(models, ensure_ascii=False, indent=2),
            "设置已保存；线上 API 密钥请在节点面板的“模型设置”按钮中填写。",
        )


class AICG3DSkillSelector:
    CATEGORY = CATEGORY
    FUNCTION = "run"
    RETURN_TYPES = ("STRING", "STRING", "STRING")
    RETURN_NAMES = ("技能包ID", "技能重点", "技能说明")
    DESCRIPTION = "选择本次提示词要强化的导演能力。输出可直接接到主节点的“技能重点”或“技能包”输入；普通任务也可只使用主节点下拉框。"

    @classmethod
    def INPUT_TYPES(cls):
        items = skills.discover()
        choices = [item["name"] for item in items] or [skills.selection_label(skills.default_skill_id())]
        return {
            "required": {
                "技能包": (
                    choices,
                    {"default": skills.selection_label(skills.default_skill_id()), "tooltip": "选择要使用的 Skill；普通任务保留内置 MiniMax H3 短剧导演 Skill。"},
                ),
                "导演重点": (
                    skills.selection_options(),
                    {
                        "default": "自动选择",
                        "tooltip": "战斗选“战斗导演”；对白选“文戏表演”；连续长片选“段缝连续性”。",
                    },
                ),
            }
        }

    def run(self, **kwargs):
        requested = _as_text(kwargs.get("技能包")) or skills.default_skill_id()
        item = skills.get(requested)
        selected = item["id"] if item else skills.default_skill_id()
        focus = _as_text(kwargs.get("导演重点")) or "自动选择"
        description = item["description"] if item else ""
        return selected, focus, description


class AICG3DSkillManager:
    CATEGORY = CATEGORY
    FUNCTION = "run"
    RETURN_TYPES = ("STRING", "STRING", "STRING")
    RETURN_NAMES = ("当前技能包ID", "技能列表JSON", "状态")
    DESCRIPTION = "浏览 skills/ 目录里的全部 Skill；点击节点上的“选择 / 管理技能”可按中文用途搜索、套用、导入 ZIP、刷新或删除技能。"

    @classmethod
    def INPUT_TYPES(cls):
        choices = skills.selection_labels() or [skills.selection_label(skills.default_skill_id())]
        return {
            "required": {
                "当前技能": (
                    choices,
                    {"default": skills.selection_label(skills.default_skill_id()), "tooltip": "点击节点上的“选择 / 管理技能”可按中文用途搜索；也支持刷新列表、导入 ZIP 或删除非内置 Skill。"},
                ),
            }
        }

    def run(self, **kwargs):
        requested = _as_text(kwargs.get("当前技能")) or skills.default_skill_id()
        item = skills.get(requested)
        selected = item["id"] if item else skills.default_skill_id()
        return selected, json.dumps(skills.payload(), ensure_ascii=False, indent=2), "Skill 管理器节点可用；点击节点上的 Skill 管理按钮导入、刷新或删除。"


class AICG3DMediaReferences:
    CATEGORY = CATEGORY
    FUNCTION = "run"
    RETURN_TYPES = ("STRING", "STRING", "INT")
    RETURN_NAMES = ("参考素材JSON", "素材目录", "图片数量")
    DESCRIPTION = "把一批参考图、视频文件、音频文件和用途整理成 H3 的 Picture/Video/Audio 标签，输出给提示词主节点。"

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "用途顺序": (
                    "STRING",
                    {
                        "multiline": True,
                        "default": "主体,主体,场景",
                        "tooltip": "按图片顺序填写：主体、场景、道具、首帧、尾帧、构图。也支持逗号或换行分隔。",
                    },
                ),
                "视频文件": (
                    "STRING",
                    {
                        "multiline": True,
                        "default": "",
                        "tooltip": "每行一个视频文件名或路径；只用于告诉提示词模型这段视频的作用，不会自动上传。",
                    },
                ),
                "音频文件": (
                    "STRING",
                    {
                        "multiline": True,
                        "default": "",
                        "tooltip": "每行一个音频文件名或路径，用于音色、节奏或音频复用说明。",
                    },
                ),
            },
            "optional": {
                "参考图片": (
                    "IMAGE",
                    {"tooltip": "可接一张或一批图片；批内每个画面自动映射为 <Picture 1>、<Picture 2>……"},
                ),
                "补充说明": (
                    "STRING",
                    {
                        "multiline": True,
                        "default": "",
                        "tooltip": "说明每张图锁定什么，例如“图1锁主角形象，图2锁对手，图3锁场景”。",
                    },
                ),
            },
        }

    def run(self, **kwargs):
        references: list[dict[str, Any]] = []
        images = kwargs.get("参考图片")
        count = _image_batch_size(images)
        roles = [
            part.strip()
            for part in re.split(r"[,，\n|｜]", _as_text(kwargs.get("用途顺序")))
            if part.strip()
        ]
        descriptions = _as_text(kwargs.get("补充说明"))
        for index in range(count):
            role = roles[index] if index < len(roles) else ("场景" if index == 2 else "主体")
            references.append(
                {
                    "label": f"<Picture {index + 1}>",
                    "kind": "image",
                    "role": "scene_reference" if "场景" in role else ("keyframe" if "帧" in role or "构图" in role else "subject_reference"),
                    "description": f"{role}参考。{descriptions}",
                    "images": [_tensor_to_data_url(_image_batch_tensor(images, index))],
                }
            )
        for index, line in enumerate([line for line in _as_text(kwargs.get("视频文件")).splitlines() if line.strip()], start=1):
            path = line.strip()
            references.append(
                {
                    "label": f"<Video {index}>",
                    "kind": "video",
                    "role": "motion_reference",
                    "description": "用于锁定动作、节奏或运镜；不复制原视频事件。",
                    "path": path,
                }
            )
        for index, line in enumerate([line for line in _as_text(kwargs.get("音频文件")).splitlines() if line.strip()], start=1):
            path = line.strip()
            references.append(
                {
                    "label": f"<Audio {index}>",
                    "kind": "audio",
                    "role": "audio_reference",
                    "description": "用于参考音色或节奏；必须与图像或视频共同使用。",
                    "path": path,
                }
            )
        catalog = "\n".join(
            f"{item['label']} | {item.get('kind')} | {item.get('role')} | {item.get('description', '')}"
            for item in references
        )
        return json.dumps({"references": references}, ensure_ascii=False, indent=2), catalog, count


class AICG3DDialogueRecognition:
    CATEGORY = CATEGORY
    FUNCTION = "run"
    RETURN_TYPES = ("STRING", "STRING", "STRING", "STRING")
    RETURN_NAMES = ("台词JSON", "台词时间线", "台词全文", "运行状态")
    DESCRIPTION = (
        "从已连接的视频音轨识别真实台词，输出带时间码和 S1/S2 说话人映射的 H3 台词时间线。"
        "把“台词时间线”接到 H3 提示词推理节点的同名输入，即可把识别台词写进 Ref2VA 提示词。"
    )

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "音频": (
                    "AUDIO",
                    {
                        "tooltip": "连接视频中的原音轨 AUDIO。若视频节点只输出 VIDEO，请先用视频加载节点提取音轨。",
                    },
                ),
                "模型": (
                    dialogue.model_choices(),
                    {
                        "default": "small",
                        "tooltip": "优先选择 ComfyUI/models/audio_encoders 里的 .pt 文件；small 适合先测试，medium/large-v3 中文准确率更高但更慢。",
                    },
                ),
                "本地模型路径": (
                    "STRING",
                    {
                        "default": "",
                        "tooltip": "可填写 .pt 绝对路径；填写后优先于上面的模型下拉框。",
                    },
                ),
                "语言": (
                    list(dialogue.LANGUAGE_OPTIONS),
                    {"default": "自动检测", "tooltip": "尽量填写明确语言，可减少误识别和语言漂移。"},
                ),
                "设备": (
                    ["自动", "cuda", "cpu"],
                    {"default": "自动", "tooltip": "自动优先使用 CUDA；显存不足时节点会尝试回退到 CPU。"},
                ),
                "允许自动下载模型": (
                    "BOOLEAN",
                    {"default": False, "tooltip": "关闭时只读取本地模型；打开后，选择 standard Whisper 名称时会下载模型。"},
                ),
                "说话人时间轴": (
                    "STRING",
                    {
                        "multiline": True,
                        "default": "",
                        "tooltip": "多人对白时每行写一个映射，例如：S1 = Picture 1 | 0.00-1.25；S2 = Picture 2 | 1.25-3.00。单人可以留空，默认全部归入 S1。",
                    },
                ),
                "最大单段秒数": (
                    "FLOAT",
                    {"default": 8.0, "min": 1.0, "max": 30.0, "step": 0.5, "tooltip": "相邻同说话人短句会合并到这个上限，避免时间线过碎。"},
                ),
                "合并相邻短句": (
                    "BOOLEAN",
                    {"default": True, "tooltip": "同一说话人的连续短句自动合并；需要逐句精确时间码时可关闭。"},
                ),
            }
        }

    def run(self, **kwargs):
        result = dialogue.transcribe_audio(
            kwargs.get("音频"),
            model_name=_as_text(kwargs.get("模型")) or "small",
            local_model_path=_as_text(kwargs.get("本地模型路径")),
            language_label=_as_text(kwargs.get("语言")) or "自动检测",
            device_label=_as_text(kwargs.get("设备")) or "自动",
            auto_download=bool(kwargs.get("允许自动下载模型", False)),
            speaker_timeline=_as_text(kwargs.get("说话人时间轴")),
            max_segment_seconds=float(kwargs.get("最大单段秒数") or 8.0),
            merge_short_segments=bool(kwargs.get("合并相邻短句", True)),
        )
        return (
            result["dialogue_json"],
            result["timeline"],
            result["text"],
            result["status"],
        )

class AICG3DSkillPromptExpander:
    CATEGORY = CATEGORY
    FUNCTION = "run"

    @classmethod
    def IS_CHANGED(cls, **kwargs):
        config = kwargs.get("模型设置JSON") or json.dumps(optimizer.load_config(), ensure_ascii=False, sort_keys=True)
        catalog = json.dumps(skills.payload(), ensure_ascii=False, sort_keys=True)
        dialogue_timeline = str(kwargs.get("台词时间线") or "")
        quick_task = _as_text(kwargs.get("反推快捷任务")) or "普通创作"
        audio = kwargs.get("音频") or _bundle_audio(kwargs.get("AICG3D资源库"))
        material_fingerprint = "|".join((
            _content_fingerprint(audio),
            _content_fingerprint(kwargs.get("参考图片")),
            _bundle_content_fingerprint(kwargs.get("AICG3D资源库")),
            _as_text(kwargs.get("音频反推模型")),
        ))
        return hashlib.sha256(
            f"{config}|{catalog}|{dialogue_timeline}|{quick_task}|{material_fingerprint}".encode("utf-8")
        ).hexdigest()
    RETURN_TYPES = ("STRING", "STRING", "STRING")
    RETURN_NAMES = ("H3提示词", "H3请求JSON", "运行状态")
    DESCRIPTION = (
        "主节点。最简用法：只填写“创意描述”，选择一个“技能包”，然后运行。"
        "截图中的四个项目是高级连线条目：参考素材JSON 来自“参考素材整理”；"
        "技能重点输入和技能包输入来自“技能选择器”；模型设置JSON 来自“模型设置”。"
        "额外要求用于填写必须遵守的自然语言限制。点击节点上的“使用说明”可查看完整填写顺序。"
        "“快捷任务”可在普通创作、图片反推、视频反推和数字人提示词生成之间切换；数字人模式会分开男女声，使用交替单人镜头和 MV 多角度运镜并隐藏无关参数。"
    )

    @classmethod
    def INPUT_TYPES(cls):
        defaults = optimizer.load_config()
        audio_models = dialogue.model_choices()
        return {
            "required": {
                "创意描述": (
                    "STRING",
                    {
                        "multiline": True,
                        "dynamicPrompts": True,
                        "default": "图1和图2在图3场景打斗",
                        "tooltip": "可以只写一句。图1、图2自动映射为参考主体，图3自动映射为参考场景。",
                    },
                ),
                "任务模式": (
                    list(MODES),
                    {"default": "Ref2VA 全能参考（推荐）", "tooltip": "有角色、场景、道具等多张参考图选 Ref2VA；纯文字选 T2VA。"},
                ),
                "输出画幅": (
                    list(ASPECTS),
                    {"default": "16:9（横屏）", "tooltip": "H3 支持 21:9、16:9、4:3、1:1、3:4、9:16。"},
                ),
                "视频时长": (
                    "FLOAT",
                    {"default": 10.0, "min": 4.0, "max": 15.0, "step": 0.5, "tooltip": "MiniMax H3 单段有效时长为 4~15 秒。数字人歌词识别仍会分析完整上传音频，不受此项限制。"},
                ),
                "动作强度": (
                    list(INTENSITIES),
                    {"default": "R2 商业高燃（默认）", "tooltip": "R2 适合大多数短剧；R1 适合写实文戏；R3 适合玄幻大招。"},
                ),
                "技能重点": (
                    skills.selection_options(),
                    {"default": "自动选择", "tooltip": "导演侧重点；普通使用保持“自动选择”，也可从“技能选择器”节点连接覆盖。"},
                ),
                "技能包": (
                    skills.selection_labels() or [skills.selection_label(skills.default_skill_id())],
                    {"default": skills.selection_label(skills.default_skill_id()), "tooltip": "选择要加载的 Skill；建议点击节点上的“选择 / 管理技能”按中文用途搜索。"},
                ),
                "输出语言": (
                    list(OUTPUT_LANGUAGES),
                    {"default": defaults.get("output_language", "中文"), "tooltip": "自然语言输出语言；对白始终保留原语言。"},
                ),
                "无模型时生成模板": (
                    "BOOLEAN",
                    {"default": True, "tooltip": "没有配置模型时仍生成结构完整、可继续修改的 H3 六段式草稿。"},
                ),
                "反推快捷任务": (
                    list(QUICK_TASKS),
                    {
                        "default": "普通创作",
                        "tooltip": "图片/视频反推会生成对应提示词；数字人提示词生成会识别歌词时间码，并用交替单人镜头分开男女声，每个歌词段只出现对应歌手，另一人完全在画外。",
                    },
                ),
            },
            "optional": {
                "参考素材JSON": (
                    "STRING",
                    {
                        "multiline": True,
                        "default": "",
                        "forceInput": True,
                        "tooltip": "高级连线项：连接“参考素材整理”的“参考素材JSON”输出；不连接时自动识别创意里的图1、图2、图3。",
                    },
                ),
                "技能重点输入": (
                    "STRING",
                    {"default": "", "forceInput": True, "tooltip": "高级连线项：连接“技能选择器”的“技能重点”输出，覆盖节点上的技能重点。"},
                ),
                "技能包输入": (
                    "STRING",
                    {"default": "", "forceInput": True, "tooltip": "高级连线项：连接“技能选择器”或“Skill 管理器”的技能包输出，覆盖节点上的技能包。"},
                ),
                "额外要求": (
                    "STRING",
                    {
                        "multiline": True,
                        "default": "",
                        "tooltip": "例如“角色保持沉默”“结束在双方对峙”“不要添加新人物”。",
                    },
                ),
                "模型设置JSON": (
                    "STRING",
                    {
                        "multiline": True,
                        "default": "",
                        "forceInput": True,
                        "tooltip": "高级连线项：连接“模型设置”的“模型设置JSON”输出；不连接时使用插件全局保存的设置。",
                    },
                ),
                "台词时间线": (
                    "STRING",
                    {
                        "default": "",
                        "forceInput": True,
                        "tooltip": "连接“视频台词识别”的“台词时间线”输出；识别台词会逐字写入 Ref2VA，并保留时间码和说话人映射。",
                    },
                ),
                "参考图片": (
                    "IMAGE",
                    {"tooltip": "可选。接图片后会自动附加给 H3 参考主体；若已有参考素材JSON则把图片补到对应 Picture 标签。"},
                ),
                "AICG3D资源库": (
                    MEDIA_BUNDLE_TYPE,
                    {"tooltip": "从 MiniMax H3 Aicg资源库 的 AICG3D 输出接入，支持多图、多视频和多音频。"},
                ),
                "音频": (
                    "AUDIO",
                    {"tooltip": "数字人提示词生成用：接入歌曲音频，自动识别带时间码的歌词并写入 11 号数字人提示词。"},
                ),
                "音频反推模型": (
                    audio_models,
                    {
                        "default": dialogue.preferred_music_model(audio_models),
                        "tooltip": "数字人歌词识别模型；通常 large-v3.pt 最准，large-v3-turbo 更快。始终分析完整上传音频；男女声由 wav2vec2 性别模型结合音色聚类识别，模型不可用时才回退音高算法。",
                    },
                ),
            },
        }

    def run(self, **kwargs):
        quick_task = _as_text(kwargs.get("反推快捷任务")) or "普通创作"
        if quick_task == LEGACY_AUDIO_REVERSE_TASK:
            quick_task = DIGITAL_HUMAN_PROMPT_TASK
        image_reverse = quick_task == "图片反推提示词"
        video_reverse = quick_task == "视频反推提示词"
        audio_reverse = quick_task == DIGITAL_HUMAN_PROMPT_TASK
        reverse_task = image_reverse or video_reverse or audio_reverse
        idea = _as_text(kwargs.get("创意描述"))
        if not idea and image_reverse:
            idea = "分析实际参考图片，只生成一段可直接复制粘贴的图片生成提示词。"
        elif not idea and video_reverse:
            idea = "分析实际参考视频的镜头、动作、连续性、节奏和声音，反推出 MiniMax H3 Ref2VA 六段式提示词。"
        elif not idea and audio_reverse:
            idea = "识别实际参考音频中带时间码的歌词，结合人物演唱图，生成可直接粘贴到 11 号数字人工作流的 MiniMax H3 六段式提示词。"
        lyric_timeline = ""
        audio_analysis_status = ""
        audio_analysis_meta: dict[str, Any] = {}
        audio_reverse_context: dict[str, Any] = {}
        idea = idea or "人物在同一空间中展开行动"
        mode = _as_text(kwargs.get("任务模式")) or "Ref2VA 全能参考（推荐）"
        h3_standard_mode = mode == "H3 六段式标准提示词"
        t2i_mode = mode == "文生图（T2I）"
        fl2i_mode = mode == "首尾帧生图（FL2I）"
        image_prompt_mode = t2i_mode or fl2i_mode
        aspect = _as_text(kwargs.get("输出画幅")) or "16:9（横屏）"
        duration = float(kwargs.get("视频时长") or 10.0)
        intensity = _as_text(kwargs.get("动作强度")) or "R2 商业高燃（默认）"
        focus = _as_text(kwargs.get("技能重点输入")) or _as_text(kwargs.get("技能重点")) or "自动选择"
        skill_id = _as_text(kwargs.get("技能包输入")) or _as_text(kwargs.get("技能包")) or skills.default_skill_id()
        if image_reverse:
            skill_id = skills.IMAGE_REVERSE_SKILL_ID
            mode = "Ref2VA 全能参考（推荐）"
            focus = "自动选择"
        elif video_reverse:
            skill_id = skills.VIDEO_REVERSE_SKILL_ID
            mode = "Ref2VA 全能参考（推荐）"
            focus = "镜头与分镜"
        elif audio_reverse:
            skill_id = skills.AUDIO_REVERSE_SKILL_ID
            mode = "Ref2VA 全能参考（推荐）"
            focus = "自动选择"
        elif h3_standard_mode:
            skill_id = skills.H3_STANDARD_SKILL_ID
            focus = "全流程导演"
        elif t2i_mode:
            skill_id = skills.T2I_SKILL_ID
            focus = "自动选择"
        elif fl2i_mode:
            skill_id = skills.FL2I_SKILL_ID
            focus = "镜头与分镜"
        extra = _as_text(kwargs.get("额外要求"))
        dialogue_timeline = _as_text(kwargs.get("台词时间线"))
        if dialogue_timeline and not audio_reverse:
            dialogue_rule = (
                "原视频台词识别结果（必须逐字使用，不得改写、翻译或新增对白；"
                "保持时间码、说话人和 Subject/Picture 映射）：\n"
                + dialogue_timeline
            )
            extra = f"{extra}\n\n{dialogue_rule}".strip()
        if reverse_task:
            reverse_rule = (
                "这是反推任务：只依据实际连接图片或视频中的可见/可听证据；"
                "无法确认的内容不要猜测，也不要在最终结果中输出不确定性说明、分析或操作建议。"
            )
            extra = f"{extra}\n\n{reverse_rule}".strip()
        output_language = _as_text(kwargs.get("输出语言")) or "中文"
        fallback_enabled = bool(kwargs.get("无模型时生成模板", True))
        config = _decode_json(kwargs.get("模型设置JSON")) or optimizer.load_config()
        config["output_language"] = output_language
        if reverse_task:
            fallback_enabled = False
            config["read_media"] = True
        elif fl2i_mode:
            config["read_media"] = True

        bundle_references = _references_from_media_bundle(kwargs.get("AICG3D资源库"))
        if bundle_references:
            references = bundle_references
        else:
            references = composer.parse_reference_catalog(_as_text(kwargs.get("参考素材JSON")))
            if not references:
                references = composer.infer_idea_references(idea)
            references = _attach_images(references, kwargs.get("参考图片"))

        if audio_reverse:
            audio_reverse_context = _infer_digital_human_roles(idea, references)
            if not any(
                str(item.get("kind") or "image").lower() == "image" and item.get("images")
                for item in references
            ):
                raise RuntimeError("数字人提示词生成需要一张人物演唱参考图：请连接“参考图片”或从 AICG3D 资源库接入图片。")
            lyric_timeline = dialogue_timeline
            if not lyric_timeline:
                audio_input = kwargs.get("音频")
                if audio_input is None:
                    audio_input = _bundle_audio(kwargs.get("AICG3D资源库"))
                if audio_input is None:
                    raise RuntimeError(
                        "数字人提示词生成需要接入歌曲音频：请把音频连接到“音频”输入，或上传到 AICG3D 资源库（插件会自动转写歌词），"
                        "或先用“视频台词识别”节点生成台词时间线并接到“台词时间线”输入。"
                    )
                transcribe_model = _as_text(kwargs.get("音频反推模型")) or dialogue.preferred_music_model()
                transcribed = dialogue.transcribe_audio(
                    audio_input,
                    model_name=transcribe_model,
                    singing=True,
                    merge_short_segments=False,
                    auto_download=True,
                    auto_gender_split=bool(audio_reverse_context.get("duet")),
                    # 数字人歌词转写始终覆盖完整上传音频；视频时长只用于 H3 生成参数，不裁剪歌词。
                    duet_mapping=audio_reverse_context,
                )
                if transcribed.get("duet_split"):
                    audio_reverse_context["auto_gender_split"] = True
                    audio_reverse_context["pitch_separation_hz"] = transcribed.get("pitch_separation_hz", 0)
                    audio_reverse_context["vocal_separator_used"] = transcribed.get("vocal_separator_used", False)
                lyric_timeline = transcribed["timeline"]
                assigned_speakers = {
                    str(segment.get("speaker") or "")
                    for segment in transcribed.get("segments") or []
                    if segment.get("speaker")
                }
                if not transcribed.get("duet_split") and len(assigned_speakers) == 1:
                    only_speaker = next(iter(assigned_speakers))
                    selected = (transcribed.get("mappings") or {}).get(only_speaker) or {}
                    selected_picture = str(selected.get("picture") or "<Picture 1>")
                    selected_subject = str(selected.get("subject") or "<Subject 1>")
                    lyric_timeline = re.sub(
                        rf"\|[ \t]*{re.escape(only_speaker)}[ \t]*\|[ \t]*{re.escape(selected_picture)}[ \t]*\|[ \t]*{re.escape(selected_subject)}[ \t]*",
                        f"| S1 | {selected_picture} | <Subject 1>",
                        lyric_timeline,
                    )
                    lyric_timeline = re.sub(
                        r"(?m)^识别台词对应的说话人映射：.*$",
                        f"单声部输出：S1 -> {selected_picture} -> <Subject 1>",
                        lyric_timeline,
                    )
                    audio_reverse_context = {
                        "duet": False,
                        "single": {
                            "speaker": "S1",
                            "picture": selected_picture,
                            "subject": "<Subject 1>",
                            "gender": selected.get("gender"),
                        },
                        "auto_gender_split": False,
                        "duet_split_confident": False,
                        "duet_split_reason": transcribed.get("duet_split_reason"),
                    }
                audio_analysis_status = str(transcribed.get("status") or "")
                audio_analysis_meta = {
                    "source_audio_seconds": transcribed.get("source_audio_seconds"),
                    "analysis_seconds": transcribed.get("analysis_seconds"),
                    "duet_split": transcribed.get("duet_split"),
                    "duet_split_confident": transcribed.get("duet_split_confident"),
                    "duet_split_reason": transcribed.get("duet_split_reason"),
                    "pitch_separation_hz": transcribed.get("pitch_separation_hz"),
                    "vocal_separator_used": transcribed.get("vocal_separator_used"),
                    "gender_model_used": transcribed.get("gender_model_used"),
                    "gender_model_id": transcribed.get("gender_model_id"),
                    "resolved_mode": "duet" if audio_reverse_context.get("duet") else "single",
                    "resolved_picture": (
                        (audio_reverse_context.get("single") or {}).get("picture")
                        if not audio_reverse_context.get("duet") else None
                    ),
                }
                if not lyric_timeline.strip():
                    raise RuntimeError(
                        "没有识别到可用歌词。请改用 large-v3.pt，或先用“视频台词识别”整理歌词时间线，再接到“台词时间线”输入。"
                    )
            if audio_reverse_context.get("duet"):
                male = audio_reverse_context.get("male") or {}
                female = audio_reverse_context.get("female") or {}
                scene = audio_reverse_context.get("scene") or {}
                scene_context = (
                    f"共同场景是 {scene.get('picture')} / {scene.get('subject')}。"
                    if scene.get("picture") and scene.get("subject") else
                    "两人使用参考素材中一致的共享环境。"
                )
                context_rule = (
                    f"这是双人数字人对唱任务：男声是 {male.get('speaker')}，绑定 {male.get('picture')} / {male.get('subject')}；"
                    f"女声是 {female.get('speaker')}，绑定 {female.get('picture')} / {female.get('subject')}；"
                    f"{scene_context}"
                    "每个时间段必须使用交替单人镜头：当前歌手是画面中唯一一个人，另一人完全在画外；"
                    "画面内不能出现第二张脸、第二张嘴、第二具身体或第二套口型。"
                )
            else:
                single_context = audio_reverse_context.get("single") or {}
                single_picture = str(single_context.get("picture") or "<Picture 1>")
                single_subject = str(single_context.get("subject") or "<Subject 1>")
                context_rule = (
                    f"这是单声部数字人提示词生成任务：{single_picture} 中的人物作为数字人主体 {single_subject}（S1）。"
                    "不要定义或切到未参与演唱的另一位人物，整段只保留当前歌手。"
                )
            camera_rule = (
                "运镜必须按创意 MV 设计，不能全片只用一个变焦或固定机位。三个以上歌词段时，至少使用三种真正不同的镜头："
                "横移/滑轨、低机位跟拍、三分之四近景 Dolly、30° 小弧线、Crane/Pedestal 或手持跟随；"
                "最后根据歌词落点做 Crane Up + Dolly Out。切镜只放在歌词起唱、换气或重音处，不能切在咬字中间；"
                "当前演唱者的完整嘴部必须清楚可见；每个歌词镜头只能出现当前歌手一人，另一人始终完全在画外。"
            )
            audio_rule = (
                context_rule
                + camera_rule
                + "歌曲音频由 11 号工作流的数字人模式全局锁定，retention_analysis 写成“锁定歌曲音轨: fully_copy - ...”。"
                "最终提示词中禁止出现 <Audio N> 标签，因为数字人节点会删除它们并留下残缺字段。"
                "以下是从音频识别出的带时间码歌词，已经是最终定稿：必须逐字原样写入 detailed_description 的 <d> 行，"
                "禁止重新转写、改写、翻译、拆句或合并。每个时间段写成一行时间范围、对应歌手动作和一条紧凑的 "
                "<d>[Mandarin singing] 原歌词</d>。\n"
                + lyric_timeline
            )
            extra = f"{extra}\n\n{audio_rule}".strip()
        if image_reverse and not any(
            str(item.get("kind") or "image").lower() == "image" and item.get("images")
            for item in references
        ):
            raise RuntimeError("图片反推需要至少一张实际图片：请连接“参考图片”或从 AICG3D 资源库接入图片。")
        if video_reverse and not any(
            str(item.get("kind") or "").lower() == "video" and item.get("images")
            for item in references
        ):
            raise RuntimeError("视频反推需要至少一个实际视频：请从 AICG3D 资源库接入视频。")
        if fl2i_mode and sum(
            1 for item in references
            if str(item.get("kind") or "image").lower() == "image" and item.get("images")
        ) < 2:
            raise RuntimeError("首尾帧生图需要两张实际图片：<Picture 1> 作为首帧，<Picture 2> 作为尾帧。")
        if reverse_task and not _config_ready(config):
            raise RuntimeError("图片/视频反推和数字人提示词生成需要视觉模型：请先点击“模型设置”，配置支持视觉的线上模型或本地视觉模型。")
        context, used_references, selected_skill_id = skills.build_context(
            idea,
            focus,
            skill_id,
            max_chars=18000 if config.get("mode") == "local" else 56000,
        )
        optimizer_task = (
            "IMAGE_REVERSE" if image_reverse
            else "VIDEO_REVERSE" if video_reverse
            else "AUDIO_REVERSE" if audio_reverse
            else composer.MODE_TO_TASK.get(mode, "Ref2VA")
        )
        if audio_reverse_context.get("duet"):
            male = audio_reverse_context.get("male") or {}
            female = audio_reverse_context.get("female") or {}
            scene = audio_reverse_context.get("scene") or {}
            scene_goal = (
                f"两人处在共同场景 {scene.get('subject')}（{scene.get('picture')}）。"
                if scene.get("subject") and scene.get("picture") else
                "两人处在参考素材中一致的共享环境。"
            )
            digital_human_goal = (
                "请只输出可直接粘贴到 11 号数字人工作流的 MiniMax H3 六段式正文。"
                f"男声使用 {male.get('subject')}（{male.get('speaker')}，来自 {male.get('picture')}），"
                f"女声使用 {female.get('subject')}（{female.get('speaker')}，来自 {female.get('picture')}），"
                f"{scene_goal}"
                "每段歌词必须绑定正确歌手并使用交替单人镜头：画面中有且只有当前歌手，另一人完全在画外。混合横移、低机位跟拍、30° 小弧线和结尾拉远；"
                "切点放在歌词起唱或重音，严禁把两张脸放进同一演唱镜头，始终保留当前演唱者完整嘴部。retention_analysis 要分别保留两张人物图和场景图（如有），"
                "并写“锁定歌曲音轨: fully_copy - ...”。禁止输出 <Audio N> 标签。把真实时间码歌词逐字写入 detailed_description。"
            )
        else:
            single_context = audio_reverse_context.get("single") or {}
            single_picture = str(single_context.get("picture") or "<Picture 1>")
            single_subject = str(single_context.get("subject") or "<Subject 1>")
            digital_human_goal = (
                "请只输出可直接粘贴到 11 号数字人工作流的 MiniMax H3 六段式正文。"
                f"把 {single_picture} 中的人物定义为 {single_subject}（S1），其他人物不参与本段演唱。"
                "歌曲使用 11 号工作流锁定的全局音轨；retention_analysis 写“锁定歌曲音轨: fully_copy - ...”。"
                "禁止输出 <Audio N> 标签。把识别歌词按真实时间码逐字写入 detailed_description，每段写成时间范围、"
                "<Subject 1> 演唱动作和一条 <d>[Mandarin singing] 原歌词</d>，让口型与每个时间段逐字同步。"
                "运镜按创意 MV 设计：横移揭示、低机位 Truck、三分之四 Dolly、30° 小弧线、Crane Up 拉远按歌词段变化；"
                "切点只放歌词起唱、换气或重音，不切在咬字中间，不做单一变焦，始终保留演唱者完整嘴部。"
                "不要分析、说明或额外解释。"
            )
        output_goal = (
            "请严格依据实际图片证据，只输出一段可直接复制粘贴的图片生成提示词。不要摘要、结构化拆解、H3 参考用法、规避说明、分析或任何额外解释。"
            if image_reverse
            else "请严格依据实际视频证据，只输出 MiniMax H3 Ref2VA 六段式正文。不要镜头时间线、说明、分析或额外解释。"
            if video_reverse
            else digital_human_goal
            if audio_reverse
            else "请只输出 MiniMax H3 六段式标准提示词正文，不要合并、省略或添加任何说明。"
            if h3_standard_mode
            else "请只输出一段可直接复制粘贴的文生图提示词。不要结构拆解、负面约束说明、视频六段式或额外解释。"
            if t2i_mode
            else "请以 <Picture 1> 为首帧、<Picture 2> 为尾帧，只输出可直接复制粘贴的首尾帧生图提示词或图片序列描述。不要分析、说明、标题或额外解释。"
            if fl2i_mode
            else None
        )
        node_prompt = composer.build_node_prompt(
            idea,
            mode,
            aspect,
            duration,
            intensity,
            focus,
            context,
            references,
            extra,
            output_goal,
        )
        request_payload = {
            "task": optimizer_task,
            "skill_id": selected_skill_id,
            "quick_task": quick_task,
            "aspect_ratio": composer.RATIO_VALUES.get(aspect, "16:9"),
            "duration_seconds": duration,
            "prompt": node_prompt,
            "media": _reference_media(references),
            "context": {},
            "system": context,
            "audio_reverse_context": audio_reverse_context,
        }
        status = ""
        try:
            if not _config_ready(config):
                raise RuntimeError("尚未配置线上 API 或本地模型")
            prompt = optimizer.generate_prompt_sync(
                config,
                {
                    "task": request_payload["task"],
                    "duration": duration,
                    "prompt": node_prompt,
                    "media": request_payload["media"],
                    "context": {},
                    "system": context,
                    "lyric_timeline": lyric_timeline,
                    "audio_reverse_context": audio_reverse_context,
                },
            )
            status = f"已使用{'本地模型' if config.get('mode') == 'local' else config.get('provider') or '线上 API'}生成；加载 {len(used_references)} 份 Skill 规则。"
            if not reverse_task and not image_prompt_mode:
                quality = validator.validate_h3(prompt)
                severe = any(str(item).startswith(("H1", "H8")) for item in quality.get("issues") or [])
                if severe or len(str(prompt)) > 30000:
                    prompt = composer.build_fallback(idea, mode, aspect, duration, intensity, references)
                    status += " 模型结果结构异常，已自动修复为可用的 H3 六段式草稿。"
        except Exception as error:
            if not fallback_enabled:
                raise RuntimeError(f"H3 提示词生成失败：{error}") from error
            if image_prompt_mode:
                prompt = composer.build_image_prompt(idea, mode, aspect, references, extra)
                status = f"模型未调用：{error}。已输出结构完整的离线图片提示词草稿。"
            else:
                prompt = composer.build_fallback(idea, mode, aspect, duration, intensity, references)
                status = f"模型未调用：{error}。已输出结构完整的离线 H3 草稿。"

        request_payload["references"] = references
        request_payload["skill_references"] = used_references
        request_payload["config_used"] = {
            "mode": config.get("mode"),
            "provider": config.get("provider"),
            "model": config.get("model"),
            "local_model": config.get("local_model"),
        }
        if audio_reverse and audio_analysis_meta:
            request_payload["audio_analysis"] = audio_analysis_meta
        if audio_reverse and lyric_timeline:
            request_payload["lyric_timeline"] = lyric_timeline
            status = f"{status}\n\n[识别歌词与时间码]\n{lyric_timeline}".strip()
        if audio_reverse and audio_analysis_status:
            status = f"{status}\n\n[音频声部分析]\n{audio_analysis_status}".strip()
        public_payload = dict(request_payload)
        public_payload["media"] = _strip_media_binary(request_payload.get("media") or [])
        public_payload["references"] = _strip_media_binary(request_payload.get("references") or [])
        return prompt, json.dumps(public_payload, ensure_ascii=False, indent=2), status


class AICG3DValidateH3Prompt:
    CATEGORY = CATEGORY
    FUNCTION = "run"
    RETURN_TYPES = ("STRING", "STRING", "STRING")
    RETURN_NAMES = ("检查结果", "问题清单", "警告清单")
    DESCRIPTION = "检查 H3 三字段/Ref2VA 六段式、镜号时间、素材引用、对白、声音分层和首镜锚定。"

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "H3提示词": (
                    "STRING",
                    {"multiline": True, "default": "", "tooltip": "可接主节点的“H3提示词”输出，也可以直接粘贴提示词。"},
                ),
                "严格模式": (
                    "BOOLEAN",
                    {"default": False, "tooltip": "开启后只要存在 FAIL 就中断工作流；关闭时只输出检查结果。"},
                ),
            }
        }

    def run(self, **kwargs):
        text = _as_text(kwargs.get("H3提示词"))
        result = validator.validate_h3(text)
        issues = result.get("issues") or []
        warnings = result.get("warnings") or []
        if bool(kwargs.get("严格模式")) and issues:
            raise RuntimeError("H3 提示词检查失败：\n" + "\n".join(str(item) for item in issues))
        status = "通过" if not issues else f"发现 {len(issues)} 个错误"
        if warnings:
            status += f"，{len(warnings)} 个警告"
        summary = {
            "result": status,
            "stats": result.get("stats") or {},
        }
        return (
            json.dumps(summary, ensure_ascii=False, indent=2),
            "\n".join(str(item) for item in issues),
            "\n".join(str(item) for item in warnings),
        )


NODE_CLASS_MAPPINGS = {
    "AICG3D_SKILLS_Settings": AICG3DSkillSettings,
    "AICG3D_SKILLS_SkillSelector": AICG3DSkillSelector,
    "AICG3D_SKILLS_SkillManager": AICG3DSkillManager,
    "AICG3D_SKILLS_MediaReferences": AICG3DMediaReferences,
    "AICG3D_SKILLS_PromptExpander": AICG3DSkillPromptExpander,
    "AICG3D_SKILLS_DialogueRecognition": AICG3DDialogueRecognition,
    "AICG3D_SKILLS_ValidateH3Prompt": AICG3DValidateH3Prompt,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "AICG3D_SKILLS_Settings": "AICG3D SKILLS · 模型设置",
    "AICG3D_SKILLS_SkillSelector": "AICG3D SKILLS · 技能选择器",
    "AICG3D_SKILLS_SkillManager": "AICG3D SKILLS · Skill 管理器",
    "AICG3D_SKILLS_MediaReferences": "AICG3D SKILLS · 参考素材整理",
    "AICG3D_SKILLS_PromptExpander": "AICG3D SKILLS · H3 提示词推理",
    "AICG3D_SKILLS_DialogueRecognition": "AICG3D SKILLS · 视频台词识别",
    "AICG3D_SKILLS_ValidateH3Prompt": "AICG3D SKILLS · H3 提示词检查",
}
