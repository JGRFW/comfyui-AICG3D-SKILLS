# Copyright (C) 2026 AICG3D
# SPDX-License-Identifier: GPL-3.0-or-later
"""Standalone ComfyUI entry point for comfyui-AICG3D-SKILLS."""

from __future__ import annotations

import os
import sys
import traceback

PLUGIN_DIR = os.path.dirname(os.path.abspath(__file__))
if PLUGIN_DIR not in sys.path:
    sys.path.insert(0, PLUGIN_DIR)

try:
    from engine import optimizer as _optimizer  # noqa: F401 - registers model/config routes
    import routes as skill_routes
    from skill_nodes import NODE_CLASS_MAPPINGS, NODE_DISPLAY_NAME_MAPPINGS

    skill_routes.register_routes()
    WEB_DIRECTORY = "./web"
    print(f"[AICG3D SKILLS] Loaded {len(NODE_CLASS_MAPPINGS)} Skill-driven MiniMax H3 nodes")
except Exception:
    traceback.print_exc()
    NODE_CLASS_MAPPINGS = {}
    NODE_DISPLAY_NAME_MAPPINGS = {}
    WEB_DIRECTORY = "./web"

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS", "WEB_DIRECTORY"]
