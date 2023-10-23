#!/usr/bin/env bash

DAQ_LOGS_PATH=$(find ~ -wholename "*/heimdall_daq_fw/Firmware/_logs" 2>/dev/null)
SHARED_FOLDER_DAQ_LOGS=$(find ~ -wholename "*/krakensdr_doa/_share/logs/heimdall_daq_fw" 2>/dev/null)

if [ -n "$DAQ_LOGS_PATH" ] && [ -n "$SHARED_FOLDER_DAQ_LOGS" ]; then
    while true; do
        cp -afu "${DAQ_LOGS_PATH}"/* "${SHARED_FOLDER_DAQ_LOGS}/"
        sleep 5
    done
fi
