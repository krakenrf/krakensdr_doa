#!/bin/bash

IPADDR="0.0.0.0"
IPPORT="8081"

SHARED_FOLDER="_share"
SHARED_FOLDER_DOA_LOGS="${SHARED_FOLDER}/logs/krakensdr_doa"
SHARED_FOLDER_DAQ_LOGS="${SHARED_FOLDER}/logs/heimdall_daq_fw"

SETTINGS_PATH="${SHARED_FOLDER}/settings.json"

declare -A STATE_TO_MESSAGE=(["true"]="ENABLED" ["false"]="DISABLED")
REMOTE_CONTROL="false"
SERVER_BIN="sudo php -S ${IPADDR}:${IPPORT} -t"
if [ -f "${SETTINGS_PATH}" ] && [ -x "$(command -v miniserve)" ] && [ -x "$(command -v jq)" ]; then
    REMOTE_CONTROL=$(jq .en_remote_control ${SETTINGS_PATH})
    if [ "$REMOTE_CONTROL" = "true" ]; then
        SERVER_BIN="miniserve -i ${IPADDR} -p ${IPPORT} -P -u -o"
    fi
fi
echo
echo "Remote Control is ${STATE_TO_MESSAGE[$REMOTE_CONTROL]}"
if [ $REMOTE_CONTROL = "false" ]; then
    echo "To enable Remote Control please install miniserve and jq."
    echo "Then change 'en_remote_control' setting in ${SETTINGS_PATH} file to 'true'."
    echo "Finally, apply settings by restarting the software."
fi
echo

echo "Starting KrakenSDR Direction Finder"

# Create folder, if it does not exists, that will contain data shared with clients
mkdir -p "${SHARED_FOLDER}"
# Create folder, if it does not exists, that will contain logs shared with clients
mkdir -p "${SHARED_FOLDER_DOA_LOGS}"
mkdir -p "${SHARED_FOLDER_DAQ_LOGS}"

# In virtual box there needs to be a delay between folder creation and the code
sync
sleep 0.1

# Start rsync to sync DAQ logs into shared folder
./util/sync_daq_logs.sh >/dev/null 2>/dev/null &

echo "Web Interface Running at $IPADDR:8080"
python3 _ui/_web_interface/app.py >"${SHARED_FOLDER_DOA_LOGS}/ui.log" 2>&1 &

# Start webserver to share output and settings with clients
echo "Data Out Server Running at $IPADDR:$IPPORT"
# $SERVER_BIN "${SHARED_FOLDER}" 2> server.log &
$SERVER_BIN "${SHARED_FOLDER}" 2>/dev/null &

# Start nodejs server for KrakenSDR Pro App
#node _nodejs/index.js 1>/dev/null 2>/dev/null &
node _nodejs/index.js
