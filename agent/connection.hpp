bool connectWebSocket(
    WebSocketClient& client,
    const char* url
);

void cleanup(WebSocketClient& client);
bool sendBinary(WebSocketClient& client, const char* data, size_t size);
bool receiveBinary(
    WebSocketClient& client,
    char* output,
    size_t outputCapacity,
    size_t& receivedSize
);