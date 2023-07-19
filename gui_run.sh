#!/bin/bash

IPADDR="0.0.0.0"
IPPORT="8081"

SHARED_FOLDER="_share"
SETTINGS_PATH="${SHARED_FOLDER}/settings.json"

declare -A STATE_TO_MESSAGE=(["true"]="ENABLED" ["false"]="DISABLED")
REMOTE_CONTROL="false"
SERVER_BIN="sudo php -S ${IPADDR}:${IPPORT} -t"
if [ -f "${SETTINGS_PATH}" ] && [ -x "$(command -v miniserve)" ]; then
    REMOTE_CONTROL=$(jq .en_remote_control ${SETTINGS_PATH})
    if [ "$REMOTE_CONTROL" = "true" ]; then
        SERVER_BIN="miniserve -i ${IPADDR} -p ${IPPORT} -P -u -o"
    fi
fi
echo "Remote Control is ${STATE_TO_MESSAGE[$REMOTE_CONTROL]}"

echo "Starting KrakenSDR Direction Finder"

# Use only for debugging
#sudo python3 _UI/_web_interface/kraken_web_interface.py 2> ui.log &

echo "Web Interface Running at $IPADDR:8080"
python3 _UI/_web_interface/kraken_web_interface.py 2> ui.log &

# Create folder, if it does not exists, that will contain data shared with clients
mkdir -p "${SHARED_FOLDER}"

# Start webserver to share output and settings with clients
echo "Data Out Server Running at $IPADDR:$IPPORT"
# $SERVER_BIN "${SHARED_FOLDER}" 2> server.log &
$SERVER_BIN "${SHARED_FOLDER}" 2> /dev/null &

# Start nodejs server for KrakenSDR Pro App
node _nodejs/index.js  1> /dev/null 2> /dev/null &
#node _nodejs/index.js
