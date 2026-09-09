#!/usr/bin/env python3
"""Print airc build diagnostics from a JSON report; exit 1 when the build failed."""
import json
import sys

report = json.load(open(sys.argv[1]))
if report.get("status") == "ok":
    sys.exit(0)
print("genesis-air: build failed", file=sys.stderr)
for entry in report.get("diagnostics", []):
    span = entry.get("span") or {}
    subject = entry.get("subject") or {}
    where = "{}:{}:{}".format(span.get("file", "?"), span.get("line", "?"), span.get("col", "?"))
    detail = entry.get("message") or entry.get("actual") or ""
    if entry.get("expected") and entry.get("actual"):
        detail = "{} (expected {}, found {})".format(detail, entry["expected"], entry["actual"])
    print("  {} {} [{}] {}".format(entry.get("code"), where,
                                   subject.get("fn") or subject.get("module") or "",
                                   detail), file=sys.stderr)
sys.exit(1)
