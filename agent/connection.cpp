#include "global.hpp"
#define PROFILE
#ifdef PROFILE
#include <iostream>

using namespace std;
#endif

void cleanup(WebSocketClient& client) {
    if (client.websocket) {
        WinHttpCloseHandle(client.websocket);
        client.websocket = nullptr;
    }
    if (client.request) {
        WinHttpCloseHandle(client.request);
        client.request = nullptr;
    }
    if (client.connect) {
        WinHttpCloseHandle(client.connect);
        client.connect = nullptr;
    }
    if (client.session) {
        WinHttpCloseHandle(client.session);
        client.session = nullptr;
    }
}

bool connectWebSocket(
    WebSocketClient& client,
    const wchar_t* host,
    INTERNET_PORT port,
    const wchar_t* path,
    bool useHttps
) {
    client.session = WinHttpOpen(
        L"WinHTTP WebSocket Client/1.0",
        WINHTTP_ACCESS_TYPE_AUTOMATIC_PROXY,
        WINHTTP_NO_PROXY_NAME,
        WINHTTP_NO_PROXY_BYPASS,
        0
    );

    if (!client.session) return false;

    client.connect = WinHttpConnect(client.session, host, port, 0);
    if (!client.connect) return false;

    client.request = WinHttpOpenRequest(
        client.connect,
        L"GET",
        path,
        nullptr,
        WINHTTP_NO_REFERER,
        WINHTTP_DEFAULT_ACCEPT_TYPES,
        useHttps ? WINHTTP_FLAG_SECURE : 0
    );

    if (!client.request) return false;

    if (useHttps) {
        DWORD securityFlags =
            SECURITY_FLAG_IGNORE_UNKNOWN_CA |
            SECURITY_FLAG_IGNORE_CERT_WRONG_USAGE |
            SECURITY_FLAG_IGNORE_CERT_CN_INVALID |
            SECURITY_FLAG_IGNORE_CERT_DATE_INVALID;

        if (!WinHttpSetOption(
                client.request,
                WINHTTP_OPTION_SECURITY_FLAGS,
                &securityFlags,
                sizeof(securityFlags))) {
            return false;
        }
    }

    if (!WinHttpSetOption(
            client.request,
            WINHTTP_OPTION_UPGRADE_TO_WEB_SOCKET,
            nullptr,
            0)) {
        return false;
    }

    if (!WinHttpSendRequest(
            client.request,
            WINHTTP_NO_ADDITIONAL_HEADERS,
            0,
            WINHTTP_NO_REQUEST_DATA,
            0,
            0,
            0)) {
        return false;
    }

    if (!WinHttpReceiveResponse(client.request, nullptr)) {
        return false;
    }

    client.websocket = WinHttpWebSocketCompleteUpgrade(client.request, 0);
    if (!client.websocket) return false;

    WinHttpCloseHandle(client.request);
    client.request = nullptr;

    return true;
}

bool sendBinary(HINTERNET websocket, const char* data, size_t size) {
    #ifdef PROFILE_1
    LARGE_INTEGER freq, start, end;

    QueryPerformanceFrequency(&freq);
    QueryPerformanceCounter(&start);
    #endif
    DWORD result = WinHttpWebSocketSend(
        websocket,
        WINHTTP_WEB_SOCKET_BINARY_MESSAGE_BUFFER_TYPE,
        size == 0 ? nullptr : (void*)data,
        static_cast<DWORD>(size)
    );
    #ifdef PROFILE_1
    QueryPerformanceCounter(&end);
    double time = (double)(end.QuadPart - start.QuadPart) / freq.QuadPart;
    cout << "Time: " << time << " seconds (sendBinary)\n";
    #endif
    return result == NO_ERROR;
}

bool receiveBinary(
    HINTERNET websocket,
    char* output,
    size_t outputCapacity,
    size_t& receivedSize
) {
    WINHTTP_WEB_SOCKET_BUFFER_TYPE bufferType;
    #ifdef PROFILE
    LARGE_INTEGER freq, start, end;

    QueryPerformanceFrequency(&freq);
    QueryPerformanceCounter(&start);
    #endif
    DWORD result = WinHttpWebSocketReceive(
        websocket,
        output,
        outputCapacity,
        (DWORD*)&receivedSize,
        &bufferType
    );
    if (result != NO_ERROR) return false;

    if (bufferType == WINHTTP_WEB_SOCKET_CLOSE_BUFFER_TYPE) return false;

    #ifdef PROFILE
    QueryPerformanceCounter(&end);
    double time = (double)(end.QuadPart - start.QuadPart) / freq.QuadPart;
    cout << "Time: " << time << " seconds (receiveBinary)\n";
    #endif

    return true;
}

