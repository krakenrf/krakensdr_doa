<h2>Kraken SDR DoA DSP</h2>
This software is intended to demonstrate the direction of arrival (DoA) estimation capabilities of the KrakenSDR and other RTL-SDR based coherent receiver systems which use the compatible data acquisition system - HeIMDALL DAQ Firmware.
<br>
<br>
The complete application is broken down into two main modules in terms of implementation, into the DAQ Subsystem and to the DSP Subsystem. These two modules can operate together either remotely through Ethernet connection or locally on the same host using shared-memory.

Running these two subsystems on separate processing units can grant higher throughput and stability, while running on the same processing unit makes the entire system more compact.

<h3>Installation</h3>
Install Notes (Tested on RaspiOS Lite 64-bit Beta 2021-10-30-raspios-bullseye-arm64-lite):

Start with the a fresh install of Raspbian 64-bit Lite from https://downloads.raspberrypi.org/raspios_lite_arm64/images/raspios_lite_arm64-2021-11-08/

Burn to SD Card and login with pi/raspberry. Set up WiFi and enable SSH if desired via raspi-config.

Install Miniconda:
``` bash
wget https://github.com/conda-forge/miniforge/releases/latest/download/Miniforge3-Linux-aarch64.sh
chmod ug+x Miniforge3-Linux-aarch64.sh
./Miniforge3-Linux-aarch64.sh
conda config --set auto_activate_base false
```

Restart the Pi, or logout, then logon again.

Set up Miniconda Environment

``` bash
conda create -n kraken python=3.9.7
conda activate kraken

conda install werkzeug==2.0
conda install dash==1.20.0
conda install quart
conda install pandas
conda install dash_bootstrap_components
conda install orjson
conda install scipy
conda install numba
pip3 install quart_compress
pip3 install dash_devices
pip3 install pyargus
```

Install the KrakenSDR software:

1. Create a root folder

``` bash
cd
mkdir krakensdr
```

1. Clone the repository of the HeIMDALL DAQ Firmware to the krakensdr folder and follow the install instructions from the readme. (https://github.com/krakenrf/heimdall_daq_fw)
2. Clone this repsitory to the same krakensdr folder.
3. Copy the the *krakensdr_doa/util/kraken_doa_start.sh* and the *krakensdr_doa/util/kraken_doa_stop.sh* scripts into the krakensdr root folder of the project.

``` bash
git clone https://github.com/krakenrf/heimdall_daq_fw
sudo ./heimdall_daq_fw/util/install.sh
./heimdall_daq_fw/util/eeprom_init.sh
git clone https://github.com/krakenrf/krakensdr_doa
sudo ./krakensdr_doa/util/setup_init.sh
cp krakensdr_doa/util/kraken_doa_start.sh .
cp krakensdr_doa/util/kraken_doa_stop.sh .
```

<h3>Running</h3>

<h4>Remote operation</h4>

1. Start the DAQ Subsystem either remotely. (Make sure that the *daq_chain_config.ini* contains the proper configuration) 
    (See:https://github.com/krakenrf/heimdall_daq_fw/Documentation)
2. Set the IP address of the DAQ Subsystem in the settings.json, *default_ip* field.
3. Start the DoA DSP software by typing:
`./gui_run.sh`
4. To stop the server and the DSP processing chain run the following script:
`./kill.sh`

<h4>Local operation</h4>

You can run the complete application on a single host either by using Ethernet interface between the two subsystems or by using a shared-memory interface. Using shared-memory is the recommended in this situation. 

1. Make sure that the *daq_chain_config.ini* contains the proper configuration
(See:https://github.com/krakenrf/heimdall_daq_fw/Documentation)
2. Set *data_interface="shmem"* in the settings.json
3. Start the full systems by typing:
`./kraken_doa_start.sh`
4. To stop the full systems run the following script:
`./kraken_doa_stop.sh`

<p1> After starting the script a web based server opens at port number 8051, which then can be accessed by typing "KRAKEN_IP:8050/" in the address bar of any web browser. </p1>

  ![image info](./doc/kraken_doadsp_main.png)


This software was 95% developed by Tamas Peto, and makes use of his pyAPRIL and pyARGUS libraries. See his website at www.tamaspeto.com
