#include "global.hpp"

using namespace std;

vector<uint8_t> stringToBytes(const string& s) {
    return vector<uint8_t>(s.begin(), s.end());
}

string bytesToString(const vector<uint8_t>& bytes) {
    return string(bytes.begin(), bytes.end());
}

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
    const wstring& host,
    INTERNET_PORT port,
    const wstring& path,
    bool useHttps
) {
    client.session = WinHttpOpen(
        L"WinHTTP WebSocket Client/1.0",
        WINHTTP_ACCESS_TYPE_AUTOMATIC_PROXY,
        WINHTTP_NO_PROXY_NAME,
        WINHTTP_NO_PROXY_BYPASS,
        0
    );

    if (!client.session) {
        cerr << "WinHttpOpen failed: " << GetLastError() << endl;
        return false;
    }

    client.connect = WinHttpConnect(
        client.session,
        host.c_str(),
        port,
        0
    );

    if (!client.connect) {
        cerr << "WinHttpConnect failed: " << GetLastError() << endl;
        return false;
    }

    client.request = WinHttpOpenRequest(
        client.connect,
        L"GET",
        path.c_str(),
        nullptr,
        WINHTTP_NO_REFERER,
        WINHTTP_DEFAULT_ACCEPT_TYPES,
        useHttps ? WINHTTP_FLAG_SECURE : 0
    );

    if (!client.request) {
        cerr << "WinHttpOpenRequest failed: " << GetLastError() << endl;
        return false;
    }

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
            cerr << "WinHttpSetOption(SECURITY_FLAGS) failed: " << GetLastError() << endl;
            return false;
        }
    }

    if (!WinHttpSetOption(
            client.request,
            WINHTTP_OPTION_UPGRADE_TO_WEB_SOCKET,
            nullptr,
            0)) {
        cerr << "WinHttpSetOption(WEB_SOCKET) failed: " << GetLastError() << endl;
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
        cerr << "WinHttpSendRequest failed: " << GetLastError() << endl;
        return false;
    }

    if (!WinHttpReceiveResponse(client.request, nullptr)) {
        cerr << "WinHttpReceiveResponse failed: " << GetLastError() << endl;
        return false;
    }

    client.websocket = WinHttpWebSocketCompleteUpgrade(client.request, 0);
    if (!client.websocket) {
        cerr << "WinHttpWebSocketCompleteUpgrade failed: " << GetLastError() << endl;
        return false;
    }

    WinHttpCloseHandle(client.request);
    client.request = nullptr;

    return true;
}

bool sendBinary(HINTERNET websocket, const vector<uint8_t>& message) {
    DWORD result = WinHttpWebSocketSend(
        websocket,
        WINHTTP_WEB_SOCKET_BINARY_MESSAGE_BUFFER_TYPE,
        message.empty() ? nullptr : const_cast<uint8_t*>(message.data()),
        static_cast<DWORD>(message.size())
    );

    if (result != NO_ERROR) {
        cerr << "WinHttpWebSocketSend failed: " << result << endl;
        return false;
    }

    return true;
}

bool receiveBinary(HINTERNET websocket, vector<uint8_t>& output) {
    output.clear();

    vector<uint8_t> buffer(4096);

    while (true) {
        DWORD bytesRead = 0;
        WINHTTP_WEB_SOCKET_BUFFER_TYPE bufferType = WINHTTP_WEB_SOCKET_BINARY_FRAGMENT_BUFFER_TYPE;

        DWORD result = WinHttpWebSocketReceive(
            websocket,
            buffer.data(),
            static_cast<DWORD>(buffer.size()),
            &bytesRead,
            &bufferType
        );

        if (result != NO_ERROR) {
            cerr << "WinHttpWebSocketReceive failed: " << result << endl;
            return false;
        }

        if (bufferType == WINHTTP_WEB_SOCKET_CLOSE_BUFFER_TYPE) {
            cerr << "Server closed the WebSocket." << endl;
            return false;
        }

        if (bufferType != WINHTTP_WEB_SOCKET_BINARY_MESSAGE_BUFFER_TYPE &&
            bufferType != WINHTTP_WEB_SOCKET_BINARY_FRAGMENT_BUFFER_TYPE) {
            cerr << "Received non-binary WebSocket frame." << endl;
            return false;
        }

        output.insert(output.end(), buffer.begin(), buffer.begin() + bytesRead);

        if (bufferType == WINHTTP_WEB_SOCKET_BINARY_MESSAGE_BUFFER_TYPE) {
            break;
        }
    }

    return true;
}

bool sendText(HINTERNET websocket, const string& message) {
    vector<uint8_t> data(message.begin(), message.end());
    return sendBinary(websocket, data);
}

bool receiveText(HINTERNET websocket, string& output) {
    vector<uint8_t> data;
    if (!receiveBinary(websocket, data)) {
        return false;
    }

    output.assign(data.begin(), data.end());
    return true;
}