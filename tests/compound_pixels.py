import sys,subprocess,math,json,hashlib,threading,queue,argparse,tempfile,os
from pathlib import Path
from array import array
sys.path.insert(0,str(Path(__file__).resolve().parent))
from video_transfer import neutral
from preview_fit import wire
FLAGS=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0
parser=argparse.ArgumentParser(description="Independent native straight-RGBA group pixel oracle")
parser.add_argument('--worker',type=Path,required=True)
parser.add_argument('--reference-worker',type=Path)
parser.add_argument('--report',type=Path)
args=parser.parse_args()
temporary=tempfile.TemporaryDirectory(prefix='genesis-compound-pixels-')
root=Path(temporary.name);w=args.worker.resolve()
p=subprocess.Popen([str(w),'--serve','--size','64','64'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,encoding='utf-8',creationflags=FLAGS)
q=queue.Queue();errs=[]
threading.Thread(target=lambda:[q.put(x.strip()) for x in p.stdout],daemon=True).start()
threading.Thread(target=lambda:errs.extend(p.stderr),daemon=True).start()
checks=0;worst=0

def send(x):
 p.stdin.write(x+'\n');p.stdin.flush();r=q.get(timeout=30);assert r.startswith('DONE'),(x[:200],r,''.join(errs[-15:]));return r

def source(name,rgba,w=64,h=64):
 f=root/(name+'.f32');array('f',rgba*(w*h)).tofile(f.open('wb'));return 'FLOATDIM:'+str(w)+':'+str(h)+':'+wire(f)
def read(f):
 a=array('f');a.frombytes(f.read_bytes());return a

def picture(base,over='-',mode=0,op=1,changes=None):
 f=neutral();f[0]=base;f[1]=over;f[4]=str(op);f[5]=str(mode)
 for k,v in (changes or {}).items():f[k]=str(v)
 out=root/'result.f32';send('FLOAT '+' '.join(f)+' '+wire(out));return read(out)
def compare(a,expected):
 global checks,worst
 assert len(a)%4==0
 e=expected* (len(a)//4);d=max(abs(x-y) for x,y in zip(a,e));worst=max(worst,d);assert d<2e-6,(d,a[:4],expected);checks+=len(a)
def blend(b,o,m):
 return [o,b*o,1-(1-b)*(1-o),2*b*o if b<.5 else 1-2*(1-b)*(1-o),min(1,b+o),min(b,o),max(b,o),abs(b-o),max(0,b-o),2*b*o if o<.5 else 1-2*(1-b)*(1-o),b-(1-2*o)*b*(1-b) if o<=.5 else b+(2*o-1)*((((16*b-12)*b+4)*b if b<=.25 else math.sqrt(b))-b),1 if o>=1 else min(1,b/(1-o))][m]
try:
 send('CANVAS 64 64 1')
 b=[.2,.6,.8,.3];o=[.8,.3,.1,.6]
 bs=source('base',b);os=source('over',o)
 for m in range(12):
  ao=o[3]*.7;ab=b[3];a=ab+ao-ab*ao
  exp=[((1-ao)*ab*b[c]+(1-ab)*ao*o[c]+ab*ao*blend(b[c],o[c],m))/a for c in range(3)]+[a]
  compare(picture(bs,os,m,.7),exp)
 # No overlap coverage: Multiply on transparent base must retain child colour.
 transparent=source('hidden',[.9,.7,.5,0]);compare(picture(transparent,os,1),o)
 compare(picture(bs,changes={101:.4}),b[:3]+[.12])
 # Whole-image transition oracle with authored constant straightRGBA sources.
 for kind in range(11):
  t=.43;img=picture(bs,changes={16:kind,17:t,18:4,19:os,20:0})
  for y in range(64):
   for x in range(64):
    if kind==0:ww=t
    elif kind in (1,2,3,4):
     position=x if kind==1 else 63-x if kind==2 else 63-y if kind==3 else y
     ww=max(0,min(1,(t*64-position)/36+.5))
    elif kind==5:ww=float(0<=int(x-(1-t)*64+.5)<64)
    elif kind==6:ww=float(0<=int(32+(x-32)/(.25+.75*t)+.5)<64 and 0<=int(32+(y-32)/(.25+.75*t)+.5)<64)
    elif kind==7:ww=max(0,min(1,(t*1.25-(b[0]*.299+b[1]*.587+b[2]*.114))*4))
    elif kind==8:ww=float(math.hypot(x/64-.5,y/64-.5)<=t*.72)
    elif kind==9:ww=float((math.atan2(x/64-.5,-(y/64-.5))+math.pi)/(2*math.pi)<=t)
    else:ww=float(abs(x/64-.5)<=t*.5)
    ba=b[3]*(1-ww);oa=o[3]*ww;aa=ba+oa;exp=[(b[c]*ba+o[c]*oa)/aa for c in range(3)]+[aa]
    delta=max(abs(img[(y*64+x)*4+c]-exp[c]) for c in range(4));assert delta<2e-6,(kind,x,y,delta,img[(y*64+x)*4:(y*64+x)*4+4],exp);checks+=4;worst=max(worst,delta)
 # Mask changes onlycoverage, including feather on bottomgroup.
 img=picture(bs,changes={85:1,86:.5,87:.5,88:.3,89:.3,90:.4,91:0})
 for y in range(64):
  for x in range(64):
   dist=max(abs(((x+.5)/64-.5)/.3),abs(((y+.5)/64-.5)/.3));mask=1 if dist<=.6 else 0 if dist>=1 else (1-dist)/.4
   exp=b[:3]+[b[3]*mask];delta=max(abs(img[(y*64+x)*4+c]-exp[c]) for c in range(4));assert delta<2e-6,(x,y,delta);checks+=4
 # Gaussian must not let hidden red bleed into blue visible pixels.
 samples=[]
 for y in range(64):
  for x in range(64):samples.extend([1,0,0,0] if x<32 else [0,0,1,1])
 gf=root/'hidden-edge.f32';array('f',samples).tofile(gf.open('wb'))
 img=picture('FLOATDIM:64:64:'+wire(gf),changes={35:2})
 weights=[math.exp(-k*k/8) for k in range(-4,5)];total=sum(weights)
 for y in range(64):
  for x in range(64):
   alpha=sum(weight for k,weight in zip(range(-4,5),weights) if min(63,max(0,x+k))>=32)/total
   exp=[0,0,1 if alpha>0 else 0,alpha];delta=max(abs(img[(y*64+x)*4+c]-exp[c]) for c in range(4));assert delta<2e-6,(x,y,delta);checks+=4;worst=max(worst,delta)
 # Premultiplied transform bilinear samples ignore hidden red across boundary.
 img=picture('FLOATDIM:64:64:'+wire(gf),changes={34:.93})
 for y in range(64):
  for x in range(64):
   sx=((x+.5)-32)/.93+31.5;sy=((y+.5)-32)/.93+31.5;x0=math.floor(sx);y0=math.floor(sy)
   if x0+1<0 or y0+1<0 or x0>63 or y0>63:exp=[0]*4
   else:
    fx=sx-x0;a0=float(max(0,min(63,x0))>=32);a1=float(max(0,min(63,x0+1))>=32);aa=a0*(1-fx)+a1*fx;exp=[0,0,1 if aa>0 else 0,aa]
   delta=max(abs(img[(y*64+x)*4+c]-exp[c]) for c in range(4));assert delta<3e-6,(x,y,delta);checks+=4;worst=max(worst,delta)
 # Three successive child frames/canvases restore dimensions and retained pixels.
 for ww,hh in [(80,48),(48,80),(96,64),(64,96),(64,64)]:
  send(f'CANVAS {ww} {hh} 1');a=picture(bs);assert len(a)==ww*hh*4
  fit=min(ww/64,hh/64);fw=int(64*fit+.5);fh=fw;left=(ww-fw)//2;top=(hh-fh)//2
  for y in range(hh):
   for x in range(ww):
    exp=b if left<=x<left+fw and top<=y<top+fh else [0]*4
    d=max(abs(a[(y*ww+x)*4+c]-exp[c]) for c in range(4));assert d<2e-6,(ww,hh,x,y,d);checks+=4
 # OPAQUE multiplies coverage once at final root.
 send('CANVAS 64 64 0');compare(picture(bs.replace('FLOATDIM:','OPAQUE:',1)),[v*b[3] for v in b[:3]]+[1])
 # Malformed group failure must not become optional missing overlay success.
 f=neutral();f[0]=bs;f[1]='FLOATDIM:64:64:'+wire(root/'missing.f32');f[4]='1';out=root/'refused.f32'
 p.stdin.write('FLOAT '+' '.join(f)+' '+wire(out)+'\n');p.stdin.flush();assert q.get(timeout=30)=='ERR';assert not out.exists()
 compare(picture(bs.replace('FLOATDIM:','OPAQUE:',1)),[v*b[3] for v in b[:3]]+[1])
 # Missing ordinary media must identify SOURCE only inside group mode.
 send('CANVAS 64 64 1');mf=neutral();mf[0]=wire(root/'missing-ordinary.mkv');mo=root/'ordinary-refused.f32'
 p.stdin.write('FLOAT '+' '.join(mf)+' '+wire(mo)+'\n');p.stdin.flush();assert q.get(timeout=30)=='ERR' and not mo.exists()
 compare(picture(bs),b)
 # Wrong child geometry/mode never reaches the configured root encoder.
 movie=root/'root-encoder.mkv';opener='OPEN '+wire(movie)+' 64 64 30 1 0 0 ffv1 0 0 - 128000 pcm_s16le 30'
 send('CANVAS 80 48 1')
 p.stdin.write(opener+'\n');p.stdin.flush();assert q.get(timeout=30)=='ERR' and not movie.exists()
 send('CANVAS 64 64 0');send(opener)
 ef=neutral();ef[0]=bs.replace('FLOATDIM:','OPAQUE:',1);enc_request='ENC '+' '.join(ef)
 for ww,hh,mode in [(64,64,1),(80,48,0)]:
  send(f'CANVAS {ww} {hh} {mode}');p.stdin.write(enc_request+'\n');p.stdin.flush();assert q.get(timeout=30)=='ERR'
 send('CANVAS 64 64 0');send(enc_request);send('CLOSE')
 assert movie.exists() and movie.stat().st_size>0
finally:
 p.stdin.close();p.wait(timeout=10)
assert p.returncode==0,''.join(errs)
assert any('[GA_VIDEO_NESTED_SOURCE] Cannot open compound picture media' in line for line in errs),errs
receipt=dict(worker_sha256=hashlib.sha256(w.read_bytes()).hexdigest(),checks=checks,max_channel_error=worst,exit=p.returncode,alpha_blends=12,alpha_transitions=11,canvas_switches=5,mask_feather=True,premultiplied_gaussian=True,premultiplied_transform=True,encoder_wrong_canvas_refusals=3)
if args.reference_worker:
 # Legacy mode0 must match the accepted worker exactly. Pattern channels and
 # alpha vary independently to expose hidden changes in spatial sampling.
 raster=root/'legacy.f32';data=[]
 for y in range(64):
  for x in range(64): data.extend(((x%11)/10,(y%13)/12,((x+y)%17)/16,((x*3+y)%7)/6))
 array('f',data).tofile(raster.open('wb'));requests=[];cases=[{}]
 for i,v in [(10,.13),(11,1.4),(12,.7),(35,2),(47,.3),(48,.4),(56,2),(58,.6),(65,.4),(66,.3),(68,1),(72,.3),(75,1),(78,.2),(81,1),(85,1),(99,.4),(101,.5)]: cases.append({i:v})
 for k in range(11):cases.append({16:k,17:.43,18:4,19:'FLOAT:'+wire(raster)})
 for m in range(12):cases.append({1:'FLOAT:'+wire(raster),4:.6,5:m})
 results=[]
 for worker,label in [(args.reference_worker.resolve(),'accepted'),(w,'candidate')]:
  commands=[];paths=[]
  for n,changes in enumerate(cases):
   f=neutral();f[0]='FLOAT:'+wire(raster)
   for i,v in changes.items():f[i]=str(v)
   out=root/f'{label}{n}.f32';paths.append(out);commands.append('FLOAT '+' '.join(f)+' '+wire(out))
  r=subprocess.run([str(worker),'--serve','--size','64','64'],input='\n'.join(commands)+'\n',text=True,capture_output=True,timeout=60,creationflags=FLAGS)
  assert r.returncode==0 and len(r.stdout.splitlines())==len(cases) and all(x.startswith('DONE') for x in r.stdout.splitlines()),r.stderr[-3000:]
  results.append([x.read_bytes() for x in paths])
 assert results[0]==results[1], 'Legacy flat renderer bytes changed'
 receipt['legacy_byte_exact_cases']=len(cases)
 receipt['legacy_reference_sha256']=hashlib.sha256(args.reference_worker.read_bytes()).hexdigest()
if args.report:args.report.write_text(json.dumps(receipt,indent=2),encoding='utf-8')
print(json.dumps(receipt));temporary.cleanup()
