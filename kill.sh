#/bin/sh!
SYSTEM_OS="$(uname -s)"

if [[ "$SYSTEM_OS" == "Darwin" ]];
then
    KILL_SIGNAL=9
else
    KILL_SIGNAL=64
fi

# Kill the Python web interface process
sudo kill -${KILL_SIGNAL} $(ps ax | grep ".*[p]ython3 .*_ui/_web_interface/app.py" | awk '{print $1}') 2> /dev/null
# Kill PHP processes
sudo kill -${KILL_SIGNAL} $(ps ax | grep "[p]hp" | awk '{print $1}') 2> /dev/null
# Kill Node.js processes
sudo pkill -f node
# Kill KrakenToTAK.py if running
sudo pkill -f "python.*KrakenToTAK.py" 2> /dev/null
