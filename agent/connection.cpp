#include "global.hpp"
#include <curl/curl.h>
#include <string.h>
#define PROFILE
#ifdef _WIN32
#include <windows.h>
#endif

void cleanup(WebSocketClient& client) {
    if (client.curl) {
        curl_easy_cleanup(client.curl);
        client.curl = nullptr;
    }
    client.connected = false;
}

bool connectWebSocket(
    WebSocketClient& client,
    const char* url
) {
    client.curl = nullptr;
    client.connected = false;

    if (curl_global_init(CURL_GLOBAL_DEFAULT) != CURLE_OK) {
        return false;
    }

    client.curl = curl_easy_init();
    if (!client.curl) {
        return false;
    }

    curl_easy_setopt(client.curl, CURLOPT_URL, url);
    curl_easy_setopt(client.curl, CURLOPT_CONNECT_ONLY, 2L);

    CURLcode rc = curl_easy_perform(client.curl);
    if (rc != CURLE_OK) {
        cleanup(client);
        return false;
    }

    client.connected = true;
    return true;
}

bool sendBinary(WebSocketClient& client, const char* data, size_t size) {
    if (!client.curl || !client.connected) {
        return false;
    }

#ifdef PROFILE
    LARGE_INTEGER freq, start, end;
    QueryPerformanceFrequency(&freq);
    QueryPerformanceCounter(&start);
#endif

    size_t sent = 0;
    while (sent < size) {
        size_t nwritten = 0;
        CURLcode rc = curl_ws_send(
            client.curl,
            data + sent,
            size - sent,
            &nwritten,
            0,
            CURLWS_BINARY
        );

        if (rc == CURLE_AGAIN) {
            continue;
        }
        if (rc != CURLE_OK) {
            return false;
        }

        sent += nwritten;
    }

    #ifdef PROFILE
        QueryPerformanceCounter(&end);
        double time = (double)(end.QuadPart - start.QuadPart) / freq.QuadPart;
        cout << "sendBinary Time: " << time << " seconds (Write)\n";
    #endif

    return true;
}

bool receiveBinary(
    WebSocketClient& client,
    char* output,
    size_t outputCapacity,
    size_t& receivedSize
) {
    receivedSize = 0;

    if (!client.curl || !client.connected) {
        return false;
    }

#ifdef PROFILE
    LARGE_INTEGER freq, start, end;
    QueryPerformanceFrequency(&freq);
    QueryPerformanceCounter(&start);
#endif

    while (1) {
        size_t nread = 0;
        const struct curl_ws_frame* meta = nullptr;

        CURLcode rc = curl_ws_recv(
            client.curl,
            output + receivedSize,
            outputCapacity - receivedSize,
            &nread,
            &meta
        );

        if (rc == CURLE_AGAIN) {
            continue;
        }
        if (rc != CURLE_OK) {
            return false;
        }

        receivedSize += nread;

        if (!meta) {
            return false;
        }

        if (meta->flags & CURLWS_CLOSE) {
            return false;
        }

        if (!(meta->flags & CURLWS_BINARY) && !(meta->flags & CURLWS_TEXT)) {
            if (meta->bytesleft == 0) {
                continue;
            }
        }

        if (meta->bytesleft == 0) {
            break;
        }

        if (receivedSize >= outputCapacity) {
            return false;
        }
    }

    #ifdef PROFILE
        QueryPerformanceCounter(&end);
        double time = (double)(end.QuadPart - start.QuadPart) / freq.QuadPart;
        cout << "receiveBinary Time: " << time << " seconds (Write)\n";
    #endif

    return true;
}