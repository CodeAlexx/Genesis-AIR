"""Cancel actual 30-minute recursive audio warming, never a stalled fake worker."""
import argparse
from array import array
import ctypes
from ctypes import wintypes
import hashlib
import json
import os
from pathlib import Path
import struct
import subprocess
import tempfile
import time
import wave

from audio_nested import authored, cache_clear, effect, pcm


def sha(path):
    value = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024*1024), b""):
            value.update(block)
    return value.hexdigest()


def children(parent):
    if os.name != "nt":
        found = []
        for entry in Path("/proc").glob("[0-9]*"):
            try:
                status = (entry/"stat").read_text().rsplit(")",1)[1].split()
                if int(status[1]) == parent:
                    found.append(int(entry.name))
            except (OSError,ValueError,IndexError):
                pass
        return found
    class Entry(ctypes.Structure):
        _fields_ = [("size",wintypes.DWORD),("usage",wintypes.DWORD),("pid",wintypes.DWORD),
                    ("heap",ctypes.c_size_t),("module",wintypes.DWORD),("threads",wintypes.DWORD),
                    ("parent",wintypes.DWORD),("priority",wintypes.LONG),("flags",wintypes.DWORD),
                    ("exe",wintypes.WCHAR*260)]
    kernel = ctypes.WinDLL("kernel32",use_last_error=True)
    kernel.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
    kernel.Process32FirstW.argtypes = [wintypes.HANDLE,ctypes.POINTER(Entry)]
    kernel.Process32NextW.argtypes = [wintypes.HANDLE,ctypes.POINTER(Entry)]
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    snapshot = kernel.CreateToolhelp32Snapshot(2,0)
    assert snapshot != ctypes.c_void_p(-1).value, "Process snapshot unavailable"
    try:
        entry = Entry(); entry.size = ctypes.sizeof(entry)
        ok, result = kernel.Process32FirstW(snapshot,ctypes.byref(entry)), []
        while ok:
            if entry.parent == parent:
                result.append(entry.pid)
            ok = kernel.Process32NextW(snapshot,ctypes.byref(entry))
        return result
    finally:
        kernel.CloseHandle(snapshot)


def alive(pid):
    if os.name != "nt":
        return Path(f"/proc/{pid}").exists()
    kernel = ctypes.WinDLL("kernel32",use_last_error=True)
    kernel.OpenProcess.argtypes = [wintypes.DWORD,wintypes.BOOL,wintypes.DWORD]
    kernel.OpenProcess.restype = wintypes.HANDLE
    kernel.GetExitCodeProcess.argtypes = [wintypes.HANDLE,ctypes.POINTER(wintypes.DWORD)]
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    process = kernel.OpenProcess(0x1000,False,pid)
    if not process:
        assert ctypes.get_last_error() == 87, ("Cannot inspect own worker",pid,ctypes.get_last_error())
        return False
    try:
        code = wintypes.DWORD()
        assert kernel.GetExitCodeProcess(process,ctypes.byref(code))
        return code.value == 259
    finally:
        kernel.CloseHandle(process)


def image(pid):
    if os.name != "nt":
        return Path(f"/proc/{pid}/exe").resolve()
    kernel = ctypes.WinDLL("kernel32",use_last_error=True)
    kernel.OpenProcess.argtypes = [wintypes.DWORD,wintypes.BOOL,wintypes.DWORD]
    kernel.OpenProcess.restype = wintypes.HANDLE
    kernel.QueryFullProcessImageNameW.argtypes = [wintypes.HANDLE,wintypes.DWORD,wintypes.LPWSTR,ctypes.POINTER(wintypes.DWORD)]
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    process = kernel.OpenProcess(0x1000,False,pid)
    if not process:
        return None
    try:
        value,size = ctypes.create_unicode_buffer(32768),wintypes.DWORD(32768)
        return Path(value.value).resolve() if kernel.QueryFullProcessImageNameW(process,0,value,ctypes.byref(size)) else None
    finally:
        kernel.CloseHandle(process)


def worker_handle(pid):
    if os.name != "nt":
        return pid
    kernel = ctypes.WinDLL("kernel32",use_last_error=True)
    kernel.OpenProcess.argtypes = [wintypes.DWORD,wintypes.BOOL,wintypes.DWORD]
    kernel.OpenProcess.restype = wintypes.HANDLE
    handle = kernel.OpenProcess(0x1000,False,pid)
    assert handle, "Cannot retain live worker identity"
    return handle


