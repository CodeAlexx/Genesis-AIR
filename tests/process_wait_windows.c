#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdint.h>
#include <stdio.h>
static DWORD controlled_wait(HANDLE handle, DWORD ms);
static BOOL controlled_exit(HANDLE handle, LPDWORD code);
#define WaitForSingleObject controlled_wait
#define GetExitCodeProcess controlled_exit
#include "air_proc_pipe_win32.c"
#undef WaitForSingleObject
#undef GetExitCodeProcess
static DWORD sequence[4]; static unsigned used, count; static BOOL exit_ok=TRUE;
static DWORD controlled_wait(HANDLE handle, DWORD ms) {
    (void)handle;(void)ms;
    return sequence[used<count?used++:count-1];
}
static BOOL controlled_exit(HANDLE handle, LPDWORD code) {
    (void)handle;*code=7u;return exit_ok;
}
static int check(const char *label, DWORD first, DWORD second, int expected_tag, int expected_value, int reaped) {
    child_state state;memset(&state,0,sizeof state);state.process=(HANDLE)(uintptr_t)1234;state.reaped=reaped;state.status.exit_code=7;
    air_child child;memset(&child,0,sizeof child);child.impl=&state;
    used=0;count=3;sequence[0]=first;sequence[1]=second;sequence[2]=second;
    air_result_proc result=air_process_wait(&child,UINT64_MAX);
    int value=result.tag==AIR_TAG_OK?result.u.ok.exit_code:result.u.err.code;
    int passed=result.tag==expected_tag&&value==expected_value;
    printf("%s\ttag=%u\tvalue=%d\twait_calls=%u\t%s\n",label,(unsigned)result.tag,value,used,passed?"PASS":"FAIL");
    if (result.tag==AIR_TAG_OK) {
        unsigned previous=used;
        air_result_proc again=air_process_wait(&child,0u);
        passed &= again.tag==AIR_TAG_OK && again.u.ok.exit_code==7 && again.u.ok.signal==0 && used==previous;
        printf("%s_repeat_retains_status\t%s\n",label,passed?"PASS":"FAIL");
    }
    return passed;
}
int main(void) {
    int passed=1;
    passed&=check("exit_between_deadline_and_recheck",WAIT_TIMEOUT,WAIT_OBJECT_0,AIR_TAG_OK,7,0);
    passed&=check("still_running_deadline",WAIT_TIMEOUT,WAIT_TIMEOUT,AIR_TAG_ERR,AIR_FS_TIMEOUT,0);
    passed&=check("signaled_exit7",WAIT_OBJECT_0,WAIT_OBJECT_0,AIR_TAG_OK,7,0);
    passed&=check("reaped_repeat_exit7",WAIT_FAILED,WAIT_FAILED,AIR_TAG_OK,7,1);
    passed&=check("real_wait_failure",WAIT_FAILED,WAIT_FAILED,AIR_TAG_ERR,AIR_FS_IO,0);
    exit_ok=FALSE;passed&=check("exit_status_failure",WAIT_OBJECT_0,WAIT_OBJECT_0,AIR_TAG_ERR,AIR_FS_IO,0);
    return passed?0:1;
}
