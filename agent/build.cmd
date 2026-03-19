@echo off
setlocal

set CXX=clang++
set CXXFLAGS=-std=c++17 -Wall -Wextra
set SOURCES=main.cpp connection.cpp identifier.cpp memoryhandling.cpp ntparsing.cpp
set TARGET=client.exe

echo Compiling %TARGET%...
%CXX% %CXXFLAGS% %SOURCES% -o %TARGET% winhttp.lib

if %errorlevel% neq 0 (
    echo.
    echo Build failed.
    exit /b %errorlevel%
)

echo.
echo Build successful: %TARGET%
endlocal