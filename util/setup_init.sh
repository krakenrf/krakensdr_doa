#/bin/bash!

# PhP for android device support
sudo apt install php7.4-cli

echo "Set execution rights"
sudo chmod +x ../gui_run.sh
sudo chmod +x ../kill.sh
echo "Install dependencies"
python3 -m pip install numpy
python3 -m pip install scipy
python3 -m pip install pyargus
python3 -m pip install matplotlib

# For web interface
python3 -m pip install dash