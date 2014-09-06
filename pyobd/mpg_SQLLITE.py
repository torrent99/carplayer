#!/usr/bin/env python
 
import obd_io
import serial
import platform
import obd_sensors
from datetime import datetime
import time
import os
import sqlite3
#from datetime import timedelta
 
from obd_utils import scanSerial
 
class OBD_Capture():
    def __init__(self):
        self.port = None
        localtime = time.localtime(time.time())
 
    def connect(self):
        print "I'm connecting"
#        portnames = scanSerial()
        portnames = [ '/dev/ttyUSB0' ]
        print portnames
        for port in portnames:
            self.port = obd_io.OBDPort(port, None, 2, 2)
            if(self.port.State == 0):
                self.port.close()
                self.port = None
            else:
                break
 
        if(self.port):
            print "Connected to "+self.port.port.name
 
    def is_connected(self):
        return self.port
 
    def find_obd_sensorindex(self, sensorName):
	index = 0
        foundit = -1
        for i in obd_sensors.SENSORS:
            if i.shortname == sensorName:
            	foundit = index
            else:
                index +=1
        return foundit

    def mpgprint(self,cShortTerm,cLongTerm,cLongTermMinutes):
        cShortTerm = cShortTerm[:4]
        cLongTerm = cLongTerm[:4]
        print "Short term MPG"+cShortTerm
        print "Long term MPG"+cLongTerm
        print "Long term Minutes"+cLongTermMinutes
        
    def ComputeFuelConsumption(self):
        nCurrentTime = time.time()
        
        try:
            nStart = nCurrentTime - 20
            cLimit = " and time_read > " + str(nStart) + " order by time_read desc limit 6"
            cursor.execute('''SELECT maf,speed from SensorReadings where speed > "0" and maf > "0" and rpm != "NODATA" ''' + cLimit)
            data = cursor.fetchall()
        except sqlite3.OperationalError,msg:
            return msg
	print "Data len is"
        print len(data)
        if (len(data) > 0):
            nFuelConsumption = 0
            for x in range(0,len(data)):
                print "Zero is"
                print float(data[x][0])
                print "One is"
                print float(data[x][1])
                if float(data[x][1]) > float(0):
                	nFuelConsumption += (3600 * float(data[x][0]))/(9069.90 * float(data[x][1]))
                
            nAvgFuelConsumption = nFuelConsumption/len(data)
            print nAvgFuelConsumption
            print type(nAvgFuelConsumption)
            #print data[x][0],data[x][1],data[x][2]
            return "{:5.2f}".format(nAvgFuelConsumption).lstrip()
        else:
            return "No data"
 
        #print nAvgFuelConsum
        
    def is_number(self,DataToTest):
        try:
            float(DataToTest)
            return True
        except ValueError:
            return False    
                
                
 
                
    def capture_data(self):
        #Creating new database
        for kounter in range(10000):
            cKounter = "{0:05d}".format(kounter)
            cNewDatabase = "obdii" + cKounter + ".db"
            #print cNewDatabase
            if not (os.path.exists(cNewDatabase)):
                #print "New database name: " + cNewDatabase
                break
 
        global conn
        global cursor
        conn = sqlite3.connect(cNewDatabase)
        cursor = conn.cursor()
            
        #Find supported sensors - by getting PIDs from OBD
        # its a string of binary 01010101010101 
        # 1 means the sensor is supported
        self.supp = self.port.sensor(0)[1]
        self.supportedSensorList = []
        self.unsupportedSensorList = []
        
        
        # loop through PIDs binary
        self.supp = "0000000000111011" # SKS 0B MAP, 0C RPM, OD VSS/speed, 0F Inlet Temp, 10 MAF
        self.supp = "0000000000011001" # SKS  0C RPM, OD VSS/speed,  10 MAF
        for i in range(0, len(self.supp)):
            if self.supp[i] == "1":
                # store index of sensor and sensor object
                self.supportedSensorList.append([i+1, obd_sensors.SENSORS[i+1]])
            else:
                self.unsupportedSensorList.append([i+1, obd_sensors.SENSORS[i+1]])
        

        rpm_sensor_index =  find_obd_sensorindex( "rpm")

 
        sqlCreateTable = "CREATE TABLE SensorReadings (time_read real, "
        sqlInsertTemplate = "INSERT INTO SensorReadings(time_read, "
        
        for supportedSensor in self.supportedSensorList:
            #print "supported sensor index = " + str(supportedSensor[0]) + " " + str(supportedSensor[1].shortname)
            sqlCreateTable += str(supportedSensor[1].shortname)  + " text,"    
            sqlInsertTemplate += str(supportedSensor[1].shortname)  + ","
            
        sqlCreateTable = sqlCreateTable[:sqlCreateTable.rfind(",")] + ")"
        #print sqlCreateTable
        try:
            cursor.execute(sqlCreateTable)
            conn.commit()
            cursor.execute('''CREATE INDEX time_read_index on SensorReadings(time_read)''')
            cMessage = "Database " + cNewDatabase + " created..."
        except sqlite3.OperationalError,msg:
            cMessage = msg
        print cMessage
 
        sqlInsertTemplate = sqlInsertTemplate[:sqlInsertTemplate.rfind(",")] + ") VALUES ("
        #print sqlInsertTemplate
        
        time.sleep(3)
 
        if(self.port is None):
            return None
        
        #Loop until Ctrl C is pressed        
        try:
            nRunningTotalFuelConsumption = 0
            nStartTime = time.time()
            x = 0
            while True:
                current_time = time.time()
                #current_time = str(localtime.hour)+":"+str(localtime.minute)+":"+str(localtime.second)+"."+str(localtime.microsecond)
                log_string = str(current_time) + "\n"
                sqlInsert = sqlInsertTemplate + '"' + str(current_time) + '",'
                results = {}
                for supportedSensor in self.supportedSensorList:
                    sensorIndex = supportedSensor[0]
                    print sensorIndex
                    (name, value, unit) = self.port.sensor(sensorIndex)
                    log_string += name + " = " + str(value) + " " + str(unit) + "\n"
                    print value,type(value)
                    print log_string
                    sqlInsert += '"' + str(value) + '",'    
                
                
                sqlInsert = sqlInsert[:sqlInsert.rfind(",")] + ")"
                #print sqlInsert
 
                try:
                    cursor.execute(sqlInsert)
                    conn.commit()
                except sqlite3.OperationalError,msg:
                    print msg
                    continue
                    
                cFuelConsumption = self.ComputeFuelConsumption()
                if (cFuelConsumption != "No data"):
                    x += 1
                if (x > 0):
                    if (self.is_number):
                        nRunningTotalFuelConsumption += float(cFuelConsumption)
                    nTripAverage = nRunningTotalFuelConsumption/x
                    cTripAverage = "{:5.2f}".format(nTripAverage).lstrip()
                else:
                    cTripAverage = "Nodata"
                
                cDurationInMinutes = "{:3.0f}".format((current_time - nStartTime)/60).lstrip()
                self.mpgprint(cFuelConsumption,cTripAverage,cDurationInMinutes)
                    
                #print log_string,
                #time.sleep(0.5)
                
 
        except KeyboardInterrupt:
            self.port.close()
            print("stopped")
            
if __name__ == "__main__":
    print "Initializing..."
 
 
    o = OBD_Capture()
    rpm_sensor_index =  o.find_obd_sensorindex( "rpm")
    print "rpm_sensor_index is"+str(rpm_sensor_index)
    o.connect()
    time.sleep(3)
    if not o.is_connected():
        print "Not connected"
        print "Error: Not connected to OBDII..."
        time.sleep(10)
        exit()
    else:
        o.capture_data()

