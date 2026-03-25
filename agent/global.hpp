#include <iostream>
#include <string>
#include <vector>
#include <random>
#include <sstream>
#include <iomanip>
#include <windows.h>
#include <winhttp.h>
using QWORD = uint64_t;
using namespace std;
string to_hex(const uint8_t* data, size_t len);
struct WebSocketClient {
    HINTERNET session = nullptr;
    HINTERNET connect = nullptr;
    HINTERNET request = nullptr;
    HINTERNET websocket = nullptr;
};