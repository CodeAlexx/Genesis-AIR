"""Independent publication and real child-process export ownership regressions.

The controlled worker writes authored complete bytes and stalls OPEN. These are
filesystem/ownership checks, not media quality checks; export_cancel.py retains
real six-frame video/audio cancellation and retry coverage.
"""
from __future__ import annotations
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import threading
import time
import uuid

from media_session import session_env, session_root, native_path

PAYLOAD = b"independent complete export payload\n"
FOREIGN = b"foreign final must survive\x00\xff\n"
FLAGS = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def capture(argv, env=None, timeout=20):
    return subprocess.run(list(map(str, argv)), env=env, capture_output=True,
                          text=True, encoding="utf-8", errors="replace", timeout=timeout,
                          creationflags=FLAGS)


def document(source):
    return dict(schema="air.editor.project", revision=2, active=2,
                source_bounds=0, monitor_source=7, next_id=30,
                program=dict(playing=False, frame=0, mark_in=-1, mark_out=-1, rate=1, looping=False),
                monitor=dict(playing=False, frame=0, mark_in=-1, mark_out=-1, rate=1, looping=False),
                bins=[dict(id=1, name="Media", parent=0)],
                sequences=[dict(id=2, name="Ownership", fps=30, width=32, height=18)],
                sources=[dict(id=7, path=str(source), name="Controlled protocol source", bin=1,
                              frames=1, fps=30, width=32, height=18, has_video=True,
                              has_audio=False, audio_rate=0, audio_channels=0, online=True)],
                tracks=[dict(id=3, owner=2, kind=0, name="V1", order=0, hidden=False,
                             muted=False, locked=False, solo=False, gain=1, pan=0, height=44)],
                clips=[dict(id=20, owner=2, source=7, nested=0, source_in=0, length=1, start=0,
                            track=3, group=0, enabled=True, selected=False, fade_in=0,
                            fade_out=0, gain=1, pan=0, speed=1, reverse=False)],
                transitions=[], keys=[], markers=[], subtitles=[], filters=[], filter_params=[],
                filter_text_params=[], names=[])


def wait_file(path, process, timeout=10):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if path.exists():
            return path.read_text(encoding="utf-8").strip()
        if process.poll() is not None:
            raise AssertionError(("worker witness missing", process.communicate(), process.returncode))
        time.sleep(.005)
    raise AssertionError(("worker witness timeout", str(path)))


def start(binary, fixture, project, work, output, blocked=True, foreign=None, delayed_create=False):
    work.mkdir()
    witness = work / "worker"
    release = work / "release"
    env = dict(os.environ, GENESIS_GCOMPOSE=str(fixture), GENESIS_SCRATCH=str(work / "scratch"),
               GENESIS_OWNERSHIP_WITNESS=str(witness))
    env.pop("GENESIS_FAKE_PROVIDER", None)
    env.pop("GENESIS_OWNERSHIP_RELEASE", None)
    env.pop("GENESIS_OWNERSHIP_FOREIGN", None)
    env.pop("GENESIS_OWNERSHIP_CREATE", None)
    if blocked:
        env["GENESIS_OWNERSHIP_RELEASE"] = str(release)
    if foreign:
        env["GENESIS_OWNERSHIP_FOREIGN"] = str(foreign)
    if delayed_create:
        env["GENESIS_OWNERSHIP_CREATE"] = str(work / "create")
    env, session_report = session_env(env, work)
    process = subprocess.Popen([str(binary), "export", str(output), str(project)], env=env,
                               stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                               encoding="utf-8", errors="replace", creationflags=FLAGS)
    try:
        media = session_root(session_report, process)
    except BaseException:
        # work was exclusively created above; these markers belong to this invocation.
        # Release only this controlled child's possible OPEN gates before joining.
        marker_errors = []
        for marker in (release, work / "create"):
            try:
                with native_path(marker).open("xb") as owned:
                    owned.write(b"startup failure cleanup\n")
            except FileExistsError:
                pass  # Preserve existing bytes; never truncate a foreign marker.
            except OSError as error:
                marker_errors.append(repr(error))
        try:
            said, _ = process.communicate(timeout=15)
        except subprocess.TimeoutExpired:
            # Bounded fallback targets only this still-owned Popen handle.
            process.kill()
            said, _ = process.communicate(timeout=5)
        with native_path(work / "startup-failure-stdout.txt").open("x", encoding="utf-8") as log:
            log.write(said)
            if marker_errors:
                log.write("\nStartup marker cleanup errors: " + repr(marker_errors))
        raise
    return process, witness, release, media