def handle_alive(handle):
    if os.name != "nt":
        return alive(handle)
    kernel = ctypes.WinDLL("kernel32",use_last_error=True)
    kernel.GetExitCodeProcess.argtypes = [wintypes.HANDLE,ctypes.POINTER(wintypes.DWORD)]
    code = wintypes.DWORD()
    assert kernel.GetExitCodeProcess(handle,ctypes.byref(code))
    return code.value==259


def terminate_children(parent, worker):
    # Only the current direct children of this test process are eligible.
    # Never infer ownership from an executable name or a stale prior PID alone.
    owned = [pid for pid in children(parent) if image(pid)==worker]
    if os.name == "nt":
        kernel = ctypes.WinDLL("kernel32",use_last_error=True)
        kernel.OpenProcess.argtypes = [wintypes.DWORD,wintypes.BOOL,wintypes.DWORD]
        kernel.OpenProcess.restype = wintypes.HANDLE
        kernel.TerminateProcess.argtypes = [wintypes.HANDLE,wintypes.UINT]
        kernel.WaitForSingleObject.argtypes = [wintypes.HANDLE,wintypes.DWORD]
        kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        for pid in owned:
            if pid not in children(parent) or image(pid)!=worker:
                continue
            process = kernel.OpenProcess(0x100001,False,pid)
            if not process:
                assert not alive(pid), ("Cannot terminate owned test worker",pid)
                continue
            try:
                assert kernel.TerminateProcess(process,1)
                assert kernel.WaitForSingleObject(process,5000)==0
            finally:
                kernel.CloseHandle(process)
    else:
        import signal
        for pid in owned:
            if pid in children(parent) and image(pid)==worker:
                os.kill(pid,signal.SIGKILL)
    return owned


