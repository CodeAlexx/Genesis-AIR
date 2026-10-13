"""Independent stationary-lower, distinct-side Blend/alpha UTRANS oracle."""
import argparse, hashlib, json, math, os, subprocess, traceback, queue, threading
from pathlib import Path
import numpy as np

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def wire(p):return str(p).replace('%','%25').replace(' ','%20')
def blend(b,o,m):
    if m==1:return b*o
    if m==2:return 1-(1-b)*(1-o)
    if m==3:return np.where(b<.5,2*b*o,1-2*(1-b)*(1-o))
    if m==4:return np.minimum(1,b+o)
    if m==5:return np.minimum(b,o)
    if m==6:return np.maximum(b,o)
    if m==7:return np.abs(b-o)
    if m==8:return np.maximum(0,b-o)
    if m==9:return np.where(o<.5,2*b*o,1-2*(1-b)*(1-o))
    if m==10:
        d=np.where(b<=.25,((16*b-12)*b+4)*b,np.sqrt(b))
        return np.where(o<=.5,b-(1-2*o)*b*(1-b),b+(2*o-1)*(d-b))
    if m==11:return np.where(o>=1,1,np.minimum(1,b/np.maximum(1-o,1e-30)))
    return o
def over(b,o,m):
    a=o[...,3:4];ba=b[...,3:4];ao=a+ba*(1-a)
    rgb=a*((1-ba)*o[...,:3]+ba*blend(b[...,:3],o[...,:3],m))+ba*(1-a)*b[...,:3]
    return np.concatenate((rgb/np.maximum(ao,1e-30),ao),axis=-1)
def expected(b,o,i,kind,t,om,im):
    h,w,_=b.shape;y,x=np.mgrid[:h,:w];sx=x.copy();sy=y.copy();q=np.full((h,w),t)
    if kind==1:q=np.clip((t*w-x)/36+.5,0,1)
    if kind==2:q=np.clip((t*w-(w-1-x))/36+.5,0,1)
    if kind==3:q=np.clip((t*h-(h-1-y))/36+.5,0,1)
    if kind==4:q=np.clip((t*h-y)/36+.5,0,1)
    if kind==5:
        sx=np.trunc(x-(1-t)*w+.5).astype(int);q=((sx>=0)&(sx<w)).astype(float)
    if kind==6:
        scale=.25+.75*t;sx=np.trunc(w*.5+(x-w*.5)/scale+.5).astype(int);sy=np.trunc(h*.5+(y-h*.5)/scale+.5).astype(int)
        q=((sx>=0)&(sx<w)&(sy>=0)&(sy<h)).astype(float)
    if kind==7:q=np.clip((t*(1+1/8)-(o[...,:3]*[.299,.587,.114]).sum(axis=-1))*8,0,1)
    if kind==8:q=(np.hypot(x/w-.5,y/h-.5)<=t*.72).astype(float)
    if kind==9:q=((np.arctan2(x/w-.5,-(y/h-.5))+math.pi)/(2*math.pi)<=t).astype(float)
    if kind==10:q=(np.abs(x/w-.5)<=t*.5).astype(float)
    i=i[np.clip(sy,0,h-1),np.clip(sx,0,w-1)]
    a=over(b,o,om);c=over(b,i,im);q=q[...,None]
    aa=a[...,3:4]*(1-q);ca=c[...,3:4]*q;alpha=aa+ca
    rgb=(a[...,:3]*aa+c[...,:3]*ca)/np.maximum(alpha,1e-30)
    return np.concatenate((rgb,alpha),axis=-1)

