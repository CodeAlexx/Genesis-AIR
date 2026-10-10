"""Independent immutable GPU picture protocol and pixel oracle."""
import argparse,hashlib,json,math,os,queue,socket,struct,subprocess,sys,tempfile,threading
from array import array
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent.parent/'tests'))
from video_transfer import neutral
from preview_fit import wire
from media_runtime import tool
p=argparse.ArgumentParser();p.add_argument('--worker',type=Path,required=True);p.add_argument('--report',type=Path,required=True);a=p.parse_args()
worker=a.worker.resolve();before=hashlib.sha256(worker.read_bytes()).hexdigest();checks=0;cases=[];errors=[]
temp=tempfile.TemporaryDirectory(prefix='genesis-snapshot-protocol-');root=Path(temp.name)
child=subprocess.Popen([str(worker),'--serve','--size','64','36'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,encoding='utf-8',errors='replace',creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
replies=queue.Queue();threading.Thread(target=lambda:[replies.put(x.strip()) for x in child.stdout],daemon=True).start();threading.Thread(target=lambda:errors.extend(child.stderr),daemon=True).start()
epoch=0
def send(line,ok=True):
 global checks
 child.stdin.write(line+'\n');child.stdin.flush();reply=replies.get(timeout=30);checks+=1
 assert reply.startswith('DONE') if ok else reply=='ERR',(line[:180],reply,''.join(errors[-12:]));return reply
def begin():
 global epoch
 epoch+=1;send(f'PICBEGIN {epoch}');return epoch
def fields(base,over='-',**changes):
 f=neutral();f[0]=base;f[1]=over
 for k,v in changes.items():f[int(k)]=str(v)
 return ' '.join(f)
def store(id,base,over='-',changes=None):send('FLOAT '+fields(base,over,**(changes or {}))+f' GPU:{epoch}:{id}');return f'GPU:{epoch}:{id}'
def capture(base,over='-',changes=None,kind='FLOAT'):
 out=root/'result 日本語 %20.f32';send(kind+' '+fields(base,over,**(changes or {}))+' '+wire(out));raw=out.read_bytes()
 if kind!='FLOAT':return raw
 data=array('f');data.frombytes(raw);assert all(math.isfinite(x) for x in data);return data
def source(name,w,h,func):
 f=root/(name+' 日本語 %20.f32');v=array('f',(c for y in range(h) for x in range(w) for c in func(x,y)))
 with f.open('wb') as stream:v.tofile(stream)
 return f'FLOATDIM:{w}:{h}:{wire(f)}',v
def compare(data,expected,tol=2e-6):
 global checks
 assert len(data)==len(expected),(len(data),len(expected));worst=max(abs(x-y) for x,y in zip(data,expected));assert worst<=tol,(worst,data[:8],expected[:8]);checks+=len(data);return worst
def constant(v,w=64,h=36):return v*(w*h)
def fit(data,sw,sh,dw,dh,opaque=False):
 factor=min(dw/sw,dh/sh);fw=math.floor(sw*factor+.5);fh=math.floor(sh*factor+.5);left=(dw-fw)//2;top=(dh-fh)//2;out=[]
 for y in range(dh):
  for x in range(dw):
   if left<=x<left+fw and top<=y<top+fh:
    sx=(x-left)*sw//fw;sy=(y-top)*sh//fh;px=list(data[(sy*sw+sx)*4:(sy*sw+sx)*4+4])
    if opaque:px=[v*px[3] for v in px[:3]]+[1.]
   else:px=[0.,0.,0.,1. if opaque else 0.]
   out.extend(px)
 return out
def case(name):cases.append(name)
passed=False
try:
 base,b=source('base',64,36,lambda x,y:[.2,.6,.8,.3]);over,o=source('over',64,36,lambda x,y:[.8,.3,.1,.6])
 begin();send('CANVAS 64 36 1');one=store(1,base);two=store(2,over)
 ao=.6*.7;ab=.3;alpha=ab+ao-ab*ao;expected=[(.8*ao+.2*ab*(1-ao))/alpha,(.3*ao+.6*ab*(1-ao))/alpha,(.1*ao+.8*ab*(1-ao))/alpha,alpha]
 compare(capture(one,two,{'4':.7}),constant(expected));case('same-size-siblings-straight-alpha')
 send('FLOAT '+fields(one)+' '+wire(root/'stale.f32'),False);assert not(root/'stale.f32').exists();case('terminal-auto-release-stale-refusal')
 begin();send('CANVAS 64 36 1');one=store(1,base);two=store(2,over);summed=store(3,one,two,{'4':.7});graded=store(4,summed,changes={'27':2,'28':2,'29':2});compare(capture(graded),constant([math.sqrt(x) for x in expected[:3]]+[expected[3]]));case('nonlinear-parent-on-completed-sum')
 begin();send('CANVAS 64 36 1');store(1,base);send(f'PICDROP {epoch} 1');send('FLOAT '+fields(base)+f' GPU:{epoch}:1',False);case('dropped-id-cannot-be-redefined')
 begin();send('CANVAS 64 36 1');one=store(1,base);send('CANVAS 80 48 1');send('FLOAT '+fields(one)+' '+wire(root/'wrong-dim.f32'),False);assert not(root/'wrong-dim.f32').exists();case('exact-canvas-refusal')
 portrait,v=source('portrait',32,64,lambda x,y:[x/64,y/128,(x+y)/192,.25+.5*((x+y)%2)])
 begin();send('CANVAS 32 64 1');store(1,portrait)
 for n in range(8):send(f'CANVAS {80+n*2} {48+n*2} 1')
 send('CANVAS 64 36 1');compare(capture(f'GPUDIM:{epoch}:1'),fit(v,32,64,64,36));case('portrait-fit-survives-four-canvas-LRU')
 begin();send('CANVAS 32 64 1');store(1,portrait);send('CANVAS 64 36 0');compare(capture(f'GPUOPAQUE:{epoch}:1'),fit(v,32,64,64,36,True));case('black-flatten-once')
 # Ordered operators preserve clipping and nonlinear order on a saved snapshot.
 begin();send('CANVAS 64 36 1');one=store(1,base,changes={'10':.1});two=store(2,one,changes={'11':1.2});compare(capture(two),constant([.26,.74,.98,.3]));case('ordered-brightness-contrast')
 begin();send('CANVAS 64 36 1');one=store(1,base,changes={'11':1.2});two=store(2,one,changes={'10':.1});compare(capture(two),constant([.24,.72,.96,.3]));case('reverse-noncommutative-order')
 begin();send('CANVAS 64 36 1');one=store(1,base,changes={'10':.1});two=store(2,one,changes={'10':.1});compare(capture(two),constant([.4,.8,1.,.3]));case('duplicate-brightness')
 # Repeated begin retires all old refs, even if a newframe reuses localID1.
 old=begin();send('CANVAS 64 36 1');store(1,base);begin();send('CANVAS 64 36 1');store(1,over)
 send('FLOAT '+fields(f'GPU:{old}:1')+' '+wire(root/'previous-frame.f32'),False);assert not(root/'previous-frame.f32').exists();case('old-epoch-cannot-alias-new-same-ID')
 begin();send('CANVAS 64 36 1');store(1,base);send(f'PICABORT {epoch}');send(f'PICDROP {epoch} 1',False)
 compare(capture(base),constant([.2,.6,.8,.3]));case('abort-restores-root-legacy')
 # Inactive overlays and transition tokens must not hide stale-reference errors.
 begin();send('CANVAS 64 36 1');send('FLOAT '+fields(base,f'GPU:{epoch-1}:1',**{'4':0})+' '+wire(root/'ignored-over.f32'),False);assert not(root/'ignored-over.f32').exists();case('inactive-overlay-stale-refusal')
 begin();send('FLOAT '+fields(base,**{'19':f'GPU:{epoch-1}:1','16':-1})+' '+wire(root/'ignored-transition.f32'),False);assert not(root/'ignored-transition.f32').exists();case('inactive-transition-stale-refusal')
 send(f'PICBEGIN {epoch}',False);send('PICBEGIN 0',False);send('PICBEGIN -1',False);case('monotonic-epoch-validation')
 begin();send('CANVAS 64 36 1');store(1,base);pix=capture(f'GPU:{epoch}:1',kind='PREVIEW');assert len(pix)==64*36*4;send(f'PICDROP {epoch} 1',False);case('preview-terminal-release')
 # A malformed input must fail before creating a caller output.
 begin();send('FLOAT '+fields('GPU:1:2:3')+' '+wire(root/'malformed.f32'),False);assert not(root/'malformed.f32').exists();case('malformed-reference-refusal')
 # The real binary monitor terminal must retain its existing40byte identity header.
 begin();send('CANVAS 64 36 1');store(1,base);send('CANVAS 64 36 0')
 with socket.socket() as listener:
  listener.bind(('127.0.0.1',0));listener.listen(1);listener.settimeout(5)
  send(f'PREVIEWTCP 64 36 {listener.getsockname()[1]} 17 {epoch} '+fields(f'GPUOPAQUE:{epoch}:1')+' '+wire(root/'unused.rgba'))
  conn,_=listener.accept();conn.settimeout(5)
  with conn:
   data=b''
   while len(data)<40+64*36*4:
    part=conn.recv(65536);assert part;data+=part
  assert struct.unpack('<8sQQIIQ',data[:40])==(b'GAPIX001',17,epoch,64,36,64*36*4)
  assert data[40:]==bytes([15,46,61,255])*(64*36);checks+=len(data);send(f'PICDROP {epoch} 1',False);case('PREVIEWTCP-header-pixels-terminal-release')
 movie=root/'snapshot-master.mkv';send('CANVAS 64 36 0');send('OPEN '+wire(movie)+' 64 36 30 1 0 0 ffv1 0 0 - 128000 pcm_s16le 30')
 begin();send('CANVAS 64 36 1');store(1,base);send('CANVAS 64 36 0');send('ENC '+fields(f'GPUOPAQUE:{epoch}:1'));send(f'PICDROP {epoch} 1',False);send('CLOSE')
 decoded=subprocess.check_output([str(tool(worker,'ffmpeg')),'-nostdin','-v','error','-i',str(movie),'-frames:v','1','-f','rawvideo','-pix_fmt','rgba64le','pipe:1'],creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
 values=array('H');values.frombytes(decoded);compare([x/65535 for x in values],constant([.06,.18,.24,1.]),3/65535);case('encoder-terminal-lossless-pixels')
 begin();send('CANVAS 64 36 1');store(1,base);case('EOF-with-active-snapshot-shutdown')
 passed=True
finally:
 try:child.stdin.close();child.wait(timeout=5)
 except Exception:child.kill();child.wait(timeout=5)
 after=hashlib.sha256(worker.read_bytes()).hexdigest()
 a.report.parent.mkdir(parents=True,exist_ok=True)
 a.report.write_text(json.dumps(dict(passed=passed,cases=cases,checks=checks,worker_sha256=before,worker_end_sha256=after,unchanged=before==after,worker_exit=child.returncode,diagnostics=errors[-30:]),indent=2))
 temp.cleanup()
print(json.dumps(dict(passed=passed,cases=len(cases),checks=checks,report=str(a.report))))
