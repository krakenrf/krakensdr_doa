# Kraken SDR DoA DSP
This software is intended to demonstrate the direction of arrival (DoA) estimation capabilities of the KrakenSDR and other RTL-SDR based coherent receiver systems which use the compatible data acquisition system - HeIMDALL DAQ Firmware.
<br>
<br>
The complete application is broken down into two main modules in terms of implementation, into the DAQ Subsystem and to the DSP Subsystem. These two modules can operate together either remotely through Ethernet connection or locally on the same host using shared-memory.

Running these two subsystems on separate processing units can grant higher throughput and stability, while running on the same processing unit makes the entire system more compact.

## Installation

1. Install the prerequisites

``` bash
sudo apt update
sudo apt install php-cli
```

2. Install Heimdall DAQ

If not done already, first, follow the instructions at https://github.com/krakenrf/heimdall_daq_fw/tree/development to install the Heimdall DAQ Firmware.

3. Set up Miniconda environment

You will have created a Miniconda environment during the Heimdall DAQ install phase.

Please run the installs in this order as we need to ensure a specific version of dash is installed.

``` bash
conda activate kraken

conda install quart
conda install pandas
conda install orjson
conda install matplotlib

pip3 install dash_bootstrap_components
pip3 install quart_compress
pip3 install dash_devices
pip3 install pyargus

conda install dash==1.20.0
```

4. Install the krakensdr_doa software

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

## Running

### Local operation (Recommended)

```bash
./kraken_doa_start.sh
```

Please be patient on the first run, at it can take 1-2 minutes for the JIT numba compiler to compile the numba optimized functions, and during this compilation time it may appear that the software has gotten stuck. On subsqeuent runs this loading time will be much faster as it will read from cache.

### Remote operation

1. Start the DAQ Subsystem either remotely. (Make sure that the *daq_chain_config.ini* contains the proper configuration) 
    (See:https://github.com/krakenrf/heimdall_daq_fw/Documentation)
2. Set the IP address of the DAQ Subsystem in the settings.json, *default_ip* field.
3. Start the DoA DSP software by typing:
`./gui_run.sh`
4. To stop the server and the DSP processing chain run the following script:
`./kill.sh`

<p1> After starting the script a web based server opens at port number 8051, which then can be accessed by typing "KRAKEN_IP:8050/" in the address bar of any web browser. You can find the IP address of the KrakenSDR Pi4 wither via your routers WiFi management page, or by typing "ip addr" into the terminal. You can also use the hostname of the Pi4 in place of the IP address, but this only works on local networks, and not the internet, or mobile hotspot networks. </p1>

  ![image info](./doc/kraken_doadsp_main.png)

## Upcoming Features and Known Bugs

1. [FEATURE] Currently squelch works by selecting the strongest signal that is active and above the set threshold within the active bandwidth. The next steps will be to allow users to create multiple channels within the active bandwidth, each with their own squelch. This will allow users to track multiple signals at once, and ignore unwated signals within the bandwidth at the same time.

2. [FEATURE] It would be better if the KrakenSDR controls, spectrum and/or DOA graphs could be accessible from the same page. Future work will look to integrate the controls in a sidebar.

3. [FEATURE] Some users would like to monitor the spectrum, and manually click on an active signal to DF that particular signal. We will be looking at a way to implement this.  

4. [BUG] Sometimes the DOA graphs will not load properly and refreshing the page is required. A fix is being investigated.

This software was 95% developed by Tamas Peto, and makes use of his pyAPRIL and pyARGUS libraries. See his website at www.tamaspeto.com
