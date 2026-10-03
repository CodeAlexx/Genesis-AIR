"""Check clean native startup, delayed imports and coded shared-runtime failures."""
import argparse
import os
from pathlib import Path
import struct
import subprocess
from tempfile import TemporaryDirectory


def imports(binary, index):
    data = binary.read_bytes()
    pe = struct.unpack_from("<I", data, 0x3c)[0]
    optional = pe + 24
    assert struct.unpack_from("<H", data, optional)[0] == 0x20b, "expected PE32+"
    count = struct.unpack_from("<H", data, pe + 6)[0]
    size = struct.unpack_from("<H", data, pe + 20)[0]
    sections = [struct.unpack_from("<IIII", data, optional + size + i*40 + 8) for i in range(count)]
    def offset(rva):
        for virtual_size, base, raw_size, raw in sections:
            if base <= rva < base + max(virtual_size, raw_size):
                return raw + rva - base
        raise AssertionError(f"invalid PE address {rva}")
    rva = struct.unpack_from("<I", data, optional + 112 + index*8)[0]
    if not rva:
        return set()
    at, stride, names = offset(rva), (20 if index == 1 else 32), set()
    while any(data[at:at+stride]):
        name = offset(struct.unpack_from("<I", data, at + (12 if index == 1 else 4))[0])
        names.add(data[name:data.index(b"\0", name)].decode("ascii").lower())
        at += stride
    return names


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--worker", type=Path, required=True)
    args = parser.parse_args()
    worker = args.worker.resolve()
    dlls = {"avutil-61.dll", "avcodec-63.dll", "avformat-63.dll", "avfilter-12.dll",
            "swscale-10.dll", "swresample-7.dll"}
    assert not imports(worker, 1) & dlls, "FFmpeg DLL loaded before native runtime selection"
    assert dlls <= imports(worker, 13), "missing delayed native import"
    config = (worker.parent / "genesis-media-runtime.txt").read_text(encoding="utf-8")
    runtime = Path(config.splitlines()[0])
    flags = subprocess.CREATE_NO_WINDOW
    with TemporaryDirectory(prefix="genesis-shared-runtime-") as directory:
        root = Path(directory)
        # Hard links retain one library copy while exercising Unicode installation paths.
        binary = root / "editor 日本語" / "genesis-gcompose.exe"
        binary.parent.mkdir()
        os.link(worker, binary)
        os.link(worker.parent / "OpenCL.dll", binary.parent / "OpenCL.dll")
        settings = binary.parent / "genesis-media-runtime.txt"
        env = dict(os.environ, PATH=os.environ["SystemRoot"] + "\\System32")
        env.pop("GENESIS_FFMPEG_RUNTIME", None)
        def run(expected, code):
            result = subprocess.run([str(binary), "--serve", "--size", "16", "16"], input="",
                                    cwd=root, env=env, capture_output=True, text=True,
                                    errors="replace", timeout=30, creationflags=flags)
            assert result.returncode == expected and code in result.stderr, (result.returncode, result.stderr)
        settings.write_text(config, encoding="utf-8")
        run(0, "serve ready")
        shared = root / "shared rôle 日本語"
        shared.mkdir()
        for dll in runtime.glob("*.dll"):
            os.link(dll, shared / dll.name)
        settings.write_text(str(shared) + "\n", encoding="utf-8")
        run(0, "serve ready")
        env["GENESIS_FFMPEG_RUNTIME"] = str(runtime)
        settings.write_text(str(root / "missing") + "\n", encoding="utf-8")
        run(0, "serve ready")
        env["GENESIS_FFMPEG_RUNTIME"] = str(root / "missing")
        run(2, "GA_MEDIA_RUNTIME")
        env.pop("GENESIS_FFMPEG_RUNTIME")
        settings.write_bytes(b"\xff\n")
        run(2, "Invalid UTF-8")
        settings.unlink()
        run(2, "GA_MEDIA_RUNTIME")
        assert set(p.name for p in binary.parent.iterdir()) == {"genesis-gcompose.exe", "OpenCL.dll"}
    print("6 shared-runtime process cases and native delay imports passed; no local codec bundle")


if __name__ == "__main__":
    main()
