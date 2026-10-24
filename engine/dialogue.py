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
import urllib.request
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
_VOCAL_SEPARATOR: Any = None
_GENDER_CLASSIFIER: Any = None
_GENDER_FEATURE_EXTRACTOR: Any = None
_GENDER_MODEL_LOCK = threading.Lock()
_GENDER_MODEL_ID = "7wolf/wav2vec2-base-gender-classification"
_GENDER_MODEL_FILES = ("config.json", "preprocessor_config.json", "model.safetensors")
_VOCAL_SEPARATOR_LOCK = threading.Lock()


def _comfy_models_dir() -> Path:
    """Return ComfyUI/models when this plugin is installed normally."""
    plugin_dir = Path(__file__).resolve().parents[1]
    return plugin_dir.parent.parent / "models"


def gender_model_dir() -> Path:
    override = str(os.environ.get("AICG3D_GENDER_MODEL_DIR") or "").strip()
    if override:
        return Path(override).expanduser()
    return _comfy_models_dir() / "audio_classifiers" / "gender_wav2vec2_7wolf"


def _download_gender_model_file(filename: str, destination: Path) -> None:
    url = f"https://hf-mirror.com/{_GENDER_MODEL_ID}/resolve/main/{filename}"
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + ".part")
    request = urllib.request.Request(url, headers={"User-Agent": "AICG3D-SKILLS"})
    with urllib.request.urlopen(request, timeout=180) as response, temporary.open("wb") as target:
        while True:
            chunk = response.read(1024 * 1024)
            if not chunk:
                break
            target.write(chunk)
    temporary.replace(destination)


def _ensure_gender_model(auto_download: bool = True) -> Path | None:
    directory = gender_model_dir()
    missing = [name for name in _GENDER_MODEL_FILES if not (directory / name).is_file()]
    if not missing:
        return directory
    if not auto_download:
        return None
    try:
        for filename in missing:
            print(f"[AICG3D SKILLS] 下载男女声分类模型: {filename}")
            _download_gender_model_file(filename, directory / filename)
        return directory
    except Exception as error:
        print(f"[AICG3D SKILLS] 男女声分类模型下载失败，将回退音高聚类: {error}")
        return None


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


def _vocal_separator_path() -> Path | None:
    candidates = (
        _comfy_models_dir() / "H3LongVideo" / "hdemucs_high_trained.pt",
        _comfy_models_dir() / "audio_encoders" / "hdemucs_high_trained.pt",
        _comfy_models_dir() / "audio_encoders" / "hdemucs_high.pt",
    )
    for path in candidates:
        try:
            if path.is_file() and path.stat().st_size > 300 * 1024 * 1024:
                return path
        except OSError:
            continue
    try:
        import torch
        legacy = Path(torch.hub.get_dir()) / "torchaudio" / "models" / "hdemucs_high_trained.pt"
        return legacy if legacy.is_file() else None
    except Exception:
        return None


def _load_vocal_separator() -> Any:
    global _VOCAL_SEPARATOR
    with _VOCAL_SEPARATOR_LOCK:
        if _VOCAL_SEPARATOR is not None:
            return _VOCAL_SEPARATOR
        checkpoint = _vocal_separator_path()
        if checkpoint is None:
            return None
        try:
            import torch
            from torchaudio.models import hdemucs_high
            model = hdemucs_high(sources=["drums", "bass", "other", "vocals"])
            model.load_state_dict(torch.load(checkpoint, weights_only=True, map_location="cpu"))
            model.eval().to("cpu")
            _VOCAL_SEPARATOR = model
            return model
        except Exception:
            return None


