#include "global.hpp"
#include <winnt.h>
#include <utility>
#include <cstdint>
#include <cstddef>
#include <optional>
#include <array>
#include <cstring>

DWORD readNextDwordIfPatternMatches(const void* address) {

    constexpr DWORD kPattern = 0xb8d18b4c; // pre-determined pattern

    const DWORD* dwordPtr = static_cast<const DWORD*>(address);

    if (*dwordPtr != kPattern) {
        return 0xFFFFFFFF;
    }

    return *(dwordPtr + 1);
}

vector<pair<string, void*>> getNtdllExports() {
    vector<pair<string, void*>> exports;

    HMODULE module = GetModuleHandleW(L"ntdll.dll");
    if (!module) {
        return exports;
    }

    auto* dos = reinterpret_cast<PIMAGE_DOS_HEADER>(module);
    if (dos->e_magic != IMAGE_DOS_SIGNATURE) {
        return exports;
    }

    auto* nt = reinterpret_cast<PIMAGE_NT_HEADERS>(
        reinterpret_cast<BYTE*>(module) + dos->e_lfanew
    );
    if (nt->Signature != IMAGE_NT_SIGNATURE) {
        return exports;
    }

    const auto& dir = nt->OptionalHeader.DataDirectory[IMAGE_DIRECTORY_ENTRY_EXPORT];
    if (!dir.VirtualAddress || !dir.Size) {
        return exports;
    }

    auto* exp = reinterpret_cast<PIMAGE_EXPORT_DIRECTORY>(
        reinterpret_cast<BYTE*>(module) + dir.VirtualAddress
    );

    auto* names = reinterpret_cast<DWORD*>(
        reinterpret_cast<BYTE*>(module) + exp->AddressOfNames
    );

    auto* functions = reinterpret_cast<DWORD*>(
        reinterpret_cast<BYTE*>(module) + exp->AddressOfFunctions
    );

    auto* ordinals = reinterpret_cast<WORD*>(
        reinterpret_cast<BYTE*>(module) + exp->AddressOfNameOrdinals
    );

    for (DWORD i = 0; i < exp->NumberOfNames; ++i) {
        const char* exportName = reinterpret_cast<const char*>(
            reinterpret_cast<BYTE*>(module) + names[i]
        );

        WORD ordinalIndex = ordinals[i];
        DWORD rva = functions[ordinalIndex];
        void* address = reinterpret_cast<void*>(
            reinterpret_cast<BYTE*>(module) + rva
        );

        exports.emplace_back(string(exportName), address);
    }

    return exports;
}

vector<pair<string, DWORD>> getNtdllSyscalls(){
    vector<pair<string, void*>> exports = getNtdllExports();
    vector<pair<string, DWORD>> returns;
    for (const auto& item : exports) {
        DWORD dwSyscall = readNextDwordIfPatternMatches(item.second);
        if(dwSyscall != 0xFFFFFFFF){
            returns.emplace_back(item.first, dwSyscall);
        }
    }
    return returns;
}

string pairsToString(const vector<pair<string, DWORD>>& values) {
    ostringstream out;

    for (size_t i = 0; i < values.size(); ++i) {
        out << values[i].first << ":" << values[i].second;

        if (i + 1 < values.size()) {
            out << ",";
        }
    }

    return out.str();
}