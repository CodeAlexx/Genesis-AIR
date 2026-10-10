// Native RGBA64 upload regression: every 16-bit code/channel/input slot,
// borrowed host-buffer reuse, retained-canvas/snapshot allocation and shutdown.
// Compile against GENESIS_COMPOSITOR_SOURCE with CL120 and the OpenCL library.
#define CL_TARGET_OPENCL_VERSION 120
#include <CL/cl.h>
#include <stdio.h>
#include <stdlib.h>
static int fail_at,alloc_attempts,mem_live,kernel_live,program_live,checks;
static size_t read_bytes;
static cl_int CL_API_CALL counted_read(cl_command_queue q,cl_mem m,cl_bool b,size_t o,size_t n,void*p,cl_uint c,const cl_event*w,cl_event*e){read_bytes+=n;return clEnqueueReadBuffer(q,m,b,o,n,p,c,w,e);}
#define clEnqueueReadBuffer counted_read
static cl_mem CL_API_CALL controlled_buffer(cl_context c,cl_mem_flags f,size_t n,void*p,cl_int*e){
 if(fail_at&&++alloc_attempts==fail_at){*e=CL_MEM_OBJECT_ALLOCATION_FAILURE;return NULL;}
 cl_mem m=clCreateBuffer(c,f,n,p,e);if(m)mem_live++;return m;
}
static cl_int CL_API_CALL controlled_release_mem(cl_mem m){cl_int e=clReleaseMemObject(m);if(e==0)mem_live--;return e;}
static cl_kernel CL_API_CALL controlled_kernel(cl_program p,const char*n,cl_int*e){cl_kernel k=clCreateKernel(p,n,e);if(k)kernel_live++;return k;}
static cl_int CL_API_CALL controlled_release_kernel(cl_kernel k){cl_int e=clReleaseKernel(k);if(e==0)kernel_live--;return e;}
static cl_program CL_API_CALL controlled_program(cl_context c,cl_uint n,const char**s,const size_t*l,cl_int*e){cl_program p=clCreateProgramWithSource(c,n,s,l,e);if(p)program_live++;return p;}
static cl_int CL_API_CALL controlled_release_program(cl_program p){cl_int e=clReleaseProgram(p);if(e==0)program_live--;return e;}
#define clCreateBuffer controlled_buffer
#define clReleaseMemObject controlled_release_mem
#define clCreateKernel controlled_kernel
#define clReleaseKernel controlled_release_kernel
#define clCreateProgramWithSource controlled_program
#define clReleaseProgram controlled_release_program
#ifndef GENESIS_COMPOSITOR_SOURCE
#error Define GENESIS_COMPOSITOR_SOURCE to the pinned overlay fpx_gpu.c under test
#endif
#include GENESIS_COMPOSITOR_SOURCE