def _separate_vocals_16k(audio: Any) -> Any | None:
    """Return an isolated vocal signal for gender-aware duet splitting."""
    model = _load_vocal_separator()
    if model is None:
        return None
    try:
        import numpy as np
        import torch
        from torchaudio.functional import resample
        waveform = audio.get("waveform") if isinstance(audio, dict) else getattr(audio, "waveform", None)
        sample_rate = _as_int(audio.get("sample_rate") if isinstance(audio, dict) else getattr(audio, "sample_rate", 0), 0)
        if waveform is None or sample_rate <= 0:
            return None
        source = torch.as_tensor(waveform).detach().cpu().float()
        if source.ndim == 3:
            source = source[0]
        if source.ndim == 1:
            source = source.unsqueeze(0)
        if source.shape[0] == 1:
            source = source.repeat(2, 1)
        if source.shape[0] != 2:
            source = source.mean(dim=0, keepdim=True).repeat(2, 1)
        if sample_rate != 44100:
            source = resample(source, sample_rate, 44100)
        mean, std = source.mean(0).mean(), source.mean(0).std().clamp_min(1e-8)
        normalized = (source - mean) / std
        output = torch.zeros_like(source)
        weights = torch.zeros(source.shape[1])
        chunk, overlap = 8 * 44100, 44100
        with _VOCAL_SEPARATOR_LOCK, torch.inference_mode():
            for start in range(0, source.shape[1], chunk - overlap):
                end = min(start + chunk, source.shape[1])
                value = model(normalized[:, start:end].unsqueeze(0))[0, 3].cpu()
                weight = torch.ones(end - start)
                fade = min(overlap, len(weight))
                if start:
                    weight[:fade] *= torch.linspace(1 / (fade + 1), 1, fade)
                if end < source.shape[1]:
                    weight[-fade:] *= torch.linspace(1, 1 / (fade + 1), fade)
                output[:, start:end] += value * weight
                weights[start:end] += weight
                if end == source.shape[1]:
                    break
        output = output / weights.clamp_min(1e-8) * std + mean
        output = output[:, : source.shape[1]]
        mono = output.mean(0)
        mono = resample(mono, 44100, 16000)
        return np.asarray(mono.numpy(), dtype=np.float32)
    except Exception:
        return None


def _median_pitch_hz(signal: Any, sample_rate: int = 16000) -> float:
    import numpy as np
    values = np.asarray(signal, dtype=np.float32).reshape(-1)
    if values.size < sample_rate // 8:
        return 0.0
    try:
        import librosa
        trimmed, _ = librosa.effects.trim(values, top_db=30)
        if trimmed.size >= sample_rate // 8:
            values = trimmed
        f0, _, _ = librosa.pyin(values, fmin=70, fmax=600, sr=sample_rate, frame_length=1024)
        voiced = f0[np.isfinite(f0)]
        return float(np.median(voiced)) if voiced.size else 0.0
    except Exception:
        pass
    frame_size, hop = 2048, 512
    min_lag, max_lag = sample_rate // 600, sample_rate // 70
    estimates = []
    for start in range(0, max(1, values.size - frame_size + 1), hop):
        frame = values[start:start + frame_size]
        frame = frame - float(frame.mean())
        energy = float(np.sqrt(np.mean(frame * frame)))
        if energy < 1e-4:
            continue
        corr = np.correlate(frame, frame, mode='full')[frame_size - 1:]
        window = corr[min_lag:min(max_lag + 1, corr.size)]
        if not window.size:
            continue
        lag = int(np.argmax(window)) + min_lag
        if corr[lag] > 0.2 * max(corr[0], 1e-8):
            estimates.append(sample_rate / lag)
    return float(np.median(estimates)) if estimates else 0.0


def _voice_feature(signal: Any) -> tuple[Any, float, float]:
    import numpy as np
    values = np.asarray(signal, dtype=np.float32).reshape(-1)
    pitch = _median_pitch_hz(values)
    try:
        import librosa
        mfcc = librosa.feature.mfcc(y=values, sr=16000, n_mfcc=20, n_fft=1024, hop_length=256)
        centroid = librosa.feature.spectral_centroid(y=values, sr=16000, n_fft=1024, hop_length=256)
        centroid_mean = float(np.mean(centroid)) if centroid.size else pitch
        feature = np.concatenate([mfcc.mean(axis=1), mfcc.std(axis=1), [centroid_mean / 1000.0, np.log(max(pitch, 1.0))]])
        return feature, pitch, centroid_mean
    except Exception:
        feature = np.asarray([np.log(max(pitch, 1.0))], dtype=np.float32)
        return feature, pitch, pitch


