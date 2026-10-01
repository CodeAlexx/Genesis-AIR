#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdio.h>
#include <wchar.h>

/* Exercise recovery through a real process, inheriting the AIR worker pipes. */
int wmain(int argc, wchar_t **argv) {
    wchar_t starts[32768], crash[32768], worker[32768], command[32768];
    if (!GetEnvironmentVariableW(L"GENESIS_TEST_STARTS", starts, 32768) ||
        !GetEnvironmentVariableW(L"GENESIS_TEST_WORKER", worker, 32768)) return 2;
    FILE *log = _wfopen(starts, L"ab");
    if (!log) return 2;
    fputs("start\n", log); fclose(log);
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
