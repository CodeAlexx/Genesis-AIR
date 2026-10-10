// Qualify the loaded color reference, lazily, before native HDR is attempted.
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <bcrypt.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <libavutil/cpu.h>
#include <libavutil/avutil.h>
#include <libavfilter/avfilter.h>
#include <libswscale/swscale.h>

// MSVC delay-import slots contain actual implementation addresses after calls.
extern void *__imp_avutil_version, *__imp_avfilter_version, *__imp_swscale_version;
typedef struct { HANDLE file; HMODULE module; } HeldModule;
static HeldModule held[3];
static INIT_ONCE once = INIT_ONCE_STATIC_INIT;
static int qualified;
static unsigned attempts;
static const char *fingerprints[3] = {
 "C8E86E863D2C1B686E39D98E37E92EE68F00AB1108507087CBD4D360B9997945",
 "3E781D3F9C25441588A243F933EC259F5D22D4FA2F3BD654F5EEE5115FBD4B9C",
 "86C97AE5ABBFF3B72F6C58528A35D0F2CE553D4FD405167847AC76C8716CCE4E"
};
#define LIMIT (256u*1024u*1024u)
typedef NTSTATUS (WINAPI *OpenAlg)(BCRYPT_ALG_HANDLE*,LPCWSTR,LPCWSTR,ULONG);
typedef NTSTATUS (WINAPI *CreateHash)(BCRYPT_ALG_HANDLE,BCRYPT_HASH_HANDLE*,PUCHAR,ULONG,PUCHAR,ULONG,ULONG);
typedef NTSTATUS (WINAPI *HashData)(BCRYPT_HASH_HANDLE,PUCHAR,ULONG,ULONG);
typedef NTSTATUS (WINAPI *FinishHash)(BCRYPT_HASH_HANDLE,PUCHAR,ULONG,ULONG);
typedef NTSTATUS (WINAPI *DestroyHash)(BCRYPT_HASH_HANDLE);
typedef NTSTATUS (WINAPI *CloseAlg)(BCRYPT_ALG_HANDLE,ULONG);

static int hash_file(HANDLE file, const char *want) {
 HMODULE library=LoadLibraryExW(L"bcrypt.dll",NULL,LOAD_LIBRARY_SEARCH_SYSTEM32);
 if(!library)return 0;
 OpenAlg open=(OpenAlg)GetProcAddress(library,"BCryptOpenAlgorithmProvider");
 CreateHash create=(CreateHash)GetProcAddress(library,"BCryptCreateHash");
 HashData add=(HashData)GetProcAddress(library,"BCryptHashData");
 FinishHash finish=(FinishHash)GetProcAddress(library,"BCryptFinishHash");
 DestroyHash destroy=(DestroyHash)GetProcAddress(library,"BCryptDestroyHash");
 CloseAlg close=(CloseAlg)GetProcAddress(library,"BCryptCloseAlgorithmProvider");
 BCRYPT_ALG_HANDLE algorithm=NULL; BCRYPT_HASH_HANDLE hash=NULL; int good=0;
 unsigned char buffer[65536],digest[32];DWORD count;char actual[65];
 if(!open||!create||!add||!finish||!destroy||!close)goto done;
 if(open(&algorithm,BCRYPT_SHA256_ALGORITHM,NULL,0)<0 || create(algorithm,&hash,NULL,0,NULL,0,0)<0)goto done;
 LARGE_INTEGER zero={0};if(!SetFilePointerEx(file,zero,NULL,FILE_BEGIN))goto done;
 for(;;){if(!ReadFile(file,buffer,sizeof(buffer),&count,NULL))goto done;if(!count)break;if(add(hash,buffer,count,0)<0)goto done;}
 if(finish(hash,digest,32,0)<0)goto done;
 for(unsigned i=0;i<32;i++)sprintf_s(actual+i*2,3,"%02X",digest[i]);
 actual[64]=0;good=!strcmp(actual,want);
done:
 if(hash&&destroy)destroy(hash);if(algorithm&&close)close(algorithm,0);FreeLibrary(library);return good;
}

