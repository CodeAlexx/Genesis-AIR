#define WIN32_LEAN_AND_MEAN
#include <winsock2.h>
#include <windows.h>
#include <stdio.h>
#include <wchar.h>
#include <string.h>
#include <stdlib.h>

/* A real independent binary socket producer. Deliberately wrong identities,
 * fragmented payloads and short/extra frames exercise refusal and recovery. */
static int send_all(SOCKET socket, const unsigned char *bytes, size_t count, size_t chunk) {
    while (count) {
        int portion = (int)(count > chunk ? chunk : count);
        int sent = send(socket, (const char *)bytes, portion, 0);
        if (sent <= 0) return 0;
        bytes += sent; count -= (size_t)sent;
    }
    return 1;
}
static void number_le(unsigned char *header, size_t at, unsigned long long value, size_t count) {
    for (size_t i=0; i<count; ++i) {header[at+i]=(unsigned char)value; value >>= 8;}
}
static void port_failure(const wchar_t *path, const char *stage, unsigned long long packets,
                         unsigned port, int error) {
    wchar_t receipt[4096];
    if(_snwprintf_s(receipt,4096,_TRUNCATE,L"%s.ports-error.jsonl",path)<0)return;
    FILE *metrics=_wfopen(receipt,L"ab");if(!metrics)return;
    fprintf(metrics,"{\"pid\":%lu,\"stage\":\"%s\",\"completed\":%llu,\"port\":%u,\"winsock_error\":%d}\n",
        GetCurrentProcessId(),stage,packets,port,error);
    fclose(metrics);
}
static int preview_input(void) {
    WSADATA data;
    if (WSAStartup(MAKEWORD(2,2),&data)) return 2;
    char line[16384];
    unsigned char client_ports[65536]={0},listener_ports[65536]={0};
    unsigned long long packets=0,unique_clients=0,unique_listeners=0;
    ULONGLONG began=GetTickCount64();
    while (fgets(line,sizeof(line),stdin)) {
        char verb[32],pattern[32],encoded[4096],decoded[4096];
        unsigned width,height,port;
        unsigned long long token,sequence;
        if (sscanf_s(line,"%31s %u %u %u %llu %llu %31s %4095s",verb,(unsigned)sizeof(verb),
            &width,&height,&port,&token,&sequence,pattern,(unsigned)sizeof(pattern),
            encoded,(unsigned)sizeof(encoded)) != 8 || strcmp(verb,"PREVIEWTCP") ||
            !width || !height || width>1280 || height>720 || !port || port>65535) return 2;
        if (!strcmp(pattern,"error")) {fputs("ERR [GA_TEST_REQUEST] fixture refusal\n",stdout); fflush(stdout); continue;}
        if (!strcmp(pattern,"missing")) {fputs("DONE\n",stdout); fflush(stdout); continue;}
        size_t at=0;
        for (size_t i=0; encoded[i]; ++i) {
            if (encoded[i]=='%' && encoded[i+1] && encoded[i+2]) {
                unsigned value; if(sscanf_s(encoded+i+1,"%2x",&value)!=1) return 2;
                decoded[at++]=(char)value; i+=2;
            } else decoded[at++]=encoded[i];
        }
        decoded[at]=0;
        int done_first=!strcmp(pattern,"done-first");
        if(done_first) {
            /* Force the consumer's text lane to become readable before its
             * accept step can complete; retain a diagnostic after DONE too. */
            fprintf(stdout,"DONE %s\n[gcompose] retained diagnostic\n",decoded);
            fflush(stdout);Sleep(100);
        }
        wchar_t path[4096];
        if(!MultiByteToWideChar(CP_UTF8,MB_ERR_INVALID_CHARS,decoded,-1,path,4096)) return 2;
        if(!strcmp(pattern,"crash-once")) {
            wchar_t marker[4096];
            if(_snwprintf_s(marker,4096,_TRUNCATE,L"%s.crash",path)<0) return 2;
            if(GetFileAttributesW(marker)==INVALID_FILE_ATTRIBUTES) {
                FILE *created=_wfopen(marker,L"wb"); if(!created) return 2;
                fclose(created); return 3;
            }
            strcpy_s(pattern,sizeof(pattern),"blue");
        }
        size_t wanted=(size_t)width*height*4;
        size_t count=!strcmp(pattern,"short")?wanted-1:!strcmp(pattern,"extra")?wanted+1:
            !strcmp(pattern,"empty")?0:wanted;
        unsigned char *pixels=(unsigned char*)malloc(wanted+1); if(!pixels)return 2;
        for(size_t i=0;i<wanted;i+=4) {
            pixels[i]=!strcmp(pattern,"red")||!strcmp(pattern,"fragment")||done_first?255:0;
            pixels[i+1]=!strcmp(pattern,"green")?255:0;
            pixels[i+2]=!strcmp(pattern,"blue")?255:0;
            pixels[i+3]=255;
        }
        pixels[wanted]=42;
        SOCKET stream=socket(AF_INET,SOCK_STREAM,IPPROTO_TCP); if(stream==INVALID_SOCKET)return 2;
        struct sockaddr_in address={0}; address.sin_family=AF_INET;
        address.sin_addr.s_addr=htonl(INADDR_LOOPBACK); address.sin_port=htons((unsigned short)port);
        DWORD timeout=3000; setsockopt(stream,SOL_SOCKET,SO_SNDTIMEO,(const char*)&timeout,sizeof(timeout));
        if(connect(stream,(struct sockaddr*)&address,sizeof(address))) {
            port_failure(path,"connect",packets,port,WSAGetLastError());
            closesocket(stream);free(pixels);return 2;
        }
        struct sockaddr_in local={0};int local_size=sizeof(local);
        if(getsockname(stream,(struct sockaddr*)&local,&local_size))return 2;
        unsigned local_port=ntohs(local.sin_port);
        if(!client_ports[local_port]){client_ports[local_port]=1;unique_clients++;}
        if(!listener_ports[port]){listener_ports[port]=1;unique_listeners++;}
        unsigned char header[40]={0}; memcpy(header,"GAPIX001",8);
        number_le(header,8,token+(!strcmp(pattern,"bad-token")),8);
        number_le(header,16,sequence+(!strcmp(pattern,"bad-sequence")),8);
        number_le(header,24,width+(!strcmp(pattern,"bad-width")),4);
        number_le(header,28,height,4);
        number_le(header,32,wanted+(!strcmp(pattern,"bad-count")),8);
        if(!strcmp(pattern,"bad-magic"))header[0]='X';
        size_t chunk=!strcmp(pattern,"fragment")?3:65536;
        int good=send_all(stream,header,40,chunk) && send_all(stream,pixels,count,chunk);
        shutdown(stream,SD_SEND);closesocket(stream);free(pixels);
        /* A consumer refusing an invalid header may close before this send ends. */
        if(!good && strncmp(pattern,"bad-",4)) {
            port_failure(path,"send",packets,port,WSAGetLastError());return 2;
        }
        packets++;
        if(packets%3600==0) {
            wchar_t receipt[4096];
            if(_snwprintf_s(receipt,4096,_TRUNCATE,L"%s.ports.json",path)<0)return 2;
            FILE *metrics=_wfopen(receipt,L"wb");if(!metrics)return 2;
            fprintf(metrics,"{\"packets\":%llu,\"unique_client_ports\":%llu,\"unique_listener_ports\":%llu,\"client_port_reuses\":%llu,\"listener_port_reuses\":%llu,\"elapsed_ms\":%llu}\n",
                packets,unique_clients,unique_listeners,packets-unique_clients,packets-unique_listeners,(unsigned long long)(GetTickCount64()-began));
            fclose(metrics);
        }
        if(!done_first){fprintf(stdout,"DONE %s\n",decoded);fflush(stdout);}
    }
    WSACleanup();return 0;
}
/* A real blocked pipe/child for active audio cancellation, only when requested
 * by the fixture. A later start delegates to the genuine compositor. */
