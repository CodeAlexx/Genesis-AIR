"""Independent bounded persistent-picture record and cancellation regression.

CPU protocol/control paths use a benign owned mock; optional real clients exercise
8193 exact frames per two Providers and GPU-plan retirement/resize/Reload.
"""
import argparse,ctypes,hashlib,json,os,pathlib,struct,subprocess,time,select,signal
from pathlib import Path
FLAGS=0x08000000 if os.name=='nt' else 0

def sha(p):return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()
def exited(pid):
 if os.name!='nt':
  try:os.kill(pid,0)
  except ProcessLookupError:return True
  return False
 k=ctypes.WinDLL('kernel32');k.OpenProcess.restype=ctypes.c_void_p
 k.WaitForSingleObject.argtypes=[ctypes.c_void_p,ctypes.c_ulong];k.CloseHandle.argtypes=[ctypes.c_void_p]
 h=k.OpenProcess(0x100000,False,pid)
 if not h:return True
 done=k.WaitForSingleObject(h,0)==0;k.CloseHandle(h);return done

def require(value, detail):
    if not value:
        raise AssertionError(detail)

def process_rows():
    """Read only process ownership, never inspect or control unrelated apps."""
    if os.name != "nt":
        rows = []
        for folder in Path("/proc").iterdir():
            if not folder.name.isdigit():
                continue
            try:
                fields = (folder / "stat").read_text().rsplit(")", 1)[1].split()
                rows.append((int(folder.name), int(fields[1]),
                             Path(os.readlink(folder / "exe")).name))
            except (OSError, ValueError):
                pass
        return rows
    from ctypes import wintypes as w
    class Entry(ctypes.Structure):
        _fields_ = [("size", w.DWORD), ("usage", w.DWORD), ("pid", w.DWORD),
                    ("heap", ctypes.c_size_t), ("module", w.DWORD),
                    ("threads", w.DWORD), ("parent", w.DWORD),
                    ("priority", w.LONG), ("flags", w.DWORD),
                    ("exe", w.WCHAR * 260)]
    api = ctypes.WinDLL("kernel32", use_last_error=True)
    api.CreateToolhelp32Snapshot.argtypes = [w.DWORD, w.DWORD]
    api.CreateToolhelp32Snapshot.restype = w.HANDLE
    api.Process32FirstW.argtypes = [w.HANDLE, ctypes.POINTER(Entry)]
    api.Process32NextW.argtypes = api.Process32FirstW.argtypes
    api.CloseHandle.argtypes = [w.HANDLE]
    handle = api.CreateToolhelp32Snapshot(2, 0)
    require(handle not in (None, ctypes.c_void_p(-1).value), "process snapshot")
    entry = Entry()
    entry.size = ctypes.sizeof(entry)
    rows = []
    try:
        more = api.Process32FirstW(handle, ctypes.byref(entry))
        while more:
            rows.append((entry.pid, entry.parent, entry.exe))
            more = api.Process32NextW(handle, ctypes.byref(entry))
    finally:
        api.CloseHandle(handle)
    return rows