def _two_means(features: list[Any]) -> tuple[list[int], float]:
    import numpy as np
    matrix = np.asarray(features, dtype=np.float32)
    matrix = (matrix - matrix.mean(axis=0)) / (matrix.std(axis=0) + 1e-6)
    first = matrix[0]
    second = matrix[int(np.argmax(((matrix - first) ** 2).sum(axis=1)))]
    centers = np.stack([first, second])
    labels = np.zeros(len(matrix), dtype=int)
    for _ in range(20):
        labels = ((matrix[:, None, :] - centers[None, :, :]) ** 2).sum(axis=2).argmin(axis=1)
        updated = []
        for index in range(2):
            group = matrix[labels == index]
            updated.append(group.mean(axis=0) if len(group) else centers[index])
        updated = np.stack(updated)
        if np.allclose(updated, centers, atol=1e-4):
            centers = updated
            break
        centers = updated
    return labels.tolist(), float(np.linalg.norm(centers[0] - centers[1]))


def _duet_split_threshold(pitches: list[float]) -> tuple[float, float, float, float]:
    values = sorted(value for value in pitches if 60 <= value <= 800)
    if len(values) < 2:
        return 190.0, 0.0, 0.0, 0.0
    best = None
    for index in range(1, len(values)):
        low, high = values[:index], values[index:]
        low_mean, high_mean = sum(low) / len(low), sum(high) / len(high)
        score = len(low) * len(high) * (high_mean - low_mean) ** 2
        if best is None or score > best[0]:
            best = (score, low_mean, high_mean)
    if best is None or best[2] - best[1] < 24:
        return 190.0, 0.0, best[1] if best else 0.0, best[2] if best else 0.0
    return (best[1] + best[2]) / 2, best[2] - best[1], best[1], best[2]


def _assign_duet_genders(pitches: list[float]) -> tuple[list[str], float, bool, str]:
    """Only split a duet when the measured vocal ranges are genuinely distinct."""
    import numpy as np
    valid = [float(value) for value in pitches if 60.0 <= float(value) <= 800.0]
    if not valid:
        return ["male"] * len(pitches), 0.0, False, "没有获得可靠音高，未自动拆分男女声"
    overall_median = float(np.median(valid))
    fallback = "female" if overall_median >= 215.0 else "male"
    if len(valid) < 4:
        return [
            [fallback] * len(pitches),
            0.0,
            False,
            f"有效音高片段不足，按整体中位音高 {overall_median:.1f}Hz 暂按{'女声' if fallback == 'female' else '男声'}处理",
        ]
    ordered = sorted(valid)
    gap, split_at = max(
        ((ordered[index + 1] - ordered[index], index) for index in range(len(ordered) - 1)),
        key=lambda item: item[0],
    )
    low_values = ordered[: split_at + 1]
    high_values = ordered[split_at + 1 :]
    low_median = float(np.median(low_values)) if low_values else 0.0
    high_median = float(np.median(high_values)) if high_values else 0.0
    ratio = high_median / max(low_median, 1.0)
    groups_are_sized = len(low_values) >= 2 and len(high_values) >= 2
    confident = bool(
        groups_are_sized
        and high_median - low_median >= 40.0
        and ratio >= 1.20
        and low_median <= 205.0
        and high_median >= 235.0
    )
    if not confident:
        return [
            [fallback] * len(pitches),
            0.0,
            False,
            (
                f"男女声区间不够明确（低组 {low_median:.1f}Hz / 高组 {high_median:.1f}Hz，最大间隔 {gap:.1f}Hz），"
                f"整段暂按{'女声' if fallback == 'female' else '男声'}处理"
            ),
        ]
    threshold = (low_median + high_median) / 2.0
    genders = [
        "female" if float(pitch or overall_median) >= threshold else "male"
        for pitch in pitches
    ]
    return (
        genders,
        high_median - low_median,
        True,
        f"男女声音高区间明确（低组 {low_median:.1f}Hz / 高组 {high_median:.1f}Hz）",
    )


