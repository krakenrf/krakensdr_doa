./kraken_doa_stop.sh

cd heimdall_daq_fw/Firmware
#sudo ./daq_synthetic_start.sh 
sudo ./daq_start_sm.sh
sleep 5
cd ../../krakensdr_doa
sudo nice -n -20 ./gui_run.sh
