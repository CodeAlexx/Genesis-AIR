#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdio.h>
#include <wchar.h>
#include <string.h>
#include <stdlib.h>

/* Deterministic wire producer for retained-reader checks. It rewrites pixels
 * in place, just like the real compositor, and deliberately emits bad lengths. */
static int preview_input(void) {
    char line[16384];
    while (fgets(line, sizeof(line), stdin)) {
        char verb[32], pattern[32], encoded[4096], decoded[4096];
        unsigned width, height;
        if (sscanf_s(line, "%31s %u %u %31s %4095s", verb, (unsigned)sizeof(verb),
                     &width, &height, pattern, (unsigned)sizeof(pattern),
                     encoded, (unsigned)sizeof(encoded)) != 5 ||
            strcmp(verb, "PREVIEWFIT") != 0 || width == 0 || height == 0 ||
            width > 1280 || height > 720) return 2;
        if (strcmp(pattern, "error") == 0) {
            fputs("ERR [GA_TEST_REQUEST] fixture refusal\n", stdout); fflush(stdout); continue;
        }
        size_t at = 0;
        for (size_t i = 0; encoded[i]; ++i) {
            if (encoded[i] == '%' && encoded[i+1] && encoded[i+2]) {
                unsigned value;
                if (sscanf_s(encoded+i+1, "%2x", &value) != 1) return 2;
                decoded[at++] = (char)value; i += 2;
            } else decoded[at++] = encoded[i];
        }
        decoded[at] = 0;
        wchar_t path[4096];
        if (!MultiByteToWideChar(CP_UTF8, MB_ERR_INVALID_CHARS, decoded, -1, path, 4096)) return 2;
        if (strcmp(pattern, "crash-once") == 0) {
            wchar_t marker[4096];
            if (_snwprintf_s(marker, 4096, _TRUNCATE, L"%s.crash", path) < 0) return 2;
            if (GetFileAttributesW(marker) == INVALID_FILE_ATTRIBUTES) {
                FILE *created = _wfopen(marker, L"wb");
                if (!created) return 2;
                fclose(created);
                if (!DeleteFileW(path)) return 2;
                return 3;
            }
            strcpy_s(pattern, sizeof(pattern), "blue");
        }
        size_t wanted = (size_t)width * height * 4;
        size_t count = strcmp(pattern, "short") == 0 ? wanted-1 :
                       strcmp(pattern, "extra") == 0 ? wanted+1 :
                       strcmp(pattern, "empty") == 0 ? 0 : wanted;
        unsigned char *pixels = (unsigned char *)malloc(wanted+1);
        if (!pixels) return 2;
        for (size_t i = 0; i < wanted; i += 4) {
            pixels[i] = strcmp(pattern, "red") == 0 ? 255 : 0;
            pixels[i+1] = strcmp(pattern, "green") == 0 ? 255 : 0;
            pixels[i+2] = strcmp(pattern, "blue") == 0 ? 255 : 0;
            pixels[i+3] = 255;
        }
        pixels[wanted] = 42;
        FILE *output = _wfopen(path, L"wb");
        if (!output) { free(pixels); return 2; }
        int wrote = fwrite(pixels, 1, count, output) == count;
        int closed = fclose(output) == 0;
        free(pixels);
        if (!wrote || !closed) return 2;
        fprintf(stdout, "DONE %s\n", decoded); fflush(stdout);
    }
    return 0;
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
