"""GPU-fitted previews must exactly match the prior full-canvas pixel sampling."""
import argparse
import math
import pathlib
import queue
import re
import struct
import subprocess
import tempfile
import threading
import zlib


def wire(value):
    return str(value).replace("%", "%25").replace(" ", "%20").replace("\t", "%09").replace("\n", "%0A").replace("\r", "%0D")


def fixture(path, width, height):
    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))
    rows = []
    for y in range(height):
        row = bytearray(b"\0")
        for x in range(width):
            row.extend((x % 256, (255 - x) % 256, (x ^ y) % 256, y % 256))
        rows.append(bytes(row))
    header = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    path.write_bytes(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", header)
                     + chunk(b"IDAT", zlib.compress(b"".join(rows))) + chunk(b"IEND", b""))


def fitted(raw, canvas_width, canvas_height, width, height):
    if (width, height) == (canvas_width, canvas_height):
        return raw
    scale = min(width / canvas_width, height / canvas_height)
    fit_width = max(1, math.floor(canvas_width * scale + 0.5))
    fit_height = max(1, math.floor(canvas_height * scale + 0.5))
    left, top = (width - fit_width) // 2, (height - fit_height) // 2
    black = b"\0\0\0\xff"
    rows = []
    cache = {}
    for y in range(height):
        sy = (y - top) * canvas_height // fit_height if top <= y < top + fit_height else -1
        if sy not in cache:
            pixels = bytearray()
            for x in range(width):
                if sy >= 0 and left <= x < left + fit_width:
                    offset = (sy * canvas_width + (x - left) * canvas_width // fit_width) * 4
                    pixels.extend(raw[offset:offset + 3])
                    pixels.append(255)
                else:
                    pixels.extend(black)
            cache[sy] = bytes(pixels)
        rows.append(cache[sy])
    return b"".join(rows)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--worker", type=pathlib.Path, required=True)
    args = parser.parse_args()
    source = (pathlib.Path(__file__).resolve().parent.parent / "src/timeline_media.ai").read_text()
    neutral = source.split("fn neutral()", 1)[1].split("\nfn source_path", 1)[0]
    fields = ["0"] * 108
    for index, value in re.findall(r'put\(values, (\d+), "([^"]+)"\)', neutral):
        fields[int(index)] = value
    for index in range(27, 33):
        fields[index] = "1"
    count = 0
    with tempfile.TemporaryDirectory(prefix="genesis-preview-fit-") as directory:
        root = pathlib.Path(directory)
        for cw, ch in ((16, 16), (32, 16), (16, 32), (256, 256)):
            image = root / "RGBA 日本語 %20.png"
            fixture(image, cw, ch)
            fields[0] = wire(image)
            output = root / "preview.rgba"
            float_output = root / "composition.f32"
            process = subprocess.Popen([str(args.worker.resolve()), "--serve", "--size", str(cw), str(ch)],
                                       stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                       text=True, encoding="utf-8", errors="replace")
            replies = queue.Queue()
            def receive():
                for line in process.stdout:
                    replies.put(line)
                replies.put("")
            reader = threading.Thread(target=receive, daemon=True)
            reader.start()
            def ask(command, refused=False):
                process.stdin.write(command + "\n")
                process.stdin.flush()
                while True:
                    line = replies.get(timeout=30)
                    assert line, "worker ended before replying"
                    if line.startswith(("DONE", "ERR")):
                        assert line.startswith("ERR") == refused, (command.split()[:3], line)
                        return
            try:
                payload = " ".join(fields)
                ask(f"PREVIEW {payload} {wire(output)}")
                raw = output.read_bytes()
                assert len(raw) == cw * ch * 4 and any(raw[::4]), "empty full composition"
                if cw == 256:
                    assert set(raw[3::4]) == set(range(256)), "fixture did not exercise all alpha levels"
                ask(f"FLOAT {payload} {wire(float_output)}")
                floats = float_output.read_bytes()
                assert len(floats) == cw * ch * 16
                shapes = ((cw, ch), (1, 1), (3, 5), (5, 3), (17, 9), (9, 17), (480, 270), (1280, 720))
                for w, h in shapes:
                    ask(f"PREVIEWFIT {w} {h} {payload} {wire(output)}")
                    actual = output.read_bytes()
                    expected = fitted(raw, cw, ch, w, h)
                    assert actual == expected, ((cw, ch), (w, h), "GPU fit changed RGBA bytes")
                    count += 1
                # A spatial effect must keep its composition-pixel meaning, and
                # a final look must read LOOKB instead of the pre-look OUTB.
                for name, changes in (("blur", {35: "2"}), ("look", {13: "1", 14: "0.7"})):
                    changed = fields.copy()
                    for index, value in changes.items():
                        changed[index] = value
                    effect_payload = " ".join(changed)
                    ask(f"PREVIEW {effect_payload} {wire(output)}")
                    full_effect = output.read_bytes()
                    assert full_effect != raw, (name, "effect fixture was neutral")
                    ask(f"PREVIEWFIT 17 9 {effect_payload} {wire(output)}")
                    assert output.read_bytes() == fitted(full_effect, cw, ch, 17, 9), (name, "effect changed during display fitting")
                    count += 1
                for dimensions in ("0 8", "8 0", "-1 8", "7.5 8", "16385 1", "8192 8192", "18446744073709551615 4"):
                    ask(f"PREVIEWFIT {dimensions} {payload} {wire(output)}", refused=True)
                ask(f"FLOAT {payload} {wire(float_output)}")
                assert float_output.read_bytes() == floats, "fitted preview changed full-precision composition"
                ask(f"PREVIEW {payload} {wire(output)}")
                assert output.read_bytes() == raw, "invalid fit changed legacy preview/recovery"
            finally:
                process.stdin.close()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)
                reader.join(timeout=1)
                process.stdout.close()
    print(f"GPU fitted preview: {count} exact RGBA comparisons, landscape/portrait/odd sizes, alpha, black bars, spatial effect/final look, bounded invalid dimensions, FLOAT preservation and legacy recovery passed", flush=True)


if __name__ == "__main__":
    main()
