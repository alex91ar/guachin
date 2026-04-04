#include <winsock2.h>
#include <ws2tcpip.h>
#include <stdint.h>
#include <stddef.h>
#include <string.h>
#include <windows.h>
#include <winhttp.h>
#include <curl/curl.h>
using QWORD = unsigned long long;
using namespace std;

struct WebSocketClient {
    CURL* curl;
    bool connected;
};

extern PVOID scratchpad;
unsigned long long measure(unsigned long long (*func)()) ;

//#define DEBUG
#include <iostream>
using namespace std;
#ifdef DEBUG
  #define DBG cout
#else
  #define DBG if (true) {} else cout
#endif