static int stall_audio(const wchar_t *marker) {
    wchar_t write_mode[16], partial[32768];
    int blocked_write = GetEnvironmentVariableW(L"GENESIS_TEST_AUDIO_BLOCK_WRITE", write_mode, 16) != 0;
    char line[16384];
    while (fgets(line, sizeof(line), stdin)) {
        if (strncmp(line, "PLAYWAVE ", 9) == 0) {
            fputs("DONE\n", stdout); fflush(stdout);
            if (!blocked_write) continue;
        } else if (strncmp(line, "AUDIOSTREAM ", 12) != 0) {
            fputs("DONE\n", stdout); fflush(stdout); continue;
        }
        if (GetEnvironmentVariableW(L"GENESIS_TEST_AUDIO_PARTIAL", partial, 32768)) {
            FILE *output = _wfopen(partial, L"wb");
            if (!output) return 2;
            fputs("partial", output); fclose(output);
        }
        FILE *record = _wfopen(marker, L"wb");
        if (!record) return 2;
        fprintf(record, "%lu\n", GetCurrentProcessId()); fclose(record);
        Sleep(INFINITE);
        return 3;
    }
    return 3;
}

/* Genuine pre-OPEN graph/query RPC for the cancellation fixture only.
 * A suspended child enters a private kill-on-close job before resume. The job
 * handle is never inherited; killing the wrapper cannot orphan its child. */
