"""The encoder preserves final PCM/FLAC samples and AAC packet duration."""
import argparse
from array import array
import json
from pathlib import Path
import re
import subprocess
import tempfile
import wave

from PIL import Image
from playback_timing import run, FLAGS
from preview_fit import wire


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--worker", type=Path, required=True)
    args = parser.parse_args()
    worker = args.worker.resolve()
    ffmpeg, ffprobe = worker.parent / "ffmpeg.exe", worker.parent / "ffprobe.exe"
    sizes = (1, 2, 1023, 1024, 1025, 1600, 9601, 48001)
    cases = [(codec, samples) for codec in ("pcm_s24le", "flac") for samples in sizes]
    cases += [("aac", samples) for samples in (1600, 4801, 9601, 48001)]
    source = (Path(__file__).resolve().parent.parent / "src/timeline_media.ai").read_text(encoding="utf-8")
    neutral = source.split("fn neutral()", 1)[1].split("\nfn source_path", 1)[0]
    fields = ["0"] * 108
    for index, value in re.findall(r'put\(values, (\d+), "([^"]+)"\)', neutral):
        fields[int(index)] = value
    fields[27:33] = ["1"] * 6
    with tempfile.TemporaryDirectory(prefix="genesis-export-audio-length-") as temporary:
        root = Path(temporary)
        picture = root / "picture 日本語.png"
        Image.new("RGB", (16, 16), (43, 81, 139)).save(picture)
        audio = root / "source 日本語.wav"
        # Exact representable values, including an audible last sample.
        expected = array("h", (value for n in range(max(sizes))
                               for value in (6000+n%37, -4000-n%29)))
        with wave.open(str(audio), "wb") as output:
            output.setparams((2, 2, 48000, 0, "NONE", "not compressed"))
            output.writeframes(expected.tobytes())
        fields[0] = wire(picture)
        payload = " ".join(fields)
        commands, outputs = [], []
        for index, (codec, count) in enumerate(cases):
            output = root / f"output-{index}.{'mp4' if codec == 'aac' else 'mkv'}"
            # OPEN allocates ceil(seconds*48000) samples. Stay inside the exact
            # count's interval so decimal roundoff cannot change the input count.
            seconds = (count-.25)/48000
            video_codec = "libx264" if codec == "aac" else "ffv1"
            commands.extend([f"OPEN {wire(output)} 16 16 30 1 0 0 {video_codec} {seconds:.17g} 0 - 320000 {codec} 30",
                             f"ENC {payload}",
                             f"AUDIO {wire(audio)} 0 {seconds:.17g} 0 1 0 0 {seconds:.17g} 0 -", "CLOSE"])
            outputs.append(output)
        child = subprocess.run([str(worker), "--serve", "--size", "16", "16"],
                               input="\n".join(commands)+"\n", text=True, encoding="utf-8",
                               errors="replace", capture_output=True, timeout=90, creationflags=FLAGS)
        assert child.returncode == 0 and "ERR" not in child.stdout, (child.returncode, child.stdout[-4000:], child.stderr[-4000:])
        assert sum(line.startswith("DONE") for line in child.stdout.splitlines()) == len(commands), child.stdout
        for (codec, count), output in zip(cases, outputs):
            info = json.loads(run([ffprobe, "-v", "error", "-show_streams", "-of", "json", output]).stdout)
            stream = next(stream for stream in info["streams"] if stream["codec_type"] == "audio")
            assert stream["codec_name"] == codec and stream["sample_rate"] == "48000" and stream["channels"] == 2, stream
            decoded = subprocess.run([str(ffmpeg), "-nostdin", "-v", "error", "-i", str(output), "-vn",
                                      "-f", "f32le", "pipe:1"], capture_output=True, timeout=30, creationflags=FLAGS)
            samples = array("f")
            samples.frombytes(decoded.stdout)
            assert decoded.returncode == 0, decoded.stderr
            if codec == "aac":
                assert stream["time_base"] == "1/48000" and int(stream["duration_ts"]) == count, (count, stream)
                assert count*2 <= len(samples) <= ((count+1023)//1024)*2048, (count, len(samples))
                assert max(abs(value) for value in samples[:count*2]) > .01
            else:
                assert len(samples) == count*2, (codec, count, len(samples))
                assert max(abs(actual-value/32768) for actual, value in zip(samples, expected)) <= 1/8388608, (codec, count)
                assert abs(samples[-1]-expected[count*2-1]/32768) <= 1/8388608, "final real sample lost"
            print(f"Export audio length: {codec}, {count} real samples preserved", flush=True)
    assert len(cases) == 20
    print("Export audio length: 16 exact PCM/FLAC lengths and samples, four exact AAC stream durations passed", flush=True)


if __name__ == "__main__":
    main()
