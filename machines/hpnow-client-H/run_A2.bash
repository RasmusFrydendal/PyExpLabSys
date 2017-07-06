#!/bin/bash

export PYTHONPATH=$HOME/PyExpLabSys

/usr/bin/python2 /home/hpnow/PyExpLabSys/machines/$HOSTNAME/voltage_current_program.py A 2 steps_A2.yaml

read -p "Press [Enter] to exit"
