x86_64-w64-mingw32-g++ \
  main.cpp connection.cpp identifier.cpp ntparsing.cpp memoryhandling.cpp \
  -std=c++17 -Wall -Wextra \
  -static -static-libgcc -static-libstdc++ \
  -o client.exe \
  -masm=intel \
  -lwinhttp -lws2_32 -lbcrypt