#define CHECK(x) do{checks++;if(!(x)){fprintf(stderr,"failed line %d: %s\n",__LINE__,#x);return 1;}}while(0)
static float input[64*64*4],out[100*100*4];
static void fill(float v){for(int i=0;i<64*64;i++){input[i*4]=v;input[i*4+1]=.6f;input[i*4+2]=.9f;input[i*4+3]=.5f;}}
static int compose(void){fpx_gpu_track1(-1,0,4);fpx_gpu_pip(0,0,0,0,1,1);fpx_gpu_grade(0,1,1);return 0;}
int main(void){
 CHECK(fpx_gpu_set_size(64,64)==0);CHECK(fpx_gpu_init()==0);CHECK(fpx_gpu_canvas(64,64,1)==0);
 CHECK(fpx_gpu_external_bytes()==0);
 CHECK(fpx_gpu_external_reserve(0)==-2);
 CHECK(fpx_gpu_external_reserve(1024*1024)==0);
 CHECK(fpx_gpu_external_bytes()==1024*1024);
 CHECK(fpx_gpu_external_reserve(FPX_CANVAS_BYTES_LIMIT)==-2);
 CHECK(fpx_gpu_external_bytes()==1024*1024);
 fpx_gpu_external_release(1024*1024);CHECK(fpx_gpu_external_bytes()==0);
 // Every 16-bit value and each slot, with immediate caller-buffer reuse.
 CHECK(fpx_gpu_canvas(256,256,1)==0);
 uint16_t*codes=malloc(256*256*4*sizeof(uint16_t));float*converted=malloc(256*256*4*sizeof(float));
 CHECK(codes&&converted);
 for(int slot=0;slot<3;slot++){
  for(int i=0;i<256*256*4;i++)codes[i]=(uint16_t)((i/4+slot*137+i%4*8191)&65535);
  CHECK(fpx_gpu_upload_u16(slot,codes)==0);memset(codes,0,256*256*4*sizeof(uint16_t));
  CHECK(clEnqueueReadBuffer(g_q,g_buf[slot],CL_TRUE,0,256*256*4*sizeof(float),converted,0,NULL,NULL)==CL_SUCCESS);
  for(int i=0;i<256*256*4;i++){float expected=(uint16_t)((i/4+slot*137+i%4*8191)&65535)*(1.0f/65535.0f);CHECK(memcmp(&expected,&converted[i],sizeof(float))==0);}
 }
 CHECK(fpx_gpu_upload_u16(-1,codes)==-1);CHECK(fpx_gpu_upload_u16(3,codes)==-1);CHECK(fpx_gpu_upload_u16(0,NULL)==-1);
 free(codes);free(converted);CHECK(fpx_gpu_canvas(64,64,1)==0);
 fill(.3f);CHECK(fpx_gpu_upload_f32(0,input)==0);compose();CHECK(fpx_gpu_picture_begin(1)==0);
 int baseline_m=mem_live,baseline_p=program_live,baseline_k=kernel_live;
 fail_at=1;alloc_attempts=0;CHECK(fpx_gpu_picture_store(1,1,0)==-2);fail_at=0;
 CHECK(mem_live==baseline_m&&program_live==baseline_p&&kernel_live==baseline_k);CHECK(g_snapshot_bytes==0);
 read_bytes=0;CHECK(fpx_gpu_picture_store(1,1,0)==0);CHECK(read_bytes==4);
 CHECK(g_snapshot_bytes==64*64*16);CHECK(fpx_gpu_picture_store(1,1,0)==-1);
 fill(.7f);CHECK(fpx_gpu_upload_f32(0,input)==0);compose();CHECK(fpx_gpu_picture_store(1,2,0)==0);
 CHECK(fpx_gpu_picture_upload(0,1,1,0)==0);compose();fpx_gpu_download_f32(0,out);
 for(int i=0;i<64*64;i++){CHECK(fabsf(out[i*4]-.3f)<1e-6);CHECK(out[i*4+3]==.5f);}
 int held_m=mem_live,held_p=program_live,held_k=kernel_live;
 fail_at=1;alloc_attempts=0;CHECK(fpx_gpu_picture_store(1,3,0)==-2);fail_at=0;
 CHECK(mem_live==held_m&&program_live==held_p&&kernel_live==held_k);CHECK(fpx_gpu_picture_check(1,1,0)==0);
 // GPU validation must retain the former intermediate-loader refusal semantics.
 for(int n=0;n<4;n++){
  fill(.3f);input[n<2?0:3]=n==0?NAN:n==1?INFINITY:n==2?-.1f:1.1f;
  CHECK(clEnqueueWriteBuffer(g_q,g_buf[OUTB],CL_TRUE,0,sizeof input,input,0,NULL,NULL)==CL_SUCCESS);
  read_bytes=0;CHECK(fpx_gpu_picture_store(1,10+n,0)==-4);CHECK(read_bytes==4);CHECK(g_snapshot_bytes==2*64*64*16);
 }
 fill(.3f);CHECK(fpx_gpu_upload_f32(0,input)==0);compose();
 // LRU eviction must not release immutable snapshots, even equal-size siblings.
 for(int n=0;n<8;n++){CHECK(fpx_gpu_canvas(80+n*2,48+n*2,1)==0);CHECK(program_live<=5);}
 CHECK(fpx_gpu_canvas(80,48,1)==0);CHECK(fpx_gpu_picture_check(1,1,0)==-1);
 CHECK(fpx_gpu_picture_upload(0,1,1,1)==0);compose();fpx_gpu_download_f32(0,out);
 for(int y=0;y<48;y++)for(int x=0;x<80;x++){
  int at=(y*80+x)*4;int inside=x>=16&&x<64;
  CHECK(fabsf(out[at]-(inside?.3f:0))<1e-6);CHECK(out[at+3]==(inside?.5f:0));
 }
 CHECK(fpx_gpu_canvas(80,48,0)==0);CHECK(fpx_gpu_picture_upload(0,1,1,2)==0);compose();fpx_gpu_download_f32(0,out);
 for(int y=0;y<48;y++)for(int x=0;x<80;x++){
  int at=(y*80+x)*4;int inside=x>=16&&x<64;
  CHECK(fabsf(out[at]-(inside?.15f:0))<1e-6);CHECK(out[at+3]==1);
 }
 uint64_t reserve=FPX_CANVAS_BYTES_LIMIT-g_canvases[g_canvas_active].bytes-g_snapshot_bytes-(g_snapshot_status?sizeof(cl_int):0);
 CHECK(fpx_gpu_external_reserve(reserve)==0);CHECK(fpx_gpu_external_bytes()==reserve);
 CHECK(fpx_gpu_picture_store(1,3,0)==-2);CHECK(fpx_gpu_picture_check(1,2,1)==0);
 fpx_gpu_external_release(reserve);CHECK(fpx_gpu_external_bytes()==0);
 uint64_t actual=g_snapshot_bytes;int count=alloc_attempts;held_m=mem_live;
 g_snapshot_bytes=FPX_CANVAS_BYTES_LIMIT;
 CHECK(canvas_make_room(4)!=0);CHECK(fpx_gpu_picture_store(1,3,0)==-2);CHECK(alloc_attempts==count);
 g_snapshot_bytes=actual;CHECK(fpx_gpu_picture_check(1,1,1)==0);
 CHECK(fpx_gpu_picture_drop(1,1)==0);CHECK(fpx_gpu_picture_check(1,1,1)==-1);
 CHECK(fpx_gpu_picture_store(1,1,0)==-1);CHECK(fpx_gpu_picture_check(1,2,1)==0);
 CHECK(fpx_gpu_picture_begin(2)==0);CHECK(g_snapshot_bytes==0);CHECK(fpx_gpu_picture_check(1,2,1)==-1);
 CHECK(fpx_gpu_picture_begin(2)==-1);CHECK(fpx_gpu_picture_begin(1)==-1);
 CHECK(fpx_gpu_canvas(64,64,1)==0);fill(.4f);CHECK(fpx_gpu_upload_f32(0,input)==0);compose();CHECK(fpx_gpu_picture_store(2,1,0)==0);
 fpx_gpu_picture_end();CHECK(g_snapshot_bytes==0&&g_snapshot_epoch==0);CHECK(fpx_gpu_picture_check(2,1,0)==-1);
 fpx_gpu_shutdown();CHECK(mem_live==0&&program_live==0&&kernel_live==0);
 printf("Native u16 upload and snapshot lifecycle: %d checks; all codes/3 slots/borrowed buffer, zero FP32 readback, allocation recovery, finite-alpha validation, same-size siblings, LRU, shared4GiB accounting, stale IDs and shutdown passed\n",checks);return 0;
}
