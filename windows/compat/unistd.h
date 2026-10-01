#ifndef GENESIS_WINDOWS_UNISTD_H
#define GENESIS_WINDOWS_UNISTD_H
#include <direct.h>
#include <io.h>
#define mkdir(path, mode) _mkdir(path)
#define strdup _strdup
#endif
