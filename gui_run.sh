#!/bin/bash

IPADDR="0.0.0.0"
IPPORT="8081"

echo "Starting KrakenSDR Direction Finder"

# Use only for debugging
#sudo python3 _UI/_web_interface/kraken_web_interface.py 2> ui.log &

sudo gunicorn -w 1 --threads 12 -b $IPADDR:8050 --chdir _UI/_web_interface kraken_web_interface:server 2> ui.log &

# Start PHP webserver to interface with Android devices
echo "Python Server running at $IPADDR:8050"
echo "PHP Server running at $IPADDR:$IPPORT"
sudo php -S $IPADDR:$IPPORT -t _android_web 2> /dev/null &