static int within(size_t begin,size_t count,size_t limit){return begin<=limit&&count<=limit-begin;}
static int read_loaded(HMODULE module,size_t rva,void *out,size_t count,size_t size){
 if(!within(rva,count,size))return 0;
 SIZE_T received=0;return ReadProcessMemory(GetCurrentProcess(),(const unsigned char*)module+rva,out,count,&received)&&received==count;
}

// The pinned file is mapped as data. Construct its bounded image, relocate only
// DIR64 values, then compare all retained executable/read-only bytes to the
// actual loaded image. This catches a mapping that predates path replacement.
static int image_refused(unsigned line){
#ifdef GENESIS_NATIVE_HDR_IDENTITY_TEST
 fprintf(stderr,"IDENTITY image refusal line=%u\n",line);
#endif
 (void)line;return 0;
}
static int image_matches(HMODULE module,const unsigned char *raw,size_t length){
 if(!within(0,sizeof(IMAGE_DOS_HEADER),length))return image_refused(__LINE__);
 const IMAGE_DOS_HEADER *dos=(const IMAGE_DOS_HEADER*)raw;
 if(dos->e_magic!=IMAGE_DOS_SIGNATURE||dos->e_lfanew<0||!within(dos->e_lfanew,sizeof(IMAGE_NT_HEADERS64),length))return image_refused(__LINE__);
 const IMAGE_NT_HEADERS64 *nt=(const IMAGE_NT_HEADERS64*)(raw+dos->e_lfanew);
 if(nt->Signature!=IMAGE_NT_SIGNATURE||nt->FileHeader.Machine!=IMAGE_FILE_MACHINE_AMD64||nt->OptionalHeader.Magic!=IMAGE_NT_OPTIONAL_HDR64_MAGIC||nt->FileHeader.SizeOfOptionalHeader!=sizeof(IMAGE_OPTIONAL_HEADER64)||nt->OptionalHeader.NumberOfRvaAndSizes!=IMAGE_NUMBEROF_DIRECTORY_ENTRIES)return image_refused(__LINE__);
 size_t size=nt->OptionalHeader.SizeOfImage, headers=nt->OptionalHeader.SizeOfHeaders;
 unsigned sections=nt->FileHeader.NumberOfSections;
 size_t section_start=dos->e_lfanew+sizeof(IMAGE_NT_HEADERS64);
 if(!size||size>LIMIT||!headers||headers>size||headers>length||!sections||sections>96||!within(section_start,sections*sizeof(IMAGE_SECTION_HEADER),length))return image_refused(__LINE__);
 MEMORY_BASIC_INFORMATION allocation;
 if(!VirtualQuery(module,&allocation,sizeof(allocation))||allocation.AllocationBase!=module||allocation.Type!=MEM_IMAGE)return image_refused(__LINE__);
 IMAGE_DOS_HEADER actual_dos;IMAGE_NT_HEADERS64 actual_nt;
 if(!read_loaded(module,0,&actual_dos,sizeof(actual_dos),size)||actual_dos.e_lfanew!=dos->e_lfanew||!read_loaded(module,dos->e_lfanew,&actual_nt,sizeof(actual_nt),size))return image_refused(__LINE__);
 if(actual_nt.Signature!=nt->Signature||memcmp(&actual_nt.FileHeader,&nt->FileHeader,sizeof(nt->FileHeader))||actual_nt.OptionalHeader.SizeOfImage!=size||(actual_nt.OptionalHeader.ImageBase!=nt->OptionalHeader.ImageBase&&actual_nt.OptionalHeader.ImageBase!=(uint64_t)(uintptr_t)module))return image_refused(__LINE__);
 // Delay import or CLR layouts require a separate normalization contract.
 if(nt->OptionalHeader.DataDirectory[IMAGE_DIRECTORY_ENTRY_DELAY_IMPORT].Size||nt->OptionalHeader.DataDirectory[IMAGE_DIRECTORY_ENTRY_COM_DESCRIPTOR].Size)return image_refused(__LINE__);
 unsigned char *image=(unsigned char*)calloc(size,1);if(!image)return image_refused(__LINE__);int good=0;unsigned failure_line=0;
 memcpy(image,raw,headers);
 const IMAGE_SECTION_HEADER *table=(const IMAGE_SECTION_HEADER*)(raw+section_start);
 for(unsigned s=0;s<sections;s++){
  const IMAGE_SECTION_HEADER *section=table+s;
  size_t span=section->Misc.VirtualSize>section->SizeOfRawData?section->Misc.VirtualSize:section->SizeOfRawData;
  if(!within(section->VirtualAddress,span,size)||!within(section->PointerToRawData,section->SizeOfRawData,length)){failure_line=__LINE__;goto done;}
  memcpy(image+section->VirtualAddress,raw+section->PointerToRawData,section->SizeOfRawData);
 }
 IMAGE_DATA_DIRECTORY reloc=nt->OptionalHeader.DataDirectory[IMAGE_DIRECTORY_ENTRY_BASERELOC];
 if(!within(reloc.VirtualAddress,reloc.Size,size)||reloc.Size>16u*1024u*1024u){failure_line=__LINE__;goto done;}
 uint64_t delta=(uint64_t)(uintptr_t)module-nt->OptionalHeader.ImageBase;
 size_t cursor=reloc.VirtualAddress,end=cursor+reloc.Size;
 while(cursor<end){
  if(!within(cursor,sizeof(IMAGE_BASE_RELOCATION),end)){failure_line=__LINE__;goto done;}
  IMAGE_BASE_RELOCATION *block=(IMAGE_BASE_RELOCATION*)(image+cursor);
  if(block->SizeOfBlock<sizeof(*block)||block->SizeOfBlock%2||!within(cursor,block->SizeOfBlock,end)){failure_line=__LINE__;goto done;}
  unsigned count=(block->SizeOfBlock-sizeof(*block))/2;WORD *entries=(WORD*)(block+1);
  for(unsigned n=0;n<count;n++){
   unsigned type=entries[n]>>12;size_t location=(size_t)block->VirtualAddress+(entries[n]&4095);
   if(type==IMAGE_REL_BASED_ABSOLUTE)continue;
   if(type!=IMAGE_REL_BASED_DIR64||!within(location,8,size)){failure_line=__LINE__;goto done;}
   uint64_t value;memcpy(&value,image+location,8);value+=delta;memcpy(image+location,&value,8);
  }
  cursor+=block->SizeOfBlock;
 }
 IMAGE_DATA_DIRECTORY iat=nt->OptionalHeader.DataDirectory[IMAGE_DIRECTORY_ENTRY_IAT];
 if(!within(iat.VirtualAddress,iat.Size,size)||iat.Size>1024u*1024u){failure_line=__LINE__;goto done;}
 unsigned char buffer[65536];unsigned compared=0;
 for(unsigned s=0;s<sections;s++){
  const IMAGE_SECTION_HEADER *section=table+s;DWORD flags=section->Characteristics;
  if(!(flags&IMAGE_SCN_MEM_READ)||(flags&IMAGE_SCN_MEM_WRITE)||(flags&IMAGE_SCN_MEM_DISCARDABLE))continue;
  size_t span=section->Misc.VirtualSize>section->SizeOfRawData?section->Misc.VirtualSize:section->SizeOfRawData;
  for(size_t n=0;n<span;){
   size_t at=section->VirtualAddress+n,amount=span-n;if(amount>sizeof(buffer))amount=sizeof(buffer);
   if(!read_loaded(module,at,buffer,amount,size)){failure_line=__LINE__;goto done;}
   size_t stop=at+amount,skip_start=iat.VirtualAddress,skip_end=skip_start+iat.Size;
   if(iat.Size&&at<skip_end&&stop>skip_start){
    size_t lo=at>skip_start?at:skip_start,hi=stop<skip_end?stop:skip_end;
    memcpy(buffer+lo-at,image+lo,hi-lo);
   }
   if(memcmp(buffer,image+at,amount)){failure_line=__LINE__;goto done;}
   n+=amount;
  }
  if(flags&IMAGE_SCN_MEM_EXECUTE)compared++;
 }
 good=compared>0;
done:free(image);return good?1:image_refused(failure_line);
}

