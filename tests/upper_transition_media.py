"""Bounded authored side-effects/lower-gap oracle; shared MM runtime only."""
import argparse,copy,hashlib,json,os,subprocess,sys,traceback
from pathlib import Path
import numpy as np
from media_runtime import tool
from PIL import Image
from preview_fit import fitted
from upper_transition_protocol import expected,over
KINDS=('crossfade','wipe_lr','wipe_rl','wipe_up','wipe_down','slide_lr','zoom','dissolve','iris','clock','barn_door')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def run(args,env=None):
    r=subprocess.run(list(map(str,args)),env=env,capture_output=True,timeout=90,creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
    assert r.returncode==0,(args,r.returncode,r.stdout[-1000:],r.stderr[-2000:]);return r.stdout
def parameter(doc,clip,kind,values):
    fid=doc['next_id'];doc['next_id']+=1
    doc['filters'].append(dict(id=fid,clip=clip,kind=kind,enabled=True,order=sum(f['clip']==clip for f in doc['filters'])))
    doc['filter_params'] += [dict(filter=fid,name=k,value=v)for k,v in values.items()];return fid
def curve(doc,clip,name,values):
    # Serialized name ids follow the public editor interner: equal semantic
    # names share one id. Duplicating opacity here would leave the second
    # clip's keys unreachable through editor.name_id, rather than test a curve.
    if name not in doc['names']:doc['names'].append(name)
    pid=doc['names'].index(name)+1
    doc['keys'] += [dict(clip=clip,owner=2,param=pid,frame=f,value=v,interp=2)for f,v in values]
def source_rgb(which):
    y,x=np.mgrid[:64,:64]
    if which==0:return np.stack(((x*5+y*3)%220+15,(x*2+y*7)%220+15,(x*9+y)%220+15),axis=-1).astype(np.uint8)
    c=np.full((64,64,3),(230,30,50)if which==1 else(20,60,220),dtype=np.uint8)
    c[(x<16) if which==1 else(y<16)]=(0,255,0);return c
def prepared(mode,which,frame):
    local=np.clip(frame-(0 if which==1 else 12),0,11)
    rgb=source_rgb(which).astype(float)/255
    alpha=np.full((64,64,1),.4 if which==1 else .7)
    if mode=='operators':
        alpha[np.all(source_rgb(which)==(0,255,0),axis=-1)]=0
        x0,y0,w,h=(.125,.25,.625,.5)if which==1 else(.375,.125,.5,.75)
        y,x=np.mgrid[:64,:64];inside=(x/64>=x0)&(x/64<x0+w)&(y/64>=y0)&(y/64<y0+h)
        sx=np.clip(((x/64-x0)/w*64).astype(int),0,63);sy=np.clip(((y/64-y0)/h*64).astype(int),0,63)
        rgba=np.concatenate((rgb,alpha),axis=-1)[sy,sx];rgba[~inside]=0;return rgba
    if which==1:
        rgb=np.clip((rgb-.5)*1.4+.5,0,1);rgb=np.clip(rgb+.02+.10*local/11,0,1)
        alpha[:]=.4+.4*local/11
    else:
        rgb=np.clip(rgb+.05,0,1);rgb=np.clip((rgb-.5)*1.5+.5,0,1);alpha[:]=.7-.4*local/11
    return np.concatenate((rgb,alpha),axis=-1)
def document(paths):
    sources=[dict(id=70+i,path=str(p),name=p.name,bin=1,frames=36,fps=30,width=64,height=64,has_video=True,has_audio=False,audio_rate=0,audio_channels=0,online=True)for i,p in enumerate(paths)]
    tracks=[dict(id=j,owner=2,kind=0,name=f'Video{j-4}',order=j-5,hidden=False,muted=False,locked=False,solo=False,gain=1,pan=0,height=44)for j in(5,6)]
    clips=[dict(id=i,owner=2,source=src,nested=0,source_in=0,length=length,start=start,track=track,group=0,enabled=True,selected=False,fade_in=0,fade_out=0,gain=1,pan=0,speed=1,reverse=False,streams=1)for i,src,length,start,track in((82,70,24,0,5),(80,71,12,0,6),(81,72,12,12,6))]
    return dict(schema='air.editor.project',revision=2,active=2,source_bounds=0,monitor_source=70,next_id=200,program=dict(playing=False,frame=12,mark_in=-1,mark_out=-1,rate=1,looping=False),monitor=dict(playing=False,frame=0,mark_in=-1,mark_out=-1,rate=1,looping=False),sources=sources,bins=[dict(id=1,name='Authored media',parent=0)],sequences=[dict(id=2,name='Independent upper-side composition',fps=30,width=64,height=64)],tracks=tracks,clips=clips,transitions=[dict(id=100,owner=2,track=6,center=12,duration=6,kind=1)],keys=[],markers=[],subtitles=[],filters=[],filter_params=[],filter_text_params=[],names=['crossfade'])

def side_graph(doc,mode):
    for clip,which in ((80,1),(81,2)):
        parameter(doc,clip,'blend',{'mode':3 if which==1 else 2})
        if mode=='operators':
            x,y,w,h=(.125,.25,.625,.5)if which==1 else(.375,.125,.5,.75)
            parameter(doc,clip,'size_position',dict(x=x,y=y,w=w,h=h))
            parameter(doc,clip,'chroma_key',dict(hue=120,tolerance=.01,softness=.01))
            curve(doc,clip,'opacity',[(0,.4 if which==1 else .7)])
        elif which==1:
            parameter(doc,clip,'contrast',{'level':1.4});fid=parameter(doc,clip,'brightness',{'level':1.02})
            curve(doc,clip,f'filter.{fid}.brightness.level',[(0,1.02),(11,1.12)])
            curve(doc,clip,'opacity',[(0,.4),(11,.8)])
        else:
            parameter(doc,clip,'brightness',{'level':1.05});parameter(doc,clip,'contrast',{'level':1.5})
            curve(doc,clip,'opacity',[(0,.7),(11,.3)])

def reference(mode,shape,code,frame):
    lower=source_rgb(0).astype(float)/255
    present=shape=='complete' or(shape=='ending'and frame<12)or(shape=='starting'and frame>=12)or(shape=='middle-gap'and(frame<10 or frame>=14))
    b=np.concatenate((lower,np.full((64,64,1),int(present))),axis=-1)
    o=prepared(mode,1,frame);i=prepared(mode,2,frame)
    if frame<9:want=over(b,o,1)
    elif frame>=15:want=over(b,i,2)
    elif code==7:
        q=np.clip(((frame-9)/6*1.25-(o[...,:3]*[.299,.587,.114]).sum(-1))*4,0,1)[...,None]
        a=over(b,o,1);z=over(b,i,2);aa=a[...,3:4]*(1-q);za=z[...,3:4]*q;coverage=aa+za
        want=np.concatenate(((a[...,:3]*aa+z[...,:3]*za)/np.maximum(coverage,1e-30),coverage),-1)
    else:want=expected(b,o,i,code,(frame-9)/6,1,2)
    want[...,:3]*=want[...,3:4];want[...,3]=1
    return np.floor(np.clip(want,0,1)*255+.5).astype(np.int16)

def main():
    p=argparse.ArgumentParser();p.add_argument('--binary',required=True);p.add_argument('--worker',required=True);p.add_argument('--report',required=True);args=p.parse_args()
    report_path=Path(args.report).resolve();assert not report_path.exists(),report_path
    out=report_path.with_suffix('');out.mkdir(parents=True,exist_ok=False)
    app=Path(args.binary).resolve();worker=Path(args.worker).resolve()
    env=dict(os.environ,GENESIS_GCOMPOSE=str(worker),GENESIS_SCRATCH=str(out/'scratch'));env.pop('GENESIS_FAKE_PROVIDER',None)
    ffmpeg=tool(worker,'ffmpeg')
    report=dict(schema='genesis.upper_transition_media.v1',passed=False,binary_sha256=sha(app),worker_sha256=sha(worker),ffmpeg_sha256=sha(ffmpeg),cases=[],frames=0,values=0,previews=0,threshold_rgb8=3,maximum_error=0,failures=[],independent_reference='Authored spatialRGB/geometry/chroma/ordered-scoped-key math; each side blends against the same stationary lower, transparent where absent. Full24-frame exports include ordinary before/after bodies. No Genesis reference renders.')
    try:
        paths=[]
        for which in range(3):
            raw=out/f'authored-{which}.rgb';media=out/f'authored-{which}.mkv';raw.write_bytes(source_rgb(which).tobytes()*36)
            run([ffmpeg,'-nostdin','-v','error','-f','rawvideo','-pixel_format','rgb24','-video_size','64x64','-framerate','30','-i',raw,'-frames:v','36','-c:v','ffv1','-pix_fmt','bgr0',media]);paths.append(media)
        base=document(paths)
        cases=[('operators',shape,kind,code)for shape in('ending','starting','middle-gap')for kind,code in(('crossfade',0),('slide_lr',5),('zoom',6),('dissolve',7),('wipe_lr',1))]
        cases.extend(('ordered-keys','complete',kind,code)for kind,code in(('crossfade',0),('slide_lr',5)))
        for mode,shape,kind,code in cases:
            doc=copy.deepcopy(base);doc['names']=[kind];side_graph(doc,mode)
            low=next(v for v in doc['clips']if v['id']==82)
            if shape=='ending':low['length']=12
            elif shape=='starting':low.update(start=12,length=12)
            elif shape=='middle-gap':
                low['length']=10;tail=copy.deepcopy(low);tail.update(id=83,start=14,length=10);doc['clips'].append(tail)
            project=out/f'{mode}-{shape}-{kind}.air';project.write_text(json.dumps(doc,ensure_ascii=False),encoding='utf-8');movie=project.with_suffix('.mkv')
            run([app,'export',movie,project],env)
            raw=run([ffmpeg,'-nostdin','-v','error','-i',movie,'-an','-f','rawvideo','-pix_fmt','rgba','pipe:1'])
            actual=np.frombuffer(raw,np.uint8).reshape(24,64,64,4);worst=0
            for frame in range(24):
                want=reference(mode,shape,code,frame);error=int(np.max(np.abs(actual[frame].astype(np.int16)-want)))
                assert error<=3,(mode,shape,kind,frame,error)
                worst=max(worst,error);report['frames']+=1;report['values']+=actual[frame].size
                if mode=='ordered-keys'and frame in(9,12,14):
                    doc['program']['frame']=frame;project.write_text(json.dumps(doc,ensure_ascii=False),encoding='utf-8');png=out/f'{mode}-{shape}-{kind}-{frame}.png'
                    run([app,'preview',png,project],env)
                    with Image.open(png)as pic:shown=pic.convert('RGBA').tobytes();assert pic.size==(640,360)
                    fit=fitted(actual[frame].tobytes(),64,64,640,360);assert max(abs(a-b)for a,b in zip(shown,fit))<=2
                    report['previews']+=1
            report['maximum_error']=max(report['maximum_error'],worst)
            report['cases'].append(dict(mode=mode,shape=shape,kind=kind,maximum_error=worst,project_sha256=sha(project),movie_sha256=sha(movie)))
        left=[str(p)for p in(out/'scratch').rglob('*')if p.is_file()and any(v in p.name for v in('.lane-count','.side-out','.side-in','.output.rgba','.preclip','.title','.ordered'))]
        assert not left,left
        report.update(passed=True,owned_side_scratch_cleaned=True,authored_media=[dict(path=p.name,sha256=sha(p))for p in paths])
    except Exception:report['failures'].append(traceback.format_exc());raise
    finally:
        with report_path.open('x',encoding='utf-8')as f:f.write(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))
if __name__=='__main__':main()

