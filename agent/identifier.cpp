#include "global.hpp"
vector<pair<string, QWORD>> getDllSyscallsOrExports(vector<pair<string, void*>> exports);
vector<pair<string, void*>> getDllExports(wstring dllName);
string pairsToString(const vector<pair<string, QWORD>>& values);
PVOID getMem();

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
    return string(8, 0);
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

string create_handshake(){
    vector<pair<string, void*>> ntdll = getDllExports(L"ntdll.dll");
    vector<pair<string, void*>> kernel32 = getDllExports(L"kernel32.dll");
    vector<pair<string, void*>> user32 = getDllExports(L"user32.dll");
    vector<pair<string, QWORD>> ntDLLSyscalls = getDllSyscallsOrExports(ntdll);
    vector<pair<string, QWORD>> kernel32Syscalls = getDllSyscallsOrExports(kernel32);
    vector<pair<string, QWORD>> user32Syscalls = getDllSyscallsOrExports(user32);
    string ntdll_syscall_list = pairsToString(ntDLLSyscalls);
    string kernel32_syscall_list = pairsToString(kernel32Syscalls);
    string user32_syscall_list = pairsToString(user32Syscalls);
    PVOID scratchpad = getMem();
    QWORD os = 0;
    string handshake;
    handshake.append(1,(char)0);
    handshake.append((char*)(&os), 8);
    handshake.append((char*)(&scratchpad), 8);
    handshake += ntdll_syscall_list;
    handshake += ", ";
    handshake += kernel32_syscall_list;
    handshake += ", ";
    handshake += user32_syscall_list;   
    return handshake;
}