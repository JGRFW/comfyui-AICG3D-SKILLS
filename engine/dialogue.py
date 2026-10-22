# Copyright (C) 2026 AICG3D
# SPDX-License-Identifier: GPL-3.0-or-later
"""Local dialogue recognition helpers for the AICG3D Skill nodes.

The helper keeps model loading and ComfyUI node code separate. Whisper is an
optional runtime dependency: importing this module never imports Whisper or
downloads a model.
"""

from __future__ import annotations

import json
import os
import re
import threading
from pathlib import Path
from typing import Any

LANGUAGE_OPTIONS = (
    "自动检测",
    "中文",
    "英语",
    "日语",
    "韩语",
    "粤语",
    "法语",
    "德语",
    "西班牙语",
    "俄语",
)

_LANGUAGE_CODES = {
    "自动检测": None,
    "中文": "zh",
    "英语": "en",
    "日语": "ja",
    "韩语": "ko",
    "粤语": "yue",
    "法语": "fr",
    "德语": "de",
    "西班牙语": "es",
    "俄语": "ru",
}

_MODEL_ALIASES = (
    "tiny",
    "base",
    "small",
    "medium",
    "large-v1",
    "large-v2",
    "large-v3",
    "turbo",
)

# Whisper's model names are safe file names. Keep the same alias list in the
# dropdown so users can either use an OpenAI model cache or point at a .pt file.
_MODEL_CACHE: dict[tuple[str, str], Any] = {}
_MODEL_CACHE_LOCK = threading.Lock()


def _comfy_models_dir() -> Path:
    """Return ComfyUI/models when this plugin is installed normally."""
    plugin_dir = Path(__file__).resolve().parents[1]
    return plugin_dir.parent.parent / "models"


def local_model_dirs() -> list[Path]:
    dirs = [
        _comfy_models_dir() / "audio_encoders",
        _comfy_models_dir() / "whisper",
        Path.home() / ".cache" / "whisper",
    ]
    result: list[Path] = []
    for directory in dirs:
        try:
            resolved = directory.expanduser().resolve()
        except OSError:
            continue
        if resolved not in result:
            result.append(resolved)
    return result


# 推荐的“靠谱”模型（中文演唱/中文歌词质量优先，按性价比排序）。
# 只暴露这几个，避免把 tiny/base/small/medium/large-v1/v2/turbo 等
# 不适合中文演唱的模型全堆进下拉框，让用户无从选择。
# 命中这些名字时 whisper 会自动下载；用户也可手动下到 audio_encoders。
_CURATED_MODEL_NAMES = (
    "large-v3",        # 中文演唱/歌词最准（约 3GB，稍慢）
    "large-v3-turbo",  # 兼容已下载的第三方 turbo 权重；无本地文件时映射官方 turbo
    "medium",          # 轻量均衡，显存小或追求速度时可选（约 1.5GB）
)

_DOWNLOAD_MODEL_ALIASES = {
    "large-v3-turbo": "turbo",
    "large-v3-turbo.pt": "turbo",
}


def model_choices() -> list[str]:
    choices: list[str] = []
    # 1) 本地已下载的 .pt 文件优先展示（用户手头实际可用的）
    for directory in local_model_dirs():
        if not directory.is_dir():
            continue
        for path in sorted(directory.glob("*.pt")):
            name = path.name
            if name not in choices:
                choices.append(name)
    # 2) 补齐推荐的“名字”项；若本地已有同名 .pt 则不重复列出
    for name in _CURATED_MODEL_NAMES:
        if name not in choices and (name + ".pt") not in choices:
            choices.append(name)
    return choices


def preferred_music_model(choices: list[str] | None = None) -> str:
    """Prefer the strongest installed checkpoint, then a downloadable alias."""
    available = list(choices or model_choices())
    for preferred in ("large-v3.pt", "large-v3", "large-v3-turbo.pt", "large-v3-turbo", "turbo", "medium"):
        if preferred in available:
            return preferred
    return available[0] if available else "large-v3"


def _resolve_local_model(model_name: str, explicit_path: str, auto_download: bool) -> tuple[str, bool]:
    """Return (value_for_whisper, may_download)."""
    explicit = str(explicit_path or "").strip().strip('"')
    if explicit:
        path = Path(explicit).expanduser()
        if not path.is_absolute():
            candidates = [directory / path for directory in local_model_dirs()]
            path = next((candidate for candidate in candidates if candidate.is_file()), path)
        if path.is_file():
            return str(path.resolve()), False
        raise FileNotFoundError(f"本地 Whisper 模型不存在：{path}")

    selected = str(model_name or "").strip()
    if not selected:
        selected = "small"

    selected_path = Path(selected).expanduser()
    if selected_path.is_file():
        return str(selected_path.resolve()), False

    for directory in local_model_dirs():
        candidate = directory / selected
        if candidate.is_file():
            return str(candidate.resolve()), False
        if not selected.lower().endswith(".pt"):
            pt_candidate = directory / f"{selected}.pt"
            if pt_candidate.is_file():
                return str(pt_candidate.resolve()), False

    download_alias = _DOWNLOAD_MODEL_ALIASES.get(selected, selected)
    if auto_download and download_alias in _MODEL_ALIASES:
        return download_alias, True
    raise FileNotFoundError(
        "没有找到本地 Whisper 模型。请把 .pt 模型放到 "
        "ComfyUI/models/audio_encoders，或打开“允许自动下载模型”。"
    )


