"""Independent nested child edits preserve full parent DSP history and exact crops.

Four graph families by four real edit states protect whole PCM, uneven retained
pulls, fresh seeks and600 processed peaks. References come only from authored
PCM and shared MM-AIR FFmpeg; Genesis output is never an expected signal.
"""
from pathlib import Path
import argparse, json, hashlib, subprocess, copy, wave, os, tempfile
import numpy as np
from audio_mix_project import document
from audio_nested import effect
from media_runtime import tool
SR=48000
FLAGS=0x08000000 if os.name=='nt' else 0
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def run(args,**kw):
    p=subprocess.run(list(map(str,args)),capture_output=True,timeout=120,creationflags=FLAGS,**kw)
    assert p.returncode==0,(args,p.returncode,p.stdout[-1000:],p.stderr[-2000:])
    return p.stdout
def pcm(p):
    with wave.open(str(p),'rb') as f:
        assert (f.getnchannels(),f.getsampwidth(),f.getframerate())==(2,2,SR)
        return np.frombuffer(f.readframes(f.getnframes()),dtype='<i2').reshape(-1,2).copy()
def quantize(v):return (np.sign(v)*np.floor(np.abs(np.clip(v,-1,1))*32767+.5)).astype(np.int16)
def peaks(v,n):return np.array([np.max(np.abs(v[k*len(v)//n:(k+1)*len(v)//n]),initial=0) for k in range(n)])
def check(client,worker,out,report_path):
    CLIENT=client.resolve()
    WORKER=worker.resolve()
    OUT=out
    FFMPEG=tool(WORKER,'ffmpeg')
    report=dict(schema='genesis.nested-descendant-full-span-pcm.v1',passed=False,
                thresholds=dict(pcm16_codes=1,raw_peak=2e-6),cases=[],
                references='Authored PCM summed in float32; removed child suffix zeros BEFORE parent FFmpeg DSP; exact postDSP crop',
                worker_sha256=sha(WORKER),client_sha256=sha(CLIENT),ffmpeg_sha256=sha(FFMPEG),
                client_fixture_sha256=sha(Path(__file__).with_suffix('.ai')),
                checker_sha256=sha(Path(__file__)))
    try:
        t=np.arange(8*SR)/SR
        # A quiet middle and loud removed suffix make original-span loudness and
        # causal release memory independently observable, with distinct channels.
        amp=np.where(t<1,.7,np.where(t<3,.05,.85))
        authored=np.column_stack((amp*np.sin(2*np.pi*173*t),amp*.81*np.cos(2*np.pi*317*t)))
        encoded=np.rint(authored*32767).astype('<i2')
        source=OUT/'authored-stereo.wav'
        with wave.open(str(source),'wb') as f:
            f.setparams((2,2,SR,0,'NONE','not compressed'));f.writeframes(encoded.tobytes())
        report['source_sha256']=sha(source)
        specs=[('compressor',1,False,'compressor',dict(threshold=-24,ratio=12,attack=80,release=1200),
                'acompressor=threshold='+str(10**(-24/20))+':ratio=12:attack=80:release=1200'),
               ('normalize',1,False,'normalize',dict(target=-14),'loudnorm=I=-14'),
               ('reverse',1,True,'compressor',dict(threshold=-24,ratio=12,attack=80,release=1200),
                'areverse,acompressor=threshold='+str(10**(-24/20))+':ratio=12:attack=80:release=1200'),
               ('rate2',2,False,'compressor',dict(threshold=-24,ratio=12,attack=80,release=1200),
                'atempo=2,acompressor=threshold='+str(10**(-24/20))+':ratio=12:attack=80:release=1200')]
        refs={}
        authored_projects={}
        for name,rate,reverse,kind,params,chain in specs:
            doc=document([source],(0,));doc['sources'][0].update(frames=240)
            doc['sequences'].append(dict(id=10,name='Mutable child sum',fps=30,width=16,height=16))
            leaf=copy.deepcopy(doc['clips'][0]);leaf.update(id=30,owner=10,track=11,length=120*rate,gain=.75,streams=2)
            second=copy.deepcopy(leaf);second.update(id=31,track=12,gain=.5)
            tr=copy.deepcopy(doc['tracks'][0]);tr.update(id=11,owner=10)
            tr2=copy.deepcopy(tr);tr2.update(id=12,order=1)
            doc['tracks'].extend([tr,tr2]);doc['clips'].extend([leaf,second])
            doc['clips'][0].update(source=0,nested=10,length=120,speed=rate,reverse=reverse,streams=2)
            doc['next_id']=100
            effect(doc,20,kind,params,50)
            (OUT/(name+'.air')).write_text(json.dumps(doc),encoding='utf8')
            authored_projects[name]=sha(OUT/(name+'.air'))
            raw=(encoded[:120*rate*1600].astype(np.float32)/32768)
            summed=(raw*np.float32(.75)+raw*np.float32(.5)).astype('<f4')
            for phase in ('before','after'):
                signals=summed.copy()
                if phase=='after':signals[90*1600:]=0
                # Explicit same 48k stereo endpoint after loudnorm's 192k internal
                # graph. No Genesis output or meter is used to calculate a reference.
                pipeline=chain+',aformat=sample_fmts=flt:sample_rates=48000:channel_layouts=stereo'
                data=run([FFMPEG,'-nostdin','-v','error','-f','f32le','-ar',SR,'-ac',2,'-i','pipe:0',
                         '-af',pipeline,'-f','f32le','pipe:1'],input=signals.tobytes())
                (OUT/f'{name}-{phase}-independent.f32').write_bytes(data)
                v=np.frombuffer(data,dtype='<f4').reshape(-1,2).copy()
                v=v[:192000];v=np.pad(v,((0,max(0,192000-len(v))),(0,0)))
                refs[name,phase]=v
        (OUT/'cases.tsv').write_text('\n'.join(n for n,*_ in specs)+'\n')
        job=subprocess.run([str(CLIENT),str(WORKER),str(OUT)],capture_output=True,timeout=180,creationflags=FLAGS)
        (OUT/'client.stdout.log').write_bytes(job.stdout);(OUT/'client.stderr.log').write_bytes(job.stderr)
        assert job.returncode==0,(job.returncode,job.stdout,job.stderr[-2000:])
        report['client_exit']=job.returncode
        compared=0
        for name,*_ in specs:
            for phase in ('before','after','head','tail'):
                original=refs[name,'before' if phase=='before' else 'after']
                end=72000 if phase=='tail' else 96000
                target=original[:end].copy()
                envelope=target
                if phase in ('head','tail'):target[:48000]=0;envelope=original[48000:end]
                prefix=OUT/f'{name}-{phase}'
                got=pcm(prefix.with_suffix('.wav'));want=quantize(target)
                assert got.shape==want.shape,(name,phase,got.shape,want.shape)
                err=int(np.max(np.abs(got.astype(np.int32)-want.astype(np.int32))))
                assert err<=1,(name,phase,'whole',err)
                pulls=np.concatenate([pcm(Path(p)) for p in (OUT/f'{name}-{phase}-pulls.txt').read_text().splitlines()])
                pe=int(np.max(np.abs(pulls.astype(np.int32)-want.astype(np.int32))))
                assert pulls.shape==want.shape and pe<=1,(name,phase,'retained',pe)
                fresh=pcm(OUT/f'{name}-{phase}-fresh.wav')
                fe=int(np.max(np.abs(fresh.astype(np.int32)-want[end-24000:].astype(np.int32))))
                assert fresh.shape==want[end-24000:].shape and fe<=1,(name,phase,'fresh',fe)
                got_peaks=np.loadtxt(OUT/f'{name}-{phase}-peaks.txt')
                peak_error=float(np.max(np.abs(got_peaks-peaks(envelope,600))))
                assert len(got_peaks)==600 and peak_error<=2e-6,(name,phase,'peaks',peak_error)
                graph=json.loads(prefix.with_suffix('.air').read_text())
                parent=next(c for c in graph['clips'] if c['id']==20)
                assert parent['audio_context']['length']==120 and parent['audio_context']['output_frames']==192000
                compared+=(len(got)+len(pulls)+len(fresh))*2
                report['cases'].append(dict(effect=name,phase=phase,whole_pcm_error=err,retained_pcm_error=pe,
                                            fresh_pcm_error=fe,raw_peak_error=peak_error,
                                            original_parent_frames=120,retained_body_frames=parent['length'],
                                            preserved_original_output_samples=192000))
        # Normalize is noncausal: removal of loud child suffix must genuinely alter
        # the retained body, so padding-after-DSP / stale-cache bugs cannot pass.
        change=float(np.max(np.abs(refs['normalize','before'][:96000]-refs['normalize','after'][:96000])))
        assert change>2e-6,change
        report['normalize_independent_body_change']=change
        report['compared_pcm_values']=compared
        assert len(report['cases'])==16 and compared==6528000
        assert all(sha(OUT/(name+'.air'))==value for name,value in authored_projects.items())
        report['authored_project_sha256']=authored_projects
        assert sha(source)==report['source_sha256']
        assert sha(WORKER)==report['worker_sha256'] and sha(CLIENT)==report['client_sha256']
        assert not list(OUT.rglob('*.rf64')) and not list(OUT.rglob('.genesis-nested-*'))
        report.update(passed=True,owned_cache_removed=True,originals_unchanged=True)
    finally:
        if report_path:
            report_path.write_text(json.dumps(report,indent=2)+'\n',encoding='utf8')
    print(json.dumps(report,indent=2))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--client',type=Path,required=True)
    parser.add_argument('--worker',type=Path,required=True)
    parser.add_argument('--report',type=Path)
    args=parser.parse_args()
    if args.report:
        args.report.parent.mkdir(parents=True,exist_ok=True)
        assert not args.report.exists(),'Refuse to overwrite a historical receipt'
    with tempfile.TemporaryDirectory(prefix='genesis-nested-context-edit-') as temporary:
        check(args.client,args.worker,Path(temporary),args.report)


if __name__=='__main__':
    main()
