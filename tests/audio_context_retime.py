"""Forward unavailable-history retime: independent original-origin DSP oracle.

The durable original window stays60 owner frames. A real SDK tail trim to30
then Rate2 declares an available input extent and a30-frame processing endpoint.
References use authored native PCM and shared MM-AIR, never Genesis output.
"""
import argparse, copy, hashlib, json, math, os, struct, subprocess, tempfile, time, wave
from pathlib import Path
import numpy as np
from audio_mix_project import document
from audio_nested import effect
from audio_stream import wire
from media_runtime import tool
from nested_waveforms import Worker
from audio_nested_cancel import children,image,worker_handle,handle_alive,terminate_children

SR=48000
FLAGS=0x08000000 if os.name=='nt' else 0
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def sample(frame,fps):return math.floor(frame*SR/fps+.5)
def run(args,**kw):
    p=subprocess.run(list(map(str,args)),capture_output=True,timeout=180,creationflags=FLAGS,**kw)
    assert p.returncode==0,(args,p.returncode,p.stdout[-2000:],p.stderr[-2000:])
    return p.stdout
def pcm(p):
    with wave.open(str(p)) as w:
        assert (w.getnchannels(),w.getsampwidth(),w.getframerate())==(2,2,SR)
        return np.frombuffer(w.readframes(w.getnframes()),dtype='<i2').reshape(-1,2).copy()
