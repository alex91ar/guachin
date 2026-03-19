#include <iostream>
#include <string>
#include <vector>
#include <random>
#include <sstream>
#include <iomanip>
#include <windows.h>
#include <winhttp.h>

using namespace std;

struct WebSocketClient {
    HINTERNET session = nullptr;
    HINTERNET connect = nullptr;
    HINTERNET request = nullptr;
    HINTERNET websocket = nullptr;
};