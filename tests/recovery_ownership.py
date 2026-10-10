"""Actual process ownership, atomic replacement and crash recovery acceptance."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time
import uuid


class Process:
    def __init__(self, binary: Path, scratch: Path, control: Path, role: str, cwd=None):
        control.mkdir(parents=True)
        self.control = control
        self.next_id = 1
        self.log = (control / "process.log").open("wb")
        self.child = subprocess.Popen(
            [str(binary), str(scratch), str(control), role],
            stdin=subprocess.DEVNULL, stdout=self.log, stderr=subprocess.STDOUT,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            cwd=cwd,
        )
        try:
            self.ready = self.wait(0)
        except Exception:
            self.close()
            raise

    def wait(self, number: int) -> dict:
        deadline = time.monotonic() + 10
        target = self.control / f"{number}.json"
        while time.monotonic() < deadline:
            if target.exists():
                try:
                    return json.loads(target.read_text(encoding="utf-8"))
                except (FileNotFoundError, PermissionError):
                    # Win32 atomic replacement can briefly retain an exclusive
                    # publication handle after the destination becomes visible.
                    # Preserve the existing deadline; do not accept partial facts.
                    time.sleep(0.005)
                    continue
            if self.child.poll() is not None:
                raise RuntimeError(f"fixture exited {self.child.returncode}: {self.control}")
            time.sleep(0.005)
        raise RuntimeError(f"fixture response timed out: {target}")

    def send(self, action: str, target: str | Path = "") -> int:
        number = self.next_id
        self.next_id += 1
        command = self.control / f"command-{number}.txt"
        temporary = command.with_suffix(".tmp")
        temporary.write_text(f"{action}\n{target}", encoding="utf-8")
        temporary.replace(command)
        return number

    def call(self, action: str, target: str | Path = "") -> dict:
        return self.wait(self.send(action, target))

    def crash(self):
        if self.child.poll() is None:
            self.child.kill()
        self.child.wait(timeout=10)

    def close(self):
        self.crash()
        self.log.close()


STATE_FIELDS = (
    "document", "history", "revision", "media_revision", "project_epoch",
    "selected_filter", "dirty", "project_path", "recovery_file", "recovered_file",
)


def preserved(before: dict, after: dict) -> bool:
    return all(before[name] == after[name] for name in STATE_FIELDS)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--binary", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    parser.add_argument("--work-root", type=Path)
    options = parser.parse_args()
    binary = options.binary.resolve()
    report = options.report.resolve()
    report.parent.mkdir(parents=True, exist_ok=True)
    root = (options.work_root or report.parent / f"recovery-process-{uuid.uuid4().hex}").resolve()
    root.mkdir(parents=True, exist_ok=False)
    processes: list[Process] = []
    checks: list[dict] = []
    failures: list[str] = []

    def check(value: bool, name: str):
        checks.append({"name": name, "passed": bool(value)})
        if not value:
            raise AssertionError(name)

    def spawn(group: str, name: str, role: str = "empty") -> Process:
        instance = Process(binary, root / group / "shared", root / group / name, role)
        processes.append(instance)
        return instance

    try:
        relative_cwd = root / "relative-root"
        relative_cwd.mkdir()
        def relative_process(name, role):
            instance = Process(binary, Path("shared state"), relative_cwd / name, role, cwd=relative_cwd)
            processes.append(instance)
            return instance
        relative_owner = relative_process("owner", "owner")
        relative_peer = relative_process("peer", "owner")
        relative_reader = relative_process("reader", "empty")
        absolute_snapshot = Path(relative_owner.ready["recovery_file"])
        absolute_peer = Path(relative_peer.ready["recovery_file"])
        check(absolute_snapshot.is_absolute() and absolute_snapshot.parent == relative_cwd / "shared state" / "recovery", "relative shared root is resolved to the process cwd before recording")
        relative_bytes, peer_bytes = sha(absolute_snapshot), sha(absolute_peer)
        check(relative_reader.call("offer")["message"] == "none", "relative-root startup skips both live owners")
        relative_refusal = relative_peer.call("recover", absolute_snapshot)
        check("GA_RECOVERY_BUSY" in relative_refusal["message"] and preserved(relative_peer.ready, relative_refusal), "absolute picker path with relative startup root refuses foreign owner without changing history")
        check(sha(absolute_snapshot) == relative_bytes and sha(absolute_peer) == peer_bytes, "relative-root refusal preserves both snapshot bytes")
        relative_owner.crash()
        relative_recovered = relative_peer.call("recover", absolute_snapshot)
        check("Recovered project" in relative_recovered["message"] and Path(relative_recovered["recovered_file"]) == absolute_snapshot, "relative-root orphan is claimable through an absolute picker path after crash")
        check(relative_reader.call("probe", absolute_snapshot)["message"] == "busy", "relative-root recovery retains the actual absolute sidecar lease")
        relative_alias = str(absolute_snapshot).replace("/", "\\").upper() if os.name == "nt" else f"{absolute_snapshot.parent}/./{absolute_snapshot.name}"
        check("Recovered project" in relative_peer.call("recover", relative_alias)["message"] and sha(absolute_snapshot) == relative_bytes, "relative-root own recovery alias transfers its lease without rewriting the snapshot")

        # Both dirty Apps own snapshots; clean startup must offer neither.
        a, b, c = spawn("live", "a", "owner"), spawn("live", "b", "owner"), spawn("live", "c")
        ap, bp = Path(a.ready["recovery_file"]), Path(b.ready["recovery_file"])
        original_a, original_b = sha(ap), sha(bp)
        check(ap != bp and ap.exists() and bp.exists(), "two processes reserve separate snapshots")
        check(c.call("offer")["message"] == "none", "startup skips both live owners")
        refused = b.call("recover", ap)
        check("GA_RECOVERY_BUSY" in refused["message"], "direct Recover refuses foreign live owner")
        check(preserved(b.ready, refused), "busy refusal preserves document, all Undo/Redo, revisions, selection and leases")
        check(sha(ap) == original_a and sha(bp) == original_b, "busy refusal preserves both snapshot bytes")
        replaced = a.call("record", "Replacement while lease is live")
        check(replaced["message"] == "recorded" and Path(replaced["recovery_file"]) == ap, "atomic autosave reuses its owned snapshot")
        check(sha(ap) != original_a, "atomic replacement publishes new complete document")
        check(json.loads(ap.read_text())["document"] == json.loads(replaced["document"]), "snapshot replacement matches independently read document")
        check("GA_RECOVERY_BUSY" in c.call("recover", ap)["message"], "lease remains busy after .air inode replacement")
        check(c.call("probe", ap)["message"] == "busy", "actual OS lock remains held across atomic replacement")
        a.crash()
        check(a.child.returncode is not None and ap.exists(), "forced process exit preserves snapshot")
        check(c.call("probe", ap)["message"] == "free", "forced exit releases OS lease")
        offered = c.call("offer")
        check(offered["message"] == "offered" and Path(offered["target"]) == ap, "orphan becomes startup recovery candidate")
        # The picker does not confer ownership: recheck at the user's decision.
        d = spawn("live", "d")
        recovered = d.call("recover", ap)
        check("Recovered project" in recovered["message"] and Path(recovered["recovered_file"]) == ap, "another process claims orphan while picker is pending")
        picked_refusal = c.call("choose", "0")
        check("GA_RECOVERY_BUSY" in picked_refusal["message"] and preserved(c.ready, picked_refusal), "pending picker race refuses before replacing current state")
        check(json.loads(recovered["document"]) == json.loads(replaced["document"]), "authoritative read under claimed lease restores exact replacement")
        before_failed_save = d.call("inspect")
        failed_save = d.call("save", root / "missing-parent" / "save.air")
        check("GA_SAVE_PUBLISH" in failed_save["message"] and preserved(before_failed_save, failed_save), "failed Save preserves recovered state and ownership")
        check(c.call("probe", ap)["message"] == "busy", "failed Save retains claimed lease")
        saved = d.call("save", root / "live" / "recovered-copy.air")
        check(saved["message"] == "saved" and not ap.exists() and bp.exists(), "Save as deletes only the claimed orphan")
        check(Path(str(ap) + ".owner").exists(), "cleanup retains stable lock sidecar")
        check(c.call("probe", ap)["message"] == "free", "successful cleanup releases sidecar lock")
        check(sha(bp) == original_b, "other live snapshot remains byte-identical after recovered Save")
        missing = c.call("recover", ap)
        check("GA_RECOVERY_READ" in missing["message"] and preserved(c.ready, missing), "failed snapshot read preserves complete current context")
        unowned = c.call("unowned", bp)
        check(unowned["message"] == "retained" and sha(bp) == original_b, "a tracked path without its lease cannot delete a foreign snapshot")

        # Two independent processes race for one orphan; exactly one owns it.
        owner = spawn("race", "owner", "owner")
        orphan = Path(owner.ready["recovery_file"])
        owner.crash()
        left, right = spawn("race", "left"), spawn("race", "right")
        left_number, right_number = left.send("recover", orphan), right.send("recover", orphan)
        left_result, right_result = left.wait(left_number), right.wait(right_number)
        winners = [(instance, facts) for instance, facts in ((left, left_result), (right, right_result)) if "Recovered project" in facts["message"]]
        losers = [(instance, facts) for instance, facts in ((left, left_result), (right, right_result)) if "GA_RECOVERY_BUSY" in facts["message"]]
        check(len(winners) == len(losers) == 1, "concurrent orphan claim has exactly one winner and one coded refusal")
        loser, refused = losers[0]
        check(preserved(loser.ready, refused), "claim loser preserves exact current state")
        winner = winners[0][0]
        winner.crash()
        check("Recovered project" in loser.call("recover", orphan)["message"], "winning recoverer's crash releases original snapshot for retry")
        loser.call("quit")
        loser.child.wait(timeout=10)
        after_exit = spawn("race", "after-exit")
        check("Recovered project" in after_exit.call("recover", orphan)["message"], "ordinary process exit drops nested App lease without deleting snapshot")

        # Own Recover transfers a handle, including Save-before-Recover.
        own = spawn("own", "owner", "owner")
        project = root / "own" / "original.air"
        check(own.call("save", project)["message"] == "saved", "initial Save succeeds")
        older = own.call("record", "Selected older snapshot")
        own_path = Path(older["recovery_file"])
        snapshot_bytes = own_path.read_bytes()
        latest = own.call("edit", "Latest unsaved document")
        requested = own.call("request", str(own_path).replace("/", "\\").upper() if os.name == "nt" else own_path)
        check(requested["pending"], "own-current Recover opens confirmation with native path aliases")
        restored = own.call("choose", "0")
        check("Recovered project" in restored["message"] and json.loads(restored["document"]) == json.loads(older["document"]), "Save-before-own-Recover transfers lease and restores selected older version")
        check(json.loads(project.read_text()) == json.loads(latest["document"]), "Save-before-Recover saves latest edits to original")
        check(own_path.read_bytes() == snapshot_bytes, "pending own recovery preserves selected snapshot bytes")
        own_probe = spawn("own", "probe")
        check("GA_RECOVERY_BUSY" in own_probe.call("recover", own_path)["message"], "transferred own snapshot remains exclusively held")
        check(own.call("save", root / "own" / "restored-copy.air")["message"] == "saved" and not own_path.exists(), "saving own recovered copy clears transferred snapshot")
        check(json.loads(project.read_text()) == json.loads(latest["document"]), "saving recovered copy preserves original latest save")

        # Ordinary projects remain ordinary even inside the managed directory.
        normal = spawn("normal", "reader")
        ordinary_document = json.loads(latest["document"])
        for inside in (False, True):
            original = root / "normal" / "shared" / ("recovery" if inside else "projects") / "user-project.air"
            original.parent.mkdir(parents=True, exist_ok=True)
            original.write_text(json.dumps(ordinary_document), encoding="utf-8")
            before = sha(original)
            result = normal.call("recover", original)
            check("Recovered project" in result["message"] and result["recovered_file"] == "", f"ordinary project stays untracked (inside={inside})")
            normal.call("save", root / "normal" / f"copy-{inside}.air")
            check(original.exists() and sha(original) == before, f"ordinary project preserved after recovered Save (inside={inside})")
            check(not Path(str(original) + ".owner").exists(), f"ordinary Recover creates no lock sidecar (inside={inside})")

        # Failed deletion keeps the ownership resource for a later retry.
        retention = spawn("retention", "owner", "owner")
        blocked_path = Path(retention.ready["recovery_file"])
        blocked_path.unlink()
        blocked_path.mkdir()
        child_path = blocked_path / "retained-child"
        child_path.write_text("prevents deletion", encoding="utf-8")
        kept = retention.call("clear")
        check(kept["message"] == "retained" and kept["recovery_file"] == str(blocked_path).replace("\\", "/"), "deletion failure retains path for retry")
        retention_probe = spawn("retention", "probe")
        check(retention_probe.call("probe", blocked_path)["message"] == "busy", "deletion failure retains actual lease")
        child_path.unlink()
        blocked_path.rmdir()
        check(retention.call("clear")["message"] == "cleared", "missing snapshot permits safe cleanup retry")
        check(retention_probe.call("probe", blocked_path)["message"] == "free", "successful retry releases retained lease")

        old_owner = spawn("retained-recovered", "old-owner", "owner")
        old_path = Path(old_owner.ready["recovery_file"])
        old_owner.crash()
        held_recovery = spawn("retained-recovered", "reader")
        check("Recovered project" in held_recovery.call("recover", old_path)["message"], "old recovered snapshot is claimed before failed-cleanup test")
        new_owner = spawn("retained-recovered", "new-owner", "owner")
        new_path = Path(new_owner.ready["recovery_file"])
        new_owner.crash()
        new_bytes = sha(new_path)
        old_path.unlink()
        old_path.mkdir()
        old_child = old_path / "retained-child"
        old_child.write_text("prevents deletion", encoding="utf-8")
        previous = held_recovery.call("inspect")
        refused = held_recovery.call("recover", new_path)
        check("GA_RECOVERY_CLEAR" in refused["message"] and preserved(previous, refused), "new Recover refuses if previous recovered snapshot cannot be cleared")
        held_probe = spawn("retained-recovered", "probe")
        check(held_probe.call("probe", old_path)["message"] == "busy", "failed Recover keeps previous recovered lease")
        check(held_probe.call("probe", new_path)["message"] == "free" and sha(new_path) == new_bytes, "failed Recover releases candidate lease and preserves candidate bytes")
        old_child.unlink()
        old_path.rmdir()
        check("Recovered project" in held_recovery.call("recover", new_path)["message"], "cleanup refusal can be retried successfully")
        check(held_probe.call("probe", old_path)["message"] == "free" and held_probe.call("probe", new_path)["message"] == "busy", "retry transfers only the newly claimed lease")

        # Retain original spelling when a selected own lease must be restored.
        alias_owner = spawn("retained-own", "old-owner", "owner")
        alias_old = Path(alias_owner.ready["recovery_file"])
        alias_owner.crash()
        alias_reader = spawn("retained-own", "reader")
        check("Recovered project" in alias_reader.call("recover", alias_old)["message"], "alias refusal fixture claims old recovered snapshot")
        own_record = alias_reader.call("record", "Current selected own snapshot")
        alias_current = Path(own_record["recovery_file"])
        current_bytes = sha(alias_current)
        alias_old.unlink()
        alias_old.mkdir()
        alias_child = alias_old / "retained-child"
        alias_child.write_text("prevents deletion", encoding="utf-8")
        before_alias = alias_reader.call("inspect")
        selected_alias = str(alias_current).replace("/", "\\").upper() if os.name == "nt" else f"{alias_current.parent}/./{alias_current.name}"
        check(alias_reader.call("request", selected_alias)["pending"], "own alias is selected while another recovered snapshot is held")
        alias_refusal = alias_reader.call("choose", "1")
        check("GA_RECOVERY_CLEAR" in alias_refusal["message"] and preserved(before_alias, alias_refusal), "alias cleanup refusal restores exact original path spellings and context")
        alias_probe = spawn("retained-own", "probe")
        check(alias_probe.call("probe", alias_current)["message"] == "busy" and alias_probe.call("probe", alias_old)["message"] == "busy", "alias refusal retains both actual ownership handles")
        check(sha(alias_current) == current_bytes, "alias refusal preserves selected current snapshot bytes")
        alias_child.unlink()
        alias_old.rmdir()
        check("Recovered project" in alias_reader.call("recover", selected_alias)["message"], "own alias recovery retries after cleanup failure")
        check(alias_probe.call("probe", alias_old)["message"] == "free" and alias_probe.call("probe", alias_current)["message"] == "busy", "successful alias retry transfers selected handle exactly once")

        # Corruption after selecting an orphan cannot alter the current project.
        corrupt_owner = spawn("corrupt", "owner", "owner")
        corrupt_path = Path(corrupt_owner.ready["recovery_file"])
        corrupt_owner.crash()
        corrupt_reader = spawn("corrupt", "reader", "owner")
        corrupt_before = corrupt_reader.ready
        check(corrupt_reader.call("request", corrupt_path)["pending"], "complete orphan can be selected before corruption")
        corrupt_path.write_text("not JSON", encoding="utf-8")
        result = corrupt_reader.call("choose", "1")
        check("GA_RECOVERY_FORMAT" in result["message"] and preserved(corrupt_before, result), "failed selected snapshot read preserves state and existing ownership")
        check(corrupt_path.read_text() == "not JSON" and corrupt_reader.call("probe", corrupt_path)["message"] == "free", "failed read preserves corrupt bytes and releases temporary ownership")
        check(corrupt_reader.call("probe", Path(corrupt_before["recovery_file"]))["message"] == "busy", "failed selected read retains current project's actual lease")

        # POSIX paths must not transfer the lease of a differently cased file.
        case_fact = "not applicable on Windows"
        if os.name != "nt":
            case_owner = spawn("case", "owner", "owner")
            lower = Path(case_owner.ready["recovery_file"])
            upper = lower.with_name(lower.name.swapcase())
            if not upper.exists():
                upper.write_bytes(lower.read_bytes())
                result = case_owner.call("recover", upper)
                check("Recovered project" in result["message"] and Path(result["recovered_file"]) == upper, "POSIX case-distinct snapshot is claimed independently")
                case_probe = spawn("case", "probe")
                check(case_probe.call("probe", upper)["message"] == "busy", "distinct-case recovered file has its own actual lease")
                check(case_probe.call("probe", lower)["message"] == "free" and not lower.exists(), "replacing project clears only actually owned old-case file")
                check(case_owner.call("save", root / "case" / "copy.air")["message"] == "saved" and not upper.exists(), "distinct-case recovered cleanup requires its own held lease")
                case_fact = "case-distinct paths passed"
            else:
                raise AssertionError("POSIX fixture requires a case-sensitive work root")
        print(f"Recovery ownership: {len(checks)} checks passed across real processes; {case_fact}")
    except Exception as error:
        failures.append(f"{type(error).__name__}: {error}")
        print(f"[GA_TEST_RECOVERY_OWNER] {failures[-1]}")
    finally:
        for instance in processes:
            instance.close()
        report.write_text(json.dumps({
            "passed": not failures, "checks": len(checks), "facts": checks,
            "failures": failures, "binary": str(binary), "binary_sha256": sha(binary),
            "work_root": str(root), "processes": len(processes),
        }, indent=2), encoding="utf-8")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