def cancel_case(client, worker, root, mode):
    process = subprocess.Popen([str(client),str(worker),str(root)]+(["shutdown"] if mode=="shutdown" else []),
                               stdout=subprocess.PIPE,stderr=subprocess.PIPE,
                               creationflags=0x08000000 if os.name=="nt" else 0)
    worker_pids, receipt, handle = [], dict(mode=mode), None
    try:
        deadline = time.monotonic()+15
        while not (root/"warm.tsv").exists():
            assert process.poll() is None, "Client exited before genuine warm"
            assert time.monotonic()<deadline, "Real nested cache did not begin warming"
            time.sleep(.002)
        witness = Path((root/"warm.tsv").read_text(encoding="utf-8"))
        header_deadline = time.monotonic()+3
        while not witness.is_file() or witness.stat().st_size<80:
            assert time.monotonic()<header_deadline, "No real RF64 header/stage written"
            time.sleep(.002)
        worker_pids = [pid for pid in children(process.pid) if image(pid)==worker]
        assert len(worker_pids)==1 and alive(worker_pids[0]), ("No unique live worker during warm",worker_pids)
        handle=worker_handle(worker_pids[0])
        receipt.update(warm_cache_size=witness.stat().st_size,observed_worker_pid=worker_pids[0])
        (root/"cancel.release").write_text("Stop",encoding="utf-8")
        stdout,stderr = process.communicate(timeout=20)
        assert process.returncode==0, (process.returncode,stdout[-4000:],stderr[-4000:])
        assert not handle_alive(handle), "Canceled native worker survived joined owner"
        cache_clear(root,"warm Stop then fresh request")
        assert not list(root.glob("cancelled.wav*")), "Canceled request published PCM or a partial"
        facts = dict(row.split("\t",1) for row in (root/"cancel.tsv").read_text(encoding="utf-8").splitlines())
        assert facts["warm_observed"]=="true" and facts["fresh_short_request"]=="true"
        assert 0<int(facts["stop_join_ns"])<=2500000000
        if mode=="discard":
            assert 0<int(facts["discard_ns"])<=2500000000
            assert "warm_discard_ack\ttrue" in (root/"discard.tsv").read_text(encoding="utf-8")
        recovered = pcm(root/"recovered.wav")
        assert len(recovered)==4800*2 and all(abs(value-(8192/32768*32767 if n%2==0 else -4096/32768*32767))<=1 for n,value in enumerate(recovered)), "Fresh short nested PCM differs from independently authored source"
        receipt.update(stop_join_ns=int(facts["stop_join_ns"]),worker_gone=True,
                       discard_ns=int(facts["discard_ns"]),same_background_owner_fresh_play=mode=="discard",
                       no_cache_or_partial=True,fresh_short_every_sample=True)
        return receipt
    finally:
        if process.poll() is None:
            (root/"stream"/"stop").write_text("stop",encoding="utf-8")
            try:
                process.communicate(timeout=5)
            except subprocess.TimeoutExpired:
                terminate_children(process.pid,worker)
                process.kill(); process.communicate(timeout=5)
        # If the parent returned an error, a direct child must still be retired
        # before deleting any of this caller's temporary cache/source files.
        remaining = terminate_children(process.pid,worker)
        assert not any(alive(pid) for pid in remaining), "Owned worker still alive during test cleanup"
        if handle is not None and os.name=="nt":
            kernel=ctypes.WinDLL("kernel32",use_last_error=True)
            kernel.CloseHandle.argtypes=[wintypes.HANDLE]
            kernel.CloseHandle(handle)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--client",type=Path,required=True)
    parser.add_argument("--worker",type=Path,required=True)
    parser.add_argument("--report",type=Path,required=True)
    args = parser.parse_args()
    client, worker = args.client.resolve(), args.worker.resolve()
    report = dict(schema="genesis.audio_nested_cancel.v1",passed=False,cases=[],
                  client_sha256=sha(client),worker_sha256=sha(worker))
    args.report.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="genesis-nested-warm-cancel-") as temporary:
        root = Path(temporary)
        long_source, short_source = root/"30 minute sparse silence.wav", root/"fresh constant.wav"
        data_bytes = 30*60*48000*4
        with long_source.open("wb") as output:
            if os.name == "nt":
                import msvcrt
                kernel = ctypes.WinDLL("kernel32",use_last_error=True)
                kernel.DeviceIoControl.argtypes = [wintypes.HANDLE,wintypes.DWORD,ctypes.c_void_p,wintypes.DWORD,
                                                  ctypes.c_void_p,wintypes.DWORD,ctypes.POINTER(wintypes.DWORD),ctypes.c_void_p]
                written = wintypes.DWORD()
                assert kernel.DeviceIoControl(msvcrt.get_osfhandle(output.fileno()),0x900C4,None,0,None,0,ctypes.byref(written),None), "Cannot create sparse authored fixture"
            output.write(struct.pack("<4sI4s4sIHHIIHH4sI",b"RIFF",data_bytes+36,b"WAVE",b"fmt ",16,1,2,48000,192000,4,16,b"data",data_bytes))
            output.seek(44+data_bytes-1); output.write(b"\0")
        with wave.open(str(short_source),"wb") as output:
            output.setparams((2,2,48000,0,"NONE","not compressed"))
            output.writeframes(array("h",[8192,-4096]*48000*8).tobytes())
        paths = [short_source]*4
        long_doc, short_doc = authored(paths), authored(paths)
        long_doc["sources"][0].update(path=str(long_source),frames=30*60*30)
        long_doc["clips"][0]["length"] = 30*60*60
        long_doc["clips"][-1]["length"] = 30*60*30
        effect(long_doc,20,"compressor",dict(threshold=-12.,ratio=4.,attack=.01,release=50.))
        projects = []
        for mode in ("discard","shutdown"):
            case_root = root/mode; case_root.mkdir()
            for name,doc in (("long",long_doc),("short",short_doc)):
                project = case_root/(name+".air")
                project.write_text(json.dumps(doc),encoding="utf-8")
                projects.append(project)
        hashes = {path:sha(path) for path in [long_source,short_source,*projects]}
        try:
            for mode in ("discard","shutdown"):
                report["cases"].append(cancel_case(client,worker,root/mode,mode))
            assert all(sha(path)==original for path,original in hashes.items()), "Cancellation changed source/project bytes"
            assert sha(worker)==report["worker_sha256"], "Worker changed during cancellation gate"
            report.update(passed=True,source_project_unchanged=True,
                          authored_source_seconds=1800,scope="real native recursive warm/Stop; no audio device")
        except Exception as problem:
            report["execution_error"] = str(problem)
            report["diagnostics"] = {str(path.relative_to(root)):path.read_text(encoding="utf-8",errors="replace")[-4000:]
                                     for path in root.rglob("*.tsv")}
            args.report.write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")
            raise
    args.report.write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")


if __name__=="__main__":
    main()