typedef struct export_preflight {
    HANDLE input, output, process, job;
    DWORD pid;
    FILE *trace;
} export_preflight;

static void export_trace(export_preflight *state, const char *kind, const char *line) {
    if (!state->trace) return;
    fprintf(state->trace,"%s %s",kind,line);
    size_t count=strlen(line);
    if (!count || line[count-1]!='\n') fputc('\n',state->trace);
    fflush(state->trace);
}
static void preflight_close(export_preflight *state) {
    if (state->input) {CloseHandle(state->input);state->input=NULL;}
    if (state->output) {CloseHandle(state->output);state->output=NULL;}
    if (state->process) {CloseHandle(state->process);state->process=NULL;}
    if (state->job) {CloseHandle(state->job);state->job=NULL;}
}
static int preflight_failure(export_preflight *state, const char *operation) {
    DWORD error=GetLastError();
    fprintf(stderr,"[GA_TEST_EXPORT_PREFLIGHT] %s (Win32 %lu)\n",operation,error);fflush(stderr);
    if (state->job) TerminateJobObject(state->job,2);
    if (state->process) WaitForSingleObject(state->process,5000);
    preflight_close(state);
    return 0;
}
static int preflight_start(export_preflight *state, int argc, wchar_t **argv, const wchar_t *worker) {
    SECURITY_ATTRIBUTES security={sizeof(security),NULL,TRUE};
    HANDLE child_input=NULL,child_output=NULL;
    if (!CreatePipe(&child_input,&state->input,&security,0) ||
        !CreatePipe(&state->output,&child_output,&security,0)) goto failure;
    if (!SetHandleInformation(state->input,HANDLE_FLAG_INHERIT,0) ||
        !SetHandleInformation(state->output,HANDLE_FLAG_INHERIT,0)) goto failure;
    state->job=CreateJobObjectW(NULL,NULL);if(!state->job)goto failure;
    JOBOBJECT_EXTENDED_LIMIT_INFORMATION limits={0};
    limits.BasicLimitInformation.LimitFlags=JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE;
    if(!SetInformationJobObject(state->job,JobObjectExtendedLimitInformation,&limits,sizeof(limits)))goto failure;
    wchar_t command[32768];
    if(_snwprintf_s(command,32768,_TRUNCATE,L"\"%s\"",worker)<0)goto failure;
    for(int i=1;i<argc;i++) {
        if(wcschr(argv[i],L'"') || wcslen(command)+wcslen(argv[i])+4>=32768)goto failure;
        wcscat_s(command,32768,L" \"");wcscat_s(command,32768,argv[i]);wcscat_s(command,32768,L"\"");
    }
    SIZE_T bytes=0;
    InitializeProcThreadAttributeList(NULL,1,0,&bytes);
    LPPROC_THREAD_ATTRIBUTE_LIST attributes=HeapAlloc(GetProcessHeap(),0,bytes);
    if(!attributes)goto failure;
    if(!InitializeProcThreadAttributeList(attributes,1,0,&bytes)) {HeapFree(GetProcessHeap(),0,attributes);goto failure;}
    HANDLE inherited[2]={child_input,child_output};
    if(!UpdateProcThreadAttribute(attributes,0,PROC_THREAD_ATTRIBUTE_HANDLE_LIST,inherited,sizeof(inherited),NULL,NULL)) {
        DeleteProcThreadAttributeList(attributes);HeapFree(GetProcessHeap(),0,attributes);goto failure;
    }
    STARTUPINFOEXW startup={0};startup.StartupInfo.cb=sizeof(startup);
    startup.StartupInfo.dwFlags=STARTF_USESTDHANDLES;
    startup.StartupInfo.hStdInput=child_input;startup.StartupInfo.hStdOutput=child_output;
    startup.StartupInfo.hStdError=child_output;startup.lpAttributeList=attributes;
    PROCESS_INFORMATION child={0};
    BOOL created=CreateProcessW(worker,command,NULL,NULL,TRUE,
        CREATE_NO_WINDOW|CREATE_SUSPENDED|EXTENDED_STARTUPINFO_PRESENT,NULL,NULL,&startup.StartupInfo,&child);
    DeleteProcThreadAttributeList(attributes);HeapFree(GetProcessHeap(),0,attributes);
    CloseHandle(child_input);child_input=NULL;CloseHandle(child_output);child_output=NULL;
    if(!created)goto failure;
    state->process=child.hProcess;state->pid=child.dwProcessId;
    if(!AssignProcessToJobObject(state->job,child.hProcess)) {
        TerminateProcess(child.hProcess,2);WaitForSingleObject(child.hProcess,5000);CloseHandle(child.hThread);goto failure;
    }
    if(ResumeThread(child.hThread)==(DWORD)-1) {CloseHandle(child.hThread);goto failure;}
    CloseHandle(child.hThread);
    char event[128];sprintf_s(event,sizeof(event),"%lu",state->pid);export_trace(state,"CHILD",event);
    return 1;
failure:
    if(child_input)CloseHandle(child_input);
    if(child_output)CloseHandle(child_output);
    return preflight_failure(state,"Cannot start owned genuine worker");
}
static int preflight_rpc(export_preflight *state, const char *command) {
    export_trace(state,"IN",command);
    size_t count=strlen(command),at=0;
    while(at<count) {
        DWORD wrote=0;
        if(!WriteFile(state->input,command+at,(DWORD)(count-at),&wrote,NULL) || !wrote)
            return preflight_failure(state,"Cannot forward pre-OPEN command");
        at+=wrote;
    }
    for(;;) {
        char reply[65536];size_t used=0;
        for(;;) {
            char byte;DWORD got=0;
            if(!ReadFile(state->output,&byte,1,&got,NULL) || got!=1)
                return preflight_failure(state,"Missing genuine worker reply");
            if(used+1>=sizeof(reply))return preflight_failure(state,"Genuine reply exceeds fixture bound");
            reply[used++]=byte;
            if(byte=='\n')break;
        }
        reply[used]=0;export_trace(state,"OUT",reply);
        if(fwrite(reply,1,used,stdout)!=used || fflush(stdout)!=0)
            return preflight_failure(state,"Cannot relay genuine worker reply");
        if(strncmp(reply,"DONE",4)==0 && (reply[4]==' ' || reply[4]=='\r' || reply[4]=='\n'))return 1;
        if(strncmp(reply,"ERR",3)==0 && (reply[3]==' ' || reply[3]=='\r' || reply[3]=='\n')) {
            preflight_failure(state,"Genuine pre-OPEN worker refused command");return 0;
        }
    }
}
static int preflight_join(export_preflight *state) {
    if(state->input){CloseHandle(state->input);state->input=NULL;}
    if(WaitForSingleObject(state->process,5000)!=WAIT_OBJECT_0)
        return preflight_failure(state,"Genuine pre-OPEN worker failed to join");
    DWORD status=2;
    if(!GetExitCodeProcess(state->process,&status) || status!=0)
        return preflight_failure(state,"Genuine pre-OPEN worker exited unsuccessfully");
    JOBOBJECT_BASIC_ACCOUNTING_INFORMATION accounting={0};
    ULONGLONG deadline=GetTickCount64()+5000;
    for(;;) {
        if(!QueryInformationJobObject(state->job,JobObjectBasicAccountingInformation,&accounting,sizeof(accounting),NULL))
            return preflight_failure(state,"Cannot verify genuine worker descendants");
        if(!accounting.ActiveProcesses)break;
        if(GetTickCount64()>=deadline)return preflight_failure(state,"Genuine worker descendants did not join");
        Sleep(5);
    }
    char event[256];sprintf_s(event,sizeof(event),"%lu exit=%lu active=%lu total=%lu",
        state->pid,status,accounting.ActiveProcesses,accounting.TotalProcesses);
    export_trace(state,"JOIN",event);preflight_close(state);return 1;
}

