# Independent retained Delay/Reverb EOF and cache protocol regression.
from pathlib import Path
import argparse, array, hashlib, json, os, subprocess, sys, wave, uuid, struct
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tests'))
from nested_waveforms import Worker, buckets, data_offset
from audio_stream import wire
from media_runtime import tool
FLAGS=0x08000000 if os.name=='nt' else 0

def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def pcm(path):
    with wave.open(str(path),'rb') as f:
        assert f.getframerate()==48000 and f.getnchannels()==2 and f.getsampwidth()==2
        return np.frombuffer(f.readframes(f.getnframes()),dtype='<i2').reshape(-1,2)
def quantize(values):
    values=np.clip(values,-1,1)
    return np.sign(values)*np.floor(np.abs(values)*32767+.5)

def guards(worker,root,summary):
    out=root/'guard-protocol';out.mkdir(exist_ok=False)
    source=out/'native stereo.wav'
    a=np.arange(192000);signal=np.stack((.12*np.sin(a*.023),.19*np.cos(a*.043)),axis=1)
    with wave.open(str(source),'wb') as f:f.setnchannels(2);f.setsampwidth(2);f.setframerate(48000);f.writeframes(np.rint(signal*32767).astype('<i2').tobytes())
    sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
    initial=sha(source);cache=out/'cache';cache.mkdir();p=Worker(worker)
    report=dict(passed=False,checks=[])
    def rows(chain='aecho=0.8:0.9:250:0.4',gain='1'):
     return [f'NESTLEAF bus.leaf bus 0 192000 {wire(source)} 0 4 {gain} 0 0 4 {chain} AUDIOCTX:0:4:192000:0 AUDIOTAIL', 'NESTBUS bus - 0 192000 0 192000 1 0 0 4 - AUDIOTAIL']
    def define(rs):
     p.command('NESTBEGIN '+wire(cache))
     for r in rs:p.command(r)
    def hashes():return {x.name:sha(x) for x in cache.iterdir()}
    def mix(code=None):
     target=out/f'query-{len(report["checks"])}.wav';p.command(f'PLAYWAVE {wire(target)} 256')
     p.command('NESTMIXTAIL bus 192000 192256 0',code);p.command('WAVECLOSE '+wire(target))
     return target
    try:
     define(rows());p.command('NESTCOMMIT');before=hashes()
     # Native EOF actually exceeds five seconds; renderer must refuse rather than truncate.
     chain='aecho=0.8:0.9:6000:0.4'
     ref=subprocess.run([str(tool(worker,'ffmpeg')),'-v','error','-nostdin','-i',str(source),'-af','aformat=sample_fmts=flt,'+chain+',aformat=sample_fmts=flt','-f','f32le','pipe:1'],capture_output=True,timeout=30,creationflags=FLAGS)
     assert ref.returncode==0 and len(ref.stdout)//8==480000,len(ref.stdout)//8
     define(rows(chain));p.command('NESTCOMMIT','GA_AUDIO_CONTEXT_TAIL');assert hashes()==before
     report['checks'].append(dict(kind='actual EOF overrun',actual_tail_frames=288000,total_cap_frames=240000,refused_not_truncated=True,old_cache_unchanged=True))
     mix();report['checks'].append(dict(kind='prior accepted tree usable after refused replacement'))
     # Every body/output/sum plus worst-case tail is reserved before decoder work.
     big=1036800000;rs=[]
     for name in ('large1','large2'):
      rs.extend([f'NESTLEAF {name}.leaf {name} 0 {big} {wire(source)} 0 21600 1 0 0 21600 aecho=0.8:0.9:250:0.4 AUDIOCTX:0:21600:{big}:0 AUDIOTAIL',
       f'NESTBUS {name} - 0 {big} 0 {big} 1 0 0 21600 - AUDIOTAIL'])
     define(rs);p.command('NESTCOMMIT','GA_AUDIO_NESTED_CAPACITY');assert hashes()==before
     report['checks'].append(dict(kind='prospective body plus worst-tail 32GiB capacity',accepted_cache_unchanged=True,no_new_cache_files=True))
     mix()

     # One same-size foreign rewrite is refused even if the header remains valid.
     target=next(cache.glob('*-1-output.rf64'));original=target.read_bytes();stat=target.stat()
     changed=bytearray(original);struct.pack_into('<f',changed,80,.314159);target.write_bytes(changed)
     mix('GA_AUDIO_NESTED_CACHE');report['checks'].append(dict(kind='same-size foreign sample rewrite refused'))
     target.write_bytes(original);os.utime(target,ns=(stat.st_atime_ns,stat.st_mtime_ns));mix()
     report['checks'].append(dict(kind='restored original identity recovery'))
     # Header change stays malformed when the recorded timestamp is preserved.
     corrupted=bytearray(original);struct.pack_into('<Q',corrupted,36,123);target.write_bytes(corrupted);os.utime(target,ns=(stat.st_atime_ns,stat.st_mtime_ns))
     mix('GA_AUDIO_NESTED_CACHE');report['checks'].append(dict(kind='mismatched RF64 audible endpoint refused'))
     target.write_bytes(original[:-8]);os.utime(target,ns=(stat.st_atime_ns,stat.st_mtime_ns));mix('GA_AUDIO_NESTED_CACHE')
     report['checks'].append(dict(kind='truncated accepted cache refused'))
     target.write_bytes(original);os.utime(target,ns=(stat.st_atime_ns,stat.st_mtime_ns));mix()
     # Actual tail retains the selected clip's scalar gain, and body-only peaks keep body geometry.
     define(rows(gain='.37'));p.command('NESTCOMMIT')
     raw=next(cache.glob('*-0-output.rf64')).read_bytes();actual=np.frombuffer(raw,dtype='<f4',offset=data_offset(raw)).reshape(-1,2)
     reference=subprocess.run([str(tool(worker,'ffmpeg')),'-v','error','-nostdin','-i',str(source),'-af','aformat=sample_fmts=flt,aecho=0.8:0.9:250:0.4,aformat=sample_fmts=flt','-f','f32le','pipe:1'],capture_output=True,timeout=30,creationflags=FLAGS)
     want=np.frombuffer(reference.stdout,dtype='<f4').reshape(-1,2)*np.float32(.37)
     assert len(actual)==len(want) and float(np.max(np.abs(actual-want)))<=2e-6
     report['checks'].append(dict(kind='scalar envelope body and tail',float_maximum_error=float(np.max(np.abs(actual-want))),actual_tail_frames=len(actual)-192000))
     # Complete gain knots continue through the tail at their body-local offset.
     rs=rows(gain='.37');rs[0]+=' GAINKEYS:0:0,0,0.2,1/192000,120,0.8,1/216000,135,0.35,1'
     define(rs);p.command('NESTCOMMIT')
     raw=next(cache.glob('*-0-output.rf64')).read_bytes();actual=np.frombuffer(raw,dtype='<f4',offset=data_offset(raw)).reshape(-1,2)
     envelope=np.interp(np.arange(len(actual)),[0,192000,216000],[.2,.8,.35]).astype(np.float32)*np.float32(.37)
     want=np.frombuffer(reference.stdout,dtype='<f4').reshape(-1,2)*envelope[:,None]
     keyed_error=float(np.max(np.abs(actual-want)));assert keyed_error<=2e-6
     report['checks'].append(dict(kind='gain keys continue at original body end',float_maximum_error=keyed_error))
     # A neutral authored tail graph reaches actual EOF at the authored endpoint.
     define(rows(chain='anull'));p.command('NESTCOMMIT')
     raw=next(cache.glob('*-0-output.rf64')).read_bytes();assert (len(raw)-80)//8==192000
     report['checks'].append(dict(kind='neutral static tail graph has zero actual EOF tail'))
     for chain,extra in [('loudnorm=I=-14,aecho=0.8:0.9:250:0.4',''),('aecho=0.8:0.9:250:0.4',' FADEKEYS:0:0:30:0,0,1,1:-')]:
      before=hashes();p.command('NESTBEGIN '+wire(cache));p.command(rows(chain=chain)[0]+extra,'GA_AUDIO_CONTEXT_TAIL');assert hashes()==before
      report['checks'].append(dict(kind='unproved normalize or fade-key graph refused',accepted_cache_unchanged=True))
     # Requests wholly beyond actual EOF contribute silence, and cannot extend beyond cap.
     p.command('PLAYWAVE '+wire(out/'pastEOF.wav')+' 128');p.command('NESTMIXTAIL bus 240000 240128 0');p.command('WAVECLOSE '+wire(out/'pastEOF.wav'))
     with wave.open(str(out/'pastEOF.wav'),'rb') as f:assert set(f.readframes(f.getnframes()))=={0}
     p.command('PLAYWAVE '+wire(out/'outside.wav')+' 128');p.command('NESTMIXTAIL bus 432000 432128 0','GA_AUDIO_NESTED_PROTOCOL');p.command('WAVECLOSE '+wire(out/'outside.wav'))
     report['checks'].append(dict(kind='actual EOF no invented sample padding and bounded request refusal'))
     report.update(passed=True,source_immutable=sha(source)==initial)
    finally:
     p.close();assert not list(cache.glob('*.rf64'));report['normal_worker_drop_cache_cleanup']=True
     summary['guards'].extend(report['checks'])
     summary['guard_cache_cleanup']=report['normal_worker_drop_cache_cleanup']
     assert report['passed'] and report['source_immutable']


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--worker',type=Path,required=True)
    ap.add_argument('--report',type=Path,required=True)
    ap.add_argument('--expect-refusal',action='store_true')
    args=ap.parse_args()
    report_path=args.report.resolve()
    assert not report_path.exists(), 'Refuse to overwrite a prior receipt'
    report_path.parent.mkdir(parents=True,exist_ok=True)
    out=report_path.parent/('audio-tail-protocol-'+uuid.uuid4().hex)
    out.mkdir(exist_ok=False)
    worker=args.worker.resolve();sr=48000;full=4*sr
    at=np.arange(full,dtype=np.float64)
    signal=np.stack((.19*np.sin(at*.037)+.05*np.cos(at*.113),.17*np.cos(at*.023)),axis=1)
    signal[-640:]=np.stack((np.linspace(.15,.4,640),np.linspace(-.32,.12,640)),axis=1)
    authored=np.rint(signal*32767).astype('<i2')
    source=out/'authored.wav'
    with wave.open(str(source),'wb') as f:
        f.setnchannels(2);f.setsampwidth(2);f.setframerate(sr);f.writeframes(authored.tobytes())
    initial_source=sha(source)
    chains=[('delay','aecho=0.8:0.9:250:0.4'),
            ('ordered','aecho=0.8:0.9:250:0.4,volume=0.73,aecho=0.8:0.9:47|97|151|211:0.15|0.12|0.09|0.06')]
    report=dict(passed=False,worker_sha256=sha(worker),oracle_sha256=sha(Path(__file__)),cases=[],refusals=[],guards=[],work_directory=str(out),
        scope="Independent packed-float native EOF, original-end ownership, authored-body peaks, malformed/cache/resource refusal. No device/cadence claim.")
    def define(p,cache,rows):
        p.command('NESTBEGIN '+wire(cache))
        for row in rows:p.command(row)
    def rows(chain,start,crop,body,tail=True,ident='bus'):
        last=start+body
        leaf=f'NESTLEAF {ident}.leaf {ident} {start} {last} {wire(source)} {crop/sr} {body/sr} 1 0 0 {body/sr} {chain} AUDIOCTX:0:4:{full}:{crop}'
        bus=f'NESTBUS {ident} - {start} {last} {start} {last} 1 0 0 {body/sr} -'
        if tail:leaf+=' AUDIOTAIL';bus+=' AUDIOTAIL'
        return [leaf,bus]
    try:
        if args.expect_refusal:
            cache=out/'baseline-cache';cache.mkdir();p=Worker(worker)
            try:
                p.command('NESTBEGIN '+wire(cache))
                p.command(rows(chains[0][1],2*sr,2*sr,2*sr)[0],'GA_AUDIO_NESTED_PROTOCOL')
                assert not list(cache.iterdir())
                report.update(passed=True,baseline_does_not_support_tail_marker=True)
            finally:p.close()
            return
        for name,chain in chains:
            # Independent full-file decode with the declared native graph's
            # packed float stereo input/output negotiation. Without the input
            # aformat FFmpeg may choose integer aecho and quantize inside DSP.
            stages=f'atrim=start_sample=0:end_sample={full},asetpts=N/SR/TB,aresample=48000,aformat=sample_fmts=flt:sample_rates=48000:channel_layouts=stereo,{chain},aformat=sample_fmts=flt:sample_rates=48000:channel_layouts=stereo'
            ref=subprocess.run([str(tool(worker,'ffmpeg')),'-nostdin','-v','error','-i',str(source),
                '-af',stages,'-f','f32le','pipe:1'],capture_output=True,timeout=30,creationflags=FLAGS)
            assert ref.returncode==0,ref.stderr
            expected=np.frombuffer(ref.stdout,dtype='<f4').reshape(-1,2)
            assert full<len(expected)<=full+5*sr and np.count_nonzero(expected[full:])>100
            cache=out/name;cache.mkdir();p=Worker(worker)
            try:
                for variant,start,crop,body,tail in [('whole',0,0,full,True),('head',2*sr,2*sr,2*sr,True),
                    ('moved',5*sr,2*sr,2*sr,True),('interior',0,0,2*sr,False)]:
                    definition=rows(chain,start,crop,body,tail)
                    define(p,cache,definition);p.command('NESTCOMMIT')
                    raw=next(cache.glob('*-0-output.rf64')).read_bytes()
                    actual=np.frombuffer(raw,dtype='<f4',offset=data_offset(raw)).reshape(-1,2)
                    wanted=expected[crop:] if tail else expected[crop:crop+body]
                    assert len(actual)==len(wanted),(name,variant,len(actual),len(wanted))
                    error=float(np.max(np.abs(actual-wanted)));assert error<=2e-6,(name,variant,error)
                    output=out/f'{name}-{variant}.wav';frames=10*sr
                    p.command(f'PLAYWAVE {wire(output)} {frames}')
                    p.command(f'{"NESTMIXTAIL" if tail else "NESTMIX"} bus {start} {start+body+(5*sr if tail else 0)} {start}')
                    p.command('WAVECLOSE '+wire(output))
                    wanted_program=np.zeros((frames,2));wanted_program[start:start+len(wanted)]=quantize(wanted)
                    codes=float(np.max(np.abs(pcm(output)-wanted_program)));assert codes<=1,(name,variant,codes)
                    peak_path=cache/f'{variant}-peaks.f32';p.command(f'NESTENV bus 73 {wire(peak_path)}')
                    actual_peaks=np.frombuffer(peak_path.read_bytes(),dtype='<f4')
                    oracle=np.array(buckets(array.array('f',expected[crop:crop+body].flatten()),73))
                    peak_error=float(np.max(np.abs(actual_peaks-oracle)));assert peak_error<=2e-6
                    if tail:
                        fresh=out/f'{name}-{variant}-after-body.wav';count=7200;begin=start+body+100
                        p.command(f'PLAYWAVE {wire(fresh)} {count}')
                        p.command(f'NESTMIXTAIL bus {begin} {begin+count} 0')
                        p.command('WAVECLOSE '+wire(fresh))
                        oracle=np.zeros((count,2));segment=wanted[body+100:body+100+count]
                        oracle[:len(segment)]=quantize(segment)
                        fresh_error=float(np.max(np.abs(pcm(fresh)-oracle)));assert fresh_error<=1
                    report['cases'].append(dict(effect=name,variant=variant,authored_body_frames=body,
                        actual_tail_frames=len(actual)-body,float_maximum_error=error,pcm_maximum_error=codes,
                        peaks_maximum_error=peak_error,after_body_seek_verified=tail))
                # Two independently cropped pieces reproduce original body+tail,
                # without duplicating or restarting the first piece's echoes.
                definitions=rows(chain,0,0,2*sr,False,'left')+rows(chain,2*sr,2*sr,2*sr,True,'right')
                define(p,cache,definitions);p.command('NESTCOMMIT')
                output=out/f'{name}-split.wav';p.command(f'PLAYWAVE {wire(output)} {8*sr}')
                p.command(f'NESTMIX left 0 {2*sr} 0');p.command(f'NESTMIXTAIL right {2*sr} {7*sr} {2*sr}')
                p.command('WAVECLOSE '+wire(output));want=np.zeros((8*sr,2));want[:len(expected)]=quantize(expected)
                error=float(np.max(np.abs(pcm(output)-want)));assert error<=1
                report['cases'].append(dict(effect=name,variant='split',pcm_maximum_error=error,tail_owned_only_by_right=True))
                # Invalid definitions may not change any accepted cache bytes.
                invalid=[(rows(chain,0,0,2*sr,True)[0],'GA_AUDIO_CONTEXT_TAIL'),
                    (rows(chain,2*sr,2*sr,2*sr)[0]+' AUDIOTAIL','GA_AUDIO_CONTEXT_TAIL'),
                    (rows('areverse,'+chain,2*sr,2*sr,2*sr)[0],'GA_AUDIO_CONTEXT_TAIL')]
                for row,code in invalid:
                    before={f.name:sha(f) for f in cache.iterdir()}
                    p.command('NESTBEGIN '+wire(cache));p.command(row,code)
                    assert {f.name:sha(f) for f in cache.iterdir()}==before
                    report['refusals'].append(dict(code=code,accepted_cache_unchanged=True))
                # Marking an arbitrary or nonneutral wrapper is refused at COMMIT.
                for rows_bad in [rows(chain,2*sr,2*sr,2*sr)[:1]+[rows(chain,2*sr,2*sr,2*sr)[1].replace(' 1 0 0 2.0 -',' 0.5 0 0 2.0 -')],
                                 rows(chain,2*sr,2*sr,2*sr)[:1]+[rows(chain,2*sr,2*sr,2*sr)[1].replace(' AUDIOTAIL','')]]:
                    before={f.name:sha(f) for f in cache.iterdir()}
                    define(p,cache,rows_bad);p.command('NESTCOMMIT','GA_AUDIO_CONTEXT_TAIL')
                    assert {f.name:sha(f) for f in cache.iterdir()}==before
                    report['refusals'].append(dict(code='GA_AUDIO_CONTEXT_TAIL',accepted_cache_unchanged=True))
                # Refuse unmarked tail reads while preserving subsequent recovery.
                wav=out/f'{name}-unmarked.wav';p.command(f'PLAYWAVE {wire(wav)} 128')
                p.command('NESTMIXTAIL left 0 128 0','GA_AUDIO_CONTEXT_TAIL');p.command('WAVECLOSE '+wire(wav))
                assert np.count_nonzero(pcm(wav))==0
                report['refusals'].append(dict(code='GA_AUDIO_CONTEXT_TAIL',unmarked_root_refused=True))
            finally:p.close()
            assert not list(cache.glob('*.rf64'))
        guards(worker,out,report)
        assert sha(source)==initial_source
        report.update(passed=True,source_immutable=True)
    finally:
        report['case_count']=len(report['cases'])+len(report['refusals'])+len(report['guards'])
        with report_path.open('x',encoding='utf-8') as output:
            output.write(json.dumps(report,indent=2)+'\n')
        print(json.dumps(report,indent=2))

if __name__=='__main__':main()
