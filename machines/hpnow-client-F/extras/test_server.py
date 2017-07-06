
from __future__ import print_function

import socket
import json
from time import sleep

# Setup communication with the power supply server
HOST, PORT = "localhost", 8500
SOCK = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
SOCK.settimeout(5)
def _send_command(output, power_supply, command, arg=None):
    """Send a command to the power supply server

    Args:
        output (str): The output number in a string; either 1 or 2
        power_supply (str): The power supply name e.g. 'A'
        command (str): The command/name of the method to call on the power
            supply object
        arg (object): The argument to the command/method
    """
    data_to_send = {'command': command, 'output': output,
                    'power_supply': power_supply}
    if arg is not None:
        data_to_send['arg'] = arg
    formatted_command = b'json_wn#' + json.dumps(data_to_send).encode('utf-8')

    SOCK.sendto(formatted_command, (HOST, PORT))
    received = SOCK.recv(1024).decode('utf-8')
    print('Send %s. Got: %s', data_to_send, received)

    if received.startswith('ERROR:'):
        raise PowerSupplyComException(received)

    # The return values starts with RET#
    return json.loads(received[4:])


for psu in ('A', 'B'):
    for channel in ('1', '2'):
        print("Activating PSU {} channel {}".format(psu, channel))
        _send_command(channel, psu, 'set_voltage', 0)
        _send_command(channel, psu, 'output_status', True)
        sleep(1)
        for n in range(10):
            _send_command(channel, psu, 'set_voltage', float(n))
            sleep(0.1)
            read = _send_command(channel, psu, 'read_actual_voltage')
            print('Set to {}, read {}'.format(float(n), read))
        #_send_command(channel, psu, 'set_voltage', 0)
        #_send_command(channel, psu, 'output_status', False)
        sleep(1)
