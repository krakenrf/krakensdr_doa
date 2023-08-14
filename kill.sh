#/bin/sh!
SYSTEM_OS="$(uname -s)"

if [[ "$SYSTEM_OS" == "Darwin" ]];
then
    KILL_SIGNAL=9
else
    KILL_SIGNAL=64
fi

sudo kill -${KILL_SIGNAL} $(ps ax | grep ".*[p]ython3 .*_UI/_web_interface/app.py" | awk '{print $1}') 2> /dev/null
sudo kill -${KILL_SIGNAL} $(ps ax | grep "[p]hp" | awk '{print $1}') 2> /dev/null
sudo pkill -f node
