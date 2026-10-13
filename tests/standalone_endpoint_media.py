"""Independent actual-EOF no-carrier proof for the private host integration."""
import argparse,copy,hashlib,json,subprocess,wave,os
from pathlib import Path
import numpy as np
from audio_mix_project import document
from audio_nested import effect
from media_runtime import tool
SR=48000;SPF=1600;BODY=96000
SEGMENTS={"unedited":[(0,60,0,True)],"split":[(0,30,0,False),(30,30,30,True)],"head":[(15,45,15,True)],"interior":[(0,15,0,False),(45,15,45,True)],"tail":[(0,30,0,False)],"moved":[(0,30,0,False),(30,30,60,True)],"repeated":[(0,30,0,False),(40,15,40,False)],"saveopen":[(0,30,0,False),(30,30,30,True)]}
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def run(argv,**kw):
 p=subprocess.run(list(map(str,argv)),capture_output=True,timeout=120,creationflags=0x08000000 if os.name=="nt" else 0,**kw)
 assert p.returncode==0,(argv,p.returncode,p.stdout[-2000:],p.stderr[-2000:]);return p.stdout

def pcm(p):
 with wave.open(str(p),'rb') as f:
  assert(f.getnchannels(),f.getsampwidth(),f.getframerate())==(2,2,SR)
  return np.frombuffer(f.readframes(f.getnframes()),dtype='<i2').reshape(-1,2).copy()
def quantize(v):return (np.sign(v)*np.floor(np.abs(np.clip(v,-1,1))*32767+.5)).astype(np.int16)
def compare(a,e,name):
 assert a.shape==e.shape,(name,a.shape,e.shape)
 err=int(np.max(np.abs(a.astype(np.int32)-e.astype(np.int32)),initial=0));assert err<=1,(name,err);return a.size,err

def variant_graph(doc,name):
 d=copy.deepcopy(doc);d['clips']=[];d['filters']=[];d['filter_params']=[]
 d['revision']=2 if name=='unedited' else 3
 for i,(offset,length,start,final) in enumerate(SEGMENTS[name]):
  c=copy.deepcopy(doc['clips'][0]);c.update(id=20+i,length=length,start=start,source_in=offset,streams=2)
  if name!='unedited':c['audio_context']=dict(source_in=0,length=60,offset=offset,fps=30,rate=1,reverse=False,origin=0,crop_start=offset*SPF,output_frames=BODY)
  d['clips'].append(c)
  for j,f in enumerate(doc['filters']):
   ff=copy.deepcopy(f);ff.update(id=100+i*10+j,clip=c['id']);d['filters'].append(ff)
   for p in doc['filter_params']:
    if p['filter']==f['id']:
     pp=copy.deepcopy(p);pp['filter']=ff['id'];d['filter_params'].append(pp)
 d['next_id']=200;return d

def expected(full,name):
 end=max((start+length)*SPF+(len(full)-BODY if final else 0) for offset,length,start,final in SEGMENTS[name])
 e=np.zeros((end,2),dtype=np.float32)
 for offset,length,start,final in SEGMENTS[name]:
  e[start*SPF:(start+length)*SPF]+=full[offset*SPF:(offset+length)*SPF]
  if final:e[(start+length)*SPF:(start+length)*SPF+len(full)-BODY]+=full[BODY:]
 return e

