<h2>Kraken SDR DoA DSP</h2>
This software is intended to demonstrate the direction of arrival (DoA) estimation capabilities of the KrakenSDR and other RTL-SDR based coherent receiver systems which use the compatible data acquisition system - HeIMDALL DAQ Firmware.
<br>
<br>
The complete application is broken down into two main modules in terms of implementation, into the DAQ Subsystem and to the DSP Subsystem. These two modules can operate together either remotely through Ethernet connection or locally on the same host using shared-memory.

Running these two subsystems on separate processing units can grant higher throughput and stability, while running on the same processing unit makes the entire system more compact.

<h3>Installation</h3>
Install Notes (Tested on RaspiOS Lite 64-bit Beta 2021-10-30-raspios-bullseye-arm64-lite):

Start with the a fresh install of Raspbian 64-bit Lite from https://downloads.raspberrypi.org/raspios_lite_arm64/images/raspios_lite_arm64-2021-11-08/

Burn to SD Card and login with pi/raspberry. Set up WiFi, enable SSH and change the hostname to "krakensdr" if desired via raspi-config. For security, don't forget to change the default default the password too.

<h4>Install pre-reqs</h4>

``` bash
sudo apt update
sudo apt install build-essential git cmake libusb-1.0-0-dev lsof php-cli
```

<h4>Install librtlsdr Drivers</h4>

``` bash
git clone https://github.com/librtlsdr/librtlsdr

cd rtl-sdr-kerberos
mkdir build
cd build
cmake ../ -DINSTALL_UDEV_RULES=ON
make
sudo make install
sudo ldconfig

echo 'blacklist dvb_usb_rtl28xxu' | sudo tee – append /etc/modprobe.d/blacklist-dvb_usb_rtl28xxu.conf
```

Reboot Pi4

``` bash
sudo reboot
```

<h4>Install Miniconda</h4>

The instructions below are so aarch64 ARM systems. If you're install to another system, please download the appropriate miniconda installer.

``` bash
wget https://github.com/conda-forge/miniforge/releases/latest/download/Miniforge3-Linux-aarch64.sh
chmod ug+x Miniforge3-Linux-aarch64.sh
./Miniforge3-Linux-aarch64.sh
```

Read the license agreement and select ENTER or [yes] for all questions.

``` bash
conda config --set auto_activate_base false
```

Restart the Pi, or logout, then log on again.

``` bash
sudo reboot
```

<h4>Set up Miniconda environment</h4>

Please run the installs in this order as we need to ensure a specific version of dash is installed.

``` bash
conda create -n kraken python=3.9.7
conda activate kraken


#conda install werkzeug==2.0
conda install quart
conda install pandas
conda install orjson
conda install scipy
conda install numba
conda install configparser
conda install matplotlib

pip3 install dash_bootstrap_components
pip3 install quart_compress
pip3 install dash_devices
pip3 install pyargus

conda install dash==1.20.0
```

Install the KrakenSDR software:







Clone the repository of the HeIMDALL DAQ Firmware to the krakensdr folder and follow the install instructions from the readme. (https://github.com/krakenrf/heimdall_daq_fw)

For 64-bit Pi 4:
```bash
cd
git clone https://github.com/krakenrf/Ne10
cd Ne10
mkdir build
cd build
cmake -DNE10_LINUX_TARGET_ARCH=aarch64 -DGNULINUX_PLATFORM=ON -DCMAKE_C_FLAGS="-mcpu=cortex-a72 -mtune=cortex-a72 -Ofast -funsafe-math-optimizations" ..
make
 ```
 
Create a root folder
``` bash
cd
mkdir krakensdr
cd krakensdr
```
 
 Install Heimdall
 
```bash
git clone https://github.com/krakenrf/heimdall_daq_fw
cd heimdall_daq_fw
git checkout development
```
 
 Build Heimdall C Files

First copy libNE10.a to _daq_core
```bash
cd heimdall_daq_fw/Firmware/_daq_core/
cp ~/Ne10/build/modules/libNE10.a .
```

Edit Makefile to enable optimized Pi 4 build
```bash
nano Makefile
```
Uncomment the line below "# Optimized C-flags for Pi 4" by deleting the '#', and comment out the top CFLAGS line by adding a '#' at the start of that line.
Ctrl+X, Y to save and exit nano.

Build heimdall
```bash
make
```

Install krakensdr_doa
```bash
cd ~/krakensdr
git clone https://github.com/krakenrf/krakensdr_doa
cd krakensdr_doa
git checkout clientside_graphs
```

Copy the the *krakensdr_doa/util/kraken_doa_start.sh* and the *krakensdr_doa/util/kraken_doa_stop.sh* scripts into the krakensdr root folder of the project.
```bash
cd ~/krakensdr
cp krakensdr_doa/util/kraken_doa_start.sh .
cp krakensdr_doa/util/kraken_doa_stop.sh .
```

<h3>Running</h3>

You can run the complete application on a single host either by using Ethernet interface between the two subsystems or by using a shared-memory interface. Using shared-memory is the recommended in this situation. 


<h4>Local operation</h4>

conda activate kraken
./kraken_doa_start.sh

1. Make sure that the *daq_chain_config.ini* contains the proper configuration
(See:https://github.com/krakenrf/heimdall_daq_fw/Documentation)
2. Set *data_interface="shmem"* in the settings.json
3. Start the full systems by typing:
`conda activate kraken`
`./kraken_doa_start.sh`
4. To stop the full systems run the following script:
`./kraken_doa_stop.sh`

<h4>Remote operation</h4>

1. Start the DAQ Subsystem either remotely. (Make sure that the *daq_chain_config.ini* contains the proper configuration) 
    (See:https://github.com/krakenrf/heimdall_daq_fw/Documentation)
2. Set the IP address of the DAQ Subsystem in the settings.json, *default_ip* field.
3. Start the DoA DSP software by typing:
`./gui_run.sh`
4. To stop the server and the DSP processing chain run the following script:
`./kill.sh`



<p1> After starting the script a web based server opens at port number 8051, which then can be accessed by typing "KRAKEN_IP:8050/" in the address bar of any web browser. You can find the IP address of the KrakenSDR Pi4 wither via your routers WiFi management page, or by typing "ip addr" into the terminal. You can also use the hostname of the Pi4 in place of the IP address, but this only works on local networks, and not the internet, or mobile hotspot networks. </p1>

  ![image info](./doc/kraken_doadsp_main.png)


This software was 95% developed by Tamas Peto, and makes use of his pyAPRIL and pyARGUS libraries. See his website at www.tamaspeto.com
