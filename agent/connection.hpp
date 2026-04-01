bool connectWebSocket(
    WebSocketClient& client,
    const wchar_t* host,
    INTERNET_PORT port,
    const wchar_t* path,
    bool useHttps
);

void cleanup(WebSocketClient& client);
bool sendBinary(HINTERNET websocket, const char* data, size_t size);
bool receiveBinary(HINTERNET websocket,char* output,size_t outputCapacity,size_t& receivedSize);
void closeWebSocket(WebSocketClient& client);