def main():
    p=argparse.ArgumentParser();p.add_argument('--worker',required=True);p.add_argument('--report',required=True);args=p.parse_args()
    report_path=Path(args.report).resolve();assert not report_path.exists(),report_path
    out=report_path.with_suffix('');out.mkdir(parents=True,exist_ok=False);worker=Path(args.worker).resolve()
    report={'schema':'genesis.upper_transition_protocol.v1','passed':False,'worker_sha256':sha(worker),'cases':0,'values':0,'threshold':2e-6,'maximum_error':0,'failures':[]}
    stderr=(out/'worker.stderr').open('wb')
    child=subprocess.Popen([str(worker),'--serve','--size','64','64'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=stderr,creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
    replies=queue.Queue()
    def collect():
        for value in child.stdout:replies.put(value)
        replies.put(b"")
    reader=threading.Thread(target=collect,daemon=True);reader.start()
    def command(line,success=True):
        child.stdin.write((line+'\n').encode());child.stdin.flush();reply=replies.get(timeout=10).decode().strip()
        assert reply.startswith('DONE') if success else reply=='ERR',(line,reply)
        return reply
    try:
        y,x=np.mgrid[:64,:64]
        b=np.stack(((x*5+y*3)%223/255,(x*2+y*7)%229/255,(x*9+y)%233/255,np.where(x%5==0,0,np.where(y%3==0,.2,1))),axis=-1).astype('<f4')
        o=np.stack(((x*7+y)%251/255,(x+y*11)%239/255,(x*3+y*5)%241/255,np.where(x%7==0,0,.4)),axis=-1).astype('<f4')
        i=np.stack(((x*3+y*9)%239/255,(x*7+y*2)%233/255,(x+y*7)%251/255,np.where(y%7==0,0,.7)),axis=-1).astype('<f4')
        paths=[]
        for name,a in [('lower',b),('outgoing',o),('incoming',i)]:
            path=out/(name+'.f32');path.write_bytes(a.tobytes());paths.append('FLOAT:'+wire(path))
        target=out/'result.f32'
        command('CANVAS 64 64 1')
        for kind in range(11):
            for om in range(12):
                im=(om+5)%12
                for t in (.17,.37,.63):
                    command(' '.join(['UTRANS',*paths,str(kind),str(t),'8',str(om),str(im),wire(target)]))
                    actual=np.fromfile(target,dtype='<f4').reshape(64,64,4)
                    want=expected(b.astype(float),o.astype(float),i.astype(float),kind,float(np.float32(t)),om,im)
                    error=float(np.max(np.abs(actual-want)));assert error<=report['threshold'],(kind,t,om,im,error)
                    report['maximum_error']=max(report['maximum_error'],error);report['values']+=actual.size;report['cases']+=1
        # Existing picture errors retire the whole epoch and restore root mode.
        # Assert untouched file output, then recover explicitly in a new epoch.
        command('PICBEGIN 7')
        command(' '.join(['UTRANS',*paths,'0','.37','8','1','2','GPU:7:1']))
        command(' '.join(['UTRANS','GPU:7:1',*paths[1:],'5','.37','8','3','7',wire(target)]))
        accepted=target.read_bytes()
        epoch=7
        for index,bad in [(4,'11'),(5,'NaN'),(7,'12'),(3,'GPU:7:999'),(9,'GPUOPAQUE:7:3')]:
            f=['UTRANS',f'GPU:{epoch}:1',*paths[1:],'5','.37','8','3','7',wire(target)];f[index]=bad
            command(' '.join(f),False);assert target.read_bytes()==accepted
            command('CANVAS 64 64 1')
            command(' '.join(['UTRANS',f'GPU:{epoch}:1',*paths[1:],'5','.37','8','3','7',wire(target)]),False)
            epoch+=1;command('CANVAS 64 64 1');command(f'PICBEGIN {epoch}')
            command(' '.join(['UTRANS',*paths,'0','.37','8','1','2',f'GPU:{epoch}:1']))
            command(' '.join(['UTRANS',f'GPU:{epoch}:1',*paths[1:],'5','.37','8','3','7',wire(target)]));assert target.read_bytes()==accepted
        command(f'PICABORT {epoch}')
        command(' '.join(['UTRANS',*paths,'0','.37','8','0','0',wire(target)]),False)
        assert target.read_bytes()==accepted
        # Reject source metadata/sample errors before any upload or sink write.
        # Each failed epoch recovers through explicit canvas selection; no silent
        # decoder/media fallback or partial accepted output is allowed.
        bad_samples=b.copy();bad_samples[0,0,0]=np.nan
        bad_alpha=b.copy();bad_alpha[0,0,3]=1.1
        for name,body in [('short',b.tobytes()[:-4]),('oversize',b.tobytes()+b'\0\0\0\0'),('nonfinite',bad_samples.tobytes()),('alpha',bad_alpha.tobytes())]:
            file=out/f'refused-{name}.f32';file.write_bytes(body)
            command('CANVAS 64 64 1');before=target.read_bytes()
            command(' '.join(['UTRANS','FLOAT:'+wire(file),*paths[1:],'0','.37','8','1','2',wire(target)]),False)
            assert target.read_bytes()==before,name
            command('CANVAS 64 64 1')
            command(' '.join(['UTRANS',*paths,'0','.37','8','1','2',wire(target)]))
        report['source_refusals']=4
        # More than the four cached canvases exercises creation, restoration,
        # eviction and release of the new per-canvas kernel without new buffers.
        for dim in (32,48,80,96,112,64):
            yy,xx=np.mgrid[:dim,:dim]
            values=[a[yy%64,xx%64] for a in (b,o,i)]
            resized=[]
            for slot,a in enumerate(values):
                file=out/f'canvas-{dim}-{slot}.f32';file.write_bytes(a.tobytes());resized.append('FLOAT:'+wire(file))
            command(f'CANVAS {dim} {dim} 1')
            command(' '.join(['UTRANS',*resized,'0','.37','4','1','2',wire(target)]))
            actual=np.fromfile(target,dtype='<f4').reshape(dim,dim,4)
            want=expected(*(a.astype(float)for a in values),0,float(np.float32(.37)),1,2)
            assert float(np.max(np.abs(actual-want)))<=report['threshold'],dim
        report.update(passed=True,malformed_recovery=5,mode_refusal=True,snapshot_epoch_abort_preserved=True,canvas_creation_restore_eviction_cases=6,canvas_pixel_values=sum(d*d*4 for d in(32,48,80,96,112,64)))
    except Exception:
        report['failures'].append(traceback.format_exc());raise
    finally:
        child.stdin.close()
        try:child.wait(timeout=10)
        except subprocess.TimeoutExpired:
            child.kill();child.wait(timeout=5);report['passed']=False;report['failures'].append('Worker did not exit after stdin close')
        reader.join(timeout=1);stderr.close();report['worker_exit']=child.returncode
        if child.returncode!=0:report['passed']=False;report['failures'].append(f'Worker exit {child.returncode}')
        codes=(out/'worker.stderr').read_text(encoding='utf-8',errors='replace')
        if codes.count('[GA_VIDEO_TRANSITION_SOURCE]')<4 or codes.count('[GA_VIDEO_TRANSITION_PROTOCOL]')<4 or '[GA_VIDEO_SNAPSHOT_REFERENCE]'not in codes:
            report['passed']=False;report['failures'].append('Missing coded refusal diagnostics')
        report['inputs']={p.name:sha(p)for p in out.glob('*.f32')if p.name!='result.f32'}
        with report_path.open('x',encoding='utf-8')as output:output.write(json.dumps(report,indent=2)+'\n')
    assert report['passed'],report['failures']
    print(json.dumps(report,indent=2))
if __name__=='__main__':main()
