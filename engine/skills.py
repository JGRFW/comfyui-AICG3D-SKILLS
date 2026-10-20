# Copyright (C) 2026 AICG3D
# SPDX-License-Identifier: GPL-3.0-or-later
"""Skill discovery and context packing for the standalone Skill plugin."""

from __future__ import annotations

import io
import json
import re
import shutil
import tempfile
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any

PLUGIN_DIR = Path(__file__).resolve().parents[1]
SKILLS_DIR = PLUGIN_DIR / "skills"
DEFAULT_SKILL_ID = "minimax-h3-short-drama-director"
IMAGE_REVERSE_SKILL_ID = "image-prompt-reverse"
VIDEO_REVERSE_SKILL_ID = "video-prompt-reverse"
H3_STANDARD_SKILL_ID = "h3-six-segment-standard"
T2I_SKILL_ID = "text-to-image-prompt"
FL2I_SKILL_ID = "first-last-frame-image-prompt"
BUILTIN_SKILL_CATEGORIES = {
    DEFAULT_SKILL_ID: "核心导演",
    IMAGE_REVERSE_SKILL_ID: "反推工具",
    VIDEO_REVERSE_SKILL_ID: "反推工具",
    H3_STANDARD_SKILL_ID: "标准格式",
    T2I_SKILL_ID: "图片生成",
    FL2I_SKILL_ID: "图片生成",
}
BUILTIN_SKILL_IDS = frozenset(BUILTIN_SKILL_CATEGORIES)
PREVIEW_MANIFEST_PATH = PLUGIN_DIR / "preview_manifest.json"
_PREVIEW_CACHE: dict[str, dict[str, Any]] | None = None
T8_SOURCE_NAME = "T8 Creative DNA Prompt Library"
T8_SOURCE_URL = "https://github.com/T8mars/minimax-h3-prompt-skill-T8"

FOCUS_OPTIONS = (
    "自动选择",
    "战斗导演",
    "文戏表演",
    "镜头与分镜",
    "段缝连续性",
    "FACS 微表情",
    "全流程导演",
)

_FOCUS_REFERENCES: dict[str, tuple[str, ...]] = {
    "战斗导演": (
        "combat-direction-engine.md",
        "action-previs-15grid.md",
        "action-cinematography-breakdown.md",
        "combat-rhythm-defense3state.md",
    ),
    "文戏表演": (
        "wenxi-micro-expression.md",
        "dialogue-doctor-7d.md",
        "dialogue-speed-check.md",
        "vo-os-weaving.md",
    ),
    "镜头与分镜": (
        "camera-specs-15rules.md",
        "camera-transitions-6types.md",
        "action-cinematography-breakdown.md",
    ),
    "段缝连续性": (
        "segment-splicing.md",
        "asset-spatial-ledger.md",
        "spatial-reference-system-V3.md",
    ),
    "FACS 微表情": (
        "★ facs-micro-expression.md",
        "facs-au-dictionary.md",
        "facs-emotion-recipes.md",
    ),
    "全流程导演": (
        "asset-first-pipeline.md",
        "seedance-render-engine.md",
        "combat-direction-engine.md",
        "wenxi-micro-expression.md",
        "quality-gate-review.md",
    ),
}

_KEYWORD_REFERENCES: tuple[tuple[re.Pattern[str], tuple[str, ...]], ...] = (
    (
        re.compile(r"打斗|战斗|武打|对决|搏斗|攻击|出手|打戏|枪战|剑|拳", re.I),
        ("combat-direction-engine.md", "action-previs-15grid.md", "action-cinematography-breakdown.md"),
    ),
    (
        re.compile(r"玄幻|法术|仙侠|神通|法宝|魔法|能量|大招|法阵", re.I),
        ("xuanhuan-magic-combat.md", "anime-ultimate-vfx-paradigm.md", "action-ultimate-finisher.md"),
    ),
    (
        re.compile(r"对白|台词|说话|争吵|谈判|独白|旁白|配音|口型", re.I),
        ("dialogue-doctor-7d.md", "dialogue-speed-check.md", "vo-os-weaving.md"),
    ),
    (
        re.compile(r"表情|眼神|哭|笑|情绪|微表情|愤怒|悲伤|恐惧", re.I),
        ("wenxi-micro-expression.md", "★ facs-micro-expression.md", "facs-emotion-recipes.md"),
    ),
    (
        re.compile(r"多段|续接|上一段|下一段|连续|衔接|长篇|长视频", re.I),
        ("segment-splicing.md", "asset-spatial-ledger.md"),
    ),
    (
        re.compile(r"镜头|运镜|推镜|拉镜|环绕|俯拍|仰拍|景别|分镜", re.I),
        ("camera-specs-15rules.md", "camera-transitions-6types.md"),
    ),
)


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig", errors="replace")


