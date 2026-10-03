"""Resolve the application's shared MM-AIR tools in native media diagnostics."""
from pathlib import Path
import os
import shutil


def tool(worker, name):
    worker = Path(worker).resolve()
    config = worker.parent / "genesis-media-runtime.txt"
    if config.is_file():
        lines = config.read_text(encoding="utf-8").splitlines()
        index = 1 if name == "ffmpeg" else 2
        if len(lines) > index and lines[index].strip():
            result = Path(lines[index].strip())
            assert result.is_file(), f"[GA_MEDIA_RUNTIME] Missing shared tool: {result}"
            return result
    sibling = worker.parent / (name + ".exe")
    if sibling.is_file():
        return sibling
    override = os.environ.get("GENESIS_" + name.upper())
    result = override or shutil.which(name)
    assert result, f"[GA_MEDIA_RUNTIME] Cannot find {name}"
    return Path(result)
