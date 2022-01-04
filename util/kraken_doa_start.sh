eval "$(conda shell.bash hook)"
conda activate kraken

./kraken_doa_stop.sh
sleep 2

cd heimdall_daq_fw/Firmware
#sudo ./daq_synthetic_start.sh
sudo env "PATH=$PATH" ./daq_start_sm.sh
sleep 2
cd ../../krakensdr_doa
sudo env "PATH=$PATH" ./gui_run.sh