def quantize(v):return (np.sign(v)*np.floor(np.abs(np.clip(v,-1,1))*32767+.5)).astype(np.int16)
def peaks(v,n):return np.array([np.max(np.abs(v[k*len(v)//n:(k+1)*len(v)//n]),initial=0) for k in range(n)])
def fitted(v,count):return np.pad(v[:count],((0,max(0,count-len(v))),(0,0)))

def cancellation(root,client,worker):
    source=root/'30-minute-original.wav';size=SR*1800*4
    with source.open('wb') as f:
        f.write(struct.pack('<4sI4s4sIHHIIHH4sI',b'RIFF',size+36,b'WAVE',b'fmt ',16,1,2,SR,SR*4,4,16,b'data',size))
        f.seek(44+size-1);f.write(b'\0')
    doc=document([source],(0,));doc['sources'][0].update(frames=54000,fps=30)
    doc['clips'][0].update(length=54000,streams=2);doc['next_id']=100
    effect(doc,20,'compressor',dict(threshold=-24,ratio=12,attack=80,release=1200),50)
    immutable=sha(source);rows=[]
    for mode in ('superseded','stop'):
        owned=root/('cancel-'+mode);owned.mkdir();project=owned/'cancel.air';project.write_text(json.dumps(doc),encoding='utf8')
        original=sha(project);marker=owned/'request.id';marker.write_text('1');witness=owned/'prefix.active'
        process=subprocess.Popen([str(client),str(worker),str(owned),'--cancel'],stdout=subprocess.PIPE,stderr=subprocess.PIPE,
            creationflags=FLAGS,env=dict(os.environ,GENESIS_AUDIO_CONTEXT_TRACE=str(witness)))
        handle=None
        try:
            deadline=time.monotonic()+20
            while not (witness.is_file() and witness.read_text()=='processed_prefix_frames=240000\n'):
                assert process.poll() is None,(mode,'Completed before actual prefix')
                assert time.monotonic()<deadline,(mode,'Prefix witness deadline');time.sleep(.002)
            pids=[pid for pid in children(process.pid) if image(pid)==worker];assert len(pids)==1,pids
            handle=worker_handle(pids[0]);started=time.monotonic()
            (owned/'stop').write_text('stop') if mode=='stop' else marker.write_text('2')
            stdout,stderr=process.communicate(timeout=10);elapsed=time.monotonic()-started
            (owned/'stdout.log').write_bytes(stdout);(owned/'stderr.log').write_bytes(stderr)
            assert process.returncode==0 and 'GA_AUDIO_STREAM_CANCELLED' in (owned/'cancel-result.txt').read_text()
            assert elapsed<=2.5 and not handle_alive(handle),(mode,elapsed)
            assert not (owned/'cancelled.wav').exists() and not list(owned.rglob('*.rf64')) and not list(owned.glob('.genesis-nested-*'))
            assert sha(project)==original
            rows.append(dict(mode=mode,processed_prefix_frames=240000,join_seconds=elapsed,output_absent=True,worker_joined=True))
        finally:
            if process.poll() is None:
                (owned/'stop').write_text('stop')
                try:process.communicate(timeout=5)
                except subprocess.TimeoutExpired:terminate_children(process.pid,worker);process.kill();process.communicate(timeout=5)
            if handle is not None and os.name=='nt':
                import ctypes
                kernel=ctypes.WinDLL('kernel32');kernel.CloseHandle.argtypes=[ctypes.c_void_p];kernel.CloseHandle(handle)
    assert sha(source)==immutable
    return rows

def protocol(root,worker,source,reference,old_worker=None):
    p=Worker(worker);cases=[]
    fx='atempo=2,acompressor=threshold='+str(10**(-24/20))+':ratio=12:attack=80:release=1200'
    def row(crop,count,token=None):
        return f'AUDIOSTREAM {wire(source)} 0 2 0 1 0 0 1 {crop/SR:.17g} {fx} 20 2 {count} '+(token or f'AUDIOCTX2:0:2:96000:48000:{crop}:{count}')
    try:
        path=root/'prime.wav';p.command(f'PLAYWAVE {wire(path)} 5000');p.command(row(0,5000));p.command(f'WAVECLOSE {wire(path)}')
        cursor=5000
        for label,token in [('zero-end','AUDIOCTX2:0:2:96000:0:5000:5000'),
                            ('end-after-virtual','AUDIOCTX2:0:2:96000:96001:5000:5000'),
                            ('unavailable-body','AUDIOCTX2:0:2:96000:48000:48000:5000'),
                            ('count-mismatch','AUDIOCTX2:0:2:96000:48000:5000:4999'),
                            ('stream-tail','AUDIOCTX2:0:2:96000:48000:5000:5000:TAIL'),
                            ('bad-fields','AUDIOCTX2:0:2:96000:48000:5000'),
                            ('overflow','AUDIOCTX2:0:2:96000:48000:18446744073709551615:5000')]:
            out=root/(label+'.wav');p.command(f'PLAYWAVE {wire(out)} 5000');p.command(row(cursor,5000,token),'GA_AUDIO_CONTEXT')
            assert not out.exists(),(label,'refusal published output')
            # Repeating PLAYWAVE keeps the touched graph; malformed context must
            # not remove/reset it or move its original output cursor.
            p.command(f'PLAYWAVE {wire(out)} 5000');p.command(row(cursor,5000));p.command(f'WAVECLOSE {wire(out)}')
            error=int(np.max(np.abs(pcm(out).astype(np.int32)-quantize(reference[cursor:cursor+5000]).astype(np.int32))))
            assert error<=1,(label,'continuation',error)
            cursor+=5000;cases.append(dict(case=label,continuation_pcm_codes=error,no_refusal_publication=True))
        # The one allowed moved endpoint zero has a distinct decoder cursor:
        # it never consumes the first native sample after the processing end.
        for label,token in [('changed-duration','AUDIOCTX2:0:1.9:96000:48000:40000:1000'),
                            ('changed-processing-end','AUDIOCTX2:0:2:96000:47000:41000:1000')]:
            out=root/(label+'.wav');p.command(f'PLAYWAVE {wire(out)} 1000')
            p.command(row(cursor,1000,token),'GA_AUDIO_CONTEXT')
            assert not out.exists()
            p.command(f'PLAYWAVE {wire(out)} 1000');p.command(row(cursor,1000));p.command(f'WAVECLOSE {wire(out)}')
            error=int(np.max(np.abs(pcm(out).astype(np.int32)-quantize(reference[cursor:cursor+1000]).astype(np.int32))))
            assert error<=1,(label,error)
            cases.append(dict(case=label,continuation_pcm_codes=error,no_refusal_publication=True));cursor+=1000
        out=root/'endpoint.wav'
        p.command(f'PLAYWAVE {wire(out)} {48000-cursor}');p.command(row(cursor,48000-cursor));p.command(f'WAVECLOSE {wire(out)}')
        zero=root/'one-zero.wav';p.command(f'PLAYWAVE {wire(zero)} 1');p.command(row(48000,1));p.command(f'WAVECLOSE {wire(zero)}')
        assert np.array_equal(pcm(zero),np.zeros((1,2),dtype=np.int16))
        cases.append(dict(case='exact-processing-end-one-zero',passed=True))
    finally:p.close()
    if old_worker:
        old=Worker(old_worker)
        try:
            out=root/'old-worker.wav';old.command(f'PLAYWAVE {wire(out)} 5000')
            old.command(row(0,5000),'GA_AUDIO_FADE_KEYS')
            assert not out.exists()
        finally:old.close()
        cases.append(dict(case='old-worker-coded-refusal',passed=True))
    return cases

def check(client,worker,root,report,old_worker=None):
    ffmpeg=tool(worker,'ffmpeg')
    report.update(client_sha256=sha(client),worker_sha256=sha(worker),ffmpeg_sha256=sha(ffmpeg),
                  fixture_sha256=sha(Path(__file__).with_suffix('.ai')),checker_sha256=sha(Path(__file__)))
    basefx='acompressor=threshold='+str(10**(-24/20))+':ratio=12:attack=80:release=1200'
    specs=[('compressor',48000,30,'compressor',dict(threshold=-24,ratio=12,attack=80,release=1200),basefx),
           ('gate',48000,30,'gate',dict(threshold=-18,hold=1200),'agate=threshold='+str(10**(-18/20))+':release=1200'),
           ('limiter',48000,30,'limiter',dict(ceiling=-12),'alimiter=limit='+str(10**(-12/20))+':level=disabled'),
           ('eq441',44100,30,'eq_3band',dict(low=4.5),'equalizer=f=100:t=q:w=1:g=4.5'),
           ('normalize',48000,30,'normalize',dict(target=-14),'loudnorm=I=-14'),
           ('fractional',48000,47,'compressor',dict(threshold=-24,ratio=12,attack=80,release=1200),basefx),
           ('aac441',44100,30,'compressor',dict(threshold=-24,ratio=12,attack=80,release=1200),basefx)]
    references={};sources={};originals={};extent_expected={};masters={}
    for name,native_rate,fps,kind,params,fx in specs:
        duration_us=math.floor(60/fps*1000000+.5)
        n=math.floor(90/fps*native_rate+.5)
        t=np.arange(n)/native_rate
        amp=np.where(t<.35,.12,np.where(t<.8,.7,np.where(t<1.1,.04,.5)))
        authored=np.rint(np.column_stack((amp*np.sin(2*np.pi*173*t),-.79*amp*np.cos(2*np.pi*317*t)))*32767).astype('<i2')
        source=root/(name+' 原音 %20.wav')
        with wave.open(str(source),'wb') as w:w.setparams((2,2,native_rate,0,'NONE','PCM'));w.writeframes(authored.tobytes())
        if name=='aac441':
            compressed=root/'native44100.m4a';run([ffmpeg,'-nostdin','-v','error','-i',source,'-c:a','aac','-b:a','192k',compressed]);source=compressed
        sources[name]=source
        doc=document([source],(0,));doc['sequences'][0]['fps']=fps
        doc['sources'][0].update(frames=60,fps=fps,audio_rate=native_rate)
        doc['sources'].append(dict(doc['sources'][0],id=8,path='',has_audio=False,frames=120))
        doc['clips'][0].update(length=60,streams=2)
        doc['clips'].append(dict(doc['clips'][0],id=21,source=8,length=120))
        doc['next_id']=100;effect(doc,20,kind,params,50)
        p=root/(name+'.air');p.write_text(json.dumps(doc),encoding='utf8');originals[p]=sha(p)
        for rate in (2,1,3):
            input_us=math.floor(60/fps*1000000+.5)
            native=math.floor(input_us*native_rate/1000000+.5)
            start=math.floor(native_rate/fps+.5) if rate==3 else 0
            stages=f'atrim=start_sample={start}:end_sample={start+native},asetpts=N/SR/TB,aresample=48000,aformat=sample_fmts=flt:sample_rates=48000:channel_layouts=stereo,'
            if rate!=1:stages+=f'atempo={2 if rate==3 else rate},'
            stages+=fx+',aformat=sample_fmts=flt:sample_rates=48000:channel_layouts=stereo'
            raw=run([ffmpeg,'-nostdin','-v','error','-i',source,'-af',stages,'-f','f32le','pipe:1'])
            references[name,rate]=np.frombuffer(raw,dtype='<f4').reshape(-1,2).copy()
        extent_expected[name]=(duration_us,sample(30,fps))
    (root/'cases.tsv').write_text('\n'.join(n for n,*_ in specs)+'\n')
    job=subprocess.run([str(client),str(worker),str(root)],capture_output=True,timeout=240,creationflags=FLAGS)
    (root/'client.stdout.log').write_bytes(job.stdout);(root/'client.stderr.log').write_bytes(job.stderr)
    assert job.returncode==0,(job.returncode,job.stdout,job.stderr[-3000:])
    rows=[];compared=0
    for name,native_rate,fps,*_ in specs:
        for variant in ('retimed','split','head','tail','repeated','moved','rate1','slipped'):
            prefix=root/f'{name}-{variant}';doc=json.loads(prefix.with_suffix('.air').read_text())
            assert doc['revision']==4
            target=np.zeros((sample(120,fps),2),dtype=np.float32)
            full=references[name,1 if variant=='rate1' else 3 if variant=='slipped' else 2]
            end=sample(60 if variant=='rate1' else 30,fps)
            for c in doc['clips']:
                if c['id']==21:continue
                ctx=c['audio_context'];extent=ctx['extent'];crop=sample(ctx['offset'],fps)
                assert ctx['length']==60 and ctx['output_frames']==sample(60,fps) and ctx['origin']==0
                assert extent['input_duration_us']==extent_expected[name][0]
                assert extent['processing_frames']==end
                at=sample(c['start'],fps);count=sample(c['start']+c['length'],fps)-at
                body=fitted(full[:end],end)[crop:crop+count];body=fitted(body,count)
                target[at:at+count]+=body
                peak_error=float(np.max(np.abs(np.loadtxt(root/f'{name}-{variant}-peaks-{c["id"]}.txt')-peaks(body,600))))
                assert peak_error<=2e-6,(name,variant,'peaks',peak_error)
                # Normalize uses the existing NEST authored-body cap, never a
                # direct whole-AUDIO TAIL. The independent reference still
                # processes the full selected input before taking this body.
                if name!='normalize' and ctx['offset']+c['length']==extent['processing_length'] and variant!='rate1':
                    tail=full[end:];first=at+count;last=min(len(target),first+len(tail))
                    target[first:last]+=tail[:last-first]
            got=pcm(prefix.with_suffix('.wav'));extra=len(got)-len(target)
            assert extra in (0,1) and (extra==0 or not got[-1].any()),(name,variant,'WAVE ceil endpoint',extra)
            whole=fitted(target,len(got));wanted=quantize(whole)
            error=int(np.max(np.abs(got.astype(np.int32)-wanted.astype(np.int32))))
            assert error<=1,(name,variant,'whole',error)
            pulls=np.concatenate([pcm(Path(p)) for p in (root/f'{name}-{variant}-pulls.txt').read_text().splitlines()])
            # Existing device pulls are authored-body bounded; whole/export alone
            # has approved native EOF tails. Phase1 does not extend device tails.
            stream_target=target.copy()
            for c in doc['clips']:
                if c['id']!=21 and c['audio_context']['offset']+c['length']==c['audio_context']['extent']['processing_length']:
                    stream_target[sample(c['start']+c['length'],fps):]=0
            pe=int(np.max(np.abs(pulls.astype(np.int32)-quantize(stream_target).astype(np.int32))))
            assert pulls.shape==stream_target.shape and pe<=1,(name,variant,'retained',pe)
            fresh=pcm(root/f'{name}-{variant}-fresh.wav');from_sample=sample(7,fps)
            fw=fitted(target[from_sample:],len(fresh));fe=int(np.max(np.abs(fresh.astype(np.int32)-quantize(fw).astype(np.int32))))
            assert fe<=1,(name,variant,'fresh',fe)
            compared+=(len(got)+len(pulls)+len(fresh))*2
            rows.append(dict(case=name,edit=variant,whole_pcm_codes=error,retained_pcm_codes=pe,fresh_pcm_codes=fe,
                             body_peaks_threshold=2e-6,wave_endpoint_zeros=extra,
                             virtual_frames=sample(60,fps),processing_frames=end))
            if variant=='retimed':masters[name]=(target.copy(),fps,sample(30,fps) if name=="normalize" else len(full))
    run([client,worker,root,'--export'])
    master_rows=[]
    for name,(wanted,fps,independent_end) in masters.items():
        movie=root/f'{name}-master.mkv'
        raw=run([ffmpeg,'-nostdin','-v','error','-i',movie,'-map','0:a:0','-f','f32le','pipe:1'])
        got=np.frombuffer(raw,dtype='<f4').reshape(-1,2)
        assert len(got)==independent_end,(name,"accepted native EOF frame count",len(got),independent_end)
        expected=np.clip(wanted[:independent_end],-1,1)
        error=float(np.max(np.abs(got-expected)))
        assert error<=2e-6,(name,'lossless PCM24',error)
        master_rows.append(dict(case=name,samples=len(got),independent_eof_samples=independent_end,pcm24_error=error,threshold=2e-6))
    valid=json.loads((root/'compressor-retimed.air').read_text());bad=[]
    for label in ('revision3','zero-end','mismatched-frames','unavailable-input','body-after-end','reverse','negative-duration','over-budget'):
        doc=copy.deepcopy(valid);clip=doc['clips'][0];extent=clip['audio_context']['extent']
        if label=='revision3':doc['revision']=3
        elif label=='zero-end':extent['processing_length']=0
        elif label=='mismatched-frames':extent['processing_frames']+=1
        elif label=='unavailable-input':doc['sources'][0]['frames']=59
        elif label=='body-after-end':clip['length']=31
        elif label=='reverse':clip['reverse']=clip['audio_context']['reverse']=True
        elif label=='negative-duration':extent['input_duration_us']=-1
        elif label=='over-budget':extent['input_duration_us']=21600000001
        file=root/'reject.air';file.write_text(json.dumps(doc),encoding='utf8');before=sha(file)
        run([client,worker,root,'--reject']);assert sha(file)==before
        bad.append(dict(case=label,decode_refused=True,authored_bytes_unchanged=True))
    report.update(cases=rows,compared_pcm_values=compared,protocol=protocol(root,worker,sources['compressor'],references['compressor',2],old_worker),
                  cancellation=cancellation(root,client,worker),
                  lossless_exports=master_rows,codec_refusals=bad,
                  filter_lifecycle=dict(dsp_inputs=len(specs),guarded_add_enable_held_enable=63,
                      supported_eq_add_disable_enable=21,refusals_preserve_authored_bytes=True),
                  authored_inputs_immutable=all(sha(p)==h for p,h in originals.items()))
    assert report['authored_inputs_immutable']
    assert not list(root.rglob('.genesis-nested-*'))
    report['owned_caches_cleaned']=True
    report['passed']=True

def main():
    p=argparse.ArgumentParser();p.add_argument('--client',required=True,type=Path);p.add_argument('--worker',required=True,type=Path)
    p.add_argument('--old-worker',type=Path);p.add_argument('--report',required=True,type=Path)
    a=p.parse_args();assert not a.report.exists(),'Preserve historical receipt'
    report=dict(schema='genesis.audio-context.forward-retime.v1',passed=False,thresholds=dict(pcm_codes=1,raw_peaks=2e-6),
                limitations=['Direct integral forward extents only; no streamed Delay/Reverb tails or nested endpoint extension.',
                             'Normalize retains the existing NEST authored-body cap; native post-body tails are excluded.'])
    try:
        folder=Path(tempfile.mkdtemp(prefix='genesis-context-retime-',dir=a.report.parent))
        report['evidence_directory']=str(folder)
        check(a.client.resolve(),a.worker.resolve(),folder,report,a.old_worker.resolve() if a.old_worker else None)
    except BaseException as e:report['error']=repr(e);raise
    finally:
        with a.report.open('x',encoding='utf8') as f:json.dump(report,f,indent=2)
    print(f'Forward retime: {len(report["cases"])} edit/DSP cases, {report["compared_pcm_values"]} PCM values, {len(report["protocol"])} protocol checks PASS')
if __name__=='__main__':main()