def _apply_duet_split(
    segments: list[dict[str, Any]],
    vocal_signal: Any,
    male_mapping: dict[str, Any],
    female_mapping: dict[str, Any],
    raw_signal: Any | None = None,
) -> tuple[dict[str, dict[str, Any]], float, bool, str, bool]:
    import numpy as np
    pitches = []
    features = []
    for segment in segments:
        start = max(0, int(float(segment["start"]) * 16000))
        end = min(len(vocal_signal), int(float(segment["end"]) * 16000))
        feature, pitch, _centroid = _voice_feature(vocal_signal[start:end])
        features.append(feature)
        pitches.append(pitch)
    predictions = _gender_model_predictions(raw_signal, segments) if raw_signal is not None else []
    genders = None
    separation = 0.0
    confident = False
    reason = ""
    model_used = bool(predictions)
    model_mapped = False
    if len(segments) >= 4 and len({tuple(round(float(value), 3) for value in item) for item in features}) > 1:
        labels, timbre_distance = _two_means(features)
        present = sorted(set(labels))
        counts = {cluster: labels.count(cluster) for cluster in present}
        if len(present) == 2 and timbre_distance >= 4.5 and min(counts.values()) >= 2:
            if len(predictions) == len(segments):
                cluster_male_probability = {
                    cluster: float(np.mean([
                        float(prediction.get("male_probability", 0.5))
                        for prediction, label in zip(predictions, labels)
                        if label == cluster
                    ]))
                    for cluster in present
                }
                predicted_cluster_genders = {
                    cluster: ("male" if cluster_male_probability[cluster] >= 0.5 else "female")
                    for cluster in present
                }
                if len(set(predicted_cluster_genders.values())) == 1:
                    only_gender = next(iter(predicted_cluster_genders.values()))
                    genders = [only_gender] * len(segments)
                    confident = False
                    reason = f"男女声模型判断两个音色簇都属于{('男声' if only_gender == 'male' else '女声')}"
                else:
                    male_cluster = max(present, key=lambda cluster: cluster_male_probability[cluster])
                    female_cluster = next(cluster for cluster in present if cluster != male_cluster)
                    male_probability = cluster_male_probability[male_cluster]
                    female_probability = cluster_male_probability[female_cluster]
                    cluster_margin = abs(male_probability - female_probability)
                    if cluster_margin >= 0.15:
                        genders = ["male" if label == male_cluster else "female" for label in labels]
                        confident = True
                        model_mapped = True
                        reason = (
                            f"wav2vec2 男女声模型 + 音色聚类："
                            f"男声簇概率 {male_probability:.3f} / 女声簇 {female_probability:.3f}，"
                            f"音色距离 {timbre_distance:.2f}"
                        )
                        for prediction, gender in zip(predictions, genders):
                            prediction["cluster_gender"] = gender
            if genders is None:
                cluster_pitch = {
                    cluster: float(np.median([
                        pitch for pitch, label in zip(pitches, labels) if label == cluster and pitch > 0
                    ] or [0.0]))
                    for cluster in present
                }
                male_cluster = min(present, key=lambda cluster: cluster_pitch[cluster])
                genders = ["male" if label == male_cluster else "female" for label in labels]
                separation = abs(cluster_pitch[present[1]] - cluster_pitch[present[0]])
                confident = True
                reason = f"音色聚类识别出两位歌手（距离 {timbre_distance:.2f}），按较低音高簇标为男声"
    if genders is None and predictions and len(predictions) == len(segments):
        predicted_genders = [str(item.get("gender") or "unknown") for item in predictions]
        confidences = [float(item.get("confidence") or 0.0) for item in predictions]
        if len(set(predicted_genders) - {"unknown"}) >= 2 and float(np.mean(confidences)) >= 0.65:
            genders = predicted_genders
            confident = True
            reason = f"wav2vec2 男女声模型逐句识别（平均置信度 {float(np.mean(confidences)):.3f}）"
    if genders is None:
        genders, separation, confident, reason = _assign_duet_genders(pitches)
    mappings = {
        str(male_mapping["speaker"]): {**male_mapping, "gender": "male"},
        str(female_mapping["speaker"]): {**female_mapping, "gender": "female"},
    }
    for index, (segment, pitch, gender) in enumerate(zip(segments, pitches, genders)):
        mapping = male_mapping if gender == "male" else female_mapping
        prediction = predictions[index] if index < len(predictions) else {}
        segment.update({
            "speaker": mapping["speaker"],
            "picture": mapping["picture"],
            "subject": mapping["subject"],
            "gender": gender,
            "gender_confidence": prediction.get("confidence"),
            "gender_source": "wav2vec2+timbre" if model_mapped else "timbre/pitch fallback",
            "median_f0": round(float(pitch), 2),
        })
    return mappings, separation, confident, reason, model_used


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
            f"{key}{('(' + str(item.get('gender')) + ')') if item.get('gender') else ''} -> "
            f"{item.get('picture') or '未指定图片'} -> {item.get('subject') or '未指定主体'}"
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


