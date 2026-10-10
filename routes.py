# Copyright (C) 2026 AICG3D
# SPDX-License-Identifier: GPL-3.0-or-later
"""HTTP API for comfyui-AICG3D-SKILLS."""

from __future__ import annotations

import asyncio

from aiohttp import web

from engine import composer, optimizer, skills, validator

VERSION = "1.2.1"
PROJECT_NAME = "AICG3D SKILLS"
_REGISTERED = False


async def _meta(_request):
    return web.json_response(
        {
            "name": PROJECT_NAME,
            "version": VERSION,
            "skills": [
                {
                    "id": item["id"],
                    "name": item["name"],
                    "description": item["description"],
                    "focus_options": skills.selection_options(),
                }
                for item in skills.discover()
            ],
        }
    )


async def _skill_list(_request):
    return web.json_response(
        {
            "skills": skills.payload(),
            "focus_options": skills.selection_options(),
        }
    )


async def _skill_detail(request):
    item = skills.detail(request.match_info.get("skill_id", ""))
    if item is None:
        return web.json_response({"error": "找不到 Skill"}, status=404)
    return web.json_response({"skill": item})


async def _validate(request):
    try:
        payload = await request.json()
        result = validator.validate_h3(str(payload.get("prompt") or ""))
        return web.json_response(result)
    except Exception as error:
        return web.json_response({"error": str(error)}, status=400)


async def _refresh_skills(_request):
    return web.json_response({"skills": skills.payload()})


async def _import_skill(request):
    try:
        reader = await request.multipart()
        field = await reader.next()
        if field is None or not getattr(field, "filename", None):
            raise ValueError("请选择要导入的 ZIP Skill 文件")
        payload = await field.read()
        replace = str(request.query.get("replace") or "").lower() in {"1", "true", "yes"}
        item = skills.import_zip(str(field.filename), payload, replace=replace)
        return web.json_response({"skill": item, "skills": skills.payload()})
    except FileExistsError as error:
        return web.json_response({"error": str(error), "code": "exists"}, status=409)
    except Exception as error:
        return web.json_response({"error": str(error)}, status=400)


async def _delete_skill(request):
    try:
        item = skills.delete_skill(request.match_info.get("skill_id", ""))
        return web.json_response({"deleted": item, "skills": skills.payload()})
    except FileNotFoundError as error:
        return web.json_response({"error": str(error)}, status=404)
    except Exception as error:
        return web.json_response({"error": str(error)}, status=400)


async def _compose(request):
    try:
        payload = await request.json()
        idea = str(payload.get("idea") or "")
        focus = str(payload.get("focus") or "自动选择")
        skill_id = str(payload.get("skill_id") or "")
        context, used, selected_skill_id = skills.build_context(idea, focus, skill_id)
        task = composer.MODE_TO_TASK.get(str(payload.get("mode") or ""), "Ref2VA")
        references = composer.parse_reference_catalog(str(payload.get("references") or ""))
        if not references:
            references = composer.infer_idea_references(idea)
        node_prompt = composer.build_node_prompt(
            idea,
            str(payload.get("mode") or "Ref2VA 全能参考（推荐）"),
            str(payload.get("aspect") or "16:9（横屏）"),
            float(payload.get("duration") or 10),
            str(payload.get("intensity") or "R2 商业高燃（默认）"),
            focus,
            context,
            references,
            str(payload.get("extra") or ""),
        )
        result = await asyncio.to_thread(
            optimizer.generate_prompt_sync,
            payload.get("config") if isinstance(payload.get("config"), dict) else None,
            {
                "task": task,
                "duration": float(payload.get("duration") or 10),
                "prompt": node_prompt,
                "media": references,
                "system": context,
            },
        )
        return web.json_response(
            {
                "prompt": result,
                "references": references,
                "skill_references": used,
                "skill_id": selected_skill_id,
            }
        )
    except Exception as error:
        return web.json_response({"error": str(error)}, status=400)


def register_routes() -> bool:
    global _REGISTERED
    if _REGISTERED:
        return True
    try:
        from server import PromptServer

        instance = getattr(PromptServer, "instance", None)
        if instance is None:
            return False
        routes = instance.routes
    except Exception:
        return False

    routes.get("/aicg3d-skills/api/meta")(_meta)
    routes.get("/aicg3d-skills/api/skills")(_skill_list)
    routes.get("/aicg3d-skills/api/skills/{skill_id}")(_skill_detail)
    routes.post("/aicg3d-skills/api/validate")(_validate)
    routes.post("/aicg3d-skills/api/compose")(_compose)
    routes.post("/aicg3d-skills/api/skills/refresh")(_refresh_skills)
    routes.post("/aicg3d-skills/api/skills/import")(_import_skill)
    routes.delete("/aicg3d-skills/api/skills/{skill_id}")(_delete_skill)
    _REGISTERED = True
    return True