/* Stall one export phase after genuinely resolving the accepted audio graph.
 * The genuine preflight child is joined before OPEN/marker. The blocked fake
 * owns no running child; its recorded PID must be gone before the CLI finishes. */
static int stall_export(const wchar_t *marker, int argc, wchar_t **argv, const wchar_t *worker) {
    wchar_t phase[32],partial[32768],trace_path[32768];
    if(!GetEnvironmentVariableW(L"GENESIS_TEST_EXPORT_PHASE",phase,32) ||
       !GetEnvironmentVariableW(L"GENESIS_TEST_EXPORT_PARTIAL",partial,32768))return 2;
    export_preflight genuine={0};
    if(GetEnvironmentVariableW(L"GENESIS_TEST_EXPORT_TRACE",trace_path,32768)) {
        genuine.trace=_wfopen(trace_path,L"wb");if(!genuine.trace)return 2;
    }
    if(!preflight_start(&genuine,argc,argv,worker)) {if(genuine.trace)fclose(genuine.trace);return 2;}
    int pre_open=1,status=3;char line[16384];
    while(fgets(line,sizeof(line),stdin)) {
        if(pre_open && strncmp(line,"OPEN ",5)!=0) {
            if(!preflight_rpc(&genuine,line)){status=2;goto finished;}
            continue;
        }
        if(pre_open) {
            if(!preflight_join(&genuine)){status=2;goto finished;}
            pre_open=0;
        }
        export_trace(&genuine,"MOCK_IN",line);
        if(strncmp(line,"OPEN ",5)==0) {
            FILE *output=_wfopen(partial,L"wb");if(!output){status=2;goto finished;}
            fputs("partial",output);fclose(output);
        }
        int audio=strncmp(line,"AUDIO ",6)==0 || strncmp(line,"NESTMIX ",8)==0 || strncmp(line,"NESTMIXTAIL ",12)==0;
        int block=(wcscmp(phase,L"open")==0 && strncmp(line,"OPEN ",5)==0) ||
            (wcscmp(phase,L"frame")==0 && strncmp(line,"ENC ",4)==0) ||
            (wcscmp(phase,L"audio")==0 && audio) ||
            ((wcscmp(phase,L"close")==0 || wcscmp(phase,L"exit")==0) && strncmp(line,"CLOSE",5)==0);
        if(!block || wcscmp(phase,L"exit")==0) {fputs("DONE\n",stdout);fflush(stdout);export_trace(&genuine,"MOCK_OUT","DONE\n");}
        if(!block)continue;
        FILE *record=_wfopen(marker,L"wb");if(!record){status=2;goto finished;}
        fprintf(record,"%lu\n",GetCurrentProcessId());fclose(record);
        export_trace(&genuine,"BLOCK",line);Sleep(INFINITE);status=3;goto finished;
    }
finished:
    if(genuine.process)preflight_failure(&genuine,"Pre-OPEN input ended before controlled stall");
    if(genuine.trace)fclose(genuine.trace);
    return status;
}

