#!/usr/bin/env bash

set -e  # stop on error

# ===== CONFIG =====
COMPILER="x86_64-w64-mingw32-g++"
OUTPUT_DIR="./"
TARGET="$OUTPUT_DIR/client.exe"

SOURCES=(
  main.cpp
  connection.cpp
  identifier.cpp
  ntparsing.cpp
  memoryhandling.cpp
  actionhandling.cpp
  profiling.cpp
)

FLAGS=(
  -std=c++17
  -Wall -Wextra
  -Os -flto
  -ffunction-sections -fdata-sections
  -fno-exceptions -fno-rtti
  -static -static-libgcc -static-libstdc++
  -Wl,--gc-sections -Wl,-s
  -masm=intel
)

LIBS=(
  -lwinhttp
  -lws2_32
  -lbcrypt
)

# ===== CREATE OUTPUT DIR =====
mkdir -p "$OUTPUT_DIR"

echo
echo "=============================="
echo "Building x64 client..."
echo "=============================="

# ===== BUILD =====
"$COMPILER" "${SOURCES[@]}" "${FLAGS[@]}" -o "$TARGET" "${LIBS[@]}"

echo
echo "✅ Build successful!"
echo "Output: $(pwd)/$TARGET"