// The compositor's directory listing ABI, backed by native Unicode Windows paths.
#ifndef GENESIS_WINDOWS_DIRENT_H
#define GENESIS_WINDOWS_DIRENT_H
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdlib.h>
#include <string.h>
struct dirent { char d_name[4096]; };
typedef struct { HANDLE handle; WIN32_FIND_DATAW data; int first; struct dirent entry; } DIR;
static DIR *opendir(const char *path) {
    wchar_t pattern[32768];
    int count = MultiByteToWideChar(CP_UTF8, MB_ERR_INVALID_CHARS, path, -1, pattern, 32765);
    if (count <= 0) return NULL;
    pattern[count-1] = L'\\'; pattern[count] = L'*'; pattern[count+1] = 0;
    DIR *directory = (DIR *)calloc(1, sizeof(DIR));
    if (!directory) return NULL;
    directory->handle = FindFirstFileW(pattern, &directory->data);
    if (directory->handle == INVALID_HANDLE_VALUE) { free(directory); return NULL; }
    directory->first = 1;
    return directory;
}
static struct dirent *readdir(DIR *directory) {
    if (!directory->first && !FindNextFileW(directory->handle, &directory->data)) return NULL;
    directory->first = 0;
    if (!WideCharToMultiByte(CP_UTF8, 0, directory->data.cFileName, -1,
        directory->entry.d_name, sizeof(directory->entry.d_name), NULL, NULL)) return NULL;
    return &directory->entry;
}
static int closedir(DIR *directory) {
    FindClose(directory->handle); free(directory); return 0;
}
#endif
