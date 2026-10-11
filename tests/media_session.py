"""Discover one CLI process's private media root without a shared latest pointer."""
from pathlib import Path
import time
import os
import uuid


def native_path(value):
    """Use extended Win32 paths only for I/O; preserve logical receipt values."""
    value = Path(value)
    if os.name != "nt":
        return value
    absolute = os.path.abspath(value)
    if absolute.startswith("\\\\?\\"):
        return Path(absolute)
    if absolute.startswith("\\\\"):
        return Path("\\\\?\\UNC\\" + absolute[2:])
    return Path("\\\\?\\" + absolute)


def session_env(env, directory):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    report = directory / f"media-session-{uuid.uuid4().hex}.txt"
    return dict(env, GENESIS_SESSION_REPORT=str(report)), report


def session_root(report, process=None, timeout=20):
    deadline = time.monotonic() + timeout
    while True:
        try:
            text = native_path(report).read_text(encoding="utf-8")
            # write_new reserves the file before writing; wait for the complete row.
            if text.endswith("\n") and text.strip():
                root = Path(text.strip())
                assert native_path(root).is_dir(), root
                assert Path(native_path(root / "session-root.txt").read_text(encoding="utf-8").strip()).resolve() == root.resolve()
                return root
        except FileNotFoundError:
            pass
        if time.monotonic() >= deadline or process is not None and process.poll() is not None:
            raise AssertionError(f"CLI did not publish a complete media session: {report}")
        time.sleep(.005)