def _as_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _audio_to_mono_16k(audio: Any) -> Any:
    """Convert ComfyUI AUDIO to a mono float32 numpy array at 16 kHz."""
    import numpy as np
    import torch

    if isinstance(audio, dict):
        waveform = audio.get("waveform")
        sample_rate = audio.get("sample_rate")
    else:
        waveform = getattr(audio, "waveform", None)
        sample_rate = getattr(audio, "sample_rate", None)
    if waveform is None:
        raise ValueError("音频输入为空；请连接 ComfyUI 的 AUDIO 输出。")
    source_rate = _as_int(sample_rate, 0)
    if source_rate <= 0:
        raise ValueError("音频缺少有效采样率。")

    tensor = torch.as_tensor(waveform)
    if tensor.ndim == 3:
        tensor = tensor[0]
    if tensor.ndim == 2:
        # ComfyUI normally uses [channels, samples]. Accept [samples, channels]
        # as well so this node also works with simple custom audio loaders.
        if tensor.shape[0] <= 8:
            tensor = tensor.mean(dim=0)
        elif tensor.shape[1] <= 8:
            tensor = tensor.mean(dim=1)
        else:
            tensor = tensor.reshape(-1)
    elif tensor.ndim > 2:
        tensor = tensor.reshape(-1)
    tensor = tensor.to(dtype=torch.float32)
    tensor = torch.nan_to_num(tensor, nan=0.0, posinf=0.0, neginf=0.0).contiguous()
    if source_rate != 16000:
        try:
            import torchaudio
            import torchaudio.functional as audio_functional

            tensor = audio_functional.resample(tensor, source_rate, 16000)
        except Exception:
            target_length = max(1, round(tensor.numel() * 16000 / source_rate))
            tensor = torch.nn.functional.interpolate(
                tensor.reshape(1, 1, -1),
                size=target_length,
                mode="linear",
                align_corners=False,
            ).reshape(-1)
    return np.asarray(tensor.detach().cpu(), dtype=np.float32)


def _clean_text(text: str) -> str:
    value = re.sub(r"\s+", " ", str(text or "")).strip()
    value = re.sub(r"^[\[（(【]\s*(?:music|音乐|applause|掌声|silence|静音)\s*[\]）)】]\s*", "", value, flags=re.I)
    value = value.strip()
    if re.fullmatch(r"[\s，。！？!?；;、,.…\-\u3000]+", value):
        return ""
    if value.lower() in {"music", "applause", "silence", "字幕由", "谢谢观看"}:
        return ""
    return value


def _load_whisper(model_ref: str, device: str, may_download: bool) -> Any:
    try:
        import whisper
    except ImportError as error:
        raise RuntimeError(
            "未安装 openai-whisper。请在 ComfyUI 的 Python 环境安装 whisper，"
            "或改用已安装的本地 ASR 节点。"
        ) from error

    key = (model_ref, device)
    with _MODEL_CACHE_LOCK:
        cached = _MODEL_CACHE.get(key)
        if cached is not None:
            return cached

    if not may_download and not Path(model_ref).is_file() and model_ref not in _MODEL_ALIASES:
        raise FileNotFoundError(f"Whisper 模型不可用：{model_ref}")
    model = whisper.load_model(model_ref, device=device)
    with _MODEL_CACHE_LOCK:
        _MODEL_CACHE[key] = model
    return model


def _parse_range(line: str) -> tuple[float, float] | None:
    match = re.search(
        r"(?<!\d)(\d+(?:\.\d+)?)\s*(?:-|–|—|~|～|至|到)\s*(\d+(?:\.\d+)?)",
        line,
    )
    if not match:
        return None
    start, end = float(match.group(1)), float(match.group(2))
    if end <= start:
        return None
    return start, end