class OwnedWorkers:
    """Retain OS process identities so observed worker exit cannot be inferred
    merely from cache deletion or a successful client exit."""
    def __init__(self, parent, worker):
        self.parent, self.worker = parent, worker
        self.handles = {}
        self.using_pidfd = hasattr(os, "pidfd_open") and hasattr(signal, "pidfd_send_signal")
        if os.name == "nt":
            from ctypes import wintypes as w
            self.api = ctypes.WinDLL("kernel32", use_last_error=True)
            self.api.OpenProcess.argtypes = [w.DWORD, w.BOOL, w.DWORD]
            self.api.OpenProcess.restype = w.HANDLE
            self.api.WaitForSingleObject.argtypes = [w.HANDLE, w.DWORD]
            self.api.TerminateProcess.argtypes = [w.HANDLE, w.UINT]
            self.api.CloseHandle.argtypes = [w.HANDLE]

    def observe(self):
        rows = process_rows()
        parents = {self.parent}
        while True:
            expanded = parents | {pid for pid, parent, _ in rows if parent in parents}
            if expanded == parents:
                break
            parents = expanded
        for pid, parent, name in rows:
            if parent not in parents or name != self.worker.name or pid in self.handles:
                continue
            if os.name == "nt":
                handle = self.api.OpenProcess(0x100001, False, pid)
                if handle:
                    self.handles[pid] = handle
            elif self.using_pidfd:
                try:
                    self.handles[pid] = os.pidfd_open(pid)
                except ProcessLookupError:
                    pass
            else:
                # Bootstrap Linux gate uses /proc; starttime guards PID reuse.
                try:
                    self.handles[pid] = Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()[19]
                except OSError:
                    pass

    def joined(self):
        require(self.handles, "No actual owned worker process observed")
        for pid, handle in self.handles.items():
            if os.name == "nt":
                require(self.api.WaitForSingleObject(handle, 0) == 0,
                        ("owned worker still live", pid))
            elif self.using_pidfd:
                require(bool(select.select([handle], [], [], 0)[0]),
                        ("owned worker still live", pid))
            else:
                try:
                    current = Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()[19]
                except OSError:
                    current = None
                require(current != handle, ("owned worker still live", pid))
        return sorted(self.handles)

    def terminate_live(self):
        """Failure only: use retained HANDLE/pidfd identities, or recheck the
        original /proc starttime immediately before the fallback PID signal.
        Return every cleanup error so an original client failure stays primary."""
        outcomes = []
        for pid, handle in self.handles.items():
            outcome = dict(pid=pid, terminated=False, exited=False)
            try:
                if os.name == "nt":
                    status = self.api.WaitForSingleObject(handle, 0)
                    if status == 258:
                        require(self.api.TerminateProcess(handle, 1), ("TerminateProcess", pid))
                        outcome["terminated"] = True
                    require(self.api.WaitForSingleObject(handle, 5000) == 0, ("worker cleanup join", pid))
                elif self.using_pidfd:
                    if not select.select([handle], [], [], 0)[0]:
                        try:
                            signal.pidfd_send_signal(handle, signal.SIGKILL)
                            outcome["terminated"] = True
                        except ProcessLookupError:
                            pass
                    require(bool(select.select([handle], [], [], 5)[0]), ("worker cleanup join", pid))
                else:
                    def still_owned():
                        try:
                            fields = Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()
                            return fields[19] == handle and fields[0] != "Z"
                        except OSError:
                            return False
                    if still_owned():
                        try:
                            os.kill(pid, signal.SIGKILL)
                            outcome["terminated"] = True
                        except ProcessLookupError:
                            pass
                    deadline = time.monotonic() + 5
                    while still_owned() and time.monotonic() < deadline:
                        time.sleep(.002)
                    require(not still_owned(), ("worker cleanup join", pid))
                outcome["exited"] = True
            except BaseException as error:
                outcome["error"] = repr(error)
            outcomes.append(outcome)
        return outcomes

    def close(self):
        for handle in self.handles.values():
            if os.name == "nt":
                self.api.CloseHandle(handle)
            elif self.using_pidfd:
                os.close(handle)

def terminate_owned(process):
    if os.name == "nt":
        subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"],
                       capture_output=True, timeout=10, creationflags=0x08000000)
    else:
        os.killpg(process.pid, signal.SIGKILL)
    process.wait(timeout=10)

