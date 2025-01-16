#!/bin/bash

#source /home/krakenrf/miniforge3/etc/profile.d/conda.sh #<- required for systemd auto startup (comment out eval and use source instead)
eval "$(conda shell.bash hook)"
conda activate kraken

# Clear pycache before starting if the -c flag is given
while getopts c flag
do
    case "${flag}" in
        c) sudo py3clean . ;;
    esac
done

./kraken_doa_stop.sh
#sleep 2

cd heimdall_daq_fw/Firmware
#sudo ./daq_synthetic_start.sh
sudo env "PATH=$PATH" ./daq_start_sm.sh
sleep 1
cd ../../krakensdr_doa
sudo env "PATH=$PATH" ./gui_run.sh

# Start the  KrakenToTAK python service if it is installed, and not already running.
if [ -d "../Kraken-to-TAK-Python" ]; then
    echo "TAK Server Installed"
    cd ../Kraken-to-TAK-Python

    # Check if the process is already running
    if pgrep -f "python KrakenToTAK.py" > /dev/null; then
        echo "KrakenToTAK.py is already running."
    else
        echo "Starting KrakenToTAK.py"
        python KrakenToTAK.py >/dev/null 2>/dev/null &
    fi
else
    echo "TAK Server NOT Installed"
fi