def parse_speaker_timeline(raw: str) -> tuple[dict[str, dict[str, Any]], list[str]]:
    """Parse lines such as ``S1 = Picture 1 | 0.00-1.25``.

    A Picture number also becomes Subject number. Lines without a time range
    are accepted as identity mappings, while time ranges are used to assign
    recognized segments to speakers.
    """
    mappings: dict[str, dict[str, Any]] = {}
    warnings: list[str] = []
    for line_no, raw_line in enumerate(str(raw or "").splitlines(), start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        picture_match = re.search(r"(?:picture|image|图|图片|参考图)\s*(\d+)", line, re.I)
        speaker_match = re.search(r"(?:speaker|说话人|说话者|人物)\s*(\d+)", line, re.I)
        short_speaker_match = re.search(r"(?<![A-Za-z0-9])S\s*(\d+)(?![A-Za-z0-9])", line, re.I)
        if speaker_match:
            speaker_number = int(speaker_match.group(1))
        elif short_speaker_match:
            speaker_number = int(short_speaker_match.group(1))
        elif picture_match:
            speaker_number = int(picture_match.group(1))
        else:
            warnings.append(f"第 {line_no} 行没有识别到 S1/S2 或 Picture 编号，已忽略。")
            continue

        speaker = f"S{speaker_number}"
        entry = mappings.setdefault(
            speaker,
            {
                "speaker": speaker,
                "picture": "",
                "subject": "",
                "ranges": [],
            },
        )
        if picture_match:
            picture_number = int(picture_match.group(1))
            picture = f"<Picture {picture_number}>"
            subject = f"<Subject {picture_number}>"
            entry["picture"] = picture
            entry["subject"] = subject
        elif not entry["picture"]:
            picture = f"<Picture {speaker_number}>"
            subject = f"<Subject {speaker_number}>"
            entry["picture"] = picture
            entry["subject"] = subject

        time_range = _parse_range(line)
        if time_range:
            entry["ranges"].append(time_range)

    return mappings, warnings


def _choose_speaker(
    start: float,
    end: float,
    mappings: dict[str, dict[str, Any]],
    fallback: str = "S1",
) -> str:
    best_speaker = ""
    best_overlap = 0.0
    for speaker, item in mappings.items():
        for range_start, range_end in item.get("ranges") or []:
            overlap = max(0.0, min(end, range_end) - max(start, range_start))
            if overlap > best_overlap:
                best_overlap = overlap
                best_speaker = speaker
    return best_speaker or fallback


def _merge_segments(segments: list[dict[str, Any]], max_seconds: float) -> list[dict[str, Any]]:
    merged: list[dict[str, Any]] = []
    for segment in segments:
        if (
            merged
            and merged[-1]["speaker"] == segment["speaker"]
            and float(segment["start"]) - float(merged[-1]["end"]) <= 0.45
            and float(segment["end"]) - float(merged[-1]["start"]) <= max_seconds
        ):
            merged[-1]["end"] = segment["end"]
            merged[-1]["text"] = f'{merged[-1]["text"]} {segment["text"]}'.strip()
            continue
        merged.append(dict(segment))
    return merged


def _format_timeline(segments: list[dict[str, Any]], mappings: dict[str, dict[str, Any]], singing: bool = False) -> str:
    lines = []
    if mappings:
        mappings_text = "；".join(
            f"{key} -> {item.get('picture') or '未指定图片'} -> {item.get('subject') or '未指定主体'}"
            for key, item in sorted(mappings.items())
        )
        lines.append(f"识别台词对应的说话人映射：{mappings_text}")
        lines.append("")
    for segment in segments:
        speaker = str(segment.get("speaker") or "S1")
        mapping = mappings.get(speaker) or {}
        picture = mapping.get("picture") or f"<Picture {speaker[1:]}>"
        subject = mapping.get("subject") or f"<Subject {speaker[1:]}>"
        language = str(segment.get("language") or "Chinese")
        if singing:
            language = {
                "Chinese": "Mandarin singing",
                "English": "English singing",
                "Japanese": "Japanese singing",
                "Korean": "Korean singing",
                "Unknown": "Mandarin singing",
            }.get(language, f"{language} singing")
        else:
            language = language or "Chinese"
        lines.append(
            f"{float(segment['start']):.2f}-{float(segment['end']):.2f} 秒 | "
            f"{speaker} | {picture} | {subject}"
        )
        lines.append(f"<d>[{language}]{segment.get('text')}</d>")
        lines.append("")
    return "\n".join(lines).strip()


def _is_music_hallucination(text: str) -> bool:
    """Whisper 对纯音乐/间奏段的典型幻听：整段只有同一个词反复重复。

    例如 small 的“作曲 作曲 作曲…”、large-v3-turbo 的“李宗盛 李宗盛…”，
    都与真实歌词无关。只要整段文本退化成单一词重复（≥2 次）就判定为幻听丢弃。
    """
    normalized = re.sub(r"\s+", "", str(text or "")).lower()
    known_noise = (
        "请不吝点赞订阅转发打赏支持明镜与点点栏目",
        "字幕由amara社区提供",
        "订阅我的频道",
        "谢谢观看",
        "感谢观看",
        "thanksforwatching",
        "pleasesubscribe",
        "subtitlesby",
    )
    if any(marker in normalized for marker in known_noise):
        return True
    tokens = re.findall(r"[\u3400-\u9fff]{2,}|[A-Za-z]{3,}", str(text or ""))
    if len(tokens) < 2:
        return False
    first = tokens[0].lower()
    return all(token.lower() == first for token in tokens)


def transcribe_audio(
    audio: Any,
    model_name: str = "small",
    local_model_path: str = "",
    language_label: str = "自动检测",
    device_label: str = "自动",
    auto_download: bool = False,
    speaker_timeline: str = "",
    max_segment_seconds: float = 8.0,
    merge_short_segments: bool = True,
    singing: bool = False,
) -> dict[str, Any]:
    """Transcribe a ComfyUI AUDIO value and return prompt-ready dialogue data."""
    import torch

    mappings, mapping_warnings = parse_speaker_timeline(speaker_timeline)
    model_ref, may_download = _resolve_local_model(model_name, local_model_path, bool(auto_download))
    device = str(device_label or "自动").lower()
    if device not in {"cuda", "cpu"}:
        device = "cuda" if torch.cuda.is_available() else "cpu"
    if device == "cuda" and not torch.cuda.is_available():
        device = "cpu"
    model = _load_whisper(model_ref, device, may_download)
    samples = _audio_to_mono_16k(audio)
    language = _LANGUAGE_CODES.get(str(language_label or "自动检测"), None)
    options = {
        "language": language,
        "task": "transcribe",
        "fp16": device == "cuda",
        "verbose": False,
        "condition_on_previous_text": False,
        "temperature": 0.0,
        "no_speech_threshold": 0.6,
        "logprob_threshold": -1.0,
        "compression_ratio_threshold": 2.4,
    }
    try:
        result = model.transcribe(samples, **options)
    except RuntimeError as error:
        # A CPU fallback is more useful than a hard failure when a CUDA model
        # is temporarily unable to fit; model files remain unchanged.
        if device == "cuda" and "out of memory" in str(error).lower():
            torch.cuda.empty_cache()
            model = _load_whisper(model_ref, "cpu", may_download)
            options["fp16"] = False
            result = model.transcribe(samples, **options)
        else:
            raise

    segments: list[dict[str, Any]] = []
    for raw in result.get("segments") or []:
        text = _clean_text(raw.get("text"))
        if not text:
            continue
        no_speech = float(raw.get("no_speech_prob") or 0.0)
        avg_logprob = float(raw.get("avg_logprob") or 0.0)
        compression = float(raw.get("compression_ratio") or 0.0)
        if no_speech >= 0.75 or avg_logprob <= -1.5 or compression > 2.4:
            continue
        if _is_music_hallucination(text):
            # 纯音乐段幻听（同词反复），与真实歌词无关，丢弃
            continue
        start = max(0.0, float(raw.get("start") or 0.0))
        end = max(start + 0.05, float(raw.get("end") or start))
        speaker = _choose_speaker(start, end, mappings)
        mapping = mappings.get(speaker) or {}
        segments.append(
            {
                "start": round(start, 3),
                "end": round(end, 3),
                "speaker": speaker,
                "picture": mapping.get("picture") or f"<Picture {speaker[1:]}>",
                "subject": mapping.get("subject") or f"<Subject {speaker[1:]}>",
                "language": "Chinese" if re.search(r"[\u3400-\u9fff]", text) else (
                    {"zh": "Chinese", "en": "English", "ja": "Japanese", "ko": "Korean"}.get(
                        str(result.get("language") or "").lower(),
                        str(result.get("language") or "Unknown"),
                    )
                ),
                "text": text,
            }
        )
    if merge_short_segments:
        segments = _merge_segments(segments, max(1.0, float(max_segment_seconds or 8.0)))
    timeline = _format_timeline(segments, mappings, singing=bool(singing))
    unmatched = [
        segment for segment in segments
        if mappings and not any(
            start <= float(segment["start"]) < end
            for item in mappings.values()
            for start, end in item.get("ranges") or []
        )
    ]
    if mappings and unmatched:
        mapping_warnings.append(f"有 {len(unmatched)} 段没有落入时间轴映射，已默认归到 S1。")
    status = (
        f"识别完成：{len(segments)} 段，模型={model_ref}，设备={device}。"
        if segments else
        f"未识别到可用的说话片段；模型={model_ref}，设备={device}。"
    )
    if mapping_warnings:
        status += " " + " ".join(mapping_warnings)
    return {
        "dialogue_json": json.dumps(segments, ensure_ascii=False, indent=2),
        "timeline": timeline,
        "text": " ".join(segment["text"] for segment in segments),
        "status": status,
        "segments": segments,
        "mappings": mappings,
        "language": result.get("language") or "",
    }
