#include "global.hpp"

wstring random_uuid() {
    random_device rd;
    mt19937 gen(rd());
    uniform_int_distribution<int> dist(0, 255);

    unsigned char bytes[16];
    for (int i = 0; i < 16; i++) {
        bytes[i] = static_cast<unsigned char>(dist(gen));
    }

    bytes[6] = (bytes[6] & 0x0F) | 0x40;
    bytes[8] = (bytes[8] & 0x3F) | 0x80;

    wstringstream ss;
    ss << hex << setfill(L'0');

    for (int i = 0; i < 16; i++) {
        ss << setw(2) << static_cast<int>(bytes[i]);
        if (i == 3 || i == 5 || i == 7 || i == 9) {
            ss << L"-";
        }
    }

    return ss.str();
}

string random_uuid_s() {
    random_device rd;
    mt19937 gen(rd());
    uniform_int_distribution<int> dist(0, 255);

    unsigned char bytes[16];
    for (int i = 0; i < 16; i++) {
        bytes[i] = static_cast<unsigned char>(dist(gen));
    }

    bytes[6] = (bytes[6] & 0x0F) | 0x40;
    bytes[8] = (bytes[8] & 0x3F) | 0x80;

    stringstream ss;
    ss << hex << setfill('0');

    for (int i = 0; i < 16; i++) {
        ss << setw(2) << static_cast<int>(bytes[i]);
        if (i == 3 || i == 5 || i == 7 || i == 9) {
            ss << "-";
        }
    }

    return ss.str();
}

string getOperatingSystem() {
#ifdef _WIN32
    return "Windows";
#elif __APPLE__
    return "macOS";
#elif __linux__
    return "Linux";
#elif __unix__
    return "Unix";
#else
    return "Unknown";
#endif
}