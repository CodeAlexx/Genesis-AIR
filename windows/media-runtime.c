// Load the shared MM-AIR media libraries before calling the delayed FFmpeg imports.
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <libavcodec/avcodec.h>
#include <libavformat/avformat.h>
#include <libavfilter/avfilter.h>
#include <libavutil/avutil.h>
#include <libswscale/swscale.h>
#include <libswresample/swresample.h>

int genesis_media_runtime_init(void) {
    wchar_t directory[32768], filename[32768];
    DWORD count = GetEnvironmentVariableW(L"GENESIS_FFMPEG_RUNTIME", directory, 32768);
    if (count >= 32768) { fprintf(stderr, "[GA_MEDIA_RUNTIME] Runtime path is too long\n"); return 0; }
    if (!count) {
        count = GetModuleFileNameW(NULL, filename, 32768);
        if (!count || count >= 32768) return 0;
        wchar_t* slash = wcsrchr(filename, L'\\');
        if (!slash) return 0;
        slash[1] = 0;
        wcscpy_s(directory, 32768, filename);
        wcscat_s(filename, 32768, L"genesis-media-runtime.txt");
        FILE* config = _wfopen(filename, L"rb");
        if (config) {
            char utf8[131072];
            if (!fgets(utf8, sizeof(utf8), config)) { fclose(config); return 0; }
            fclose(config);
            utf8[strcspn(utf8, "\r\n")] = 0;
            if (!MultiByteToWideChar(CP_UTF8, MB_ERR_INVALID_CHARS, utf8, -1, directory, 32768)) {
                fprintf(stderr, "[GA_MEDIA_RUNTIME] Invalid UTF-8 runtime path\n"); return 0;
            }
        }
    }
    const wchar_t* libraries[] = {L"avutil-61.dll", L"swresample-7.dll", L"avcodec-63.dll",
        L"avformat-63.dll", L"avfilter-12.dll", L"swscale-10.dll"};
    for (int i = 0; i < 6; ++i) {
        wcscpy_s(filename, 32768, directory);
        size_t n = wcslen(filename);
        if (n && filename[n-1] != L'\\' && filename[n-1] != L'/') wcscat_s(filename, 32768, L"\\");
        wcscat_s(filename, 32768, libraries[i]);
        if (!LoadLibraryExW(filename, NULL, LOAD_LIBRARY_SEARCH_DLL_LOAD_DIR | LOAD_LIBRARY_SEARCH_DEFAULT_DIRS)) {
            fprintf(stderr, "[GA_MEDIA_RUNTIME] Cannot load shared media library %ls (Windows error %lu)\n",
                libraries[i], GetLastError()); return 0;
        }
    }
    if (AV_VERSION_MAJOR(avcodec_version()) != LIBAVCODEC_VERSION_MAJOR ||
        AV_VERSION_MAJOR(avformat_version()) != LIBAVFORMAT_VERSION_MAJOR ||
        AV_VERSION_MAJOR(avfilter_version()) != LIBAVFILTER_VERSION_MAJOR ||
        AV_VERSION_MAJOR(avutil_version()) != LIBAVUTIL_VERSION_MAJOR ||
        AV_VERSION_MAJOR(swscale_version()) != LIBSWSCALE_VERSION_MAJOR ||
        AV_VERSION_MAJOR(swresample_version()) != LIBSWRESAMPLE_VERSION_MAJOR) {
        fprintf(stderr, "[GA_MEDIA_ABI] Shared media libraries do not match this compositor\n"); return 0;
    }
    return 1;
}
