/* Controlled real child-process fixture. It records the exact OPEN target,
 * completes deterministic bytes, and blocks until the test releases it.
 * No codec, display, audio device, or parent-process emulation is involved. */
#ifndef _WIN32
#define _POSIX_C_SOURCE 200809L
#endif
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#ifdef _WIN32
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
static FILE *open_file(const char *path, const char *mode) {
    wchar_t name[32768], how[16];
    if (!MultiByteToWideChar(CP_UTF8, MB_ERR_INVALID_CHARS, path, -1, name, 32768) ||
        !MultiByteToWideChar(CP_UTF8, MB_ERR_INVALID_CHARS, mode, -1, how, 16)) return NULL;
    return _wfopen(name, how);
}
static void pause_step(void) { Sleep(5); }
static unsigned long pid(void) { return GetCurrentProcessId(); }
static const char *variable(const wchar_t *name, char *buffer) {
    wchar_t value[32768];
    DWORD n=GetEnvironmentVariableW(name,value,32768);if(!n||n>=32768)return NULL;
    return WideCharToMultiByte(CP_UTF8,WC_ERR_INVALID_CHARS,value,-1,buffer,131072,NULL,NULL)?buffer:NULL;
}
#else
#include <unistd.h>
#include <time.h>
static FILE *open_file(const char *path, const char *mode) { return fopen(path, mode); }
static void pause_step(void) { struct timespec t={0,5000000}; nanosleep(&t,NULL); }
static unsigned long pid(void) { return (unsigned long)getpid(); }
#endif
static int write_file(const char *path, const char *body) {
    FILE *f=open_file(path,"wb"); if(!f)return 0;
    size_t n=strlen(body); int ok=fwrite(body,1,n,f)==n;
    return fclose(f)==0 && ok;
}
static int exists(const char *path) {
    FILE *f=open_file(path,"rb");if(!f)return 0;fclose(f);return 1;
}
int main(void) {
#ifdef _WIN32
    static char env_witness[131072],env_release[131072],env_foreign[131072],env_create[131072];
    const char *witness=variable(L"GENESIS_OWNERSHIP_WITNESS",env_witness);
    const char *release=variable(L"GENESIS_OWNERSHIP_RELEASE",env_release);
    const char *foreign=variable(L"GENESIS_OWNERSHIP_FOREIGN",env_foreign);
    const char *create=variable(L"GENESIS_OWNERSHIP_CREATE",env_create);
#else
    const char *witness=getenv("GENESIS_OWNERSHIP_WITNESS");
    const char *release=getenv("GENESIS_OWNERSHIP_RELEASE");
    const char *foreign=getenv("GENESIS_OWNERSHIP_FOREIGN");
    const char *create=getenv("GENESIS_OWNERSHIP_CREATE");
#endif
    if(!witness)return 2;
    static char line[1048576],token[32768],target[32768],name[32768],body[128];
    while(fgets(line,sizeof(line),stdin)) {
        if(strncmp(line,"OPEN ",5)==0) {
            if(sscanf(line+5,"%32767s",token)!=1)return 2;
            size_t at=0;
            for(size_t i=0;token[i];i++) {
                if(token[i]=='%'&&token[i+1]&&token[i+2]) {
                    unsigned value;if(sscanf(token+i+1,"%2x",&value)!=1)return 2;
                    target[at++]=(char)value;i+=2;
                }else target[at++]=token[i];
            }
            target[at]=0;
            if(!create&&!write_file(target,"independent complete export payload\n"))return 2;
            if(snprintf(name,sizeof(name),"%s.target",witness)>=(int)sizeof(name)||!write_file(name,target))return 2;
            snprintf(body,sizeof(body),"%lu\n",pid());
            if(snprintf(name,sizeof(name),"%s.pid",witness)>=(int)sizeof(name)||!write_file(name,body))return 2;
            if(create) {
                while(!exists(create))pause_step();
                if(!write_file(target,"independent complete export payload\n"))return 2;
            }
            if(foreign&&!write_file(foreign,"foreign entry preserved\n"))return 2;
            while(release&&!exists(release))pause_step();
        }
        fputs("DONE\n",stdout);fflush(stdout);
    }
    return 0;
}