def client_run(client, worker, argv, folder, env=None, timeout=60, required_workers=0):
 """Retain descendant identities while the owned client runs; never infer
 worker exit from a successful client or an empty PID set."""
 process=None;owned=None;succeeded=False
 row=dict(argv=list(map(str,argv)),client_sha256=sha(client),worker_sha256=sha(worker),required_workers=required_workers)
 begin=time.monotonic()
 try:
  with (folder/'output.log').open('xb') as output:
   process=subprocess.Popen(row['argv'],env=env,stdout=output,stderr=subprocess.STDOUT,creationflags=FLAGS,start_new_session=os.name!='nt')
   row['client_pid']=process.pid
   owned=OwnedWorkers(process.pid,worker)
   deadline=time.monotonic()+timeout
   while process.poll() is None:
    owned.observe()
    require(time.monotonic()<deadline,('Owned client deadline',timeout))
    time.sleep(.002)
   owned.observe()
   row['exit']=process.wait(timeout=5)
  require(row['exit']==0,('client failed',row['exit'],(folder/'output.log').read_text(errors='replace')))
  if required_workers:
   require(len(owned.handles)>=required_workers,('actual owned worker count',len(owned.handles),required_workers))
  row['owned_pids']=owned.joined() if owned.handles else []
  row['all_owned_exited']=bool(row['owned_pids'])
  row['client_joined']=True
  succeeded=True
  return row
 except BaseException as error:
  row['failure']=repr(error)
  raise
 finally:
  if owned is not None:
   try:owned.observe()
   except BaseException as error:row["final_observation_error"]=repr(error)
  if process is not None and process.poll() is None:
   try:terminate_owned(process)
   except BaseException as error:row['parent_cleanup_error']=repr(error)
  if owned is not None:
   if not succeeded:row['failed_run_worker_cleanup']=owned.terminate_live()
   row['observed_worker_pids']=sorted(owned.handles)
   owned.close()
  row['seconds']=time.monotonic()-begin
  row['passed']=succeeded
  with (folder/'process.json').open('x',encoding='utf8') as f:json.dump(row,f,indent=2);f.write('\n')

