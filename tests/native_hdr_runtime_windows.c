#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <libavutil/cpu.h>
#include <libavutil/avutil.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
int genesis_media_runtime_init(void);
int genesis_nativehdr_qualified(void);
unsigned genesis_nativehdr_test_attempts(void);
int genesis_nativehdr_test_module(const void*,const char*);
int genesis_nativehdr_test_hold(const void*,const char*);
void genesis_nativehdr_test_release(void);
static const char *hash="C8E86E863D2C1B686E39D98E37E92EE68F00AB1108507087CBD4D360B9997945";
static unsigned checks;
#define CHECK(x) do{checks++;if(!(x)){fprintf(stderr,"FAIL line=%d expression=%s error=%lu\n",__LINE__,#x,GetLastError());return 1;}}while(0)
static void *symbol(HMODULE m){return (void*)GetProcAddress(m,"avutil_version");}
int main(int argc,char **argv){
 CHECK(argc==3);CHECK(genesis_media_runtime_init());CHECK(genesis_nativehdr_test_attempts()==0);
 if(!strcmp(argv[1],"idle")){printf("IDENTITY idle attempts=0 checks=%u\n",checks);return 0;}
 if(!strcmp(argv[1],"cpu")){av_force_cpu_flags(AV_CPU_FLAG_AVX2|AV_CPU_FLAG_FMA3);CHECK(!genesis_nativehdr_qualified());CHECK(!genesis_nativehdr_qualified());CHECK(genesis_nativehdr_test_attempts()==1);printf("IDENTITY CPU fallback checks=%u\n",checks);return 0;}
 CHECK(!strcmp(argv[1],"identity"));
 CHECK(genesis_nativehdr_qualified());CHECK(genesis_nativehdr_qualified());CHECK(genesis_nativehdr_test_attempts()==1);
 HMODULE original=GetModuleHandleW(L"avutil-61.dll");CHECK(original);wchar_t path[32768],root[32768],copy[32768],changed[32768],old[32768];
 CHECK(GetModuleFileNameW(original,path,32768));CHECK(MultiByteToWideChar(CP_UTF8,MB_ERR_INVALID_CHARS,argv[2],-1,root,32768));
 CHECK(CreateDirectoryW(root,NULL));swprintf_s(copy,32768,L"%ls\\avutil-61.dll",root);swprintf_s(changed,32768,L"%ls\\avutil-changed.dll",root);swprintf_s(old,32768,L"%ls\\avutil-old.dll",root);
 CHECK(CopyFileW(path,copy,TRUE));CHECK(CopyFileW(path,changed,TRUE));
 HANDLE writer=CreateFileW(changed,GENERIC_WRITE,0,NULL,OPEN_EXISTING,0,NULL);CHECK(writer!=INVALID_HANDLE_VALUE);
 LARGE_INTEGER end={0};CHECK(SetFilePointerEx(writer,end,NULL,FILE_END));DWORD count;char value=0;CHECK(WriteFile(writer,&value,1,&count,NULL)&&count==1);CHECK(CloseHandle(writer));
 HMODULE clone=LoadLibraryExW(copy,NULL,LOAD_LIBRARY_SEARCH_DLL_LOAD_DIR|LOAD_LIBRARY_SEARCH_DEFAULT_DIRS);CHECK(clone&&clone!=original);void *entry=symbol(clone);CHECK(entry);
 CHECK(genesis_nativehdr_test_module(entry,hash));
 DWORD protection,ignored;unsigned char byte;
 // Read-only data, not only executable code, affects gamma coefficients.
 IMAGE_DOS_HEADER *dos=(IMAGE_DOS_HEADER*)clone;IMAGE_NT_HEADERS64 *nt=(IMAGE_NT_HEADERS64*)((unsigned char*)clone+dos->e_lfanew);
 IMAGE_SECTION_HEADER *sections=IMAGE_FIRST_SECTION(nt);unsigned char *data=NULL;
 for(unsigned n=0;n<nt->FileHeader.NumberOfSections;n++)if(!memcmp(sections[n].Name,".rdata",6)){data=(unsigned char*)clone+sections[n].VirtualAddress+16;break;}
 CHECK(data);CHECK(VirtualProtect(data,1,PAGE_READWRITE,&protection));byte=*data;*data=byte^1;
 CHECK(!genesis_nativehdr_test_module(entry,hash));*data=byte;CHECK(VirtualProtect(data,1,protection,&ignored));CHECK(genesis_nativehdr_test_module(entry,hash));
 byte=*(unsigned char*)entry;
 CHECK(!genesis_nativehdr_test_module(entry,"0000000000000000000000000000000000000000000000000000000000000000"));
 HMODULE other=LoadLibraryExW(changed,NULL,LOAD_LIBRARY_SEARCH_DLL_LOAD_DIR|LOAD_LIBRARY_SEARCH_DEFAULT_DIRS);CHECK(other);CHECK(!genesis_nativehdr_test_module(symbol(other),hash));CHECK(FreeLibrary(other));
 // A mapped read-only code page differs while its on-disk file remains pinned.
 // It must not qualify merely because the current filename hashes correctly.
 MEMORY_BASIC_INFORMATION memory;CHECK(VirtualQuery(entry,&memory,sizeof(memory)));
 CHECK(VirtualProtect(entry,1,PAGE_EXECUTE_READWRITE,&protection));byte=*(unsigned char*)entry;*(unsigned char*)entry=byte^1;
 CHECK(!genesis_nativehdr_test_module(entry,hash));*(unsigned char*)entry=byte;CHECK(VirtualProtect(entry,1,protection,&ignored));CHECK(FlushInstructionCache(GetCurrentProcess(),entry,1));
 CHECK(genesis_nativehdr_test_module(entry,hash));
 // Where Windows permits loaded-file rename, recreate the pathname and prove
 // mapped-page identity still wins over a matching replacement-file digest.
 int replaced=MoveFileExW(copy,old,0)!=0;
 if(replaced){CHECK(CopyFileW(path,copy,TRUE));CHECK(VirtualProtect(entry,1,PAGE_EXECUTE_READWRITE,&protection));*(unsigned char*)entry=byte^1;CHECK(!genesis_nativehdr_test_module(entry,hash));*(unsigned char*)entry=byte;CHECK(VirtualProtect(entry,1,protection,&ignored));CHECK(FlushInstructionCache(GetCurrentProcess(),entry,1));}
 CHECK(genesis_nativehdr_test_hold(entry,hash));
 writer=CreateFileW(copy,GENERIC_WRITE,FILE_SHARE_READ,NULL,OPEN_EXISTING,0,NULL);CHECK(writer==INVALID_HANDLE_VALUE);CHECK(!MoveFileExW(copy,changed,MOVEFILE_REPLACE_EXISTING));
 genesis_nativehdr_test_release();
 DWORD before,after;CHECK(GetProcessHandleCount(GetCurrentProcess(),&before));
 for(unsigned n=0;n<100;n++)CHECK(!genesis_nativehdr_test_module(entry,"0000000000000000000000000000000000000000000000000000000000000000"));
 CHECK(GetProcessHandleCount(GetCurrentProcess(),&after));CHECK(before==after);CHECK(FreeLibrary(clone));
 printf("IDENTITY passed checks=%u replaced_loaded_path=%d reject_handles_before=%lu after=%lu attempts=%u\n",checks,replaced,before,after,genesis_nativehdr_test_attempts());return 0;
}
