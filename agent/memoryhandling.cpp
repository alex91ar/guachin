#include "global.hpp"


#include <windows.h>

PVOID getMem(SIZE_T size, DWORD dwProtect){
    PVOID base = NULL;
    base = VirtualAlloc(0, size, MEM_COMMIT | MEM_RESERVE, dwProtect);
    return base;
}