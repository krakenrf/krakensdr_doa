#!/bin/bash

# miniserve for sharing data with clients over HTTP
sudo apt-get -y install rustc cargo
cargo install miniserve

echo "Set execution rights"
sudo chmod +x ../gui_run.sh
sudo chmod +x ../kill.sh
echo "Install dependencies"
python3 -m pip install numpy
python3 -m pip install scipy==1.9.3
python3 -m pip install pyargus
python3 -m pip install matplotlib

# For web interface
python3 -m pip install dash
python3 -m pip install dash-bootstrap-components
python3 -m pip install gunicorn