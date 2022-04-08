#!/bin/bash

IPADDR="0.0.0.0"
IPPORT="8081"

echo "Starting KrakenSDR Direction Finder"

# Use only for debugging
#sudo python3 _UI/_web_interface/kraken_web_interface.py 2> ui.log &

python3 _UI/_web_interface/kraken_web_interface.py 2> ui.log &

# Start PHP webserver to interface with Android devices
echo "Web Interface Running at $IPADDR:8080"
echo "PHP Data Out Server Running at $IPADDR:$IPPORT"
sudo php -S $IPADDR:$IPPORT -t _android_web 2> /dev/null &

# Start nodejs server for KrakenSDR Pro App
node _nodejs/index.js  1> /dev/null &
