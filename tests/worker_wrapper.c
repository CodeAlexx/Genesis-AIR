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

/* Stall one export phase, including exit after replying to CLOSE. The fake
 * owns no child; its recorded PID must be gone before the CLI finishes. */
static int stall_export(const wchar_t *marker) {
    wchar_t phase[32], partial[32768];
    if (!GetEnvironmentVariableW(L"GENESIS_TEST_EXPORT_PHASE", phase, 32) ||
        !GetEnvironmentVariableW(L"GENESIS_TEST_EXPORT_PARTIAL", partial, 32768)) return 2;
    char line[16384];
    while (fgets(line, sizeof(line), stdin)) {
        if (strncmp(line, "OPEN ", 5) == 0) {
            FILE *output = _wfopen(partial, L"wb");
            if (!output) return 2;
            fputs("partial", output); fclose(output);
        }
        int block = (wcscmp(phase, L"open") == 0 && strncmp(line, "OPEN ", 5) == 0) ||
            (wcscmp(phase, L"frame") == 0 && strncmp(line, "ENC ", 4) == 0) ||
            (wcscmp(phase, L"audio") == 0 && strncmp(line, "AUDIO ", 6) == 0) ||
            ((wcscmp(phase, L"close") == 0 || wcscmp(phase, L"exit") == 0) && strncmp(line, "CLOSE", 5) == 0);
        if (!block || wcscmp(phase, L"exit") == 0) { fputs("DONE\n", stdout); fflush(stdout); }
        if (!block) continue;
        FILE *record = _wfopen(marker, L"wb");
        if (!record) return 2;
        fprintf(record, "%lu\n", GetCurrentProcessId()); fclose(record);
        Sleep(INFINITE);
        return 3;
    }
    return 3;
}

/* Exercise recovery through a real process, inheriting the AIR worker pipes. */
int wmain(int argc, wchar_t **argv) {
    wchar_t preview_mode[16];
    if (GetEnvironmentVariableW(L"GENESIS_TEST_PREVIEW_INPUT", preview_mode, 16)) return preview_input();
    wchar_t starts[32768], crash[32768], worker[32768], command[32768];
    if (!GetEnvironmentVariableW(L"GENESIS_TEST_STARTS", starts, 32768) ||
        !GetEnvironmentVariableW(L"GENESIS_TEST_WORKER", worker, 32768)) return 2;
    FILE *log = _wfopen(starts, L"ab");
    if (!log) return 2;
    fputs("start\n", log); fclose(log);
    wchar_t audio_block[32768];
    if (GetEnvironmentVariableW(L"GENESIS_TEST_AUDIO_BLOCK", audio_block, 32768) &&
        GetFileAttributesW(audio_block) == INVALID_FILE_ATTRIBUTES) return stall_audio(audio_block);
    wchar_t export_block[32768];
    if (argc > 1 && wcscmp(argv[1], L"--serve") == 0 &&
        GetEnvironmentVariableW(L"GENESIS_TEST_EXPORT_BLOCK", export_block, 32768) &&
        GetFileAttributesW(export_block) == INVALID_FILE_ATTRIBUTES) return stall_export(export_block);
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
