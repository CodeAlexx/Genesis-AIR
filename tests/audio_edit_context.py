"""Independent full-DSP reference survives real SDK Split/trim/Move and seeks.

Original authored PCM is processed once independently, then exact retained
48k intervals are selected. Genesis output is never an expected signal. Files
and decoder graphs remain floating point until final PCM quantization.
"""
import argparse
import copy
import hashlib
import json
import math
import os
import shutil
from pathlib import Path
import subprocess
import tempfile
import struct
import time
import wave
import numpy as np
from audio_mix_project import document
from audio_nested import effect
from media_runtime import tool
from nested_waveforms import Worker
from audio_stream import wire
from audio_nested_cancel import children,image,worker_handle,handle_alive,terminate_children

SR=48000
FLAGS=0x08000000 if os.name=="nt" else 0
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def sample(frame,fps):return math.floor(frame*SR/fps+.5)
def run(args,**kwargs):
    result=subprocess.run(list(map(str,args)),capture_output=True,timeout=120,creationflags=FLAGS,**kwargs)
    assert result.returncode==0,(args,result.returncode,result.stdout[-2000:],result.stderr[-2000:])
    return result.stdout
def pcm(path):
    with wave.open(str(path),'rb') as f:
        assert (f.getnchannels(),f.getsampwidth(),f.getframerate())==(2,2,SR)
        return np.frombuffer(f.readframes(f.getnframes()),dtype='<i2').reshape(-1,2).copy()
