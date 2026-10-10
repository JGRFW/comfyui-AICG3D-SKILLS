# Copyright (C) 2026 AICG3D
# SPDX-License-Identifier: GPL-3.0-or-later
"""Thin wrapper around the Skill's H1-H12 prompt validator."""

from __future__ import annotations

import importlib.util
import re
from pathlib import Path
from typing import Any

from engine import skills


def _load_validator():
    skill = skills.get()
    if skill is None:
        return None
    path = skill["directory"] / "scripts" / "validate_prompt.py"
    if not path.is_file():
        return None
    spec = importlib.util.spec_from_file_location("aicg3d_skill_prompt_validator", path)
    if spec is None or spec.loader is None:
        return None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def validate_h3(text: str) -> dict[str, Any]:
    module = _load_validator()
    if module is not None and hasattr(module, "validate_h3"):
        issues, warnings, stats = module.validate_h3(str(text or ""), "new")
        return {"issues": list(issues), "warnings": list(warnings), "stats": stats}
    return _fallback_validate(text)


def _fallback_validate(text: str) -> dict[str, Any]:
    value = str(text or "")
    issues: list[str] = []
    warnings: list[str] = []
    ref_sections = [
        "subject_definitions",
        "summary",
        "retention_analysis",
        "detailed_description",
        "overall_soundscape",
        "non_diegetic_music",
    ]
    basic_sections = [
        "integrated_multimodal_description",
        "overall_soundscape",
        "non_diegetic_music",
    ]
    if not all(re.search(rf"(?m)^{re.escape(name)}\s*:", value) for name in ref_sections):
        if not all(re.search(rf"(?m)^{re.escape(name)}\s*:", value) for name in basic_sections):
            issues.append("H1: 未找到完整的三字段或 Ref2VA 六段式字段。")
    if re.search(r"【(?:画幅风格|站位声明|接续状态|强制禁止项)】|@CHR-|@SCN-", value):
        issues.append("H8: 正文泄漏七段式栏名或 @ 资产锚点。")
    if re.search(r"不要出现|没有[^\n。；，]+|禁止出现", value):
        warnings.append("H8: 正文包含否定式描述，建议改成只写实际存在的画面。")
    labels = set(re.findall(r"<(?:Subject|Picture|Video|Audio)\s+\d+>", value))
    if labels and not re.search(r"(?m)^subject_definitions\s*:", value):
        warnings.append("H5: 使用了 H3 标签，但缺少 subject_definitions。")
    return {
        "issues": issues,
        "warnings": warnings,
        "stats": {
            "chars": len(value),
            "shots": len(re.findall(r"\[Shot\s+\d+\]", value)),
        },
    }
