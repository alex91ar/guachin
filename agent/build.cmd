@echo off
setlocal

REM ===== CONFIG =====
set CXX=clang++
set CXXFLAGS=-std=c++17 -Wall -Wextra -m64
set SOURCES=main.cpp connection.cpp identifier.cpp memoryhandling.cpp ntparsing.cpp
set OUTPUT_DIR=build
set TARGET=%OUTPUT_DIR%\client.exe

REM ===== CREATE OUTPUT DIR =====
if not exist %OUTPUT_DIR% (
    mkdir %OUTPUT_DIR%
)

echo.
echo ==============================
echo Compiling %TARGET%...
echo ==============================

REM ===== COMPILE =====
%CXX% %CXXFLAGS% %SOURCES% -o %TARGET% winhttp.lib

REM ===== CHECK RESULT =====
if %errorlevel% neq 0 (
    echo.
    echo ❌ Build failed.
    exit /b %errorlevel%
)

REM ===== SUCCESS =====
echo.
echo ✅ Build successful!
echo Output: %CD%\%TARGET%

endlocal