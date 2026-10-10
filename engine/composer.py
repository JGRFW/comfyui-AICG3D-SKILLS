# Copyright (C) 2026 AICG3D
# SPDX-License-Identifier: GPL-3.0-or-later
"""Request building and deterministic fallback composer for H3 prompts."""

from __future__ import annotations

import json
import re
from typing import Any

MODE_TO_TASK = {
    "Ref2VA 全能参考（推荐）": "Ref2VA",
    "T2VA 纯文本": "T2VA",
    "I2VA 首帧参考": "I2VA",
    "FL2VA 首尾帧参考": "FL2VA",
    "L2VA 尾帧参考": "L2VA",
}

RATIO_VALUES = {
    "16:9（横屏）": "16:9",
    "9:16（竖屏）": "9:16",
    "21:9（宽幕）": "21:9",
    "4:3": "4:3",
    "3:4": "3:4",
    "1:1": "1:1",
}

INTENSITY_TEXT = {
    "R1 写实克制": "写实克制的动作与镜头，力度和速度清楚但不夸张。",
    "R2 商业高燃（默认）": "商业高燃节奏，动作清楚、镜头有推进、冲击点明确。",
    "R3 玄幻大招": "高动态玄幻动作，以可见轨迹、能量反馈和环境受力表现爆发。",
}


def parse_reference_catalog(raw: str) -> list[dict[str, Any]]:
    value = str(raw or "").strip()
    if not value:
        return []
    try:
        payload = json.loads(value)
        if isinstance(payload, list):
            return [item for item in payload if isinstance(item, dict)]
        if isinstance(payload, dict) and isinstance(payload.get("references"), list):
            return [item for item in payload["references"] if isinstance(item, dict)]
    except ValueError:
        pass
    result: list[dict[str, Any]] = []
    for index, line in enumerate(value.splitlines(), start=1):
        text = line.strip().lstrip("-").strip()
        if not text:
            continue
        parts = [part.strip() for part in re.split(r"[|｜]", text)]
        result.append(
            {
                "label": parts[0],
                "kind": parts[1] if len(parts) > 1 else "image",
                "role": parts[2] if len(parts) > 2 else "reference",
                "description": parts[3] if len(parts) > 3 else "",
                "index": index,
            }
        )
    return result


def infer_idea_references(idea: str) -> list[dict[str, Any]]:
    """Map shorthand such as 图1/图2/图3 to H3 picture labels."""
    found: list[int] = []
    for match in re.finditer(r"(?:图|图片|参考图|picture)\s*(\d+)", idea, flags=re.IGNORECASE):
        number = int(match.group(1))
        if 1 <= number <= 9 and number not in found:
            found.append(number)
    if not found and re.search(r"首帧|尾帧|参考", idea):
        found = [1]
    return [
        {
            "label": f"<Picture {number}>",
            "kind": "image",
            "role": (
                "scene_reference"
                if re.search(rf"(?:图|图片|参考图)\s*{number}(?:在|为|是|作为)?场景|场景[^。；，,]{{0,4}}(?:图|图片|参考图)\s*{number}", idea)
                else "subject_reference"
            ),
            "description": "用户输入中明确指向的参考图",
        }
        for number in sorted(found)
    ]


def build_node_prompt(
    idea: str,
    mode: str,
    aspect_label: str,
    duration: float,
    intensity_label: str,
    focus: str,
    skill_context: str,
    references: list[dict[str, Any]],
    extra_requirements: str = "",
) -> str:
    reference_lines = []
    for index, item in enumerate(references, start=1):
        label = str(item.get("label") or item.get("name") or f"<Picture {index}>")
        reference_lines.append(
            f"- {label} | kind={item.get('kind') or 'image'} | role={item.get('role') or 'reference'} | "
            f"description={item.get('description') or item.get('path') or ''}"
        )
    aspect = RATIO_VALUES.get(aspect_label, "16:9")
    task = MODE_TO_TASK.get(mode, "Ref2VA")
    return "\n".join(
        [
            "===== 用户原始创意 =====",
            str(idea or "").strip(),
            "",
            "===== 本次 H3 任务参数 =====",
            f"task={task}",
            f"aspect_ratio={aspect}",
            f"duration_seconds={float(duration):.2f}",
            f"动作强度={INTENSITY_TEXT.get(intensity_label, intensity_label)}",
            f"技能重点={focus}",
            "",
            "===== 参考素材目录 =====",
            "\n".join(reference_lines) if reference_lines else "无参考素材。",
            "",
            "===== 额外要求 =====",
            str(extra_requirements or "").strip() or "无。",
            "",
            "===== 已加载的 Skill 规则 =====",
            str(skill_context or "").strip(),
            "",
            "请严格执行以上规则，把用户创意扩展为最终 MiniMax H3 提示词。",
        ]
    )


def _subject_name(index: int, scene: bool = False) -> str:
    return f"场景主体{index}" if scene else f"画面主体{index}"


