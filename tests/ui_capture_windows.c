/* Actual Win32 canvas message/event-ring code with capture calls injected.
   No HWND is created, user input is sent, or desktop capture is acquired. */
#define WIN32_LEAN_AND_MEAN
#define NOMINMAX
#include <winsock2.h>
#include <windows.h>
#include <stdint.h>
#include <stdio.h>
static void *test_window;
static HWND captured;
static unsigned releases, checks;
static LONG_PTR WINAPI test_window_ptr(HWND handle,int index){(void)handle;(void)index;return (LONG_PTR)test_window;}
static HWND WINAPI test_set_capture(HWND handle){HWND prior=captured;captured=handle;return prior;}
static HWND WINAPI test_get_capture(void){return captured;}
static BOOL WINAPI test_release_capture(void);
#define GetWindowLongPtrW test_window_ptr
#define SetCapture test_set_capture
#define GetCapture test_get_capture
#define ReleaseCapture test_release_capture
#ifndef GENESIS_UI_SOURCE
#error Define GENESIS_UI_SOURCE to the maintained patched air_ui_win32.c
#endif
#include GENESIS_UI_SOURCE
static BOOL WINAPI test_release_capture(void){HWND previous=captured;captured=NULL;releases++;if(previous)window_proc(previous,WM_CAPTURECHANGED,0,0);return TRUE;}
#define CHECK(value) do{checks++;if(!(value)){fprintf(stderr,"FAIL line %d: %s\n",__LINE__,#value);return 1;}}while(0)
static int next(air_win_window *window,uint8_t kind,uint32_t x,uint32_t y){air_ui_event event;return pop_event(window,&event)&&event.kind==kind&&event.widget==x&&event.key==y;}
int main(void){
 air_win_window window={0};window.canvas=1;test_window=&window;
 HWND handle=(HWND)(uintptr_t)0x1234;LPARAM position=MAKELPARAM(30,40);
 /* Real message sequence: left selection drag, second button press/release,
    captured movement outside, final primary release. Secondary Up must not
    steal capture, otherwise the outside primary Up cannot reach this canvas. */
 window_proc(handle,WM_LBUTTONDOWN,MK_LBUTTON,position);
 CHECK(captured==handle);CHECK(next(&window,6,30,40));
 window_proc(handle,WM_RBUTTONDOWN,MK_LBUTTON|MK_RBUTTON,position);
 CHECK(next(&window,6,30,40|0x80000000u));
 window_proc(handle,WM_RBUTTONUP,MK_LBUTTON,position);
 CHECK(captured==handle&&releases==0);CHECK(next(&window,7,30,40|0x80000000u));CHECK(window.event_count==0);
 window_proc(handle,WM_MOUSEMOVE,MK_LBUTTON,MAKELPARAM(-20,180));
 CHECK(next(&window,8,0,180|0x40000000u));
 window_proc(handle,WM_LBUTTONUP,0,MAKELPARAM(-20,180));
 CHECK(captured==NULL&&releases==1);CHECK(next(&window,7,0,180));CHECK(window.event_count==0&&!window.releasing_capture);
 /* Symmetric ordering also preserves the remaining secondary button. */
 window_proc(handle,WM_RBUTTONDOWN,MK_RBUTTON,position);CHECK(next(&window,6,30,40|0x80000000u));
 window_proc(handle,WM_LBUTTONDOWN,MK_LBUTTON|MK_RBUTTON,position);CHECK(next(&window,6,30,40));
 window_proc(handle,WM_LBUTTONUP,MK_RBUTTON,position);CHECK(captured==handle&&releases==1);CHECK(next(&window,7,30,40));
 window_proc(handle,WM_RBUTTONUP,0,position);CHECK(captured==NULL&&releases==2);CHECK(next(&window,7,30,40|0x80000000u));CHECK(window.event_count==0);
 /* External capture loss and WM_CANCELMODE deliver one explicit loss event;
    normal final Up has already proved that event is suppressed. */
 window_proc(handle,WM_LBUTTONDOWN,MK_LBUTTON,position);CHECK(next(&window,6,30,40));
 captured=NULL;window_proc(handle,WM_CAPTURECHANGED,0,(LPARAM)(uintptr_t)0x5678);
 CHECK(next(&window,15,0,0));CHECK(window.event_count==0);
 window_proc(handle,WM_LBUTTONDOWN,MK_LBUTTON,position);CHECK(next(&window,6,30,40));
 window_proc(handle,WM_CANCELMODE,0,0);CHECK(captured==NULL&&releases==3);CHECK(next(&window,15,0,0));CHECK(window.event_count==0);
 window_proc(handle,WM_CANCELMODE,0,0);CHECK(releases==3&&window.event_count==0);
 air_free(window.events);
 printf("{\"passed\":true,\"checks\":%u,\"native_message_code\":true,\"desktop_access\":false}\n",checks);
 return 0;
}
