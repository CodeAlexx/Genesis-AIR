"""Odd visible AV1/PQ sizes retain their final chroma row/column and reference path."""
import argparse
from array import array
import json
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory

from hdr_preview import capture, FLAGS
from media_runtime import tool


def fit(width, height, ow, oh):
    if width*oh >= ow*height:
        dw,dh=ow,ow*height//width
    else:
        dw,dh=oh*width//height,oh
    return max(2,dw)&~1,max(2,dh)&~1


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--worker',required=True,type=Path)
    parser.add_argument('--report',type=Path)
    parser.add_argument('--scratch',type=Path)
    parser.add_argument('--require-gpu',action='store_true')
    args=parser.parse_args()
    worker=args.worker.resolve();ffmpeg=tool(worker,'ffmpeg')
    results=[]
    with TemporaryDirectory(prefix='genesis-odd-hdr-') as temporary:
        root=args.scratch.resolve() if args.scratch else Path(temporary)
        root.mkdir(parents=True,exist_ok=True)
        for width,height in ((514,290),(513,289),(513,290),(514,289)):
            cw,ch=(width+1)//2,(height+1)//2
            odd=bool(width%2 or height%2)
            raw=root/f'{width}x{height}.yuv'
            with raw.open('wb') as stream:
                for frame in range(2):
                    luma=array('H',[512+frame*32])*(width*height)
                    if odd:
                        for y in range(height):luma[y*width+width-1]=768+frame*32
                        for x in range(width):luma[(height-1)*width+x]=768+frame*32
                    stream.write(luma.tobytes())
                    for plane in range(2):
                        data=array('H')
                        for y in range(ch):
                            for x in range(cw):
                                # A constant edge band survives the codec's
                                # chroma padding. Single-pixel luma markers still
                                # distinguish the actual final visible edges.
                                edge=odd and ((plane==0 and x>=cw-16) or (plane==1 and y>=ch-16))
                                data.append(640 if edge else 512)
                        stream.write(data.tobytes())
            source=raw.with_suffix('.mp4')
            encode=[str(ffmpeg),'-nostdin','-v','error','-y','-f','rawvideo','-pixel_format','yuv420p10le',
                '-video_size',f'{width}x{height}','-framerate','24',
                '-color_primaries','bt2020','-color_trc','smpte2084','-colorspace','bt2020nc',
                '-color_range','tv','-chroma_sample_location','left','-i',str(raw),
                '-c:v','libaom-av1','-pix_fmt','yuv420p10le','-cpu-used','8','-g','1','-crf','0','-b:v','0','-aom-params','lossless=1',
                '-color_primaries','bt2020','-color_trc','smpte2084','-colorspace','bt2020nc',
                '-color_range','tv','-chroma_sample_location','left',
                '-bsf:v','av1_metadata=color_primaries=9:transfer_characteristics=16:matrix_coefficients=9:color_range=0:chroma_sample_position=1',str(source)]
            completed=subprocess.run(encode,capture_output=True,timeout=120,creationflags=FLAGS)
            assert completed.returncode==0,completed.stderr.decode(errors='replace')
            # An independent software decoder checks the complete odd-sized source,
            # including the extra final chroma samples rather than a cropped proxy.
            decoded=subprocess.run([str(ffmpeg),'-nostdin','-v','error','-i',str(source),
                '-pix_fmt','yuv420p10le','-f','rawvideo','-'],capture_output=True,timeout=30,creationflags=FLAGS)
            if decoded.stdout!=raw.read_bytes() and args.scratch:
                raw.with_suffix('.decoded.yuv').write_bytes(decoded.stdout)
            assert decoded.returncode==0 and decoded.stdout==raw.read_bytes(),(width,height,'source planes changed or were cropped',len(decoded.stdout),raw.stat().st_size)
            cpu,_=capture(worker,source,[0,1,0],root,False,512,288)
            shown,log=capture(worker,source,[0,1,0],root,True,512,288)
            hardware='Native GPU HDR preview:' in log
            assert shown[0]==shown[2] and shown[0]!=shown[1],'odd selected frame or rewind identity changed'
            assert 'GA_GPU_COLOR' not in log and 'GA_COLOR_CONVERSION' not in log,log[-2000:]
            if width%2 or height%2:
                assert not hardware and shown==cpu,'odd source must use exact reference color sampling'
                dw,dh=fit(width,height,512,288);ox,oy=(512-dw)//2,(288-dh)//2
                center=((oy+dh//2)*512+ox+dw//2)*4
                right=((oy+dh//2)*512+ox+dw-1)*4
                bottom=((oy+dh-1)*512+ox+dw//2)*4
                assert shown[0][right+2]>shown[0][center+2]+1/255,'final blue chroma column was lost'
                assert shown[0][bottom]>shown[0][center]+1/255,'final red chroma row was lost'
                before_right=right-5*4;before_bottom=bottom-5*512*4
                assert sum(shown[0][right:right+3])>sum(shown[0][before_right:before_right+3])+3/255,'final visible luma column was cropped'
                assert sum(shown[0][bottom:bottom+3])>sum(shown[0][before_bottom:before_bottom+3])+3/255,'final visible luma row was cropped'
                # Reference-color exports and explicit HDR/native masters must
                # also accept the same source and preserve selected-frame identity.
                for ow,oh,hdr,reference in ((512,288,False,True),(width,height,False,False),(width,height,True,False)):
                    expected,_=capture(worker,source,[0,1,0],root,False,ow,oh,hdr,reference)
                    actual,master_log=capture(worker,source,[0,1,0],root,True,ow,oh,hdr,reference)
                    assert actual==expected and actual[0]==actual[2] and actual[0]!=actual[1]
                    assert 'Native GPU HDR preview:' not in master_log
                results.append(dict(width=width,height=height,mode='exact reference',visible_chroma_edges=True,master_modes=3))
            else:
                if args.require_gpu:assert hardware,'even control did not exercise the GPU'
                worst=max(abs(a-b)*255 for p,q in zip(cpu,shown) for a,b in zip(p,q))
                assert worst<=1,('even color path changed',worst)
                results.append(dict(width=width,height=height,mode='GPU' if hardware else 'reference',maximum_delta_255=worst))
    if args.report:
        args.report.parent.mkdir(parents=True,exist_ok=True)
        args.report.write_text(json.dumps(results,indent=2)+'\n',encoding='utf8')
    print('Odd HDR: three complete lossless sources, visible chroma edges, exact preview/reference/native/HDR masters; even control passed')


if __name__=='__main__':main()
