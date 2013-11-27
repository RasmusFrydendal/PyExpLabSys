import threading
import Queue
import time
#import matplotlib.pyplot as plt
import MySQLdb
import curses
import logging
import socket

import sys
sys.path.append('../')
import SQL_saver

import qmg_status_output
import qmg_meta_channels

import qmg420


class qms():

    def __init__(self, qmg, sqlqueue=None, loglevel=logging.ERROR):
        self.qmg = qmg
        if not sqlqueue == None:
            self.sqlqueue = sqlqueue
        else: #We make a dummy queue to make the program work
            self.sqlqueue = Queue.Queue()
        self.operating_mode = "Idling"
        self.current_timestamp = "None"
        self.measurement_runtime = 0
        self.stop = False
        self.chamber = 'dummy'
        self.channel_list = {}
        
        #Clear log file
        with open('qms.txt', 'w'):
            pass
        logging.basicConfig(filename="qms.txt", level=logging.INFO)
        logging.info("Program started. Log level: " + str(loglevel))
        logging.basicConfig(level=logging.INFO)
        

    def communication_mode(self, computer_control=False):
        return self.qmg.communication_mode(computer_control)

    def emission_status(self, current=-1, turn_off=False, turn_on=False):
        return self.qmg.emission_status(current, turn_off, turn_on)

    def sem_status(self, voltage=-1, turn_off=False, turn_on=False):
        return self.qmg.sem_status(voltage, turn_off, turn_on)

    def detector_status(self, SEM=False, faraday_cup=False):
        return self.qmg.detector_status(SEM, faraday_cup)

    def read_voltages(self):
        self.qmg.read_voltages()

    def simulation(self):
        """ Chekcs wheter the instruments returns real or simulated data """
        self.qmg.simulation()

    def config_channel(self, channel, mass=-1, speed=-1, amp_range=0, enable=""):
        self.qmg.config_channel(channel, mass=mass, speed=speed, amp_range=amp_range, enable=enable)


    def create_mysql_measurement(self, channel, timestamp, masslabel, comment,
                                 metachannel=False, type=5):
        """ Creates a MySQL row for a channel.
        
        Create a row in the measurements table and populates it with the
        information from the arguments as well as what can be
        auto-generated.
        
        """
        cnxn = MySQLdb.connect(host="servcinf", user=self.chamber, 
                               passwd=self.chamber, db="cinfdata")

        cursor = cnxn.cursor()
        
        if not metachannel:
            self.qmg.set_channel(channel)
            sem_voltage = self.qmg.read_sem_voltage()
            preamp_range = self.qmg.read_preamp_range()
            timestep = self.qmg.read_timestep()   #TODO: We need a look-up table, this number is not physical
        else:
            sem_voltage = "-1"
            preamp_range = "-1"
            timestep = "-1"
                
        query = ""
        query += 'insert into measurements_' + self.chamber + ' set mass_label="' 
        query += masslabel + '"'
        query += ', sem_voltage="' + sem_voltage + '", preamp_range="'
        query += preamp_range + '", time="' + timestamp + '", type="' + str(type) + '"'
        query += ', comment="' + comment + '"'

        cursor.execute(query)
        cnxn.commit()
        
        query = 'select id from measurements_' + self.chamber + ' order by id desc limit 1'
        cursor.execute(query)
        id_number = cursor.fetchone()
        id_number = id_number[0]
        cnxn.close()
        return(id_number)

    def create_ms_channellist(self, channel_list, timestamp, no_save=False):
        """ This function creates the channel-list and the associated mysql-entries """
        #TODO: Implement various ways of creating the channel-list

        ids = {}
        
        for i in range(0,16):
            self.config_channel(i, mass=99, speed=1, amp_range=-1,enable='no')

        comment = channel_list[0]['comment']
        for i in range(1,len(channel_list)):
            ch = channel_list[i]
            self.config_channel(channel=i, mass=ch['mass'], speed=ch['speed'], amp_range=ch['amp_range'], enable="yes")
            self.channel_list[i] = {'masslabel':ch['masslabel'],'value':'-'}
            
            if no_save == False:
                ids[i] = self.create_mysql_measurement(i,timestamp,ch['masslabel'],comment)
            else:
                ids[i] = i
        ids[0] = timestamp
        logging.error(ids)
        return ids
        
    def mass_time(self,ms_channel_list, timestamp):
        self.operating_mode = "Mass Time"
        self.stop = False
        ns = len(ms_channel_list) - 1
        logging.warn(ns)
        self.qmg.mass_time(ns)

        start_time = time.time()
        ids = self.create_ms_channellist(ms_channel_list, timestamp, no_save=False)
        self.current_timestamp = ids[0]
        
        while self.stop == False:
            self.qmg.set_channel(1)
            self.qmg.start_measurement()
            time.sleep(0.1)
            channel = 0
            for j in range(0, ns):
                self.measurement_runtime = time.time()-start_time
                #value = self.comm('MDB')
                error = 0
                while (qmg.waiting_samples() == 0) and (error < 40):
                    time.sleep(0.2)
                    error = error + 1
                    logging.warn(error)
                if error > 39:
                    logging.error('Sample did arrive on time')
                    break
                value = self.qmg.comm(chr(5))
                logging.warn(value)
                channel = channel + 1
                self.channel_list[channel]['value'] = value
                sqltime = str((time.time() - start_time) * 1000)
                if value == "":
                    break
                else:
                    value = float(value)
                    value = value / 10**(ms_channel_list[j+1]['amp_range']+5)
                    query  = 'insert into '
                    query += 'xy_values_' + self.chamber + ' '
                    query += 'set measurement="' + str(ids[channel])
                    query += '", x="' + sqltime + '", y="' + str(value) + '"'
                self.sqlqueue.put(query)
                time.sleep(0.25)
            time.sleep(0.1)
        self.operating_mode = "Idling"
        

    def mass_scan(self, first_mass=0, scan_width=50):

        data = self.qmg.mass_scan(first_mass, scan_width)

        comment = 'Test scan - qgm420'
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        id = self.create_mysql_measurement(0,timestamp,'Mass Scan',comment, type=4)
        for i in range(0, len(data['x'])):
            query = 'insert into xy_values_' + self.chamber + ' set measurement = ' + str(id) + ', x = ' + str(data['x'][i]) + ', y = ' + str(data['y'][i])
            self.sqlqueue.put(query)
        time.sleep(10)
        
