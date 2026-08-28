#!/bin/bash
cd "$(dirname "$0")/.."
./venv/bin/python3 -m quantshield.intraday.feed &
FEED=$!
./venv/bin/python3 -m quantshield.intraday.paper --live &
ORB=$!
wait $FEED
wait $ORB
./venv/bin/python3 -m quantshield.intraday.candles