def finish(process, work):
    said, _ = process.communicate(timeout=15)
    (work / "stdout.txt").write_text(said, encoding="utf-8")
    return process.returncode, said


def stop_owned(process):
    if process.poll() is None:
        process.kill()
        process.communicate(timeout=5)


def helper_checks(helper, root):
    results = []
    for name, existing in (("existing-file", "file"), ("existing-directory", "dir")):
        work = root / name
        work.mkdir()
        source, final = work / "source complete", work / "final"
        source.write_bytes(PAYLOAD)
        if existing == "file":
            final.write_bytes(FOREIGN)
        else:
            final.mkdir()
            (final / "foreign").write_bytes(FOREIGN)
        result = capture([helper, source, final])
        assert result.returncode == 2, (name, result.returncode)
        assert source.read_bytes() == PAYLOAD
        assert (final if existing == "file" else final / "foreign").read_bytes() == FOREIGN
        results.append(dict(name=name, passed=True))
    work = root / "concurrent-atomic-publication"
    work.mkdir()
    final = work / "complete 日本 %20.bin"
    sources = [work / f"source-{i}" for i in range(8)]
    bodies = [bytes([i+17])*524288 for i in range(8)]
    for source, body in zip(sources, bodies):
        source.write_bytes(body)
    barrier = threading.Barrier(8)
    observing = threading.Event()
    observations = []
    observer_errors = []
    def watch():
        while not observing.is_set():
            try:
                observations.append(hashlib.sha256(final.read_bytes()).hexdigest())
            except (FileNotFoundError, PermissionError):
                # Windows can deny opening the destination during its atomic
                # namespace operation. No bytes were observed in that state.
                pass
            except Exception as error:
                observer_errors.append(repr(error))
                break
    observer = threading.Thread(target=watch)
    observer.start()
    def publish(source):
        barrier.wait()
        return capture([helper, source, final]).returncode
    try:
        with ThreadPoolExecutor(max_workers=8) as pool:
            codes = list(pool.map(publish, sources))
        time.sleep(.02)
    finally:
        observing.set()
        observer.join()
    assert codes.count(0) == 1 and codes.count(2) == 7, codes
    assert not observer_errors and observations, (observer_errors, "no complete observation")
    winner = codes.index(0)
    assert final.read_bytes() == bodies[winner]
    expected_hash = hashlib.sha256(bodies[winner]).hexdigest()
    assert all(body == expected_hash for body in observations), "partial final became visible"
    assert not sources[winner].exists()
    assert all(source.read_bytes() == bodies[i] for i, source in enumerate(sources) if i != winner)
    results.append(dict(name="concurrent-atomic-publication", passed=True, exporters=8,
                        complete_observations=len(observations), winning_sha256=sha(final)))
    # The session witness can exceed MAX_PATH even when the report itself fits.
    # Exercise a complete authored witness, preserving the ordinary logical path.
    session_work = root / "long-session-marker"
    session = session_work / ("nested-" + "a" * 90) / ("nested-" + "b" * 90)
    native_path(session).mkdir(parents=True)
    report = session_work / "complete-session.txt"
    row = str(session).replace("\\", "/") + "\n"
    native_path(session / "session-root.txt").write_text(row, encoding="utf-8")
    native_path(report).write_text(row, encoding="utf-8")
    assert len(str(session / "session-root.txt")) > 260
    assert session_root(report, timeout=1).resolve() == session.resolve()
    results.append(dict(name="long-session-marker", passed=True,
                        marker_characters=len(str(session / "session-root.txt")),
                        logical_session_unchanged=True))
    # A source link is not an accepted complete owned regular source.
    if os.name != "nt":
        linked = work / "source-link"
        linked.symlink_to(final)
        rejected = capture([helper, linked, work / "bad-final"])
        assert rejected.returncode == 3 and not (work / "bad-final").exists()
        results.append(dict(name="source-symlink-refused", passed=True))
    return results