if __name__ == "__main__":
    sql_queue = Queue.Queue()
    sql_saver = SQL_saver.sql_saver(sql_queue,'microreactorNG')
    sql_saver.daemon = True
    sql_saver.start()

    qmg = qmg420.qmg_420()

    qms = qms(qmg, sql_queue)
    qms.communication_mode(computer_control=True)
    #qms.mass_scan()
    
    printer = qmg_status_output.qms_status_output(qms,sql_saver_instance=sql_saver)
    printer.daemon = True
    printer.start()
 
    time.sleep(1)
    
    channel_list = {}
    channel_list[0] = {'comment':'DELETE'}
    channel_list[1] = {'mass':2,'speed':10, 'amp_range':6, 'masslabel':'M2'}
    channel_list[2] = {'mass':4,'speed':10, 'amp_range':6, 'masslabel':'M4'}
    channel_list[3] = {'mass':18,'speed':10, 'amp_range':5, 'masslabel':'M18'}
    channel_list[4] = {'mass':28,'speed':10, 'amp_range':5, 'masslabel':'M28'}
    channel_list[5] = {'mass':28,'speed':10, 'amp_range':6, 'masslabel':'M28L'}
    channel_list[6] = {'mass':32,'speed':10, 'amp_range':6, 'masslabel':'M32'}
    channel_list[7] = {'mass':44,'speed':10, 'amp_range':6, 'masslabel':'M44'}

    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")

    #meta_udp = qmg_meta_channels.udp_meta_channel(qms, timestamp, channel_list[0]['comment'], 5)
    #meta_udp.create_channel('Temp, TC', 'rasppi12', 9999, 'tempNG')
    #meta_udp.create_channel('Pirani buffer volume', 'rasppi07', 9997, 'read_buffer')
    #meta_udp.create_channel('Pirani containment', 'rasppi07', 9997, 'read_containment')
    #meta_udp.create_channel('RTD Temperature', 'rasppi05', 9992, 'read_rtdval')
    #meta_udp.daemon = True
    #meta_udp.start()

    #meta_flow = qmg_meta_channels.compound_udp_meta_channel(qms, timestamp, channel_list[0]['comment'],5,'rasppi16',9998, 'read_all')
    #meta_flow.create_channel('Sample Pressure',0)
    #meta_flow.create_channel('Flow, H2',4)
    #meta_flow.create_channel('Flow, CO',6)
    #meta_flow.daemon = True
    #meta_flow.start()
    
    print qms.mass_time(channel_list, timestamp)
    #qmg.scan_test()
    printer.stop()