def _word_piece_segments(raw: dict[str, Any], fallback_text: str) -> list[tuple[float, float, str]]:
    words = raw.get("words") if isinstance(raw.get("words"), list) else []
    if not words:
        return [(
            float(raw.get("start") or 0.0),
            max(float(raw.get("start") or 0.0) + 0.05, float(raw.get("end") or raw.get("start") or 0.0)),
            fallback_text,
        )]
    pieces = []
    current: list[str] = []
    piece_start = 0.0
    piece_end = 0.0
    previous_end = 0.0
    for item in words:
        word = str(item.get("word") or "")
        if not word:
            continue
        start = float(item.get("start") or piece_start)
        end = max(start + 0.02, float(item.get("end") or start + 0.02))
        punctuation_break = bool(current and re.search(r"[。！？!?；;]", "".join(current)))
        if current and (start - previous_end > 0.35 or punctuation_break or end - piece_start > 5.5):
            text = _clean_text("".join(current))
            if text:
                pieces.append((round(piece_start, 3), round(piece_end, 3), text))
            current = []
        if not current:
            piece_start = start
        current.append(word)
        piece_end = end
        previous_end = end
    if current:
        text = _clean_text("".join(current))
        if text:
            pieces.append((round(piece_start, 3), round(piece_end, 3), text))
    return pieces or [(float(raw.get("start") or 0.0), max(float(raw.get("start") or 0.0) + 0.05, float(raw.get("end") or 0.0)), fallback_text)]


