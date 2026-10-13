"""Committed accepted audio EOF query regression; no device/UI/GPU."""
from pathlib import Path
import argparse,hashlib,json,os,struct,subprocess,sys,time,traceback,uuid,wave
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tests'))
from nested_waveforms import Worker,data_offset
from audio_stream import wire
from media_runtime import tool
FLAGS=0x08000000 if os.name=='nt' else 0
SR=48000;FULL=SR
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
def quantize(a):
 a=np.clip(a,-1,1);return np.sign(a)*np.floor(np.abs(a)*32767+.5)
def pcm(p):
 with wave.open(str(p),'rb') as f:
  assert (f.getframerate(),f.getnchannels(),f.getsampwidth())==(SR,2,2)
  return np.frombuffer(f.readframes(f.getnframes()),dtype='<i2').reshape(-1,2)
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--worker',type=Path,required=True);ap.add_argument('--report',type=Path,required=True);args=ap.parse_args()
 report=args.report.resolve();assert not report.exists(),'Exclusive report already exists';report.parent.mkdir(parents=True,exist_ok=True)
 out=report.parent/('audio-eof-query-'+uuid.uuid4().hex);out.mkdir();worker=args.worker.resolve()
 result=dict(schema='genesis.audio_eof_query.v1',passed=False,worker_sha256=sha(worker),harness_sha256=sha(__file__),work_directory=str(out),numeric=[],identity=[],refusals=[],cache_guards=[],checks=0,pcm_values=0,
 scope='Actual native EOF from independent MM-AIR float DSP; direct static 48k integral-phase only. No transport/default-export/device/physical-audio or GPU read-only qualification.')
 source=out/'native source.wav';t=np.arange(FULL);signal=np.stack((.19*np.sin(t*.037)+.05*np.cos(t*.113),.17*np.cos(t*.023)),axis=1);signal[-512:]=np.stack((np.linspace(.15,.4,512),np.linspace(-.32,.12,512)),axis=1)
 with wave.open(str(source),'wb') as f:f.setnchannels(2);f.setsampwidth(2);f.setframerate(SR);f.writeframes(np.rint(signal*32767).astype('<i2').tobytes())
 source_sha=sha(source);cache=out/'cache';cache.mkdir();p=Worker(worker);req=0
 def rows(chain,start=0,crop=0,body=FULL,tail=True,ident='bus'):
  end=start+body
  a=f'NESTLEAF {ident}.leaf {ident} {start} {end} {wire(source)} {crop/SR} {body/SR} 1 0 0 {body/SR} {chain} AUDIOCTX:0:1:{FULL}:{crop}'
  b=f'NESTBUS {ident} - {start} {end} {start} {end} 1 0 0 {body/SR} -'
  return [a+(' AUDIOTAIL' if tail else ''),b+(' AUDIOTAIL' if tail else '')]
 def define(rs,commit=True):
  p.command('NESTBEGIN '+wire(cache))
  for row in rs:p.command(row)
  if commit:p.command('NESTCOMMIT')
 def hashes():return {q.name:sha(q) for q in cache.iterdir() if q.is_file()}
 def query(root='bus',generation=0,request=None):
  nonlocal req
  if request is None:req+=1;request=req
  before=hashes();tr=p.command(f'NESTEND {request} {root} {generation}');r=tr[-1].split();assert len(r)==8 and r[:2]==['DONE','NESTEND'] and r[2]==str(request) and r[3]==root,r
  fields=tuple(map(int,r[4:]));assert fields[0]>0 and fields[2]>=fields[1] and fields[3]>=fields[2],fields
  assert hashes()==before,'Query changed cache files';result['checks']+=1;return fields
 def refusal(line,code='GA_AUDIO_NESTED_PROTOCOL'):
  before=hashes();tr=p.command(line,code);assert hashes()==before;result['refusals'].append(dict(command=line,code=code,cache_unchanged=True));result['checks']+=1;return tr
 def mix(begin,end,wanted,tail=True):
  count=end-begin;output=out/f'mix-{len(result["numeric"])}-{result["checks"]}.wav'
  p.command(f'PLAYWAVE {wire(output)} {count}');query();p.command(f'{"NESTMIXTAIL" if tail else "NESTMIX"} bus {begin} {end} 0');p.command('WAVECLOSE '+wire(output))
  actual=pcm(output);assert len(actual)==count;assert len(wanted)==count
  error=float(np.max(np.abs(actual.astype(float)-quantize(wanted)))) if count else 0;assert error<=1,(error,begin,end)
  result['pcm_values']+=actual.size;result['checks']+=1;return error
 try:
  refusal('NESTEND 1 bus 0','GA_AUDIO_NESTED_CACHE')
  define(rows('anull',tail=False));first=query();assert first[1:]==(0,FULL,FULL)
  for line in ['NESTEND','NESTEND 1 bus','NESTEND 1 bus 0 extra','NESTEND 0 bus 0','NESTEND -1 bus 0','NESTEND +1 bus 0','NESTEND 1.0 bus 0','NESTEND 18446744073709551616 bus 0','NESTEND 1 bus -1','NESTEND 1 bus +1','NESTEND 1 bus 18446744073709551616','NESTEND 1 - 0','NESTEND 1 '+'a'*257+' 0','NESTEND '+'1'*520+' bus 0','NESTEND 1 missing 0','NESTEND 1 bus.leaf 0']:
   refusal(line)
  assert query(request=18446744073709551615)==first
  # Query failures do not abort pending definitions, even when malformed/stale.
  rs=rows('aecho=0.8:0.9:250:0.4');define(rs,False)
  refusal('NESTEND 2 bus 0');refusal(f'NESTEND 2 bus {first[0]+1}');refusal('NESTEND +2 bus 0')
  p.command('NESTCOMMIT');second=query();assert second[0]>first[0]
  refusal(f'NESTEND 2 bus {first[0]}');assert query(generation=second[0])==second
  oldhash=hashes();define(rs);hit=query();assert hit==second and hashes()==oldhash
  result['identity'].append(dict(kind='pending errors preserve complete transaction; replacement increments; identical hit retains',first=first,replacement=second,hit=hit));result['checks']+=1
  # Failed replacement advances internal build serial but cannot relabel accepted tree.
  define(rows('aecho=0.8:0.9:6000:0.4'),False);p.command('NESTCOMMIT','GA_AUDIO_CONTEXT_TAIL');assert hashes()==oldhash and query(generation=second[0])==second
  result['identity'].append(dict(kind='failed six-second actual EOF replacement retains old accepted generation/cache',accepted=second));result['checks']+=1
  define(rows('aecho=0.8:0.9:250:0.4',ident='other'));other=query('other');assert other[0]>second[0]
  refusal('NESTEND 3 bus 0');result['identity'].append(dict(kind='reused and unknown root identity refused',other=other));result['checks']+=1
  chains=[('neutral','anull'),('delay','aecho=0.8:0.9:250:0.4'),('reverb','aecho=0.8:0.9:47|97|151|211:0.15|0.12|0.09|0.06'),('ordered','aecho=0.8:0.9:250:0.4,volume=0.73,aecho=0.8:0.9:47|97|151|211:0.15|0.12|0.09|0.06')]
  for effect,chain in chains:
   stages=f'atrim=start_sample=0:end_sample={FULL},asetpts=N/SR/TB,aresample=48000,aformat=sample_fmts=flt:sample_rates=48000:channel_layouts=stereo,{chain},aformat=sample_fmts=flt:sample_rates=48000:channel_layouts=stereo'
   oracle=subprocess.run([str(tool(worker,'ffmpeg')),'-nostdin','-v','error','-i',str(source),'-af',stages,'-f','f32le','pipe:1'],capture_output=True,timeout=30,creationflags=FLAGS)
   assert oracle.returncode==0,oracle.stderr;expected=np.frombuffer(oracle.stdout,dtype='<f4').reshape(-1,2)
   assert FULL<=len(expected)<=FULL+5*SR
   if effect!='neutral':assert np.count_nonzero(expected[FULL:])>100
   (out/f'{effect}-oracle.f32').write_bytes(oracle.stdout)
   for variant,start,crop,body,tail in [('whole',0,0,FULL,True),('head',24000,24000,24000,True),('move',96000,24000,24000,True),('interior',0,0,24000,False),('tailtrim',0,0,FULL-1600,False)]:
    rs=rows(chain,start,crop,body,tail);define(rs);got=query();want=expected[crop:] if tail else expected[crop:crop+body];end=start+len(want)
    assert got[1:]==(start,start+body,end),(effect,variant,got,end)
    raw=next(cache.glob('*-1-output.rf64')).read_bytes();actual=np.frombuffer(raw,dtype='<f4',offset=data_offset(raw)).reshape(-1,2)
    assert actual.shape==want.shape;float_error=float(np.max(np.abs(actual-want)));assert float_error<=2e-6
    code_error=mix(start,end,want,tail)
    # A marked crop ends exactly at explicit caller count, independently of queried tail.
    cropped=min(body,7200);crop_error=mix(start,start+cropped,want[:cropped],tail)
    if tail and end>start+body:
     begin=start+body+37;count=min(4096,end-begin);assert count>0
     seek_error=mix(begin,begin+count,want[body+37:body+37+count],True)
    else:seek_error=None
    result['numeric'].append(dict(effect=effect,variant=variant,generation=got[0],start=start,authored_end=start+body,actual_end=end,oracle_frames=len(expected),nonzero_tail_values=int(np.count_nonzero(expected[FULL:])),float_maximum_error=float_error,pcm_maximum_codes=code_error,explicit_crop_codes=crop_error,postbody_seek_codes=seek_error));result['checks']+=1
  # Distinct accepted roots share one tree generation; only the right survivor owns tail.
  chain=chains[1][1];reference=np.frombuffer((out/'delay-oracle.f32').read_bytes(),dtype='<f4').reshape(-1,2)
  define(rows(chain,0,0,24000,False,'left')+rows(chain,24000,24000,24000,True,'right'))
  left=query('left');right=query('right');assert left[0]==right[0] and left[3]==24000 and right[3]==len(reference)
  result['identity'].append(dict(kind='split roots same generation, original tail owned once at right endpoint',left=left,right=right));result['checks']+=1
  # Query does not need an accumulator and cannot create one or consume it.
  p.command(f'NESTMIX left 0 128 0','GA_AUDIO_NESTED_PROTOCOL');query('left')
  # Inspect corruption in body-only and marked-tail roots; restore exact original metadata.
  for tail in (False,True):
   define(rows(chain,tail=tail));accepted=query();root=next(cache.glob('*-1-output.rf64'));original=root.read_bytes();stat=root.stat()
   changed=bytearray(original);struct.pack_into('<f',changed,80,.314159);root.write_bytes(changed);os.utime(root,ns=(stat.st_atime_ns,stat.st_mtime_ns+10000000));refusal('NESTEND 9 bus 0','GA_AUDIO_NESTED_CACHE')
   root.write_bytes(original);os.utime(root,ns=(stat.st_atime_ns,stat.st_mtime_ns));assert query()==accepted
   changed=bytearray(original);struct.pack_into('<Q',changed,36,17);root.write_bytes(changed);os.utime(root,ns=(stat.st_atime_ns,stat.st_mtime_ns));refusal('NESTEND 9 bus 0','GA_AUDIO_NESTED_CACHE')
   root.write_bytes(original[:-8]);os.utime(root,ns=(stat.st_atime_ns,stat.st_mtime_ns));refusal('NESTEND 9 bus 0','GA_AUDIO_NESTED_CACHE')
   root.write_bytes(original);os.utime(root,ns=(stat.st_atime_ns,stat.st_mtime_ns));assert query()==accepted
   backup=root.with_suffix('.held');root.rename(backup);root.mkdir();refusal('NESTEND 9 bus 0','GA_AUDIO_NESTED_CACHE');root.rmdir();backup.rename(root);assert query()==accepted
   result['cache_guards'].append(dict(marked_tail=tail,timestamp_rewrite=True,same_timestamp_bad_header=True,truncation=True,nonfile_path=True,restored_accepted_generation=accepted[0]));result['checks']+=1
  # Accepted source identity is source-bound at commit; new owner commits new generation.
  assert sha(source)==source_sha;result['source_sha256']=source_sha
  result['ffmpeg_sha256']=sha(tool(worker,'ffmpeg'));result['worker_sha256_end']=sha(worker);assert result['worker_sha256_end']==result['worker_sha256']
  result['passed']=True
 except Exception:
  result['failure']=traceback.format_exc();raise
 finally:
  p.close();result['worker_exit_code']=p.process.returncode;result['normal_owned_rf64_cleanup']=not list(cache.glob('*.rf64'));result['source_unchanged']=sha(source)==source_sha
  if not result['normal_owned_rf64_cleanup'] or not result['source_unchanged'] or p.process.returncode!=0:result['passed']=False
  report.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8');print(json.dumps({k:result[k] for k in ('passed','checks','pcm_values','worker_sha256','normal_owned_rf64_cleanup')},indent=2))
 assert result['passed'], '[GA_TEST_AUDIO_EOF_QUERY] worker exit, source identity or owned cache cleanup failed'
if __name__=='__main__':main()