def main():
 p=argparse.ArgumentParser()
 for name in ['protocol-client','control-client','mock','report']:p.add_argument('--'+name,type=pathlib.Path,required=True)
 for name in ['persistent-client','epoch-client','worker']:p.add_argument('--'+name,type=pathlib.Path)
 a=p.parse_args();report=a.report.resolve()
 if report.exists():raise FileExistsError(report)
 root=report.parent/(report.stem+'-work');root.mkdir()
 paths=[a.protocol_client,a.control_client,a.mock,pathlib.Path(__file__)]
 if any(x is not None for x in [a.worker,a.persistent_client,a.epoch_client]):
  assert all(x is not None for x in [a.worker,a.persistent_client,a.epoch_client])
  paths +=[a.worker,a.persistent_client,a.epoch_client]
 inputs={str(x.resolve()):sha(x)for x in paths};cases=[]
 with(root/'invocation.json').open('x')as f:json.dump(dict(inputs=inputs,real_pictures_each=8193,scope='functional transport, no playback cadence/native device assertion'),f,indent=2)
 source=root/'source.f32'
 with source.open('xb')as f:f.write(b''.join(struct.pack('<4f',*[float((x+y)%2==0)]*3,1.)for y in range(16)for x in range(16)))
 def run(name,client,args,mock=False):
  work=root/name;work.mkdir();env=dict(os.environ)
  if mock:env.update(PROGRAM_MOCK_MODE_FILE=str(work/'mode.txt'),PROGRAM_MOCK_WITNESS=str(work/'witness.tsv'))
  worker=a.mock.resolve() if mock else a.worker.resolve()
  try:
   row=client_run(client.resolve(),worker,[str(client.resolve()),*map(str,args(work))],work,env=env,timeout=60,required_workers=0 if mock else (2 if name=='sustained' else 6))
  finally:
   if (work/'process.json').exists():
    row=json.loads((work/'process.json').read_text());row['name']=name;cases.append(row)
  witness=work/'witness.tsv'
  if mock:
   pids={int(x.split('\t')[0])for x in witness.read_text().splitlines()}if witness.exists()else set()
   require(pids,('No actual owned mock PID witness',name))
   row['mock_witness_pids']=sorted(pids)
   row['all_owned_exited']=all(exited(pid)for pid in pids)
   require(row['all_owned_exited'],row)
  return work
 for mode in ['valid','wrong-token','wrong-ticket','wrong-dims','wrong-size','wrong-magic','wrong-footer','wrong-footer-token','wrong-footer-ticket','wrong-footer-size','wrong-done','extra','truncated','exit','delayed-extra','legacy-valid','legacy-extra']:
  run('protocol-'+mode,a.protocol_client,lambda w:[a.mock.resolve(),source,w,mode],True)
 for mode in ['retire','stop','replacement','malformed','retire-replace']:
  run('control-'+mode,a.control_client,lambda w:[a.mock.resolve(),w,mode],True)
 if a.worker:
  for name,invert in [('a',False),('b',True)]:
   with(root/(name+'.f32')).open('xb')as f:f.write(b''.join(struct.pack('<4f',*[float(((x+y)%2==0)!=invert)]*3,1.)for y in range(16)for x in range(16)))
  sustained=run('sustained',a.persistent_client,lambda w:[a.worker.resolve(),root/'a.f32',root/'b.f32',w,8193])
  rows=[x.split('\t')for x in(sustained/'ports.tsv').read_text().splitlines()[1:]]
  assert len(rows)==16386 and (sustained/'result.tsv').read_text()=='8193\t8193\t1\n'
  identities=[]
  for name in ['a','b']:
   selected=[x for x in rows if x[1]==name];assert len(selected)==8193
   assert [int(x[0])for x in selected]==list(range(8193))
   assert [int(x[4])for x in selected]==list(range(1,8194)) and all(x[5]=='1'for x in selected)
   pairs={(x[2],x[3])for x in selected};assert len(pairs)==1;identities.append(next(iter(pairs)))
  assert identities[0][0]!=identities[1][0] and identities[0][1]!=identities[1][1]
  from media_runtime import tool
  raw=bytes([255,0,0])*32*18*30+bytes([0,0,255])*32*18*30
  with(root/'colors.rgb').open('xb')as f:f.write(raw)
  ffmpeg=tool(a.worker.resolve(),'ffmpeg');media=root/'colors.mkv'
  subprocess.run([str(ffmpeg),'-nostdin','-v','error','-f','rawvideo','-pixel_format','rgb24','-video_size','32x18','-framerate','30','-i',str(root/'colors.rgb'),'-c:v','ffv1','-pix_fmt','bgr0',str(media)],check=True,timeout=30,creationflags=FLAGS)
  decoded=subprocess.run([str(ffmpeg),'-nostdin','-v','error','-i',str(media),'-f','rawvideo','-pix_fmt','rgb24','pipe:1'],check=True,stdout=subprocess.PIPE,timeout=30,creationflags=FLAGS).stdout
  assert decoded==raw
  epoch=run('epochs',a.epoch_client,lambda w:[a.worker.resolve(),media,w])
  assert (epoch/'result.tsv').read_text()=='1\n'
  rows=[x.split('\t')for x in(epoch/'epochs.tsv').read_text().splitlines()]
  assert [int(x[0])for x in rows]==[1,3,4,5,6,7,9] and all(x[-1]=='1'for x in rows)
  roles=[x.split('\t') for x in (epoch/'worker-roles.tsv').read_text().splitlines()]
  assert roles==[['metadata-before','1'],['metadata-after','1']], roles
  assert [int(x[4]) for x in rows]==[1,3,3,5,6,6,9], rows
  assert len({int(x[4]) for x in rows})==5
  physical=next(x for x in cases if x['name']=='epochs')
  assert len(physical['owned_pids'])==len(physical['observed_worker_pids'])==6,physical
  assert physical['owned_pids']==physical['observed_worker_pids'],physical
  assert 'FLOAT 'in(epoch/'authored-plan.txt').read_text()
 assert inputs=={key:sha(key)for key in inputs}
 evidence={str(x.relative_to(root)):sha(x)for x in root.rglob('*')if x.is_file()and x.suffix in ['.json','.tsv','.log','.txt']}
 result=dict(schema='genesis.program-picture-transport.v2',passed=True,cases=cases,protocol_cases=17,control_cases=5,real_pictures_each=8193 if a.worker else 0,real_epoch_windows=7 if a.worker else 0,real_metadata_workers=1 if a.worker else 0,real_render_epochs=5 if a.worker else 0,inputs=inputs,evidence=evidence,scope='benign framed-record/cancellation and optional actual tiny-worker functional proof; no GUI/device/cadence acceptance')
 with(report.open('x',encoding='utf8'))as f:json.dump(result,f,indent=2);f.write('\n')
 print(json.dumps(dict(passed=True,cases=len(cases),report=str(report))))
if __name__=='__main__':main()