def _preview_manifest() -> dict[str, dict[str, Any]]:
    global _PREVIEW_CACHE
    if _PREVIEW_CACHE is not None:
        return _PREVIEW_CACHE
    try:
        payload = json.loads(_read_text(PREVIEW_MANIFEST_PATH)) if PREVIEW_MANIFEST_PATH.is_file() else {}
    except (OSError, ValueError):
        payload = {}
    _PREVIEW_CACHE = {
        str(key): value for key, value in payload.items() if isinstance(value, dict)
    } if isinstance(payload, dict) else {}
    return _PREVIEW_CACHE


def _preview_for(skill_id: str) -> dict[str, Any]:
    return dict(_preview_manifest().get(str(skill_id), {}))


def _front_matter(text: str) -> dict[str, str]:
    if not text.startswith("---"):
        return {}
    end = text.find("\n---", 3)
    if end < 0:
        return {}
    values: dict[str, str] = {}
    block_key = ""
    block_lines: list[str] = []
    for raw in text[3:end].splitlines():
        if block_key and (raw.startswith(" ") or raw.startswith("\t")):
            block_lines.append(raw.strip())
            continue
        if block_key:
            values[block_key] = "\n".join(block_lines).strip()
            block_key = ""
            block_lines = []
        match = re.match(r"^([\w-]+):\s*(.*)$", raw)
        if not match:
            continue
        key, raw_value = match.group(1), match.group(2).strip()
        if raw_value in {"|", ">"}:
            block_key = key
        else:
            values[key] = _yaml_scalar(raw_value)
    if block_key:
        values[block_key] = "\n".join(block_lines).strip()
    return values


def _yaml_scalar(raw: str) -> str:
    value = str(raw or "").strip()
    if len(value) >= 2 and value[0] == value[-1] == '"':
        try:
            return str(json.loads(value))
        except ValueError:
            return value[1:-1].replace('\\"', '"')
    if len(value) >= 2 and value[0] == value[-1] == "'":
        return value[1:-1].replace("''", "'")
    return value


def _interface_metadata(directory: Path) -> dict[str, str]:
    """Read the lightweight interface block used by imported Skill packages."""
    path = directory / "agents" / "openai.yaml"
    if not path.is_file():
        return {}
    values: dict[str, str] = {}
    for raw in _read_text(path).splitlines():
        match = re.match(r"^\s+(display_name|short_description|default_prompt):\s*(.*)$", raw)
        if match:
            values[match.group(1)] = _yaml_scalar(match.group(2))
    return values


def _entry(directory: Path) -> dict[str, Any] | None:
    entry = directory / "SKILL.md"
    if not directory.is_dir() or not entry.is_file():
        return None
    metadata = _front_matter(_read_text(entry))
    interface = _interface_metadata(directory)
    original_name = metadata.get("name") or directory.name
    full_description = metadata.get("description") or ""
    references = directory / "references"
    is_builtin = directory.name in BUILTIN_SKILL_IDS
    is_t8_skill = (
        not is_builtin
        and bool(interface)
        and (references / "summary.md").is_file()
        and (references / "template.md").is_file()
    )
    display_name = interface.get("display_name") or ("MiniMax H3 短剧提示词导演" if directory.name == DEFAULT_SKILL_ID else original_name)
    source = T8_SOURCE_NAME if is_t8_skill else ("AICG3D" if is_builtin else "本地 Skill")
    category = BUILTIN_SKILL_CATEGORIES.get(
        directory.name,
        "创意 DNA" if is_t8_skill else "专业 Skill",
    )
    return {
        "id": directory.name,
        "name": display_name,
        "original_name": original_name,
        "description": interface.get("short_description") or full_description,
        "full_description": full_description,
        "default_prompt": interface.get("default_prompt") or "",
        "source": source,
        "source_url": T8_SOURCE_URL if is_t8_skill else "",
        "category": category,
        "directory": directory,
        "entry": entry,
        "reference_count": len([path for path in references.glob("**/*") if path.is_file()]) if references.is_dir() else 0,
        "bundled": is_builtin,
    }


def discover() -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    if not SKILLS_DIR.is_dir():
        return result
    seen: set[Path] = set()
    for root in sorted(SKILLS_DIR.iterdir(), key=lambda item: item.name.lower()):
        if not root.is_dir() or root.name.startswith((".", "_")):
            continue
        candidates = [root]
        candidates.extend(
            child
            for child in sorted(root.iterdir(), key=lambda item: item.name.lower())
            if child.is_dir() and not child.name.startswith((".", "_"))
        )
        for directory in candidates:
            resolved = directory.resolve()
            if resolved in seen:
                continue
            item = _entry(directory)
            if item is None:
                continue
            seen.add(resolved)
            result.append(item)
            break
    result.sort(key=lambda item: (not item["bundled"], item["name"].lower()))
    return result


