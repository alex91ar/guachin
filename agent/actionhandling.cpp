#include "global.hpp"
#include <sstream>
#include <iomanip>

typedef unsigned long long (*ShellcodeFunc)();
using QWORD = uint64_t;

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
        cout << "Empty message" << endl;
        return "";
    }

    uint8_t type = (uint8_t) msg[0];

    switch (type) {
        case 0x00:{
            cout << "Action 0 triggered (exec)" << endl;
            printStringAsHex(msg);
            QWORD shellcode_size = *((QWORD*)msg.substr(1).c_str());
            string shellcode = msg.substr(1+8,shellcode_size);
            cout << "Shellcode size = " << (hex) << shellcode_size << endl;
            memcpy(mem, shellcode.c_str(), shellcode_size);
            QWORD retparams[20];
            int paramcounter = 0;
            for(QWORD returnvals = 1+8+shellcode_size; returnvals < msg.size();returnvals+=8)
            {
                memcpy(retparams+paramcounter, ((char*)msg.c_str())+returnvals, 8);
                paramcounter++;

            }
            ShellcodeFunc exec = (ShellcodeFunc)(mem);
            
            unsigned long long retval = exec();
            string s_retval = string(1, 1);
            for(int i = 0; i < paramcounter; i++){
                cout << to_hex((uint8_t*)retparams[i], 4) << endl;
                s_retval += to_hex((uint8_t*)retparams[i],4);
            }
            
            s_retval += to_hex((uint8_t*)retval, 4);
            return s_retval;
            break;
        }
        case 0x01: {
        cout << "Action 1 triggered (read)" << endl;
        
        // Check if message has enough header data (1 byte type + 8 bytes addr + 8 bytes len)
        if (msg.size() < 17) {
            cout << "Invalid read request: Message too short" << endl;
            return string(1, 0x01) + "ERROR: SHORT_MSG";
        }

        // Extract Address and Length from the message string
        uint64_t startAddr;
        uint64_t readLen;
        memcpy(&startAddr, msg.data() + 1, 8);
        memcpy(&readLen, msg.data() + 9, 8);

        cout << "Reading " << dec << readLen << " bytes from 0x" << hex << startAddr << endl;

        // Use a stringstream to build the hex response or return raw bytes
        // For a pentest tool, returning raw bytes is usually more efficient
        string s_retval = string(1, 0x01); // Header indicating success/type 1
        
        try {
            // Caution: Accessing arbitrary addresses can cause a crash (Access Violation)
            // If startAddr is invalid. In a real tool, consider using IsBadReadPtr 
            // or a __try/__except block.
            s_retval.append(reinterpret_cast<const char*>(startAddr), readLen);
        } catch (...) {
            cout << "Memory access violation at 0x" << hex << startAddr << endl;
            return string(1, 0x01) + "ERROR: FAULT";
        }

        // If you want the output as a Hex String for the console:
        stringstream ss;
        ss << hex << setfill('0');
        for (unsigned char c : s_retval.substr(1)) {
            ss << setw(2) << static_cast<int>(c);
        }
        
        // Return the response (Type byte + hex string)
        return string(1, 0x01) + ss.str();
        break;
        }

        case 0x02:
            cout << "Action 2 triggered" << endl;
            break;

        case 0x03:
            cout << "Action 3 triggered" << endl;
            break;

        default:
            cout << "Unknown action: 0x" << hex << (int)type << endl;
            break;
    }
    return "";
}