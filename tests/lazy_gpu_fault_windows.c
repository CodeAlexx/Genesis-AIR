// Test-only OpenCL proxy. Never installed beside the production worker.
#define CL_TARGET_OPENCL_VERSION 120
#define CL_NO_CORE_PROTOTYPES
#include <CL/cl.h>
#include <windows.h>
#include <stdlib.h>
#include <string.h>
static HMODULE original(void) {
    static HMODULE module;
    if (!module) module = LoadLibraryW(L"OpenCL_real.dll");
    return module;
}
static void trace(const char* event) {
    wchar_t path[32768];
    DWORD n=GetEnvironmentVariableW(L"GENESIS_TEST_OPENCL_TRACE",path,32768);
    if (!n || n>=32768) return;
    HANDLE file=CreateFileW(path,FILE_APPEND_DATA,FILE_SHARE_READ|FILE_SHARE_WRITE,NULL,OPEN_ALWAYS,FILE_ATTRIBUTE_NORMAL,NULL);
    if (file!=INVALID_HANDLE_VALUE) {DWORD written;WriteFile(file,event,(DWORD)strlen(event),&written,NULL);CloseHandle(file);}
}
__declspec(dllexport) CL_API_ENTRY cl_int CL_API_CALL clGetPlatformIDs(cl_uint entries, cl_platform_id* platforms, cl_uint* count) {
    trace("platform\n");
    const char* fault=getenv("GENESIS_TEST_OPENCL_FAILURE");
    if (fault && !strcmp(fault,"init")) {if(count)*count=0;return -1001;}
    typedef cl_int (CL_API_CALL *call)(cl_uint,cl_platform_id*,cl_uint*);
    call next=(call)GetProcAddress(original(),"clGetPlatformIDs");
    return next?next(entries,platforms,count):-1001;
}
__declspec(dllexport) CL_API_ENTRY cl_int CL_API_CALL clEnqueueReadBuffer(cl_command_queue queue,cl_mem buffer,cl_bool blocking,size_t offset,size_t size,void* data,cl_uint count,const cl_event* events,cl_event* event) {
    trace("read\n");
    const char* fault=getenv("GENESIS_TEST_OPENCL_FAILURE");
    if (fault && !strcmp(fault,"read")) return CL_OUT_OF_RESOURCES;
    typedef cl_int (CL_API_CALL *call)(cl_command_queue,cl_mem,cl_bool,size_t,size_t,void*,cl_uint,const cl_event*,cl_event*);
    call next=(call)GetProcAddress(original(),"clEnqueueReadBuffer");
    return next?next(queue,buffer,blocking,offset,size,data,count,events,event):CL_OUT_OF_RESOURCES;
}

