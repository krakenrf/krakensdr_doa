#/bin/sh!
sudo kill -64 $(ps ax | grep "[p]ython3 _UI/_web_interface/kraken_web_interface.py" | awk '{print $1}') 2> /dev/null
sudo kill -64 $(ps ax | grep "[p]hp" | awk '{print $1}') 2> /dev/null
#sudo pkill -f gunicorn