def _expand_word_segments(segments: list[dict[str, Any]]) -> list[dict[str, Any]]:
    expanded = []
    for segment in segments:
        words = segment.pop("words", None)
        if not isinstance(words, list) or not words:
            expanded.append(segment)
            continue
        pieces = _word_piece_segments(
            {"start": segment["start"], "end": segment["end"], "words": words},
            str(segment.get("text") or ""),
        )
        for start, end, text in pieces:
            item = dict(segment)
            item.update({"start": start, "end": end, "text": text})
            expanded.append(item)
    return expanded


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
    auto_gender_split: bool = False,
    duet_mapping: dict[str, dict[str, Any]] | None = None,
    max_audio_seconds: float | None = None,
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
    source_seconds = float(samples.size) / 16000.0
    analysis_seconds = source_seconds
    try:
        requested_seconds = float(max_audio_seconds or 0.0)
    except (TypeError, ValueError):
        requested_seconds = 0.0
    if requested_seconds > 0 and source_seconds > requested_seconds:
        sample_limit = max(1, int(round(requested_seconds * 16000.0)))
        samples = samples[:sample_limit]
        analysis_seconds = float(samples.size) / 16000.0
    analysis_audio = {
        "waveform": torch.from_numpy(samples).reshape(1, 1, -1),
        "sample_rate": 16000,
    }
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
        "word_timestamps": True,
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
        if start >= analysis_seconds:
            continue
        end = min(end, analysis_seconds)
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
                "words": raw.get("words") if isinstance(raw.get("words"), list) else [],
            }
        )
    if auto_gender_split:
        segments = _expand_word_segments(segments)
    duet_separation = 0.0
    duet_split_confident = False
    gender_model_used = False
    duet_split_reason = ""
    used_vocal_separator = False
    explicit_ranges = any(item.get("ranges") for item in mappings.values())
    if auto_gender_split and isinstance(duet_mapping, dict) and not explicit_ranges:
        male = duet_mapping.get("male") if isinstance(duet_mapping.get("male"), dict) else None
        female = duet_mapping.get("female") if isinstance(duet_mapping.get("female"), dict) else None
        if male and female and segments:
            vocal_signal = _separate_vocals_16k(analysis_audio)
            used_vocal_separator = vocal_signal is not None
            if vocal_signal is None:
                vocal_signal = samples
            mappings, duet_separation, duet_split_confident, duet_split_reason, gender_model_used = _apply_duet_split(
                segments, vocal_signal, male, female, samples,
            )
            if not duet_split_confident:
                mapping_warnings.append(
                    f"{duet_split_reason}；为避免男女画面串声，本次没有伪造男女切换。"
                    "如果原歌曲确实是对唱，请在“台词时间线”中逐段标注 S1/S2 后重新运行。"
                )
    if merge_short_segments:
        segments = _merge_segments(segments, max(1.0, float(max_segment_seconds or 8.0)))
    timeline = _format_timeline(segments, mappings, singing=bool(singing))
    unmatched = [
        segment for segment in segments
        if explicit_ranges and mappings and not any(
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
    if analysis_seconds + 1e-6 < source_seconds:
        status += f" 已按目标时长裁剪到 {analysis_seconds:.2f}s（原音频 {source_seconds:.2f}s）。"
    if auto_gender_split and duet_split_confident:
        status += f" {duet_split_reason}；人声分离={'已使用' if used_vocal_separator else '未使用'}。"
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
        "duet_split": bool(
            auto_gender_split
            and duet_split_confident
            and len({segment.get("gender") for segment in segments if segment.get("gender")}) >= 2
        ),
        "duet_split_confident": bool(duet_split_confident),
        "duet_split_reason": duet_split_reason,
        "pitch_separation_hz": round(float(duet_separation), 2),
        "source_audio_seconds": round(source_seconds, 3),
        "analysis_seconds": round(analysis_seconds, 3),
        "vocal_separator_used": used_vocal_separator,
        "gender_model_used": bool(gender_model_used),
        "gender_model_id": _GENDER_MODEL_ID if gender_model_used else "",
    }


def _load_gender_classifier() -> bool:
    global _GENDER_CLASSIFIER, _GENDER_FEATURE_EXTRACTOR
    if _GENDER_CLASSIFIER is not None and _GENDER_FEATURE_EXTRACTOR is not None:
        return True
    with _GENDER_MODEL_LOCK:
        if _GENDER_CLASSIFIER is not None and _GENDER_FEATURE_EXTRACTOR is not None:
            return True
        directory = _ensure_gender_model(auto_download=True)
        if directory is None:
            return False
        try:
            import torch
            from transformers import AutoFeatureExtractor, AutoModelForAudioClassification

            extractor = AutoFeatureExtractor.from_pretrained(str(directory), local_files_only=True)
            classifier = AutoModelForAudioClassification.from_pretrained(
                str(directory), local_files_only=True
            )
            classifier.eval().to("cpu")
            _GENDER_FEATURE_EXTRACTOR = extractor
            _GENDER_CLASSIFIER = classifier
            return True
        except Exception as error:
            print(f"[AICG3D SKILLS] 男女声分类模型加载失败，将回退音高聚类: {error}")
            return False


def _gender_model_predictions(samples: Any, segments: list[dict[str, Any]]) -> list[dict[str, float | str]]:
    if not segments or not _load_gender_classifier():
        return []
    import torch
    classifier = _GENDER_CLASSIFIER
    extractor = _GENDER_FEATURE_EXTRACTOR
    if classifier is None or extractor is None:
        return []
    labels = {int(index): str(label) for index, label in classifier.config.id2label.items()}
    male_index = next(
        (index for index, label in labels.items() if "муж" in label.lower() or label.strip().lower() == "male"),
        0,
    )
    results = []
    with torch.inference_mode():
        for segment in segments:
            start = max(0, int(float(segment["start"]) * 16000))
            end = min(len(samples), int(float(segment["end"]) * 16000))
            audio = samples[start:end]
            if audio.size < 1600:
                results.append({"gender": "unknown", "confidence": 0.0, "male_probability": 0.5})
                continue
            inputs = extractor(audio, sampling_rate=16000, return_tensors="pt", padding=True)
            probabilities = torch.softmax(classifier(**inputs).logits[0], dim=-1).detach().cpu()
            male_probability = float(probabilities[male_index])
            gender = "male" if male_probability >= 0.5 else "female"
            confidence = male_probability if gender == "male" else 1.0 - male_probability
            results.append({
                "gender": gender,
                "confidence": round(confidence, 4),
                "male_probability": round(male_probability, 4),
            })
    return results
