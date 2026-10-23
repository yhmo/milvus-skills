#!/usr/bin/env python3
"""Shared helpers for compare-sdk tests."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType


SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"


def load_script(module_name: str) -> ModuleType:
    path = SCRIPTS_DIR / f"{module_name}.py"
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load test module: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
