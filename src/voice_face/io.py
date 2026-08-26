# pyright: reportMissingImports=false, reportImplicitRelativeImport=false
"""Small IO helpers used by scripts and tests."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

try:
    import yaml
except Exception:  # pragma: no cover - optional dependency
    yaml = None


def should_skip(path: Path, force: bool) -> bool:
    return path.exists() and not force


def read_config(path: Path | None) -> dict[str, Any]:
    if path is None:
        return {}
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() in {".yaml", ".yml"}:
        if yaml is None:
            raise RuntimeError("PyYAML is required to read YAML configs")
        return yaml.safe_load(text) or {}
    return json.loads(text)


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
