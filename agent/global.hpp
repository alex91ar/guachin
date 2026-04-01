#include <vector>
#include <windows.h>
#include <winhttp.h>
using QWORD = unsigned long long;
using namespace std;
struct WebSocketClient {
    HINTERNET session = nullptr;
    HINTERNET connect = nullptr;
    HINTERNET request = nullptr;
    HINTERNET websocket = nullptr;
};

extern PVOID scratchpad;