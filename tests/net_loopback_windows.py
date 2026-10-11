"""Independent Windows TCP policy, setup failure and bounded-resource checks.

Native fixtures use real AIR connect/accept/send/receive adapters. The policy
fixture injects only OS option/peer-query outcomes; no external host is contacted.
SO_SNDBUF sums are configured allowances, not measured kernel committed memory.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(binary: Path, *args: str) -> dict:
    result = subprocess.run([str(binary.resolve()), *args], capture_output=True,
                            text=True, timeout=90)
    if result.returncode:
        raise AssertionError(f"{binary.name} {args}: exit {result.returncode}: "
                             f"{result.stdout}\n{result.stderr}")
    report = json.loads(result.stdout)
    assert report.get("passed") is True, report
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("classifier", "policy", "resource", "report"):
        parser.add_argument(f"--{name}", type=Path, required=True)
    args = parser.parse_args()
    report = {"schema": "genesis.windows.loopback-policy.v1", "passed": False,
              "configured_allowance_is_not_kernel_memory_measurement": True,
              "cadence_qualified": False,
              "remote_policy_probe_uses_controlled_peer_metadata": True,
              "source_sha256": sha(Path(__file__)),
              "clients": {name: {"path": str(getattr(args, name)),
                                  "sha256": sha(getattr(args, name))}
                          for name in ("classifier", "policy", "resource")}}
    try:
        classifier = run(args.classifier)
        assert classifier["checks"] == 20 and classifier["failures"] == 0
        report["classifier"] = classifier
        policy = run(args.policy)
        assert policy["checks"] == 19 and policy["failures"] == 0
        assert policy["handles_before"] == policy["handles_after"]
        report["policy"] = policy
        for family, options in (("ipv4", ()), ("ipv6", ("v6",))):
            resource = run(args.resource, *options)
            pool = resource["resource_pool"]
            assert pool["passed"] and pool["all_handles_closed"]
            assert pool["pairs"] == 32 and pool["connected_sockets"] == 64
            assert pool["configured_send_room_sum"] == 64 * 1048576
            assert pool["queued_and_verified_bytes"] == 32 * 16 * (65536 + 96)
            assert resource["handles_before"] == resource["handles_after"]
            report[family] = resource
        report["passed"] = True
    except Exception as error:
        report["error"] = f"{type(error).__name__}: {error}"
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"passed": report["passed"], "report": str(args.report)}))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
