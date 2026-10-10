/* Exercise the actual Win32 canvas message/queue code without a window or any
   access to the user's clipboard. Only clipboard ownership and key state are
   injected; Unicode conversion, message routing and growing event ring are real. */
#define WIN32_LEAN_AND_MEAN
#define NOMINMAX
#include <winsock2.h>
#include <windows.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
static void *test_window;
static const WCHAR *clipboard_data;
static SIZE_T clipboard_bytes;
static unsigned key_flags, opens, closes, locks, unlocks, checks;
static int available=1, present=1, lockable=1;
static LONG_PTR WINAPI test_window_ptr(HWND window,int index){(void)window;(void)index;return (LONG_PTR)test_window;}
static SHORT WINAPI test_key_state(int key){return (key==VK_SHIFT&&(key_flags&1))||(key==VK_CONTROL&&(key_flags&2))||(key==VK_MENU&&(key_flags&4))?(SHORT)0x8000:0;}
static BOOL WINAPI test_open(HWND owner){(void)owner;opens++;return available;}
static BOOL WINAPI test_close(void){closes++;return TRUE;}
static HANDLE WINAPI test_clipboard(UINT format){return present&&format==CF_UNICODETEXT?(HANDLE)(uintptr_t)1:NULL;}
static SIZE_T WINAPI test_size(HGLOBAL memory){(void)memory;return clipboard_bytes;}
static LPVOID WINAPI test_lock(HGLOBAL memory){(void)memory;locks++;return lockable?(LPVOID)clipboard_data:NULL;}
static BOOL WINAPI test_unlock(HGLOBAL memory){(void)memory;unlocks++;return TRUE;}
#define GetWindowLongPtrW test_window_ptr
#define GetKeyState test_key_state
#define OpenClipboard test_open
#define CloseClipboard test_close
#define GetClipboardData test_clipboard
#define GlobalSize test_size
#define GlobalLock test_lock
#define GlobalUnlock test_unlock
#ifndef GENESIS_UI_SOURCE
#error Define GENESIS_UI_SOURCE to the maintained patched air_ui_win32.c
#endif
#include GENESIS_UI_SOURCE
#define CHECK(value) do{checks++;if(!(value)){fprintf(stderr,"FAIL line %d: %s\n",__LINE__,#value);return 1;}}while(0)
static int next(air_win_window *window,uint8_t kind,uint32_t first,uint32_t second){air_ui_event event;return pop_event(window,&event)&&event.kind==kind&&event.widget==first&&event.key==second;}
static void setup(const WCHAR *data,SIZE_T count){clipboard_data=data;clipboard_bytes=count*sizeof(WCHAR);available=present=lockable=1;}
int main(void){
 air_win_window window={0};window.canvas=1;test_window=&window;key_flags=2;
 const WCHAR title[]={L'E',L'D',L'I',L'T',L' ',0x65e5,0x672c,0xd83d,0xde00,0};
 setup(title,sizeof(title)/sizeof(title[0]));
 CHECK(window_proc(NULL,WM_KEYDOWN,'V',0)==0);
 CHECK(next(&window,9u,'v',2u));
 const uint32_t expected[]={'E','D','I','T',' ',0x65e5,0x672c,0x1f600};
 for(unsigned n=0;n<sizeof(expected)/sizeof(expected[0]);n++)CHECK(next(&window,10u,expected[n],0));
 CHECK(window.event_count==0);CHECK(opens==1&&closes==1&&locks==1&&unlocks==1);
 CHECK(title[7]==0xd83d&&title[8]==0xde00); /* borrowed clipboard stays intact */
 /* More than the initial128 events: no loss, exact ordering, no synthetic key. */
 WCHAR *long_text=malloc(1001*sizeof(WCHAR));CHECK(long_text);
 for(unsigned n=0;n<1000;n++)long_text[n]=(WCHAR)('a'+n%26);long_text[1000]=0;
 setup(long_text,1001);push_event(&window,9u,'a',2u);
 CHECK(window_proc(NULL,WM_PASTE,0,0)==0);push_event(&window,9u,65293u,0);
 CHECK(window.event_count==1002&&window.event_capacity>=1002);CHECK(next(&window,9u,'a',2u));
 for(unsigned n=0;n<1000;n++)CHECK(next(&window,10u,'a'+n%26,0));
 CHECK(next(&window,9u,65293u,0));CHECK(window.event_count==0);free(long_text);
 const WCHAR tiny[]={L'Z',0};setup(tiny,2);key_flags=1;
 CHECK(window_proc(NULL,WM_KEYDOWN,VK_INSERT,0)==0);CHECK(next(&window,9u,65379u,1u));CHECK(next(&window,10u,'Z',0));
 key_flags=0;unsigned before=opens;window_proc(NULL,WM_KEYDOWN,'V',0);CHECK(next(&window,9u,'v',0));CHECK(opens==before);
 key_flags=6;window_proc(NULL,WM_KEYDOWN,'V',0);CHECK(next(&window,9u,'v',6));CHECK(opens==before);
 const WCHAR malformed[]={0xd800,L'Z',0xdc00,0};setup(malformed,4);
 window_proc(NULL,WM_PASTE,0,0);CHECK(next(&window,10u,0xfffd,0));CHECK(next(&window,10u,'Z',0));CHECK(next(&window,10u,0xfffd,0));
 window.pending_surrogate=0xd800;window.pending_text_modifiers=4;setup(tiny,2);
 window_proc(NULL,WM_PASTE,0,0);CHECK(next(&window,10u,0xfffd,4));CHECK(next(&window,10u,'Z',0));CHECK(window.pending_surrogate==0);
 key_flags=0;window_proc(NULL,WM_CHAR,0xd83d,0);CHECK(window.event_count==0);window_proc(NULL,WM_CHAR,0xde00,0);CHECK(next(&window,10u,0x1f600,0));
 /* Failed transfer publishes no partial text and balances borrowed ownership. */
 setup(tiny,2);available=0;before=closes;window_proc(NULL,WM_PASTE,0,0);CHECK(closes==before&&window.event_count==0);
 setup(tiny,2);present=0;before=closes;window_proc(NULL,WM_PASTE,0,0);CHECK(closes==before+1&&window.event_count==0);
 setup(tiny,2);lockable=0;before=unlocks;window_proc(NULL,WM_PASTE,0,0);CHECK(unlocks==before&&window.event_count==0);
 setup(tiny,2);clipboard_bytes=3;before=locks;window_proc(NULL,WM_PASTE,0,0);CHECK(locks==before&&window.event_count==0);
 const WCHAR no_terminator[]={L'X',L'Y'};setup(no_terminator,2);before=unlocks;window_proc(NULL,WM_PASTE,0,0);CHECK(unlocks==before+1&&window.event_count==0);
 const WCHAR empty[]={0};setup(empty,1);window_proc(NULL,WM_PASTE,0,0);CHECK(window.event_count==0);
 WCHAR *oversized=malloc((AIR_WIN_CLIPBOARD_UNITS_LIMIT+2)*sizeof(WCHAR));CHECK(oversized);
 for(unsigned n=0;n<=AIR_WIN_CLIPBOARD_UNITS_LIMIT;n++)oversized[n]='X';oversized[AIR_WIN_CLIPBOARD_UNITS_LIMIT+1]=0;
 setup(oversized,AIR_WIN_CLIPBOARD_UNITS_LIMIT+2);window_proc(NULL,WM_PASTE,0,0);CHECK(window.event_count==0);free(oversized);
 setup(tiny,2);clipboard_bytes=SIZE_MAX-1;window_proc(NULL,WM_PASTE,0,0);CHECK(next(&window,10u,'Z',0));CHECK(window.event_count==0);
 air_free(window.events);
 printf("Windows canvas clipboard: %u checks; Ctrl+V/Shift+Insert/WM_PASTE, Unicode/invalid surrogate, ordered1000-scalar queue, bounded failure and balanced ownership passed; no user clipboard or window access\n",checks);
 return 0;
}
