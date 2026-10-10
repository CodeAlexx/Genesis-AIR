#define CL_TARGET_OPENCL_VERSION 120
#include <CL/cl.h>
#include <stdio.h>
#include <stdlib.h>
static int fail_at,alloc_attempts,mem_live,kernel_live,program_live,checks;
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
int main(void){
 CHECK(fpx_gpu_set_size(64,64)==0);CHECK(fpx_gpu_init()==0);
 float pixels[64*64*4],out[64*64*4];for(int i=0;i<64*64;i++){pixels[i*4]=.3f;pixels[i*4+1]=.6f;pixels[i*4+2]=.9f;pixels[i*4+3]=.5f;}
 CHECK(fpx_gpu_canvas(64,64,1)==0);
 int oldm=mem_live,oldk=kernel_live,oldp=program_live;
 for(int n=1;n<=16;n++){
  fail_at=n;alloc_attempts=0;CHECK(fpx_gpu_canvas(80,48,1)!=0);fail_at=0;
  CHECK(GVW==64&&GVH==64&&g_ready&&g_compound==1);
  CHECK(mem_live==oldm&&kernel_live==oldk&&program_live==oldp);
  CHECK(fpx_gpu_upload_f32(0,pixels)==0);fpx_gpu_track1(-1,0,4);fpx_gpu_pip(0,0,0,0,1,1);fpx_gpu_grade(0,1,1);fpx_gpu_download_f32(0,out);
  CHECK(fabs(out[0]-.3f)<1e-6&&fabs(out[3]-.5f)<1e-6);
 }
 // Prospective allocation exceeds4GiB: reject before allocating buffers.
 int count=alloc_attempts;CHECK(canvas_make_room(FPX_CANVAS_BYTES_LIMIT)!=0);CHECK(alloc_attempts==count);CHECK(mem_live==oldm&&GVW==64);
 // Four-slotLRU must release old inactive entries; global resource counts bounded.
 for(int n=0;n<8;n++){CHECK(fpx_gpu_canvas(80+n*2,48+n*2,1)==0);CHECK(program_live<=4&&mem_live<=4*oldm&&kernel_live<=4*oldk);}
 CHECK(fpx_gpu_canvas(64,64,0)==0);fpx_gpu_shutdown();CHECK(mem_live==0&&kernel_live==0&&program_live==0);
 printf("Native canvas failure/recovery: %d checks;16 allocation failures,4GiB refusal,LRU release and shutdown passed\n",checks);return 0;
}