def _payload_item(item: dict[str, Any]) -> dict[str, Any]:
    preview = _preview_for(item["id"])
    return {
        "id": item["id"],
        "preview_gif": preview.get("gif_url") or "",
        "preview_poster": preview.get("poster_url") or "",
        "preview_title": preview.get("title") or "",
        "preview_summary": preview.get("summary") or "",
        "name": item["name"],
        "original_name": item["original_name"],
        "description": item["description"],
        "full_description": item["full_description"],
        "default_prompt": item["default_prompt"],
        "source": item["source"],
        "source_url": item["source_url"],
        "category": item["category"],
        "relative_path": item["directory"].relative_to(SKILLS_DIR).as_posix(),
        "reference_count": item["reference_count"],
        "bundled": item["bundled"],
    }


def payload() -> list[dict[str, Any]]:
    return [_payload_item(item) for item in discover()]


def selection_labels() -> list[str]:
    """Return unique user-facing skill labels while keeping ids as the stable fallback."""
    items = discover()
    counts: dict[str, int] = {}
    for item in items:
        label = str(item.get("name") or item["id"])
        counts[label] = counts.get(label, 0) + 1
    return [
        str(item.get("name") or item["id"])
        if counts.get(str(item.get("name") or item["id"]), 0) == 1
        else f"{item.get('name') or item['id']} ({item['id']})"
        for item in items
    ]


def default_skill_id() -> str:
    items = discover()
    bundled = next((item["id"] for item in items if item["id"] == DEFAULT_SKILL_ID), "")
    return bundled or (items[0]["id"] if items else "")


def get(skill_id: str | None = None) -> dict[str, Any] | None:
    wanted = str(skill_id or "").strip() or default_skill_id()
    wanted_casefold = wanted.casefold()
    return next(
        (
            item
            for item in discover()
            if wanted
            in {item["id"], item.get("name"), item.get("original_name")}
            or wanted_casefold in {str(item["id"]).casefold(), str(item.get("name") or "").casefold(), str(item.get("original_name") or "").casefold()}
        ),
        None,
    )


def selection_label(skill_id: str | None = None) -> str:
    item = get(skill_id)
    if item is None:
        return ""
    labels = selection_labels()
    ids = [entry["id"] for entry in discover()]
    try:
        return labels[ids.index(item["id"])]
    except ValueError:
        return str(item.get("name") or item["id"])


def _reference_path(skill: dict[str, Any], filename: str) -> Path | None:
    path = skill["directory"] / "references" / filename
    return path if path.is_file() else None


def _trim(text: str, limit: int) -> str:
    clean = text.strip()
    if len(clean) <= limit:
        return clean
    head = int(limit * 0.72)
    tail = limit - head
    return clean[:head] + "\n\n[...中间略，保留关键总结...]\n\n" + clean[-tail:]


def detail(skill_id: str | None = None) -> dict[str, Any] | None:
    item = get(skill_id)
    if item is None:
        return None
    payload = _payload_item(item)
    references = item["directory"] / "references"
    summary_path = None
    for name in ("summary.md", "minimax-h3-plugin-context.md", "h3-adapter.md"):
        candidate = references / name
        if candidate.is_file():
            summary_path = candidate
            break
    template_path = references / "template.md"
    payload["summary"] = _trim(_read_text(summary_path), 9000) if summary_path else item["full_description"]
    payload["template_excerpt"] = _trim(_read_text(template_path), 6000) if template_path.is_file() else ""
    payload["demo_prompt"] = item.get("default_prompt") or payload["summary"]
    return payload


def _selected_references(idea: str, focus: str) -> list[str]:
    selected: list[str] = []
    if focus in _FOCUS_REFERENCES:
        selected.extend(_FOCUS_REFERENCES[focus])
    for pattern, names in _KEYWORD_REFERENCES:
        if pattern.search(idea):
            selected.extend(names)
    if not selected:
        selected.extend(_FOCUS_REFERENCES["全流程导演"])
    return list(dict.fromkeys(selected))