static void release(HeldModule *item){if(item->file&&item->file!=INVALID_HANDLE_VALUE)CloseHandle(item->file);if(item->module)FreeLibrary(item->module);memset(item,0,sizeof(*item));}
static int check_module(const void *address,const char *hash,HeldModule *item){
 wchar_t path[32768];LARGE_INTEGER size;HANDLE mapping=NULL;unsigned char *raw=NULL;int good=0;
 if(!GetModuleHandleExW(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS,(LPCWSTR)address,&item->module))return 0;
 DWORD length=GetModuleFileNameW(item->module,path,32768);if(!length||length>=32768)goto done;
 // Deny preexisting/new writers and deletion. Successful identity keeps this
 // exact file object open for the process lifetime; failure owns no handles.
 item->file=CreateFileW(path,GENERIC_READ,FILE_SHARE_READ,NULL,OPEN_EXISTING,FILE_ATTRIBUTE_NORMAL,NULL);
 if(item->file==INVALID_HANDLE_VALUE||!GetFileSizeEx(item->file,&size)||size.QuadPart<=0||size.QuadPart>LIMIT)goto done;
 if(!hash_file(item->file,hash)){fprintf(stderr,"NATIVEHDR_IDENTITY file fingerprint refused: %ls\n",path);goto done;}
 mapping=CreateFileMappingW(item->file,NULL,PAGE_READONLY,0,0,NULL);if(!mapping)goto done;
 raw=(unsigned char*)MapViewOfFile(mapping,FILE_MAP_READ,0,0,0);if(!raw)goto done;
 __try{good=image_matches(item->module,raw,(size_t)size.QuadPart);}__except(EXCEPTION_EXECUTE_HANDLER){good=0;}
 if(!good)fprintf(stderr,"NATIVEHDR_IDENTITY loaded image refused: %ls\n",path);
done:if(raw)UnmapViewOfFile(raw);if(mapping)CloseHandle(mapping);if(!good)release(item);return good;
}

