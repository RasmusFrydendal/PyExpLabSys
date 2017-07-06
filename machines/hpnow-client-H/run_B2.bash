#!/bin/bash

export PYTHONPATH=$HOME/PyExpLabSys

/usr/bin/python2 /home/hpnow/PyExpLabSys/machines/$HOSTNAME/voltage_current_program.py B 2 steps_B2.yaml

read -p "Press [Enter] to exit"
