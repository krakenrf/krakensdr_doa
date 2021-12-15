# Kraken SDR DoA DSP
This software is intended to demonstrate the direction of arrival (DoA) estimation capabilities of the KrakenSDR and other RTL-SDR based coherent receiver systems which use the compatible data acquisition system - HeIMDALL DAQ Firmware.
<br>
<br>
The complete application is broken down into two main modules in terms of implementation, into the DAQ Subsystem and to the DSP Subsystem. These two modules can operate together either remotely through Ethernet connection or locally on the same host using shared-memory.

Running these two subsystems on separate processing units can grant higher throughput and stability, while running on the same processing unit makes the entire system more compact.

## Pi 4 Image QUICKSTART (For Interested KerberosSDR Owners, or beta KrakenSDR Testers)

We have a beta Pi 4 SD card image available here **https://drive.google.com/file/d/1TTb9UOu3nuPCiMQWc4DCdKDlWTDBfN00/view?usp=sharing**. As this is a beta, the code will not autostart on boot and it is intended to be used by those familiar with Linux. For efficiency, the image is terminal only, with no desktop GUI. You can access the terminal either via SSH or by plugging in a HDMI monitor.

To run this code flash the image file to an 8GB or larger SD Card, and login to the terminal via username: pi, password: krakensdr.

Then run sudo raspi-config to set up your WiFi connection and WiFi country if not using Ethernet. Alternatively, you could connect headlessly by using the wpa_supplicant method. Once you're connected, you can login via SSH if desired (or you can continue to use a physical HDMI screen if preferred). You can try connecting to SSH via the hostname 'krakensdr', or if hostnames are not supported by your network you will need to determine the IP address of the Pi 4 either by running the 'ip addr' command on the Pi 4, or using your WiFi routers configuration page to find the 'krakensdr' device IP.

KerberosSDR BOOTING NOTE: The Pi 4 hardware has a problem where it will not boot if a powered USB hub drawing current from the Pi 4 is plugged in. Inside the KerberosSDR is a powered USB hub and hence the Pi 4 will not boot if the KerberosSDR is plugged in. So please plug the KerberosSDR in after booting. For the KrakenSDR the hardware implementation forces external power only, so this problem does not occurr. If this is a problem for your particular KerberosSDR setup, you can force external power only on the KerberosSDR by opening the enclosure and removing the JP2 jumper

For KerberosSDR users you will need to initially flash the EEPROM to use the new serial numbering scheme. There is a script in krakensdr/heimdall_daq_fw/util/eeprom_init.sh that can guide your through this. Just plug in your KerberosSDR (ensuring it is powered from the power port), and run the script ./eeprom_init.sh. The script will guide you to use the DIP switches to turn all units off, except the currently requested tuner. It will then flash the realtek_oem firmware, then the serial number, before asking you to turn off that tuner, and turn on the next one. Answer 'Y' each time it asks to flash.

Once the EEPROM is flashed you can run the code.

Go into the ~/krakensdr folder and run the ./kraken_doa_start.sh script. This will automatically start the DAQ and DoA DSP software. After a minute or so you should be able to go to a device on your network, and using a browser browse to the web interface at krakensdr:8050. If hostnames are not supported on your network, you can connect via PI4_IP_ADDRESS:8050.

The image is currently set up for the KerberosSDR, but you may wish to double check the "Advanced DAQ Settings" by clicking on that checkbox. Ensure that the # RX channels is set to 4, and the "Calibration Track Mode" is set to "No Tracking". For the first run we don't recommend making any changes, but if you do, or use one of the preconfig files, ensure that you set these settings back for the KerberosSDR. Clicking on "Reconfigure & Restart DAQ Chain" will restart the system with the changes.

If there is nothing to change on the DAQ, just click the 'Start Processing' button on the top. You should see the update rate start to work. You can set the frequency and gain using the boxes in the top left, making sure to click on 'Update Receiver Parameters' after every change.

The KrakenSDR code base is designed to autocalibrate phase on each retune. Unfortunately this feature is not available on the KerberosSDR due to the lack of a noise source switching circuit. So with the KerberosSDR every time you change the frequency or DAQ settings, make sure that you have the antennas disconnected. Also ensure that "Calibration Track Mode" is set to "No Tracking" otherwise the software will attempt to recalibrate every X-minutes.

Once you've set the frequency, you can connect your antennas. Then click on the spectrum tab. Ensure that the signal is there, and is not overloading. If it looks like the spectrum is overloaded, reduce the gain. Take note of an appropriate squelching threshold for the signal.

Go back to the main configuration page, and set the squelch threshold and click enable squelch. The system will now automatically tune and lock to the strongest signal that is above the threshold in the current spectrum. You can tell which signal the software is tuned to by the red rectangle that will highlight it. If no signal is above the threshold the spectrum and DOA graphs will not update.

The default active bandwidth in the image is set to 300 kHz. If you need to reduce the active bandwidth because there are unwanted strong signals in the active bandwidth, you can do so by changing the "Decimated Bandwidth" setting in the configuration page. The default bandwidth of 300 kHz may be too large for a single signal of interest in there are several signals close to one another. After changing the value, disconnect your antennas, and click "Reconfigure & Restart DAQ Chain" as before.

## Pi 3 Users

The image recommended for use and is tested for the Pi 4 only. We strongly recommend using a Pi 4. The Pi 3 can also be used in a pinch, though it will run the code much slower and it may not be fast enough to process fast bursty signals. The initial code run numba JIT compiles will take several minutes as well (first time you click start or enable the squelch), and the spectrum display may lag. To convert the Pi 4 image to a Pi 3 install, you will need to recompile the NE10 ARM DSP library and the Heimdall C DAQ files for the Pi 3 CPU first however. 

Follow the steps above, but before you run the code you'll need to follow the steps in the Heimdall README for the NE10 and Heimdall compile, BUT use the following commands instead:

For the NE10 compile, enter the build folder and run:

``` bash
cmake -DNE10_LINUX_TARGET_ARCH=aarch64 -DGNULINUX_PLATFORM=ON -DCMAKE_C_FLAGS="-mcpu=cortex-a53 -mtune=cortex-a53 -Ofast -funsafe-math-optimizations" ..
make
```

Then copy the new libNE10.a library over.

``` bash
cd ~/krakensdr/heimdall_daq_fw/Firmware/_daq_core/
cp ~/Ne10/build/modules/libNE10.a .
```

Next edit the Makefile and optimize it for the Pi 3.

``` bash
nano Makefile
```

Change the CFLAGS line to the following:

CFLAGS=-Wall -std=gnu99 -mcpu=cortex-a53 -mtune=cortex-a53 -Ofast -funsafe-math-optimizations -funroll-loops

Ctrl+X, Y to save

Then run 'make' to recompile heimdall.

Now you can run the code as normal on the Pi 3.

As the Pi 3 very quickly thermal throttles, we recommend adding a fan and installing cpufrequtils "sudo apt install cpufrequtils", and in ~/krakensdr/heimdall_daq_fw/Firmware/daq_start_sm.sh uncomment #sudo cpufreq-set -g performance

## Manual Installation from a fresh OS

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
