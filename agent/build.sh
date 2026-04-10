#!/usr/bin/env bash
set -e

COMPILER="x86_64-w64-mingw32-g++"

OUTPUT_DIR="./"
TARGET="$OUTPUT_DIR/client.exe"

# ===== PATHS =====
CURL_DIR="./curl-8.16.0"
CURL_BUILD="$CURL_DIR/build-win64"


INCLUDES=(
  -I"$CURL_DIR/include"
)

SOURCES=(
  main.cpp
  connection.cpp
  identifier.cpp
  ntparsing.cpp
  memoryhandling.cpp
  actionhandling.cpp
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
  -DCURL_STATICLIB
)

LIBS=(
  "$CURL_BUILD/lib/libcurl.a"
  -lws2_32
  -lbcrypt
  -lwinmm
  -liphlpapi
  -lcrypt32
)

mkdir -p "$OUTPUT_DIR"

echo
echo "=============================="
echo "Building x64 client (libcurl)..."
echo "=============================="

"$COMPILER" \
  "${SOURCES[@]}" \
  "${FLAGS[@]}" \
  "${INCLUDES[@]}" \
  -o "$TARGET" \
  "${LIBS[@]}"

echo
echo "✅ Build successful!"
echo "Output: $(pwd)/$TARGET"