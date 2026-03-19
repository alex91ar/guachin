#include "global.hpp"


#include <windows.h>

PVOID getMem(){
    PVOID base = NULL;
    SIZE_T size = 4096;
    base = VirtualAlloc(0, size, MEM_COMMIT | MEM_RESERVE, PAGE_EXECUTE_READWRITE);
    return base;
}