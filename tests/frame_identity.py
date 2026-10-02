"""Native monitor/timeline pixels must identify each frame, including fractional rates."""
import argparse
import os
import pathlib
import subprocess
import tempfile


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--worker", type=pathlib.Path, required=True)
    parser.add_argument("--client", type=pathlib.Path, required=True)
    args = parser.parse_args()
    worker = args.worker.resolve()
    ffmpeg = worker.parent / "ffmpeg.exe"
    flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    with tempfile.TemporaryDirectory(prefix="genesis-frame-identity-") as directory:
        root = pathlib.Path(directory)
        raw = root / "identity.rgb"
        frames = b"".join(bytes(32 + (n * multiplier) % 192 for multiplier in (37, 73, 109))
                          * (320 * 180) for n in range(96))
        raw.write_bytes(frames)
        media = root / "every frame 日本語 %20.mp4"
        subprocess.run([str(ffmpeg), "-nostdin", "-y", "-v", "error", "-f", "rawvideo",
                        "-pixel_format", "rgb24", "-video_size", "320x180", "-framerate", "24000/1001",
                        "-i", str(raw), "-c:v", "libx264rgb", "-crf", "0", "-preset", "fast",
                        "-bf", "3", "-g", "24", str(media)], check=True, timeout=30, creationflags=flags)
        # Independently decode the fixture before asking the application's worker.
        decoded = subprocess.run([str(ffmpeg), "-nostdin", "-v", "error", "-i", str(media),
                                  "-f", "rawvideo", "-pix_fmt", "rgb24", "pipe:1"],
                                 check=True, stdout=subprocess.PIPE, timeout=30, creationflags=flags).stdout
        assert decoded == frames, "lossless per-frame fixture changed in independent FFmpeg decoding"
        env = dict(os.environ, GENESIS_SCRATCH=str(root))
        env.pop("GENESIS_FAKE_PROVIDER", None)
        completed = subprocess.run([str(args.client.resolve()), str(root / "native"), str(worker),
                                    str(media), "frame-identity"], env=env, text=True, encoding="utf-8",
                                   errors="replace", stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                   timeout=120, creationflags=flags)
        assert completed.returncode == 0, (completed.returncode, completed.stdout[-6000:])
        assert "44 source/program pictures" in completed.stdout and "128 actual timeline bitmaps" in completed.stdout
        print(completed.stdout.strip(), flush=True)


if __name__ == "__main__":
    main()
