"""Real loopback TCP plus a test-only 200 ms stall after 4096 framed bytes.

The dedicated native test target hooks emitted send calls only. Both portions
use the real socket runtime and the same absolute deadline; production code is
unhooked. A Python peer independently checks every byte and frame sequence.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import socket
import subprocess
import tempfile
import threading
import time

PAYLOAD = bytes((i * 17 + 3) % 256 for i in range(262144))
MODES = ("credit", "long", "legacy", "fatal")


def line(sock: socket.socket) -> bytes:
    out = bytearray()
    while not out.endswith(b"\n"):
        data = sock.recv(1)
        if not data:
            return bytes(out)
        out += data
        if len(out) > 96:
            raise ValueError("oversized frame header")
    return bytes(out)


def frame(sock: socket.socket) -> dict:
    header = line(sock)
    fields = header.strip().split()
    if len(fields) != 5 or fields[0] != b"A1":
        raise ValueError(f"malformed frame header: {header!r}")
    wanted = int(fields[4])
    if not 0 <= wanted <= len(PAYLOAD):
        raise ValueError("unbounded payload length")
    data = bytearray()
    while len(data) < wanted:
        try:
            chunk = sock.recv(wanted - len(data))
        except ConnectionResetError:
            break
        if not chunk:
            break
        data += chunk
    return {"header": header.decode().strip(), "kind": int(fields[1]),
            "sequence": int(fields[2]), "dropped": int(fields[3]),
            "wanted": wanted, "data": bytes(data),
            "complete": len(data) == wanted}


def exact_wire(mode: str, frames: list[dict]) -> bool:
    if any(f["dropped"] != 0 for f in frames):
        return False
    if mode == "credit":
        expected = [(11, 1, b"first"), (12, 2, b"second"), (99, 3, b"done")]
    elif mode == "long":
        expected = [(20, 1, PAYLOAD), (99, 2, b"done")]
    else:
        header = b"A1 20 1 0 262144\n"
        return (len(frames) == 1 and frames[0]["kind"] == 20
                and frames[0]["sequence"] == 1
                and frames[0]["wanted"] == len(PAYLOAD)
                and not frames[0]["complete"]
                and frames[0]["data"] == PAYLOAD[:4096 - len(header)])
    return (len(frames) == len(expected)
            and all(f["complete"] and f["wanted"] == len(data)
                    and (f["kind"], f["sequence"], f["data"]) == (kind, seq, data)
                    for f, (kind, seq, data) in zip(frames, expected)))


def run(binary: Path, root: Path, mode: str) -> dict:
    out = root / mode
    out.mkdir()
    result = {"mode": mode, "frames": [], "peer_errors": []}
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    listener.listen(1)
    listener.settimeout(5)
    port = listener.getsockname()[1]

    def consume() -> None:
        try:
            sock, _ = listener.accept()
            with sock:
                sock.settimeout(5)
                if line(sock) != b"deadline-test\n":
                    raise ValueError("wrong channel greeting")
                if mode == "credit":
                    result["frames"].append(frame(sock))
                    time.sleep(.2)  # Actual peer withholds credit, not a send hook.
                    sock.sendall(b"C")
                result["frames"].append(frame(sock))
                if mode in ("long", "credit"):
                    result["frames"].append(frame(sock))
                try:
                    extra = sock.recv(1)
                except ConnectionResetError:
                    extra = b""
                if extra:
                    raise ValueError("unexpected frame bytes after completion")
        except Exception as exc:
            result["peer_errors"].append(repr(exc))
        finally:
            listener.close()

    thread = threading.Thread(target=consume, daemon=True)
    thread.start()
    try:
        with subprocess.Popen([str(binary), mode, str(port), str(out)],
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                              text=True) as child:
            try:
                stdout, stderr = child.communicate(timeout=8)
                result["exit_code"] = child.returncode
            except subprocess.TimeoutExpired:
                child.kill()  # Only this fixture's owned child.
                stdout, stderr = child.communicate(timeout=2)
                result["exit_code"] = child.returncode
                result["peer_errors"].append("fixture deadline exceeded")
            (out / "stdout.txt").write_text(stdout, encoding="utf-8")
            (out / "stderr.txt").write_text(stderr, encoding="utf-8")
    except Exception as exc:
        result["exit_code"] = -1
        result["peer_errors"].append(repr(exc))
        listener.close()
    thread.join(6)
    if thread.is_alive():
        result["peer_errors"].append("peer did not terminate within bounded deadline")
    timing = out / "timing.tsv"
    if timing.exists():
        result["write_elapsed_ns"], result["code"] = map(int, timing.read_text().split("\t"))
    report = out / "report.json"
    if report.exists():
        result["test"] = json.loads(report.read_text())["payload"]
    result["exact_wire"] = not result["peer_errors"] and exact_wire(mode, result["frames"])
    result["passed"] = (result["exit_code"] == 0 and result["exact_wire"]
                        and result.get("test", {}).get("status") == "pass")
    for received in result["frames"]:
        data = received.pop("data")
        received["received_bytes"] = len(data)
        received["sha256"] = hashlib.sha256(data).hexdigest()
    (out / "wire.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--binary", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    parser.add_argument("--root", type=Path)
    args = parser.parse_args()
    binary = args.binary.resolve(strict=True)
    temporary = None
    if args.root is None:
        temporary = tempfile.TemporaryDirectory(prefix="genesis-channel-deadlines-")
        root = Path(temporary.name)
    else:
        root = args.root.resolve()
        root.mkdir(parents=True, exist_ok=False)
    try:
        results = [run(binary, root, mode) for mode in MODES]
        report = {"schema": "genesis.channel_deadlines.v1",
                  "passed": all(r["passed"] for r in results), "cases": len(results),
                  "checks": sum(r.get("test", {}).get("checks", 0) for r in results),
                  "exact_wire_cases": sum(r["exact_wire"] for r in results),
                  "binary_sha256": hashlib.sha256(binary.read_bytes()).hexdigest(),
                  "controlled_started_write_stall_ms": 200, "results": results}
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print(f"Channel deadlines: {report['cases']} cases / {report['checks']} checks; "
              f"{report['exact_wire_cases']} exact real-TCP wire oracles; passed={report['passed']}")
        return 0 if report["passed"] else 1
    finally:
        if temporary is not None:
            temporary.cleanup()


if __name__ == "__main__":
    raise SystemExit(main())