def main():
 p=argparse.ArgumentParser();p.add_argument('--worker',type=Path,required=True);p.add_argument('--client',type=Path,required=True);p.add_argument('--report',type=Path,required=True);p.add_argument('--work',type=Path,required=True);a=p.parse_args()
 assert not a.report.exists() and not a.work.exists();a.work.mkdir(parents=True)
 r=dict(schema='genesis.private.standalone-eof.v1',passed=False,worker_sha256=sha(a.worker),client_sha256=sha(a.client),checker_sha256=sha(__file__),cases=[],witnesses=[],reference='Authored PCM -> independent ordered MM-AIR DSP actual EOF; no carrier, Genesis output, body cap, or padding')
 try:
  t=np.arange(BODY)/SR;amp=np.where(t<.45,.18,np.where(t<1.55,.025,.24));raw=np.column_stack((amp*np.sin(2*np.pi*173*t),.79*amp*np.cos(2*np.pi*317*t)));v=np.rint(raw*32767).astype('<i2')
  source=a.work/'source.wav'
  with wave.open(str(source),'wb') as f:f.setparams((2,2,SR,0,'NONE','not compressed'));f.writeframes(v.tobytes())
  original=sha(source);ffmpeg=tool(a.worker,'ffmpeg');r['ffmpeg_sha256']=sha(ffmpeg)
  delay=('delay',dict(time=350,decay=.4),'aecho=0.8:0.9:350:0.4');reverb=('reverb',dict(amount=.35,room=.8),'aecho=0.8:0.9:61|126|196|274:0.175|0.14|0.105|0.07');comp=('compressor',dict(threshold=-18,ratio=4,attack=12,release=250),'acompressor=threshold='+str(10**(-18/20))+':ratio=4:attack=12:release=250')
  for name,fx in [('delay',[delay]),('reverb',[reverb]),('delay-compressor',[delay,comp]),('compressor-delay',[comp,delay])]:
   doc=document([source],(0,));doc['sources'][0]['frames']=60;doc['clips'][0].update(length=60,streams=2)
   for j,(kind,params,_) in enumerate(fx):effect(doc,20,kind,params,50+j);doc['filters'][-1]['order']=j
   data=run([ffmpeg,'-nostdin','-v','error','-f','f32le','-ar',SR,'-ac',2,'-i','pipe:0','-af',','.join(q[2] for q in fx)+',aformat=sample_fmts=flt:sample_rates=48000:channel_layouts=stereo','-f','f32le','pipe:1'],input=(v.astype(np.float32)/32768).astype('<f4').tobytes())
   full=np.frombuffer(data,dtype='<f4').reshape(-1,2).copy();assert BODY<len(full)<=BODY+5*SR and np.count_nonzero(full[BODY:])>100
   (a.work/(name+'-reference.f32')).write_bytes(data);r['witnesses'].append(dict(name=name,actual_frames=len(full),nonzero_tail_values=int(np.count_nonzero(full[BODY:]))))
   for var in SEGMENTS:
    label=name+'-'+var;out=a.work/label;out.mkdir();project=out/'input.air';g=variant_graph(doc,var);project.write_text(json.dumps(g),encoding='utf8');before=sha(project)
    run([a.client,a.worker,project,out]);assert sha(project)==before
    e=expected(full,var);actual=np.concatenate([pcm(q) for q in (out/'pulls.txt').read_text().splitlines()]);count,err=compare(actual,quantize(e),label)
    f=(out/'endpoint.air').read_text().splitlines()[0].split();authored=max((start+length)*SPF for offset,length,start,final in SEGMENTS[var]);presentation=(max(authored,len(e))+SPF-1)//SPF
    assert (int(f[2]),int(f[3]),int(f[4]))==(authored,len(e),presentation),(label,f,authored,len(e),presentation)
    if authored+17<len(e):compare(pcm(out/'postbody.wav'),quantize(e[authored+17:authored+17+4093]),label+'-postbody')
    saved=json.loads((out/'saved.air').read_text());assert[(c['start'],c['length']) for c in saved['clips']]==[(c['start'],c['length']) for c in g['clips']]
    if var=='saveopen':
     again=out/'reopened';again.mkdir();run([a.client,a.worker,out/'saved.air',again]);compare(np.concatenate([pcm(q) for q in (again/'pulls.txt').read_text().splitlines()]),quantize(e),label+'-reopened')
    assert not list(out.rglob('*.rf64'));r['cases'].append(dict(name=label,pcm_values=count,max_error_codes=err,authored_end=authored,actual_eof=len(e),presentation_frames=presentation,no_carrier=True))
  assert sha(source)==original;r['passed']=True;r['cases_count']=len(r['cases']);r['pcm_values']=sum(c['pcm_values'] for c in r['cases'])
 except BaseException as exc:r['error']=repr(exc);raise
 finally:a.report.write_text(json.dumps(r,indent=2)+'\n',encoding='utf8')
if __name__=='__main__':main()