/* CPU-only strip producer: coded refusal and retained-session recovery, without
 * starting the media runtime. The opt-in value is the exact command receipt. */
static int strip_input(const wchar_t *receipt) {
    FILE *record=_wfopen(receipt,L"wb");if(!record)return 2;
    fprintf(record,"PID %lu\n",GetCurrentProcessId());fflush(record);
    char line[16384];
    while(fgets(line,sizeof(line),stdin)) {
        fprintf(record,"%s",line);fflush(record);
        char source[4096],output[4096];long long frame;unsigned width,height;
        if(sscanf_s(line,"THUMB %4095s %lld %u %u %4095s",source,(unsigned)sizeof(source),
            &frame,&width,&height,output,(unsigned)sizeof(output))!=5 || width!=80 || height!=45) {
            fputs("[GA_TEST_STRIP_PROTOCOL] Unexpected CPU strip command\nERR\n",stdout);fflush(stdout);continue;
        }
        if(strstr(source,"missing")) {
            fputs("[GA_TEST_THUMB_SOURCE] Authored unreadable source\nERR\n",stdout);fflush(stdout);continue;
        }
        char decoded[4096];size_t at=0;
        for(size_t i=0;output[i];i++) {
            if(output[i]=='%'&&output[i+1]&&output[i+2]) {
                unsigned value;if(sscanf_s(output+i+1,"%2x",&value)!=1){fclose(record);return 2;}
                decoded[at++]=(char)value;i+=2;
            }else decoded[at++]=output[i];
        }
        decoded[at]=0;wchar_t path[4096];
        if(!MultiByteToWideChar(CP_UTF8,MB_ERR_INVALID_CHARS,decoded,-1,path,4096)){fclose(record);return 2;}
        FILE *pixels=_wfopen(path,L"wb");if(!pixels){fclose(record);return 2;}
        unsigned char pixel[4]={17,91,(unsigned char)(frame%256),255};
        for(unsigned i=0;i<width*height;i++)if(fwrite(pixel,1,4,pixels)!=4){fclose(pixels);fclose(record);return 2;}
        fclose(pixels);fputs("DONE\n",stdout);fflush(stdout);
    }
    fclose(record);return 0;
}