def application_checks(binary, fixture, project, root, baseline=False):
    results = []
    # The final appears after OPEN and before publication. It must survive exactly.
    output = root / "late final 日本語.mp4"
    work = root / "late-final"
    process, witness, release, media = start(binary, fixture, project, work, output)
    try:
        partial = Path(wait_file(witness.with_suffix(".target"), process))
        assert partial.read_bytes() == PAYLOAD
        output.write_bytes(FOREIGN)
        release.write_bytes(b"release")
        code, said = finish(process, work)
        if baseline:
            assert code == 0 and output.read_bytes() == PAYLOAD, ("baseline overwrite defect absent", code, said)
            results.append(dict(name="baseline-late-final-overwritten", passed=True,
                                defect_witness=True, final_sha256=sha(output)))
        else:
            assert code != 0 and "[GA_EXPORT_EXISTS]" in said, said
            assert output.read_bytes() == FOREIGN and not partial.exists()
            assert not Path(str(output)+".genesis-air-owner").exists()
            results.append(dict(name="late-final-preserved", passed=True, final_sha256=sha(output)))
    finally:
        stop_owned(process)

    # First exporter owns a real blocked child. Second must refuse before OPEN.
    output = root / "competing exporters.mp4"
    first_work = root / "first"
    first, witness, release, media = start(binary, fixture, project, first_work, output, delayed_create=True)
    second = None
    try:
        partial = Path(wait_file(witness.with_suffix(".target"), first))
        first_bytes = partial.read_bytes() if partial.exists() else None
        second_work = root / "second"
        second, other, other_release, _ = start(binary, fixture, project, second_work, output,
                                                blocked=baseline, delayed_create=baseline)
        if baseline:
            second_target = Path(wait_file(other.with_suffix(".target"), second))
            assert second_target == partial, ("baseline shared-partial witness absent", second_target, partial)
            assert not partial.exists(), "both baseline workers must reach OPEN before either writes"
            (second_work / "create").write_bytes(b"create")
            other_release.write_bytes(b"release")
            second_code, second_said = finish(second, second_work)
            assert second_code == 0, second_said
            (first_work / "create").write_bytes(b"create")
            release.write_bytes(b"release")
            first_code, first_said = finish(first, first_work)
            # The first now recreates/replaces the shared partial and publishes
            # over the already published destination: two concurrent owners.
            assert first_code == 0, first_said
            results.append(dict(name="baseline-same-target-shared-partial", passed=True, defect_witness=True))
            return results
        second_code, second_said = finish(second, second_work)
        assert second_code != 0 and "[GA_EXPORT_BUSY]" in second_said, second_said
        assert not other.with_suffix(".pid").exists() and partial.read_bytes() == first_bytes
        (first_work / "create").write_bytes(b"create")
        release.write_bytes(b"release")
        first_code, first_said = finish(first, first_work)
        assert first_code == 0 and output.read_bytes() == PAYLOAD, first_said
        assert not partial.exists() and not partial.parent.exists()
        results.append(dict(name="same-target-exclusive-before-worker", passed=True))
    finally:
        stop_owned(first)
        if second is not None:
            stop_owned(second)

    # Every pre-existing foreign target artifact is refused without child launch.
    for name, suffix, code in (("foreign-final", "", "GA_EXPORT_EXISTS"),
                               ("foreign-legacy-partial", ".genesis-air-part.mp4", "GA_EXPORT_PARTIAL_EXISTS"),
                               ("foreign-reservation", ".genesis-air-owner", "GA_EXPORT_BUSY")):
        output = root / f"{name}.mp4"
        foreign = Path(str(output)+suffix)
        if name == "foreign-reservation":
            foreign.mkdir()
            sentinel = foreign / "foreign"
        else:
            sentinel = foreign
        sentinel.write_bytes(FOREIGN)
        work = root / name
        process, witness, _, _ = start(binary, fixture, project, work, output, blocked=False)
        status, said = finish(process, work)
        assert status != 0 and f"[{code}]" in said, said
        assert sentinel.read_bytes() == FOREIGN and not witness.with_suffix(".pid").exists()
        results.append(dict(name=name, passed=True))

    # Cancel while the owner is blocked, then retry. No foreign partial is touched.
    output = root / "cancel-retry.mp4"
    work = root / "cancel"
    process, witness, release, media = start(binary, fixture, project, work, output)
    try:
        partial = Path(wait_file(witness.with_suffix(".target"), process))
        began = time.monotonic()
        (media / "export.cancel").write_text("cancel\n")
        status, said = finish(process, work)
        elapsed = time.monotonic()-began
        assert status != 0 and "[GA_EXPORT_CANCELLED]" in said and elapsed < 2.5, said
        assert not output.exists() and not partial.exists() and not partial.parent.exists()
        child_pid = int(witness.with_suffix(".pid").read_text())
        if os.name == "nt":
            from audio_stream import assert_process_exited
            assert_process_exited(child_pid)
        else:
            try:
                os.kill(child_pid, 0)
            except ProcessLookupError:
                pass
            else:
                raise AssertionError(("cancelled worker remains alive", child_pid))
        results.append(dict(name="cancel-owned-cleanup", passed=True, elapsed_seconds=elapsed))
    finally:
        stop_owned(process)
    retry_work = root / "retry"
    retry, _, _, _ = start(binary, fixture, project, retry_work, output, blocked=False)
    status, said = finish(retry, retry_work)
    assert status == 0 and output.read_bytes() == PAYLOAD, said
    results.append(dict(name="same-target-retry", passed=True))

    # A foreign unexpected entry inside the reservation cannot be removed.
    # The output has committed, so this is success with a coded cleanup warning.
    output = root / "committed-cleanup.mp4"
    reservation = Path(str(output)+".genesis-air-owner")
    foreign = reservation / "foreign-entry"
    work = root / "committed-cleanup"
    process, witness, _, _ = start(binary, fixture, project, work, output, blocked=False, foreign=foreign)
    status, said = finish(process, work)
    assert status == 0 and "[GA_EXPORT_PUBLISHED_CLEANUP]" in said, said
    assert output.read_bytes() == PAYLOAD and foreign.read_bytes() == b"foreign entry preserved\n"
    assert (reservation / "cleanup.error").exists()
    assert not (reservation / "export.mp4").exists()
    results.append(dict(name="committed-success-cleanup-warning", passed=True))

    # Copy just the native payload without the helper: refuse before any output
    # reservation/worker, with the specific dependency diagnostic.
    isolated = root / "without-helper"
    isolated.mkdir()
    isolated_binary = isolated / binary.name
    shutil.copy2(binary, isolated_binary)
    if os.name == "nt":
        for dll in binary.parent.glob("*.dll"):
            shutil.copy2(dll, isolated / dll.name)
    output = root / "missing-helper.mp4"
    work = root / "missing-helper"
    process, witness, _, _ = start(isolated_binary, fixture, project, work, output, blocked=False)
    status, said = finish(process, work)
    assert status != 0 and "[GA_EXPORT_HELPER]" in said, said
    assert not output.exists() and not Path(str(output)+".genesis-air-owner").exists()
    assert not witness.with_suffix(".pid").exists()
    results.append(dict(name="missing-helper-preflight", passed=True))
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("binary", "fixture", "helper", "report"):
        parser.add_argument(f"--{name}", type=Path, required=True)
    parser.add_argument("--root", type=Path)
    parser.add_argument("--expect-baseline-defects", action="store_true")
    args = parser.parse_args()
    binary, fixture, helper = (p.resolve() for p in (args.binary, args.fixture, args.helper))
    root = (args.root or args.report.parent / (args.report.stem+"-"+uuid.uuid4().hex)).resolve()
    root.mkdir(parents=True, exist_ok=False)
    report = dict(schema="genesis.export-ownership.v1", passed=False, controlled_worker_media_quality=False,
                  baseline_defect_proof=args.expect_baseline_defects, cases=[], root=str(root),
                  source_sha256=sha(__file__), binary_sha256=sha(binary), fixture_sha256=sha(fixture),
                  helper_sha256=sha(helper), platform=os.name)
    try:
        source = root / "controlled-source"
        source.write_bytes(b"the fixture acknowledges commands without decoding this source")
        project = root / "authored.air"
        project.write_text(json.dumps(document(source)), encoding="utf-8")
        original = sha(project)
        report["cases"].extend(helper_checks(helper, root))
        report["cases"].extend(application_checks(binary, fixture, project, root, args.expect_baseline_defects))
        assert sha(project) == original
        report.update(passed=True, case_count=len(report["cases"]), project_sha256=original,
                      project_unchanged=True)
    except Exception as error:
        report["error"] = repr(error)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2)+"\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