def build_fallback(
    idea: str,
    mode: str,
    aspect_label: str,
    duration: float,
    intensity_label: str,
    references: list[dict[str, Any]],
) -> str:
    task = MODE_TO_TASK.get(mode, "Ref2VA")
    aspect = RATIO_VALUES.get(aspect_label, "16:9")
    duration = max(4.0, min(15.0, float(duration or 10.0)))
    clean_idea = str(idea or "人物在同一空间中展开行动").strip()
    refs = references or infer_idea_references(clean_idea)
    if task == "Ref2VA":
        definitions: list[str] = []
        used_labels: list[str] = []
        subject_tokens: list[str] = []
        for index, item in enumerate(refs[:9], start=1):
            label = str(item.get("label") or f"<Picture {index}>").strip()
            if not re.fullmatch(r"<[^>]+>", label):
                label = f"<Picture {index}>"
            role = str(item.get("role") or "")
            scene = "scene" in role or "场景" in str(item.get("description") or "")
            description = str(item.get("description") or "").strip()
            if scene:
                definitions.append(
                    f"<Subject {index}> 为 {label} 中的核心环境：保留空间结构、主要陈设、材质和主光方向；"
                    f"{description or '用于锁定动作发生地'}。"
                )
            else:
                definitions.append(
                    f"<Subject {index}> 为 {label} 中的主要人物：保留可辨识发型、服装轮廓、主色和身份特征；"
                    f"参考用途为锁定形象与动作起点；{description or '不重复解析无关五官细节'}。"
                )
            subject_tokens.append(f"<Subject {index}>")
            used_labels.append(label)
        if not definitions:
            definitions.append("<Subject 1> 为无参考素材的主要人物，以用户给出的身份和动作执行。")
            subject_tokens.append("<Subject 1>")
        # The compressed Skill normally lets the model decide subjects. The fallback
        # keeps at least one subject so the result remains structurally valid.
        sections = [
            "subject_definitions:",
            "\n".join(definitions),
            "",
            "summary:",
            f"[reference generation] 以 {aspect} 画幅、{duration:.2f} 秒完成“{clean_idea}”。",
            "",
            "retention_analysis:",
            *[
                f"{label}: fully_preserved - 保留参考中的身份、服装主体轮廓和关键色彩；动作与场景在目标视频中重新组织。"
                for label in used_labels
            ],
        ]
    else:
        sections = [
            "integrated_multimodal_description:",
            f"目标视频为 {aspect} 画幅、约 {duration:.2f} 秒。{INTENSITY_TEXT.get(intensity_label, '')}"
            f"用户创意：{clean_idea}。",
        ]
        subject_tokens = []

    if task in {"I2VA", "FL2VA", "L2VA"}:
        alignment = []
        if refs:
            first = str(refs[0].get("label") or "<Picture 1>")
            if task == "I2VA":
                alignment.append(f"{first} 对齐目标视频 0.00 秒首帧。")
            elif task == "L2VA":
                alignment.append(f"{first} 对齐目标视频 {duration:.2f} 秒尾帧。")
            else:
                second = str((refs[1] if len(refs) > 1 else refs[0]).get("label") or "<Picture 2>")
                alignment.append(
                    f"{first} 对齐 0.00 秒首帧；{second} 对齐 {duration:.2f} 秒尾帧。"
                )
        sections.extend(["", *alignment])

    midpoint = max(1.0, duration * 0.42)
    opening_subject = subject_tokens[0] if subject_tokens else "画面主体"
    second_subject = subject_tokens[1] if len(subject_tokens) > 1 else opening_subject
    final_subject = subject_tokens[2] if len(subject_tokens) > 2 else second_subject
    sections.extend(
        [
            "",
            "detailed_description:" if task == "Ref2VA" else "",
            f"[Shot 1] {opening_subject} 在中近景斜角中进入可执行的起始姿态，重心下沉并主动向冲突点移动。"
            "镜头以稳定推进和轻微横移保持空间方向，动作从准备直接进入第一次接触，接触点清晰可见，"
            f"{second_subject} 的受击方向和周围环境受力形成明确反馈。",
            f"[Shot 2] 在 00:{midpoint:06.3f} 处，镜头切至 {second_subject} 的近景对招。"
            "攻方连续完成两次不同招式，第二击包含肘部或肩部变化；守方经历完整防守、防线被震开和短暂狼狈过渡，"
            "并立即用大幅侧移或下潜改变位置。镜头跟随位移完成一次交叉换位，避免双方原地站桩。",
            f"[Shot 3] 在 00:{max(midpoint + 1.2, duration - 2.0):06.3f} 处，镜头切至低角度中景。"
            f"{final_subject} 借环境支点再次发力，动作方向与前镜连续，最终形成一记有清楚接触点的收束动作。"
            "末帧停在主体仍保持动作张力、环境受力反馈尚未完全消散的画面上。",
        ]
    )
    sections.extend(
        [
            "",
            "overall_soundscape:",
            "脚步擦地、衣料摩擦、呼吸变化、两次清楚的身体接触声，"
            "以及动作结束后短促的环境回响；对白若存在，保留原语言并以清楚语气呈现。",
            "",
            "non_diegetic_music:",
            "低频脉冲从首镜轻起，第二镜对招时增加节奏层次，收束动作命中的一拍短暂收紧，末帧留下余响并收掉。",
        ]
    )
    lines = [line for line in sections if line != ""]
    # Keep blank lines between official sections without accumulating empty items.
    text = "\n".join(sections)
    return re.sub(r"\n{3,}", "\n\n", text).strip()
