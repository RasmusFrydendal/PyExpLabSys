import threading
import Queue
import time
from datetime import datetime
import MySQLdb
import omegabus


def sqlTime():
    sqltime = datetime.now().isoformat(' ')[0:19]
    return(sqltime)

def sqlInsert(query):
    try:
        cnxn = MySQLdb.connect(host="servcinf",user="gasmonitor",passwd="gasmonitor",db="cinfdata")
	cursor = cnxn.cursor()
    except:
	print "Unable to connect to database"
	return()
    try:
	cursor.execute(query)
	cnxn.commit()
    except:
	print "SQL-error, query written below:"
	print query
    cnxn.close()


class omegaClass(threading.Thread):
    def __init__(self):
        threading.Thread.__init__(self)
        name = {}
        omega = omegabus.OmegaBus('/dev/ttyUSB0')
        name[0] = omega.read_name()
        name[0] = name[0].strip()
        name[0] = name[0].strip(chr(0))
        omega = omegabus.OmegaBus('/dev/ttyUSB1')
        name[1] = omega.read_name().strip(chr(0))
        name[1] = name[1].strip()
        name[1] = name[1].strip(chr(0))

        omega = omegabus.OmegaBus('/dev/ttyUSB2')
        name[2] = omega.read_name().strip(chr(0))
        name[2] = name[2].strip()
        name[2] = name[2].strip(chr(0))

        omega = omegabus.OmegaBus('/dev/ttyUSB3')
        name[3] = omega.read_name().strip(chr(0))
        name[3] = name[3].strip()
        name[3] = name[3].strip(chr(0))

        self.omega = {}
        
        for i in range(0,4):
            if name[i] == '*ch_01_02_03_04':
                self.omega[1] = omegabus.OmegaBus('/dev/ttyUSB' + str(i))
                print("ch_01_02_03_04: /dev/ttyUSB" + str(i))

        for i in range(0,4):
            if name[i] == '*ch_05_06_07_08':
                self.omega[2] = omegabus.OmegaBus('/dev/ttyUSB' + str(i))
                print("ch_05_06_07_08: /dev/ttyUSB" + str(i))

        for i in range(0,4):
            if name[i] == '*ch_09_10_11_12':
                self.omega[3] = omegabus.OmegaBus('/dev/ttyUSB' + str(i))
                print("ch_09_10_11_12: /dev/ttyUSB" + str(i))

        for i in range(0,4):
            if name[i] == '*ch_13':
                self.omega[4] = omegabus.OmegaBus('/dev/ttyUSB' + str(i))
                print("ch_13: /dev/ttyUSB" + str(i))


    def run(self):
        global value_01
        global value_02
        global value_03
        global value_04
        global value_05
        global value_06
        global value_07
        global value_08
        global value_09
        global value_10
        global value_11
        global value_12
        global value_13

        while not quit:
            time.sleep(1)
            value_01 = self.omega[1].ReadValue(1)
            value_02 = self.omega[1].ReadValue(2)
            value_03 = self.omega[1].ReadValue(3)
            value_04 = self.omega[1].ReadValue(4)
            value_05 = self.omega[2].ReadValue(1)
            value_06 = self.omega[2].ReadValue(2)
            value_07 = self.omega[2].ReadValue(3)
            value_08 = self.omega[2].ReadValue(4)
            value_09 = self.omega[3].ReadValue(1)
            value_10 = self.omega[3].ReadValue(2)
            value_11 = self.omega[3].ReadValue(3)
            value_12 = self.omega[3].ReadValue(4)
            value_13 = self.omega[4].ReadValue(1)


class omegaSaver(threading.Thread):
    def __init__(self):
        threading.Thread.__init__(self)

    def run(self):
        while not quit:
            time.sleep(1)
            meas_time = sqlTime()
            val_1 = "%.2f" % value_01
            val_2 = "%.2f" % value_02
            val_3 = "%.2f" % value_03
            val_4 = "%.2f" % value_04
            val_5 = "%.2f" % value_05
            val_6 = "%.2f" % value_06
            val_7 = "%.2f" % value_07
            val_8 = "%.2f" % value_08
            val_9 = "%.2f" % value_09
            val_10 = "%.2f" % value_10
            val_11 = "%.2f" % value_11
            val_12 = "%.2f" % value_12
            val_13 = "%.2f" % value_13


            ch01_sql = "insert into gasmonitor_ch01 set time=\"" +  meas_time + "\", value = " + val_1
            ch02_sql = "insert into gasmonitor_ch02 set time=\"" +  meas_time + "\", value = " + val_2
            ch03_sql = "insert into gasmonitor_ch03 set time=\"" +  meas_time + "\", value = " + val_3
            ch04_sql = "insert into gasmonitor_ch04 set time=\"" +  meas_time + "\", value = " + val_4
            ch05_sql = "insert into gasmonitor_ch05 set time=\"" +  meas_time + "\", value = " + val_5
            ch06_sql = "insert into gasmonitor_ch06 set time=\"" +  meas_time + "\", value = " + val_6
            ch07_sql = "insert into gasmonitor_ch07 set time=\"" +  meas_time + "\", value = " + val_7
            ch08_sql = "insert into gasmonitor_ch08 set time=\"" +  meas_time + "\", value = " + val_8
            ch09_sql = "insert into gasmonitor_ch09 set time=\"" +  meas_time + "\", value = " + val_9
            ch10_sql = "insert into gasmonitor_ch10 set time=\"" +  meas_time + "\", value = " + val_10
            ch11_sql = "insert into gasmonitor_ch11 set time=\"" +  meas_time + "\", value = " + val_11
            ch12_sql = "insert into gasmonitor_ch12 set time=\"" +  meas_time + "\", value = " + val_12
            ch13_sql = "insert into gasmonitor_ch13 set time=\"" +  meas_time + "\", value = " + val_13
                        
            print ch01_sql
            print ch02_sql
            print ch03_sql
            print ch04_sql
            print ch05_sql
            print ch06_sql
            print ch07_sql
            print ch08_sql
            print ch09_sql
            print ch10_sql
            print ch11_sql
            print ch12_sql
            print ch13_sql
            sqlInsert(ch01_sql)
            sqlInsert(ch02_sql)
            sqlInsert(ch03_sql)
            sqlInsert(ch04_sql)
            sqlInsert(ch05_sql)
            sqlInsert(ch06_sql)
            sqlInsert(ch07_sql)
            sqlInsert(ch08_sql)
            sqlInsert(ch09_sql)
            sqlInsert(ch10_sql)
            sqlInsert(ch11_sql)
            sqlInsert(ch12_sql)
            sqlInsert(ch13_sql)
            time.sleep(60)
        
		
				
quit = False
value_01 = 0
value_02 = 0
value_03 = 0
value_04 = 0
value_05 = 0
value_06 = 0
value_07 = 0
value_08 = 0
value_09 = 0
value_10 = 0
value_11 = 0
value_12 = 0
value_13 = 0
	
O = omegaClass()
gasSaver = omegaSaver()

O.start()
time.sleep(20)
gasSaver.start()

while not quit:
    try:
        time.sleep(1)
    except:
        quit = True