/* Exercise recovery through a real process, inheriting the AIR worker pipes. */
int wmain(int argc, wchar_t **argv) {
    wchar_t strip_receipt[32768];
    if(GetEnvironmentVariableW(L"GENESIS_TEST_STRIP_INPUT",strip_receipt,32768))return strip_input(strip_receipt);
    wchar_t preview_mode[16];
    if (GetEnvironmentVariableW(L"GENESIS_TEST_PREVIEW_INPUT", preview_mode, 16)) return preview_input();
    wchar_t starts[32768], crash[32768], worker[32768], command[32768];
    if (!GetEnvironmentVariableW(L"GENESIS_TEST_STARTS", starts, 32768) ||
        !GetEnvironmentVariableW(L"GENESIS_TEST_WORKER", worker, 32768)) return 2;
    FILE *log = _wfopen(starts, L"ab");
    if (!log) return 2;
    fputs("start\n", log); fclose(log);
    /* Separate opt-in receipt: existing start-count fault tests stay unchanged. */
    wchar_t canvas_trace[32768];
    if (argc >= 5 && wcscmp(argv[1], L"--serve") == 0 && wcscmp(argv[2], L"--size") == 0 &&
        GetEnvironmentVariableW(L"GENESIS_TEST_CANVAS_TRACE", canvas_trace, 32768)) {
        FILE *canvas_log = _wfopen(canvas_trace, L"ab");
        if (!canvas_log) return 2;
        fwprintf(canvas_log, L"%ls\t%ls\n", argv[3], argv[4]);
        fclose(canvas_log);
    }
    wchar_t audio_block[32768];
    if (GetEnvironmentVariableW(L"GENESIS_TEST_AUDIO_BLOCK", audio_block, 32768) &&
        GetFileAttributesW(audio_block) == INVALID_FILE_ATTRIBUTES) return stall_audio(audio_block);
    wchar_t export_block[32768];
    if (argc > 1 && wcscmp(argv[1], L"--serve") == 0 &&
        GetEnvironmentVariableW(L"GENESIS_TEST_EXPORT_BLOCK", export_block, 32768) &&
        GetFileAttributesW(export_block) == INVALID_FILE_ATTRIBUTES) return stall_export(export_block,argc,argv,worker);
    if (GetEnvironmentVariableW(L"GENESIS_TEST_CRASH", crash, 32768) &&
        GetFileAttributesW(crash) == INVALID_FILE_ATTRIBUTES) {
        FILE *marker = _wfopen(crash, L"wb");
        if (!marker) return 2;
        fclose(marker); return 3;
    }
    _snwprintf_s(command, 32768, _TRUNCATE, L"\"%s\"", worker);
    for (int i = 1; i < argc; i++) {
        if (wcschr(argv[i], L'"') || wcslen(command) + wcslen(argv[i]) + 4 >= 32768) return 2;
        wcscat_s(command, 32768, L" \""); wcscat_s(command, 32768, argv[i]);
        wcscat_s(command, 32768, L"\"");
    }
    STARTUPINFOW startup = {sizeof(startup)};
    PROCESS_INFORMATION child = {0};
    startup.dwFlags = STARTF_USESTDHANDLES;
    startup.hStdInput = GetStdHandle(STD_INPUT_HANDLE);
    startup.hStdOutput = GetStdHandle(STD_OUTPUT_HANDLE);
    startup.hStdError = GetStdHandle(STD_ERROR_HANDLE);
    if (!CreateProcessW(worker, command, NULL, NULL, TRUE, CREATE_NO_WINDOW, NULL, NULL, &startup, &child)) return 2;
    CloseHandle(child.hThread);
    WaitForSingleObject(child.hProcess, INFINITE);
    DWORD code; GetExitCodeProcess(child.hProcess, &code); CloseHandle(child.hProcess);
    return (int)code;
}
