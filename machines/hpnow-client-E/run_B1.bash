#!/bin/bash

export PYTHONPATH=$HOME/PyExpLabSys

/usr/bin/python2 /home/hpnow/PyExpLabSys/machines/$HOSTNAME/voltage_current_program.py B 1 steps_B1.yaml

read -p "Press [Enter] to exit"
