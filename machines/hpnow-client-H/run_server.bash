#!/bin/bash

export PYTHONPATH=$HOME/PyExpLabSys

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
echo $DIR

/usr/bin/python3 $DIR/power_supply_server.py

read -p "Press [Enter] to exit"
