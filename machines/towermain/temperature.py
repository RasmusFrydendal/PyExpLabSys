# -*- coding: utf-8 -*-
"""This script read the sample temperature from an Omega CNi3244_C24
temperature control unit and makes it available on a data socket. Furthermore,
it also log significant temperature points to the database.
"""
import time

from PyExpLabSys.drivers.omega import CNi3244_C24
from PyExpLabSys.common.sockets import DataSocket
from PyExpLabSys.common.loggers import ContinuousLogger
from PyExpLabSys.common.utilities import get_logger


LOGGER = get_logger('temperatue')
TEMPERATURE_CHANGE_THRESHOLD = 0.3
TIMEOUT = 600
SHORT_NAME = 'tts'
NAME = 'tower_temperature_sample'


def main():
    LOGGER.info('main started')
    cni = CNi3244_C24(0)
    socket = DataSocket([SHORT_NAME])
    socket.start()
    db_logger = ContinuousLogger(
        table='dateplots_tower', username='N/A', password='N/A',
        measurement_codenames=[NAME],
        dsn='servcinf'
    )
    db_logger.start()
    time.sleep(0.1)

    # Main part
    try:
        last_temp = -100000
        last_time = 0
        while True:
            # Current values
            now = time.time()
            current = cni.read_temperature()

            # Set point on socket
            socket.set_point_now(SHORT_NAME, current)

            # Log if required
            if now - last_time > TIMEOUT or\
                    abs(current - last_temp) > TEMPERATURE_CHANGE_THRESHOLD:
                db_logger.enqueue_point_now('tower_temperature_sample',
                                            current)                
                LOGGER.info('Value {} sent'.format(current))
                last_time = now
                last_temp = current
            
    except KeyboardInterrupt:
        LOGGER.info('Keyboard Interrupt. Shutting down!')
        db_logger.stop()
        cni.close()
        socket.stop()


if __name__ == '__main__':
    main()
    raw_input()