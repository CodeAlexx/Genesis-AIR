/* Atomic, no-replace publication of a complete regular file on the same volume.
 * Exit 0: published and source removed; 2: destination exists; 3: invalid source;
 * 4: invalid invocation; 5: publication failed; 6: published, source retained.
 * The caller owns the source and must handle exit 6 as success plus cleanup.
 * No shell, copy fallback, overwrite flag, or codec dependency is involved. */
#ifdef _WIN32
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
int wmain(int argc, wchar_t **argv) {
    if (argc != 3 || !argv[1][0] || !argv[2][0]) return 4;
    DWORD attrs = GetFileAttributesW(argv[1]);
    if (attrs == INVALID_FILE_ATTRIBUTES ||
        (attrs & (FILE_ATTRIBUTE_DIRECTORY | FILE_ATTRIBUTE_REPARSE_POINT))) return 3;
    if (MoveFileExW(argv[1], argv[2], 0)) return 0;
    DWORD error = GetLastError();
    if (error == ERROR_FILE_EXISTS || error == ERROR_ALREADY_EXISTS) return 2;
    /* Windows may report ACCESS_DENIED for an existing directory destination. */
    if (GetFileAttributesW(argv[2]) != INVALID_FILE_ATTRIBUTES) return 2;
    return 5;
}
#else
#define _POSIX_C_SOURCE 200809L
#include <errno.h>
#include <sys/stat.h>
#include <unistd.h>
int main(int argc, char **argv) {
    if (argc != 3 || !argv[1][0] || !argv[2][0]) return 4;
    struct stat st;
    if (lstat(argv[1], &st) != 0 || !S_ISREG(st.st_mode)) return 3;
    /* link() is atomic and cannot replace a destination, including a symlink.
     * EXDEV is refused rather than exposing a partially copied final file. */
    if (link(argv[1], argv[2]) != 0) return errno == EEXIST ? 2 : 5;
    return unlink(argv[1]) == 0 ? 0 : 6;
}
#endif