static BOOL CALLBACK initialize(PINIT_ONCE unused,PVOID parameter,PVOID *context){
 (void)unused;(void)parameter;(void)context;LARGE_INTEGER begin,end,frequency;
 QueryPerformanceFrequency(&frequency);QueryPerformanceCounter(&begin);attempts++;
 int required=AV_CPU_FLAG_AVX512|AV_CPU_FLAG_AVX2|AV_CPU_FLAG_FMA3;
 if((av_get_cpu_flags()&required)!=required||getenv("GENESIS_NATIVE_HDR_FORCE_CPU_FALLBACK"))goto done;
 // Force delayed imports before using their actual IAT implementation slots.
 (void)avutil_version();(void)avfilter_version();(void)swscale_version();
 const void *addresses[3]={__imp_avutil_version,__imp_avfilter_version,__imp_swscale_version};
 for(unsigned n=0;n<3;n++)if(!check_module(addresses[n],fingerprints[n],held+n))goto done;
 qualified=1;
done:
 if(!qualified)for(unsigned n=0;n<3;n++)release(held+n);
 QueryPerformanceCounter(&end);
 fprintf(stderr,"NATIVEHDR_GUARD qualified=%d duration_us=%lld attempts=%u held_files=%u\n",qualified,(long long)((end.QuadPart-begin.QuadPart)*1000000/frequency.QuadPart),attempts,qualified?3u:0u);
 return TRUE;
}
int genesis_nativehdr_qualified(void){InitOnceExecuteOnce(&once,initialize,NULL,NULL);return qualified;}

#ifdef GENESIS_NATIVE_HDR_IDENTITY_TEST
int genesis_nativehdr_test_module(const void *address,const char *hash){HeldModule item={0};int result=check_module(address,hash,&item);release(&item);return result;}
unsigned genesis_nativehdr_test_attempts(void){return attempts;}
static HeldModule test_held;
int genesis_nativehdr_test_hold(const void *address,const char *hash){release(&test_held);return check_module(address,hash,&test_held);}
void genesis_nativehdr_test_release(void){release(&test_held);}
#endif
