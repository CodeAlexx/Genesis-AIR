#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdio.h>
#include <wchar.h>
#include <string.h>

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
