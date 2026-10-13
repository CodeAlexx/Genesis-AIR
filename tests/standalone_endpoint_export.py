"""Private exact accepted-EOF export oracle; no carrier or ceil-PCM padding."""
import argparse,copy,json,subprocess,os
from pathlib import Path
import numpy as np
from standalone_endpoint_media import sha,run
from media_runtime import tool

def main():
 p=argparse.ArgumentParser();p.add_argument('--worker',type=Path,required=True);p.add_argument('--client',type=Path,required=True);p.add_argument('--references',type=Path,required=True);p.add_argument('--work',type=Path,required=True);p.add_argument('--report',type=Path,required=True);a=p.parse_args()
 assert not a.report.exists() and not a.work.exists();a.work.mkdir(parents=True)
 r=dict(schema='genesis.private.standalone-eof.export.v1',passed=False,worker_sha256=sha(a.worker),client_sha256=sha(a.client),helper_sha256=sha(a.client.parent/('air-file-publish.exe' if os.name=='nt' else 'air-file-publish')),cases=[],reference='Independent ordered MM-AIR actual-EOF float reference plus independently authored frame-coded RGB16')
 try:
  ffmpeg=tool(a.worker,'ffmpeg');ffprobe=tool(a.worker,'ffprobe')
  colors=np.array([10000,22000,35000],dtype='<u2');images=np.tile(colors,(60,16,16,1));video=a.work/'source-video.mkv'
  run([ffmpeg,'-nostdin','-v','error','-f','rawvideo','-pixel_format','rgb48le','-video_size','16x16','-framerate','30','-i','pipe:0','-c:v','ffv1','-pix_fmt','gbrp16le',video],input=images.tobytes())
  decoded=np.frombuffer(run([ffmpeg,'-v','error','-i',video,'-f','rawvideo','-pix_fmt','rgb48le','pipe:1']),dtype='<u2').reshape(60,16,16,3);assert np.max(np.abs(decoded.astype('i4')-images.astype('i4')))==0
  for fx in ['delay','reverb','delay-compressor','compressor-delay']:
   full=np.frombuffer((a.references/(fx+'-reference.f32')).read_bytes(),dtype='<f4').reshape(-1,2)
   base=json.loads((a.references/(fx+'-unedited')/'input.air').read_text());base['sources'].append(dict(id=8,path=str(video.resolve()),name='Video',bin=1,frames=60,fps=30,width=16,height=16,has_video=True,has_audio=False,audio_rate=0,audio_channels=0,online=True));base['tracks'].append(dict(id=4,owner=2,kind=0,name='V1',order=0,hidden=False,muted=False,locked=False,solo=False,gain=1,pan=0,height=44));c=copy.deepcopy(base['clips'][0]);c.update(id=22,source=8,track=4,streams=1);base['clips'].append(c);base['next_id']=200
   modes=['default'] if fx!='delay' else ['default','marked-body','mark-in-tail','marked-in-body','video-longer','muted']
   for mode in modes:
    g=copy.deepcopy(base);start=0;expected_audio=full
    if mode=='marked-body':g['program']['mark_out']=60;video_end=60;expected_audio=full[:96000]
    elif mode=='marked-in-body':g['program'].update(mark_in=15,mark_out=60);start=15;video_end=60;expected_audio=full[24000:96000]
    elif mode=='mark-in-tail':g['program']['mark_in']=64;start=64;video_end=(len(full)+1599)//1600;expected_audio=full[102400:]
    elif mode=='video-longer':
     g['sources'][-1]['frames']=180;g['clips'][-1]['length']=180;g['clips'][-1]['speed']=0;video_end=180
    elif mode=='muted':g['tracks'][0]['muted']=True;video_end=60;expected_audio=np.empty((0,2),dtype='f4')
    else:video_end=(len(full)+1599)//1600
    label=fx+'-'+mode;out=a.work/label;out.mkdir();project=out/'input.air';project.write_text(json.dumps(g),encoding='utf8');before=sha(project)
    run([a.client,a.worker,project,out,'--export']);assert sha(project)==before
    movie=out/'master.mkv';rgb=np.frombuffer(run([ffmpeg,'-v','error','-i',movie,'-map','0:v:0','-f','rawvideo','-pix_fmt','rgb48le','pipe:1']),dtype='<u2').reshape(-1,16,16,3)
    assert len(rgb)==video_end-start,(label,'video count',len(rgb),video_end-start)
    for n,frame in enumerate(rgb):
     desired=colors if start+n<60 or mode=='video-longer' else np.array([0,0,0]);e=int(np.max(np.abs(frame.astype('i4')-desired.astype('i4'))));assert e<=5,(label,'picture',start+n,e)
    info=json.loads(run([ffprobe,'-v','error','-show_streams','-of','json',movie]));audio=[s for s in info['streams'] if s['codec_type']=='audio']
    if len(expected_audio):
     values=np.frombuffer(run([ffmpeg,'-v','error','-i',movie,'-map','0:a:0','-f','f32le','pipe:1']),dtype='<f4').reshape(-1,2);assert values.shape==expected_audio.shape,(label,'audio count',values.shape,expected_audio.shape)
     error=float(np.max(np.abs(values-expected_audio),initial=0));assert error<=2e-6,(label,error)
    else:
     values=np.empty((0,2),dtype='f4');error=0
     if audio:values=np.frombuffer(run([ffmpeg,'-v','error','-i',movie,'-map','0:a:0','-f','f32le','pipe:1']),dtype='<f4').reshape(-1,2);assert not len(values),(label,'silence allocated PCM')
    assert not list(out.rglob('*.rf64')) and not list(out.glob('.genesis-air*'))
    r['cases'].append(dict(name=label,video_frames=len(rgb),exact_audio_frames=len(values),max_float_error=error,master_sha256=sha(movie),no_ceil_audio_padding=True))
  r['passed']=True;r['cases_count']=len(r['cases'])
 except BaseException as exc:r['error']=repr(exc);raise
 finally:a.report.write_text(json.dumps(r,indent=2)+'\n')
if __name__=='__main__':main()
