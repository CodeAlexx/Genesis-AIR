"""Independent owning-mixer-neutral display peaks; processed endpoint stays exact."""
import argparse, copy, hashlib, json, math, os, subprocess, sys, time
from array import array
from pathlib import Path
REPO=next(p for p in Path(__file__).resolve().parents if (p/'tests'/'audio_nested.py').is_file())
sys.path.insert(0,str(REPO/'tests'))
from audio_nested import authored,effect,keys
from nested_waveforms import float_wav,clip_signal,buckets
from standalone_endpoint_actor import OwnedWorkers,terminate_owned
FLAGS=0x08000000 if os.name=='nt' else 0
THRESHOLD=2e-6

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def neutral(doc):
    doc=copy.deepcopy(doc)
    for t in doc['tracks']:
        if t['owner']==doc['active']:t.update(gain=1,pan=0,muted=False,solo=False)
    return doc

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--client',type=Path,required=True)
    ap.add_argument('--worker',type=Path,required=True)
    ap.add_argument('--report',type=Path,required=True)
    a=ap.parse_args();a.client=a.client.resolve();a.worker=a.worker.resolve();a.report=a.report.resolve()
    root=a.report.parent/(a.report.stem+'-artifacts');root.mkdir(parents=True,exist_ok=False)
    source=root/'Own signal 日本語 %20.wav'
    raw=array('f')
    for n in range(4*48000):
        level=0.0 if n//6000%7==0 else (.125,.625,.25,.875)[n//1200%4]
        raw.extend((level if n%5 else -level,-level*.75 if n%3 else level*.5))
    float_wav(source,raw)
    base=authored([source],30,30)
    base['sequences']=base['sequences'][:1];base['tracks']=base['tracks'][:1]
    base['sources'][0]['frames']=120
    base['clips']=[dict(base['clips'][-1],source=7,nested=0,length=60,gain=1.25,pan=-.25,fade_in=6,fade_out=10)]
    effect(base,30,'compressor',dict(threshold=-14,ratio=4,attack=3,release=80))
    keys(base,30,2,'gain',[(0,.5,2),(19,1.4,2),(60,.65,2)])
    docs=[]
    for name,changes in [('normal',{}),('mute',dict(muted=True)),('gain0',dict(gain=0)),('pan',dict(pan=-.75)),('solo-excluded',{}),('combined',dict(gain=0,pan=.875,muted=True,solo=True))]:
        doc=copy.deepcopy(base);doc['tracks'][0].update(changes)
        if name=='solo-excluded':doc['tracks'].append(dict(doc['tracks'][0],id=4,order=1,solo=True,name='Root solo excluding A1'))
        docs.append((name,doc))
    nested=authored([source],30,30);nested['sources'][0]['frames']=120
    nested['clips'][0].update(length=60,gain=.6,pan=.125)
    nested['clips'][-1].update(length=60,gain=1.2,fade_out=7)
    nested['tracks'][1].update(gain=.3,pan=-.25)
    effect(nested,20,'compressor',dict(threshold=-10,ratio=3,attack=5,release=60),51)
    effect(nested,30,'compressor',dict(threshold=-17,ratio=5,attack=3,release=90),50)
    docs.append(('nested',nested));muted=copy.deepcopy(nested);muted['tracks'][0].update(gain=0,muted=True,pan=1);docs.append(('nested-mute',muted))
    for name,doc in docs:(root/f'{name}.air').write_text(json.dumps(doc,ensure_ascii=False),encoding='utf-8')
    manifest=root/'inputs.tsv';manifest.write_text(''.join(name+'\n' for name,_ in docs),encoding='utf-8')
    native=root/'native';native.mkdir()
    report=dict(schema='genesis.waveform-visual.v1',passed=False,driver_sha256=sha(Path(__file__)),client_sha256=sha(a.client),worker_sha256=sha(a.worker),source_sha256=sha(source),peak_tolerance=THRESHOLD,normalization=False,cases=[],failures=[])
    env=dict(os.environ,GENESIS_FONT='C:/Windows/Fonts/segoeui.ttf')
    try:
        process=None;owned=None;success=False
        try:
            with (root/'client.stdout.log').open('wb') as out,(root/'client.stderr.log').open('wb') as err:
                process=subprocess.Popen([str(a.client),str(native),str(a.worker),str(manifest)],stdout=out,stderr=err,creationflags=FLAGS,env=env,start_new_session=os.name!='nt')
                owned=OwnedWorkers(process.pid,a.worker)
                deadline=time.monotonic()+120
                while process.poll() is None:
                    owned.observe()
                    assert time.monotonic()<deadline,'Visual client deadline'
                    time.sleep(.002)
                report['client_exit']=process.wait(timeout=5)
            assert report['client_exit']==0,(report['client_exit'],(root/'client.stdout.log').read_text(encoding='utf-8',errors='replace')[-3000:],(root/'client.stderr.log').read_text(encoding='utf-8',errors='replace')[-3000:])
            report['observed_worker_pids_joined']=owned.joined()
            report['client_joined']=True;success=True
        finally:
            if process is not None and process.poll() is None:terminate_owned(process)
            if owned is not None:
                if not success:report['failed_owned_worker_cleanup']=owned.terminate_live()
                owned.close()
        client_proof=json.loads((native/'visual-media-tests.json').read_text(encoding='utf-8'))['payload']
        assert client_proof['status']=='pass' and client_proof['cases']==dict(total=8,passed=8,failed=0,skipped=0) and client_proof['checks']==64,client_proof
        report['client_cases']=8;report['client_checks']=64
        retained_keys={};values_checked=0
        for name,doc in docs:
            values=clip_signal(neutral(doc),30,{7:raw},a.worker);want=buckets(values,20)
            actual=[float(x) for x in (native/name/'visual.tsv').read_text(encoding='utf-8').splitlines()]
            kept=[float(x) for x in (native/name/'retained.tsv').read_text(encoding='utf-8').splitlines()]
            assert len(actual)==len(kept)==20 and all(math.isfinite(x) for x in actual)
            assert actual==kept,(name,'mixer change altered retained bytes')
            error=max(abs(x-y) for x,y in zip(actual,want));assert error<=THRESHOLD,(name,'reference',error)
            t=doc['tracks'][0];audible=not t['muted'] and (not any(x['solo'] for x in doc['tracks'] if x['owner']==2) or t['solo'])
            output=clip_signal(doc,30,{7:raw},a.worker) if audible else array('f',[0.]*len(values))
            expected=buckets(output,20)
            processed=[float(x) for x in (native/name/'processed.tsv').read_text(encoding='utf-8').splitlines()]
            assert len(processed)==20 and all(math.isfinite(x) for x in processed)
            err=max(abs(x-y) for x,y in zip(processed,expected));assert err<=THRESHOLD,(name,'processed',err)
            if name in ('mute','gain0','solo-excluded','combined','nested-mute'):assert processed==[0.]*20 and max(actual)>0
            key=(native/name/'key.txt').read_text(encoding='utf-8');retained_keys[name]=key
            report['cases'].append(dict(name=name,reference_peak_error=error,processed_peak_error=err,buckets=20,independent_pcm_values=len(values),reused_without_worker=True))
            values_checked+=len(values)+len(output)
        assert len({retained_keys[x] for x in ('normal','mute','gain0','pan','solo-excluded','combined')})==1
        assert retained_keys['nested']==retained_keys['nested-mute']
        report['owned_caches']=[str(p) for p in native.rglob('.genesis-nested-*')];assert not report['owned_caches']
        report['independent_pcm_values']=values_checked;report['numeric_peak_values']=320;report['passed']=True
        assert sha(a.client)==report['client_sha256'] and sha(a.worker)==report['worker_sha256']
    except BaseException as e:report['failures'].append(repr(e))
    finally:a.report.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False,indent=2));return 0 if report['passed'] else 1
if __name__=='__main__':raise SystemExit(main())