def quantize(values):return (np.sign(values)*np.floor(np.abs(np.clip(values,-1,1))*32767+.5)).astype(np.int16)
def peaks(values,count):
    n=len(values)
    return np.array([np.max(np.abs(values[k*n//count:(k+1)*n//count]),initial=0.) for k in range(count)])

def stream_contract(root,worker,source,expected,ffmpeg):
    """Refused metadata must leave an already-primed native graph untouched."""
    chain='acompressor=threshold='+str(10**(-24/20))+':ratio=12:attack=80:release=1200'
    def line(crop,count,token=None,remaining='4',path=source,destination='0'):
        token=token or f'AUDIOCTX:0:4:192000:{crop}:{count}'
        return f'AUDIOSTREAM {wire(path)} {crop/SR} {count/SR} {destination} 1 0 0 4 {crop/SR} {chain} 99 {remaining} {count} {token}'
    rows=[];p=Worker(worker);cursor=0
    try:
        for name,token,remaining,path,dst in [('prime',None,'4',source,'0'),
          ('nan','AUDIOCTX:nan:4:192000:4800:4800','4',source,'0'),
          ('count','AUDIOCTX:0:4:192000:9600:4799','4',source,'0'),
          ('overflow','AUDIOCTX:0:4:192000:192000:4800','4',source,'0'),
          ('duplicate','AUDIOCTX:0:4:192000:19200:4800 AUDIOCTX:0:4:192000:19200:4800','4',source,'0'),
          ('identity','AUDIOCTX:0.1:4:192000:24000:4800','4',source,'0'),
          ('duration',None,'nan',source,'0'),('missing-path',None,'4',root/'missing.wav','0'),
          ('destination',None,'4',source,'1e30'),
          ('stream-tail','AUDIOCTX:0:4:192000:43200:4800:TAIL','4',source,'0')]:
            out=root/('protocol-'+name+'.wav');p.command(f'PLAYWAVE {wire(out)} 4800')
            if name!='prime':p.command(line(cursor,4800,token,remaining,path,dst),'GA_AUDIO_CONTEXT')
            p.command(line(cursor,4800));p.command('WAVECLOSE '+wire(out))
            actual=pcm(out);wanted=quantize(expected[cursor:cursor+4800])
            error=int(np.max(np.abs(actual.astype(np.int32)-wanted.astype(np.int32))))
            assert actual.shape==(4800,2) and error<=1,(name,error)
            if name!='prime':rows.append(dict(case=name,retained_graph_preserved=True,maximum_pcm_error=error))
            cursor+=4800
        out=root/'protocol-huge-block-destination.wav';p.command(f'PLAYWAVE {wire(out)} 4800')
        p.command(f'AUDIO {wire(source)} 0 6 1e30 1 0 0 8 0 {chain} AUDIOCTX:0:8:384000:0:240001','GA_AUDIO_CONTEXT')
        p.command(line(cursor,4800));p.command('WAVECLOSE '+wire(out))
        assert np.array_equal(pcm(out),quantize(expected[cursor:cursor+4800]))
        rows.append(dict(case='multi-block-destination',retained_graph_preserved=True,maximum_pcm_error=0))
        cursor+=4800
        for token in ('AUDIOCTX:0:4:192000:0:4800:TAIL','AUDIOCTX:0:4:192000:0:192000:wrong'):
            out=root/f'protocol-tail-invalid-{cursor}.wav';p.command(f'PLAYWAVE {wire(out)} 4800')
            p.command(f'AUDIO {wire(source)} 0 4 0 1 0 0 4 0 {chain} {token}','GA_AUDIO_CONTEXT')
            p.command(line(cursor,4800));p.command('WAVECLOSE '+wire(out))
            assert np.array_equal(pcm(out),quantize(expected[cursor:cursor+4800]))
            cursor+=4800;rows.append(dict(case='invalid-whole-tail',retained_graph_preserved=True,maximum_pcm_error=0))
        out=root/'protocol-tail-budget.wav';p.command(f'PLAYWAVE {wire(out)} 4800')
        p.command(f'AUDIO {wire(source)} 0 4 0 1 0 0 4 0 aecho=0.8:0.9:6000:0.4 AUDIOCTX:0:4:192000:0:192000:TAIL','GA_AUDIO_CONTEXT_TAIL')
        assert not out.exists(),'Failed tail budget published a WAV'
        out=root/'protocol-tail-budget-recovery.wav';p.command(f'PLAYWAVE {wire(out)} 4800')
        p.command(line(cursor,4800));p.command('WAVECLOSE '+wire(out))
        assert np.array_equal(pcm(out),quantize(expected[cursor:cursor+4800]))
        rows.append(dict(case='actual-eof-tail-budget',coded_failure_without_partial_wav=True,retained_graph_preserved=True))
    finally:p.close()
    p=Worker(worker)
    try:
        for crop,count in ((191999,1),(192000,1)):
            out=root/f'protocol-endpoint-{crop}.wav';p.command(f'PLAYWAVE {wire(out)} {count}')
            p.command(line(crop,count));p.command('WAVECLOSE '+wire(out))
            wanted=quantize(expected[-1:]) if crop==191999 else np.zeros((1,2),dtype=np.int16)
            assert np.array_equal(pcm(out),wanted),('exact endpoint',crop)
    finally:p.close()
    # Actual complete DSP bodies retain raw float headroom through fine peaks.
    envroot=root/'protocol-peaks';envroot.mkdir();p=Worker(worker)
    try:
        for count in (600,25567,65536):
            p.command('NESTBEGIN '+wire(envroot))
            p.command(f'NESTLEAF bus.leaf bus 96000 192000 {wire(source)} 2 2 1 0 0 2 {chain} AUDIOCTX:0:4:192000:96000')
            p.command('NESTBUS bus - 96000 192000 96000 192000 1 0 0 2 -')
            out=envroot/f'env{count}.f32';p.command(f'NESTPEAK bus {count} {wire(out)}')
            got=np.frombuffer(out.read_bytes(),dtype='<f4');wanted=peaks(expected[96000:192000],count)
            error=float(np.max(np.abs(got-wanted)));assert len(got)==count and error<=2e-6,(count,error)
            rows.append(dict(case='fine-context-peaks',buckets=count,maximum_peak_error=error))
    finally:p.close()
    assert not list(envroot.glob('*.rf64'))
    tails=[]
    for name,fx in [('compressor',chain),('gate','agate=threshold='+str(10**(-18/20))+':release=1200'),
       ('limiter','alimiter=limit='+str(10**(-12/20))+':level=disabled'),
       ('eq','equalizer=f=100:t=q:w=1:g=4.5,equalizer=f=1000:t=q:w=1:g=-2,equalizer=f=8000:t=q:w=1:g=1.5'),
       ('normalize','loudnorm=I=-14'),('tempo15','atempo=1.5,'+chain),('tempo05','atempo=0.5,'+chain)]:
        speed=1.5 if name=='tempo15' else .5 if name=='tempo05' else 1;duration=4*speed;p=Worker(worker)
        try:
            old=root/(name+'-legacy-tail.wav');new=root/(name+'-context-tail.wav')
            for out,token in ((old,''),(new,f' AUDIOCTX:0:{duration}:192000:0:192000:TAIL')):
                p.command(f'WAVE {wire(out)} 8');p.command(f'AUDIO {wire(source)} 0 {duration} 0 1 0 0 4 0 {fx}{token}');p.command('WAVECLOSE '+wire(out))
            a,b=pcm(old),pcm(new);error=int(np.max(np.abs(a.astype(np.int32)-b.astype(np.int32))))
            stages=f'atrim=start_sample=0:end_sample={int(duration*SR)},asetpts=N/SR/TB,aresample=48000,aformat=sample_fmts=flt:sample_rates=48000:channel_layouts=stereo,{fx},aformat=sample_fmts=flt:sample_rates=48000:channel_layouts=stereo'
            data=run([ffmpeg,'-nostdin','-v','error','-i',source,'-af',stages,'-f','f32le','pipe:1'])
            reference=np.frombuffer(data,dtype='<f4').reshape(-1,2)
            wanted=quantize(np.pad(reference[:384000],((0,max(0,384000-len(reference))),(0,0))))
            independent=int(np.max(np.abs(b.astype(np.int32)-wanted.astype(np.int32))))
            tail=int(np.count_nonzero(a[192000:]));assert error<=1 and independent<=1,(name,error,tail,independent)
            if name not in ('tempo15','tempo05'):assert tail==0,(name,tail)
            tails.append(dict(effect=name,maximum_pcm_error=error,legacy_after_body_nonzero_values=tail))
            if name=='tempo15':
                for delta in (-1,1):
                    count=192000+delta;out=root/f'tail-endpoint-{delta}.wav'
                    p.command(f'WAVE {wire(out)} 8')
                    p.command(f'AUDIO {wire(source)} 0 {duration} 0 1 0 0 4 0 {fx} AUDIOCTX:0:{duration}:192000:0:{count}:TAIL')
                    p.command('WAVECLOSE '+wire(out))
                    body=reference[:192000]
                    body=body[:-1] if delta<0 else np.concatenate([body,np.zeros((1,2),dtype=np.float32)])
                    wanted=np.concatenate([body,reference[192000:]])
                    wanted=quantize(np.pad(wanted[:384000],((0,max(0,384000-len(wanted))),(0,0))))
                    error=int(np.max(np.abs(pcm(out).astype(np.int32)-wanted.astype(np.int32))))
                    assert error<=1,(delta,'body endpoint then native tail',error)
                    rows.append(dict(case='tail-endpoint-placement',endpoint_delta=delta,maximum_pcm_error=error))
        finally:p.close()
    return dict(refusal_and_peak_cases=rows,exact_last_sample_then_one_zero_continuation=True,post_body_tail_controls=tails)

def edited_tails(root,client,worker,ffmpeg,docs,source):
    owned=root/'edited-tails';owned.mkdir();names=('tempo15','tempo05')
    for name in names:
        doc=copy.deepcopy(docs[name]);silent=copy.deepcopy(doc['clips'][0])
        silent.update(id=21,start=120,length=120,gain=0,speed=1,reverse=False)
        doc['clips'].append(silent);(owned/(name+'.air')).write_text(json.dumps(doc),encoding='utf8')
    (owned/'cases.tsv').write_text('\n'.join(names)+'\n',encoding='utf8');run([client,worker,owned])
    rows=[];chain='acompressor=threshold='+str(10**(-24/20))+':ratio=12:attack=80:release=1200'
    for name in names:
        speed=docs[name]['clips'][0]['speed'];duration=4*speed
        stages=f'atrim=start_sample=0:end_sample={int(duration*SR)},asetpts=N/SR/TB,aresample=48000,aformat=sample_fmts=flt:sample_rates=48000:channel_layouts=stereo,atempo={speed},{chain}'
        data=run([ffmpeg,'-nostdin','-v','error','-i',source,'-af',stages,'-f','f32le','pipe:1'])
        raw=np.frombuffer(data,dtype='<f4').reshape(-1,2).copy();native_output_frames=len(raw)
        # Native atempo can finish before the authored four-second endpoint;
        # both original whole allocation and retained reads fill that gap zero.
        raw=np.pad(raw,((0,max(0,192000-len(raw))),(0,0)))
        tail_nonzero=int(np.count_nonzero(quantize(raw[192000:])))
        for variant in ('original','split','head','tail','repeated','moved'):
            target=raw.copy()
            if variant=='head':target[:96000]=0
            elif variant=='tail':target=target[:96000] # retained original prefix; removed endpoint has no original tail
            elif variant=='repeated':target[96000:118400]=0
            elif variant=='moved':target=np.concatenate([np.zeros((102400,2),dtype=np.float32),raw[99200:]])
            target=np.pad(target[:384000],((0,max(0,384000-len(target))),(0,0)))
            actual=pcm(owned/(name+'-'+variant+'.wav'));wanted=quantize(target)
            error=int(np.max(np.abs(actual.astype(np.int32)-wanted.astype(np.int32))));assert actual.shape==wanted.shape and error<=1,(name,variant,'full tail',error)
            rows.append(dict(effect=name,operation=variant,maximum_pcm_error=error,original_after_body_nonzero_values=tail_nonzero,
                             original_native_output_frames=native_output_frames,authored_output_frames=192000,
                             policy='Tail trim retains original prefix and removes original-end tail; other final survivors retain native tail'))
    assert not list(owned.rglob('*.rf64')) and not list(owned.rglob('.genesis-nested-*'))
    return dict(cases=rows,independent_full_original_eof=True,pcm_threshold_codes=1)

def cancel_prefix(root,client,worker,template):
    """Cancel the real original graph after a witnessed 5s discarded prefix."""
    source=root/'30-minute-prefix.wav';size=SR*1800*4
    with source.open('wb') as f:
        f.write(struct.pack('<4sI4s4sIHHIIHH4sI',b'RIFF',size+36,b'WAVE',b'fmt ',16,1,2,SR,SR*4,4,16,b'data',size))
        f.seek(44+size-1);f.write(b'\0')
    doc=copy.deepcopy(template);doc['sources'][0].update(path=str(source),frames=54000,fps=30,audio_rate=SR)
    doc['clips'][0].update(length=54000);doc['sequences'][0]['fps']=30
    original=sha(source);results=[]
    for mode in ('superseded','stop'):
        owned=root/('prefix-'+mode);owned.mkdir();project=owned/'cancel.air';project.write_text(json.dumps(doc),encoding='utf8')
        before=sha(project);marker=owned/'request.id';marker.write_text('1',encoding='utf8');witness=owned/'prefix.active'
        process=subprocess.Popen([str(client),str(worker),str(owned),'--cancel','36000'],stdout=subprocess.PIPE,stderr=subprocess.PIPE,
                                 creationflags=FLAGS,env=dict(os.environ,GENESIS_AUDIO_CONTEXT_TRACE=str(witness)))
        handle=None
        try:
            deadline=time.monotonic()+20
            while True:
                assert process.poll() is None,(mode,'Completed before real prefix witness')
                if witness.is_file() and witness.read_text(encoding='utf8')=='processed_prefix_frames=240000\n':break
                assert time.monotonic()<deadline,(mode,'Prefix witness deadline');time.sleep(.002)
            pids=[pid for pid in children(process.pid) if image(pid)==worker];assert len(pids)==1,(mode,pids)
            handle=worker_handle(pids[0]);started=time.monotonic()
            if mode=='stop':(owned/'stop').write_text('stop',encoding='utf8')
            else:marker.write_text('2',encoding='utf8')
            stdout,stderr=process.communicate(timeout=10);elapsed=time.monotonic()-started
            error=(owned/'cancel-result.txt').read_text(encoding='utf8')
            assert process.returncode==0 and 'GA_AUDIO_STREAM_CANCELLED' in error,(mode,error,stdout,stderr)
            assert elapsed<=2.5 and not handle_alive(handle),(mode,elapsed,'Worker survived cancellation')
            assert not (owned/'cancelled.wav').exists() and not list(owned.rglob('*.rf64')) and not list(owned.glob('.genesis-nested-*'))
            assert sha(project)==before
            results.append(dict(mode=mode,processed_prefix_frames=240000,cancel_join_seconds=elapsed,no_output_or_rf64=True,worker_joined=True))
        finally:
            if process.poll() is None:
                (owned/'stop').write_text('stop',encoding='utf8')
                try:process.communicate(timeout=5)
                except subprocess.TimeoutExpired:terminate_children(process.pid,worker);process.kill();process.communicate(timeout=5)
            if handle is not None and os.name=='nt':
                import ctypes
                kernel=ctypes.WinDLL('kernel32');kernel.CloseHandle.argtypes=[ctypes.c_void_p];kernel.CloseHandle(handle)
            if witness.exists():witness.unlink() # owned opt-in witness after a hard kill
    assert sha(source)==original
    return dict(cases=results,source_project_immutable=True)

def check(root,client,binary,worker):
    ffmpeg=tool(worker,'ffmpeg')
    sources={};source_hashes={}
    for rate in (48000,44100):
        n=np.arange(rate*8);v=np.empty((len(n),2),dtype='<i2')
        # Constant-level segments expose slow attack/release history; signed
        # sample-coded modulation distinguishes the exact retained time span.
        amplitude=np.where(n<rate,.15,np.where(n<rate*3,.6,.3))
        v[:,0]=(amplitude*32768+(n%97==0)*3).astype(np.int16)
        v[:,1]=(-amplitude*.75*32768-(n%113==0)*2).astype(np.int16)
        path=root/f'authored {rate} \u65e5\u672c\u8a9e %20.wav'
        with wave.open(str(path),'wb') as f:f.setparams((2,2,rate,0,'NONE','none'));f.writeframes(v.tobytes())
        sources[rate]=(path,v);source_hashes[str(path)]=sha(path)
    compressed=root/'authored compressed48k.m4a'
    run([ffmpeg,'-nostdin','-v','error','-i',sources[48000][0],'-c:a','aac','-b:a','192k',compressed])
    source_hashes[str(compressed)]=sha(compressed)
    specs=[('compressor',48000,1,False,30,'compressor',dict(threshold=-24,ratio=12,attack=80,release=1200),'acompressor=threshold='+str(10**(-24/20))+':ratio=12:attack=80:release=1200'),
           ('gate',48000,1,False,30,'gate',dict(threshold=-18,hold=1200),'agate=threshold='+str(10**(-18/20))+':release=1200'),
           ('limiter',48000,1,False,30,'limiter',dict(ceiling=-12),'alimiter=limit='+str(10**(-12/20))+':level=disabled'),
           ('eq',48000,1,False,30,'eq_3band',dict(low=4.5,mid=-2,high=1.5),'equalizer=f=100:t=q:w=1:g=4.5,equalizer=f=1000:t=q:w=1:g=-2,equalizer=f=8000:t=q:w=1:g=1.5'),
           ('normalize',48000,1,False,30,'normalize',dict(target=-14),'loudnorm=I=-14'),
           ('plain',48000,1,False,30,None,{},'anull'),
           ('compressor441',44100,1,False,30,'compressor',dict(threshold=-24,ratio=12,attack=80,release=1200),'acompressor=threshold='+str(10**(-24/20))+':ratio=12:attack=80:release=1200'),
           ('reverse',48000,1,True,30,'compressor',dict(threshold=-24,ratio=12,attack=80,release=1200),'acompressor=threshold='+str(10**(-24/20))+':ratio=12:attack=80:release=1200'),
           ('tempo15',48000,1.5,False,30,'compressor',dict(threshold=-24,ratio=12,attack=80,release=1200),'acompressor=threshold='+str(10**(-24/20))+':ratio=12:attack=80:release=1200'),
           ('tempo05',48000,.5,False,30,'compressor',dict(threshold=-24,ratio=12,attack=80,release=1200),'acompressor=threshold='+str(10**(-24/20))+':ratio=12:attack=80:release=1200'),
           ('plainaac',48000,1,False,30,None,{},'anull'),
           ('nested_compressor',48000,1,False,30,'compressor',dict(threshold=-24,ratio=12,attack=80,release=1200),'acompressor=threshold='+str(10**(-24/20))+':ratio=12:attack=80:release=1200'),
           ('fractional',48000,1,False,60000/1001,'compressor',dict(threshold=-24,ratio=12,attack=80,release=1200),'acompressor=threshold='+str(10**(-24/20))+':ratio=12:attack=80:release=1200')]
    references={};docs={}
    for name,rate,speed,reverse,fps,kind,params,chain in specs:
        source,values=sources[rate]
        if name=='plainaac':source=compressed
        doc=document([source],(0,));doc['sequences'][0]['fps']=fps
        doc['sources'][0].update(frames=math.ceil(8*fps),fps=fps,audio_rate=rate)
        doc['clips'][0].update(length=120,speed=speed,reverse=reverse,streams=2)
        doc['next_id']=100
        if kind:effect(doc,20,kind,params,50)
        if name=='nested_compressor':
            owner=doc['active'];child=copy.deepcopy(doc['sequences'][0]);child.update(id=10,name='Independent child sum');doc['sequences'].append(child)
            leaf=copy.deepcopy(doc['clips'][0]);leaf.update(id=30,owner=10,track=11,gain=.75)
            second=copy.deepcopy(leaf);second.update(id=31,track=12,gain=.5)
            lane=copy.deepcopy(doc['tracks'][0]);lane.update(id=11,owner=10,name='Child A1');lane2=copy.deepcopy(lane);lane2.update(id=12,name='Child A2',order=1)
            doc['tracks'].extend([lane,lane2]);doc['clips'].extend([leaf,second]);doc['clips'][0].update(source=0,nested=10)
        docs[name]=doc
        # Native trim-before-resample selection remains the public contract.
        # Round microseconds and their native-rate sample index independently.
        us=math.floor(120*speed/fps*1000000+.5)
        native=math.floor(us*rate/1000000+.5)
        stages=[f'atrim=start_sample=0:end_sample={native}','asetpts=N/SR/TB','aresample=48000','aformat=sample_fmts=flt:sample_rates=48000:channel_layouts=stereo']
        if reverse:stages.append('areverse')
        if speed!=1:stages.append(f'atempo={speed}')
        stages.extend([chain,'aformat=sample_fmts=flt:sample_rates=48000:channel_layouts=stereo'])
        if name=='nested_compressor':
            # Independent float children are summed BEFORE the nonlinear parent.
            native_values=values[:native].astype(np.float32)/32768
            child_sum=(native_values*np.float32(.75)+native_values*np.float32(.5)).astype('<f4')
            data=run([ffmpeg,'-nostdin','-v','error','-f','f32le','-ar',SR,'-ac',2,'-i','pipe:0','-af',chain,'-f','f32le','pipe:1'],input=child_sum.tobytes())
        else:data=run([ffmpeg,'-nostdin','-v','error','-i',source,'-af',','.join(stages),'-f','f32le','pipe:1'])
        raw=np.frombuffer(data,dtype='<f4').reshape(-1,2).copy();count=sample(120,fps)
        raw=raw[:count];raw=np.pad(raw,((0,max(0,count-len(raw))),(0,0)))
        references[name]=raw
        (root/(name+'.air')).write_text(json.dumps(doc),encoding='utf8')
    (root/'cases.tsv').write_text('\n'.join(docs)+'\n')
    run([client,worker,root])
    results=[];maxpcm=0.;maxpeak=0.;compared=0
    for name,doc in docs.items():
        fps=doc['sequences'][0]['fps'];raw=references[name];cut=sample(60,fps);again=sample(75,fps)
        repeated_at=74 if doc['clips'][0]['speed']!=1 else 75
        moved_at=62 if doc['clips'][0]['speed']!=1 else 61
        for variant in ('original','split','head','tail','repeated','moved'):
            target=raw.copy()
            if variant=='head':target[:cut]=0
            elif variant=='tail':target=target[:cut]
            elif variant=='repeated':target[cut:sample(repeated_at,fps)]=0
            elif variant=='moved':
                original_crop=sample(moved_at,fps);begin=sample(moved_at+2,fps);end=sample(122,fps)
                body=raw[original_crop:];body=body[:end-begin]
                body=np.pad(body,((0,max(0,end-begin-len(body))),(0,0)))
                target=np.concatenate([np.zeros((begin,2),dtype=np.float32),body])
            expected=quantize(target);prefix=root/(name+'-'+variant)
            whole_count=math.ceil((122 if variant=='moved' else 60 if variant=='tail' else 120)/fps*SR)
            assert 0<=whole_count-len(expected)<=1,(name,variant,'WAVE endpoint',whole_count,len(expected))
            whole_expected=np.pad(expected,((0,whole_count-len(expected)),(0,0)))
            actual=pcm(prefix.with_suffix('.wav'));assert actual.shape==whole_expected.shape,(name,variant,actual.shape,whole_expected.shape)
            error=float(np.max(np.abs(actual.astype(np.int32)-whole_expected.astype(np.int32))));assert error<=1,(name,variant,'whole',error)
            chunks=np.concatenate([pcm(Path(p)) for p in (root/(name+'-'+variant+'-pulls.txt')).read_text().splitlines()])
            ce=float(np.max(np.abs(chunks.astype(np.int32)-expected.astype(np.int32))));assert chunks.shape==expected.shape and ce<=1,(name,variant,'retained',ce)
            if len(target)>again:
                fresh=pcm(root/(name+'-'+variant+'-fresh.wav'))
                fresh_count=math.ceil(((122 if variant=='moved' else 120)-75)/fps*SR)
                fresh_expected=expected[again:]
                assert 0<=fresh_count-len(fresh_expected)<=1,(name,variant,'fresh WAVE endpoint',fresh_count,len(fresh_expected))
                fresh_expected=np.pad(fresh_expected,((0,fresh_count-len(fresh_expected)),(0,0)))
                fe=float(np.max(np.abs(fresh.astype(np.int32)-fresh_expected.astype(np.int32))))
                assert fresh.shape==fresh_expected.shape and fe<=1,(name,variant,'fresh',fe)
            graph=json.loads(prefix.with_suffix('.air').read_text())
            assert graph['revision']==(2 if variant=='original' else 3)
            pe=0.
            for clip in graph['clips']:
                if clip['owner']!=graph['active']:continue
                first=sample(clip['start'],fps);last=sample(clip['start']+clip['length'],fps)
                got=np.loadtxt(root/(name+'-'+variant+'-peaks-'+str(clip['id'])+'.txt'))
                wanted=peaks(target[first:last],600)
                e=float(np.max(np.abs(got-wanted)));assert e<=2e-6,(name,variant,'peaks',clip['id'],e)
                pe=max(pe,e)
            maxpcm=max(maxpcm,error,ce);maxpeak=max(maxpeak,pe);compared+=expected.size*2
            results.append(dict(name=name,operation=variant,whole_pcm_error=error,retained_pcm_error=ce,peak_error=pe,source_rate=doc['sources'][0]['audio_rate'],whole_wav_frames=whole_count,retained_frames=len(expected),endpoint_silence_frames=whole_count-len(expected)))
        assert 'AUDIOCTX:' not in (root/(name+'-split.plan')).read_text() if name in ('plain','plainaac') else 'AUDIOCTX:' in (root/(name+'-split.plan')).read_text()
    # Independent lossless master checks use the actual CLI export adapter.
    exports=[]
    env=dict(os.environ,GENESIS_GCOMPOSE=str(worker),GENESIS_SCRATCH=str(root/'state'))
    env.pop('GENESIS_FAKE_PROVIDER',None);env.pop('GENESIS_SESSION_REPORT',None)
    for name in ('compressor','limiter','eq','nested_compressor'):
        path=root/(name+'-split-master.mkv');run([binary,'export',path,root/(name+'-split.air')],env=env)
        data=run([ffmpeg,'-nostdin','-v','error','-i',path,'-map','0:a:0','-f','f32le','pipe:1'])
        actual=np.frombuffer(data,dtype='<f4').reshape(-1,2);expected=references[name]
        assert actual.shape==expected.shape,(name,'master count',actual.shape,expected.shape)
        e=float(np.max(np.abs(actual-expected)));assert e<=2e-6,(name,'master',e)
        exports.append(dict(name=name,pcm24_maximum_error=e,stereo_values=actual.size))
    protocol=stream_contract(root,worker,sources[48000][0],references['compressor'],ffmpeg)
    tails=edited_tails(root,client,worker,ffmpeg,docs,sources[48000][0])
    cancellation=cancel_prefix(root,client,worker,docs['compressor'])
    assert all(sha(Path(p))==h for p,h in source_hashes.items())
    assert not list(root.rglob('.genesis-nested-*')),'Owned float cache survives closed workers'
    return dict(cases=len(results),results=results,exports=exports,maximum_pcm_error=maxpcm,maximum_peak_error=maxpeak,
                compared_pcm_values=compared,source_hashes=source_hashes,source_immutable=True,owned_cache_cleanup=True,
                pcm_threshold_codes=1,peak_threshold=2e-6,master_threshold=2e-6,protocol=protocol,cancellation=cancellation,edited_tails=tails)

def main():
    p=argparse.ArgumentParser();p.add_argument('--client',type=Path,required=True);p.add_argument('--binary',type=Path,required=True)
    p.add_argument('--worker',type=Path,required=True);p.add_argument('--report',type=Path,required=True);a=p.parse_args()
    client,binary,worker=(v.resolve() for v in (a.client,a.binary,a.worker))
    report=dict(passed=False,client_sha256=sha(client),binary_sha256=sha(binary),worker_sha256=sha(worker))
    a.report.parent.mkdir(parents=True,exist_ok=True)
    work=Path(tempfile.mkdtemp(prefix='audio-edit-context-',dir=a.report.parent))
    try:
        report.update(check(work,client,binary,worker))
        assert report['client_sha256']==sha(client) and report['binary_sha256']==sha(binary) and report['worker_sha256']==sha(worker)
        report['passed']=True
        shutil.rmtree(work)
        print(f'Audio edit context: {report["cases"]} independent whole/chunk/fresh/peak cases, {len(report["exports"])} lossless masters; PCMâ‰¤1 code, peaksâ‰¤2e-6')
    except BaseException as problem:
        report['failure']=str(problem);report['retained_failure_directory']=str(work)
        raise
    finally:a.report.parent.mkdir(parents=True,exist_ok=True);a.report.write_text(json.dumps(report,indent=2)+'\n',encoding='utf8')
if __name__=='__main__':main()
