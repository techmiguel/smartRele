#!/bin/sh
# Builds the host test harness: BearSSL (from the ESP8266 core sources) + the bot firmware code.
# Usage: hosttest/build.sh   (from firmware/; run `pio run` once first to fetch the packages)
set -e
cd "$(dirname "$0")"
CORE=${CORE:-$HOME/.platformio/packages/framework-arduinoespressif8266}
BEARSSL=$CORE/tools/sdk/ssl/bearssl
JSON=../.pio/libdeps/esp12f/ArduinoJson/src
OUT=build
mkdir -p $OUT/bearssl

if [ ! -f $OUT/libbearssl.a ]; then
  echo "building BearSSL for the host..."
  for f in $(find $BEARSSL/src -name '*.c'); do
    gcc -O2 -w -c -I$BEARSSL/inc -I$BEARSSL/src "$f" -o $OUT/bearssl/$(basename "$f" .c).o
  done
  ar rcs $OUT/libbearssl.a $OUT/bearssl/*.o
fi

# Test certificate authority and server certificate for api.telegram.org
if [ ! -f $OUT/ca.pem ]; then
  openssl req -x509 -newkey rsa:2048 -nodes -days 30 -subj "/CN=SmartRele Test CA" \
    -keyout $OUT/ca.key -out $OUT/ca.pem 2>/dev/null
  openssl req -newkey rsa:2048 -nodes -subj "/CN=api.telegram.org" \
    -keyout $OUT/server.key -out $OUT/server.csr 2>/dev/null
  printf "subjectAltName=DNS:api.telegram.org\nbasicConstraints=CA:FALSE\n" > $OUT/ext.cnf
  openssl x509 -req -in $OUT/server.csr -CA $OUT/ca.pem -CAkey $OUT/ca.key -CAcreateserial \
    -days 30 -extfile $OUT/ext.cnf -out $OUT/server.pem 2>/dev/null
  python3 -W ignore ../../scripts/gen_trust_anchors.py $OUT/test_ca.h TELEGRAM_TA $OUT/ca.pem
fi
# A carrier's top-up portal: self-signed, not trusted by the bot
if [ ! -f $OUT/portal.pem ]; then
  openssl req -x509 -newkey rsa:2048 -nodes -days 30 -subj "/CN=recargas.example" \
    -keyout $OUT/portal.key -out $OUT/portal.pem 2>/dev/null
fi

build() {  # $1 output, then extra flags
  out=$1
  shift
  g++ -std=gnu++17 -O1 -g -Wall -Wno-unused-function \
    -DARDUINO=10800 -DARDUINOJSON_ENABLE_PROGMEM=0 -DARDUINOJSON_ENABLE_ARDUINO_STREAM=0 \
    -DARDUINOJSON_ENABLE_ARDUINO_PRINT=0 -DFW_VERSION='"host-test"' -DTELEGRAM_POLL_SEC=4 \
    -DTELEGRAM_TEST_ANCHORS='"../hosttest/build/test_ca.h"' \
    -DTELEGRAM_TEST_BUILTIN_IP=0x0500007f "$@" \
    -Imock -I$BEARSSL/inc -I$JSON \
    harness.cpp ../src/telegram.cpp ../src/tls_link.cpp $OUT/libbearssl.a -o $OUT/$out
  echo "built $OUT/$out"
}
build ${HARNESS:-harness}
# Watchdog tests: its 5 min / 10 min / 60 min steps become 5 s / 10 s / 60 s
build harness_wd -DTELEGRAM_WD_SCALE=60