def build_context(
    idea: str,
    focus: str = "自动选择",
    skill_id: str | None = None,
    max_chars: int = 56000,
) -> tuple[str, list[str], str]:
    """Return a compact Skill context plus the reference names actually used."""
    skill = get(skill_id)
    if skill is None:
        return "No packaged Skill was found.", [], ""

    blocks: list[str] = []
    used: list[str] = []
    blocks.append("# Skill 主说明：SKILL.md\n" + _trim(_read_text(skill["entry"]), 12000))
    used.append("SKILL.md")

    quickstart = skill["directory"] / "references" / "minimax-h3-plugin-context.md"
    if quickstart.is_file():
        blocks.append(_trim(_read_text(quickstart), 18000))
        used.append(quickstart.name)

    h3_adapter = _reference_path(skill, "h3-adapter.md")
    if h3_adapter:
        blocks.append("# 权威适配：references/h3-adapter.md\n" + _trim(_read_text(h3_adapter), 26000))
        used.append(h3_adapter.name)

    for filename in _selected_references(str(idea or ""), focus):
        path = _reference_path(skill, filename)
        if path is None or filename in used:
            continue
        blocks.append(f"# 专业规则：references/{filename}\n" + _trim(_read_text(path), 12000))
        used.append(filename)

    if not quickstart.is_file() and not h3_adapter:
        reference_dir = skill["directory"] / "references"
        preferred: list[Path] = []
        for filename in ("summary.md", "template.md"):
            preferred.append(reference_dir / filename)
        if reference_dir.is_dir():
            preferred.extend(path for path in sorted(reference_dir.rglob("*.md")) if path not in preferred)
        for path in preferred:
            if not path.is_file():
                continue
            relative_name = path.relative_to(reference_dir).as_posix()
            if relative_name in used:
                continue
            limit = 15000 if relative_name == "template.md" else 9000
            blocks.append(f"# Skill 参考：references/{relative_name}\n" + _trim(_read_text(path), limit))
            used.append(relative_name)
            if len([name for name in used if name != "SKILL.md"]) >= 6:
                break

    packed = "\n\n".join(
        [
            f"# Skill：{skill['name']}（{skill['id']}）",
            skill["description"],
            "\n\n".join(blocks),
            "用户只给一句创意时，先补足合理的可见动作、镜头、声音与连续性；不得改变用户明确指定的主体、对白和事件。",
        ]
    )
    return _trim(packed, max_chars), used, skill["id"]


def selection_options() -> list[str]:
    return list(FOCUS_OPTIONS)


def _safe_skill_id(value: str) -> str:
    clean = re.sub(r"[^a-zA-Z0-9._-]+", "-", str(value or "").strip()).strip(".-")
    return clean[:64] or "imported-skill"


def import_zip(filename: str, payload: bytes, replace: bool = False) -> dict[str, Any]:
    """Import a ZIP Skill package into skills/ and return its metadata."""
    if not payload:
        raise ValueError("上传的 ZIP 文件为空")
    SKILLS_DIR.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="aicg3d-skill-") as temp_name:
        temp_root = Path(temp_name)
        try:
            with zipfile.ZipFile(io.BytesIO(payload)) as archive:
                for info in archive.infolist():
                    name = info.filename.replace("\\", "/")
                    path = PurePosixPath(name)
                    if path.is_absolute() or ".." in path.parts:
                        raise ValueError(f"ZIP 包含不安全路径：{name}")
                archive.extractall(temp_root)
        except zipfile.BadZipFile as error:
            raise ValueError("上传文件不是有效的 ZIP 压缩包") from error

        candidates = sorted(
            (path.parent for path in temp_root.rglob("SKILL.md") if path.is_file()),
            key=lambda item: (len(item.relative_to(temp_root).parts), str(item).lower()),
        )
        if not candidates:
            raise ValueError("ZIP 中找不到 SKILL.md，Skill 包必须包含该文件")
        package_dir = candidates[0]
        preferred = package_dir.name if package_dir != temp_root else Path(filename).stem
        skill_id = _safe_skill_id(preferred)
        target = (SKILLS_DIR / skill_id).resolve()
        root = SKILLS_DIR.resolve()
        if root not in target.parents and target != root:
            raise ValueError("目标 Skill 路径超出插件目录")
        if target.exists():
            if not replace:
                raise FileExistsError(f"Skill「{skill_id}」已经存在")
            shutil.rmtree(target)
        shutil.copytree(package_dir, target)
    item = get(skill_id)
    if item is None:
        raise RuntimeError("Skill 导入后无法读取")
    return {
        "id": item["id"],
        "name": item["name"],
        "description": item["description"],
        "reference_count": item["reference_count"],
    }


def delete_skill(skill_id: str) -> dict[str, Any]:
    item = get(skill_id)
    if item is None:
        raise FileNotFoundError(f"找不到 Skill：{skill_id}")
    if item["bundled"]:
        raise ValueError("内置 MiniMax H3 Skill 不允许删除")
    target = item["directory"].resolve()
    root = SKILLS_DIR.resolve()
    if root not in target.parents:
        raise ValueError("Skill 路径超出插件目录")
    shutil.rmtree(target)
    return {"deleted": item["id"], "name": item["name"]}
