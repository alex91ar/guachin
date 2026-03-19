bool connectWebSocket(
    WebSocketClient& client,
    const wstring& host,
    INTERNET_PORT port,
    const wstring& path,
    bool useHttps
);

void cleanup(WebSocketClient& client);
bool sendText(HINTERNET websocket, const string& message);
bool receiveText(HINTERNET websocket, string& output);
