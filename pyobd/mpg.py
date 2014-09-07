#!/usr/bin/python
 
import obd_io
import serial
import platform
import obd_sensors
from datetime import datetime
import time
import pickle
import os
#import sqlite3
import os.path
import random
import csv
#from datetime import timedelta
 
from obd_utils import scanSerial

current_milli_time = lambda: int(round(time.time() * 1000))

FAKEIT = 0
FAKEIT_line = 0
OLD_VERSION = 0
NUM_TRIPS = 3
FUELUP_TRIP = NUM_TRIPS + 1
if FAKEIT == 1:
    PERM_PARAMS_FILE = "./perm_params.txt"
    TEMP_PARAMS_FILE = "./temp_params.txt"
    RESET_TRIP_FILE = "./RESET_TRIP"
    RESET_CURRENT_FILE = "./RESET_CURRENT"
    FUELUP_COM_FILE = "./FUELUP_COM_FILE"
    FUELUP_DATA_FILE_OUT = "./FUELUP_DATA_FILE_OUT"
    FUELUP_DATA_FILE_IN = "./FUELUP_DATA_FILE_IN"
    FUELUPS_DATABASE = "./FUELUP_DATABASE_FILE"
else:
    PERM_PARAMS_FILE = "/mnt/music/stick2/mpg_params.txt"
    TEMP_PARAMS_FILE = "/ramcache/mpg_params.txt"
    RESET_TRIP_FILE = "/ramcache/RESET_TRIP"
    RESET_CURRENT_FILE = "/ramcache/RESET_CURRENT"
    FUELUP_COM_FILE = "/ramcache/FUELUP_COM_FILE"
    FUELUPS_DATABASE = "/mnt/music/stick2/FUELUP_DATABASE_FILE"
    FUELUP_DATA_FILE_OUT = "/ramcache/FUELUP_DATA_FILE_OUT"
    FUELUP_DATA_FILE_IN = "/ramcache/FUELUP_DATA_FILE_IN"
PARAMS_SAVE_INTERVAL = 10
 
class tank():

       def __init__(self):
		self.distance = float(0)
		self.fuel = float(0 )
		self.cost_l = float(0 )
		self.total_cost = float(0 )
		self.mpg = float(0 )

       def save_tank(self):
                params_file = open(FUELUPS_DATABASE,"ab+")
                params_file.write(str(self.distance)+","+str(self.fuel)+","+str(self.cost_l)+","+str(self.total_cost)+","+str(self.mpg)+"\n")
                params_file.close()
 


class MPG_fuelup_data():

       def __init__(self):
		self.mpg_fuelup_distance_miles = float(0)
		self.mpg_fuelup_fuel_l = float(0 )
		self.mpg_fuelup_fuel_cost = float(0 )
		self.carplayer_fuelup_distance_miles = float(0)
		self.carplayer_fuelup_fuel_l = float(0 )
		self.carplayer_fuelup_fuel_cost = float(0 )

       def  save_fuelup(self):
                try:
                    params_file = open(FUELUP_DATA_FILE_OUT,"w")
                    pickle.dump(self,params_file)
                    params_file.close()
                except:
                    print "couldn't save fuelup file"

       def  load_fuelup(self,filename):
                try:
                    params_file = open(FUELUP_DATA_FILE_IN,"r")
                    self = pickle.load(params_file)
                    params_file.close()
                except:
                    print "couldn't save fuelup file"

       def  copy_auto_to_manual(self):
                self.carplayer_fuelup_distance_miles = self.mpg_fuelup_distance_miles
                self.carplayer_fuelup_fuel_l =  self.mpg_fuelup_fuel_l
                self.carplayer_fuelup_fuel_cost = self.mpg_fuelup_fuel_cost


       def  copy_current_params(self,params):
                self.mpg_fuelup_distance_miles = float((params.this_run_distance_cm / 160900)) 
                self.mpg_fuelup_fuel_l =  float(params.this_runs_ml /1000)
                self.mpg_fuelup_fuel_cost = float(params.fuel.price)
     		


class MPG_trip():

       def __init__(self):
		self.trip_distance_cm = float(0)
		self.trip_fuel_wasted_ml = float(0 )
		self.trip_fuel_ml = float(0 )
		self.trip_distance_DFCO_cm = float(0 )
		self.trip_fuel_cost = float(0 )

       def reset(self):
		self.trip_distance_cm = float(0)
		self.trip_fuel_wasted_ml = float(0 )
		self.trip_fuel_ml = float(0 )
		self.trip_distance_DFCO_cm = float(0 )
		self.trip_fuel_cost = float(0 )

class MPG_Params():

	def __init__(self):
		self.this_run_distance_cm = float(0)
		self.this_run_fuel_ml = float(0 )
		self.this_run_distance_DFCO_cm = float(0 )
		self.fuel_price = float(1.32 )
                self.trips = [0] * (NUM_TRIPS + 1)
	        self.instant_mpg_from_dist = 0
                self.previous_rpm_value = 0
                self.this_run_MPG = 0
                self.this_run_duration = 0
                self.params_save_count = 1
                self.lasttank = tank()
                self.fuel_adjust = float(1)
                self.speed_adjust = float(1)
    	        for i in range(0,(NUM_TRIPS +1)):
                    trip = MPG_trip()
                    self.trips[i] =  trip
                    #self.trips.append ( trip)

	def reset_current(self):
		self.this_run_distance_cm = float(0)
		self.this_run_fuel_ml = float(0 )
		self.this_run_distance_DFCO_cm = float(0 )
	        self.instant_mpg_from_dist = 0
                self.this_run_MPG = 0
                self.this_run_duration = 0

        def  actual_save_params(self,filename):
		params_file = open(filename,"w")
        	pickle.dump(self,params_file)
        	params_file.close()

        def  actual_load_params(self,filename):
		params_file = open(filename,"r")
        	self = pickle.load(params_file)
        	params_file.close()

        def  load_params(self):
                try:
                      print "Trying to load the RAMCACHE params file\n"
		      self.actual_load_params(TEMP_PARAMS_FILE)
                      print "Successfully loaded the RAMCACHE params file\n"
                except:
                      try:
                          print "Didn't find the RAMCACHE params file, so loading the perm version\n"
		          self.actual_load_params(PERM_PARAMS_FILE)
                      except:
                          print "Didn't find the PERM params file, so saving a FRESH version\n"
                          self.actual_save_params(PERM_PARAMS_FILE)

        def  save_params(self):
               if self.params_save_count == 0:
                      self.actual_save_params(PERM_PARAMS_FILE)
                      self.params_save_count = PARAMS_SAVE_INTERVAL
               self.params_save_count -= 1
               self.actual_save_params(TEMP_PARAMS_FILE)

 
     
# *********************************************************************************************
#===============================================================================================
#**********************************************************************************************
class OBD_Capture():

    def clear_icons_t_speed(self):
    	for i in range(0,self.NBSMOOTH):
            self.t_speed[i]=0;

    def clear_icons_t_maf(self):
    	for i in range(0,self.NBSMOOTH):
            self.t_maf[i]=0;

    def __init__(self):
        self.port = None
        self.NBSMOOTH = 30
        self.t_speed = [0] * self.NBSMOOTH
        self.t_maf = [0] * self.NBSMOOTH
        self.timestamp = [0] * self.NBSMOOTH
        self.fuel_cons = [0] * self.NBSMOOTH
        self.dist_travelled = [0] * self.NBSMOOTH
        self.params = MPG_Params()
        self.params.load_params()
        self.FAKEIT_line = 0
        self.smooth_maf = float(0)
        self.smooth_vss = float(0)
        self.smooth_cons = float(0)
        self.throttle_pos = 0
        self.fuelup_data = MPG_fuelup_data()

    	for i in range(0,self.NBSMOOTH):
            self.t_speed[i]=0;
    	for i in range(0,self.NBSMOOTH):
            self.t_maf[i]=0;
 	self.tindex=0	# index in the smoothing table
	self.min_throttle_pos=255   # idle throttle position, start high
        localtime = time.localtime(time.time())
        self.old_milli_time = current_milli_time()
        self.before_query_time = current_milli_time()
	self.DFCO = 0
	self.params.instant_mpg_from_dist = 0
        self.longTermAvTime = 10
        self.longTermAvFirstVal = 0
        
        if FAKEIT == 0: 
        	self.telemetry_file = open("./telemetry.csv","ab+")
        else:
        	self.telemetry_file = open("./fakeit.csv","rb")
        	self.telemetry_file_csv = csv.reader(self.telemetry_file, delimiter = ",", quotechar = '!')
 
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
            self.mpgfile_message ("Connected...",self.port.port.name)
            print "Connected to "+self.port.port.name
 
    def is_connected(self):
        if FAKEIT:
        	return 1
        else:
        	return self.port

    def kick_it(self):
        self.mpgfile_message ("Problem!!!!","RECONNECTING!!!")
        print "Problem!!! RECONNECTING!!!"
        self.port.close()
        self.connect()



    def get_control_commands(self):
    	for i in range(0,NUM_TRIPS):
		if os.path.isfile(RESET_TRIP_FILE+str(i)):
                        print "Resetting TRIP "+str(i)
			self.params.trips[i].reset()
                        os.remove(RESET_TRIP_FILE+str(i))
	if os.path.isfile(RESET_CURRENT_FILE):
                print "Resetting CURRENT "
		self.params.reset_current()
                os.remove(RESET_CURRENT_FILE)
	if os.path.isfile(FUELUP_COM_FILE ):
                print "FUELUP TIME "
                self.fuelup_data.load_fuelup()
                if self.fuelup_data.carplayer_fuelup_distance_miles <> self.fuelup_data.mpg_fuelup_distance_miles:
                    self.params.speed_adjust = self.fuelup_data.carplayer_fuelup_distance_miles / self.fuelup_data.mpg_fuelup_distance_miles
                if self.fuelup_data.carplayer_fuelup_fuel_l <> self.fuelup_data.mpg_fuelup_fuel_l:
                    self.params.fuel_adjust = self.fuelup_data.carplayer_fuelup_fuel_l / self.fuelup_data.mpg_fuelup_fuel_l
		self.params.lasttank.distance = self.fuelup_data.carplayer_fuelup_distance_miles 
		self.params.lasttank.fuel = self.fuelup_data.carplayer_fuelup_fuel_l
		self.params.lasttank.cost_l = self.fuelup_data.carplayer_fuelup_fuel_cost
		self.params.lasttank.total_cost = float(self.params.lasttank.fuel * self.params.lasttank.cost_l )
		self.params.lasttank.mpg = float(self.params.lasttank.distance / (self.params.lasttank.fuel / 4.54) )
                self.params.lasttank.save_tank()
		self.params.trips[FUELUP_TRIP].reset()
                os.remove(FUELUP_COM_FILE )
 
    def find_obd_sensorindex(self, sensorName):
	index = 0
        foundit = -1
        for i in obd_sensors.SENSORS:
            if i.shortname == sensorName:
            	foundit = index
            else:
                index +=1
        return foundit

    def is_odd(self,num):
        return num & 0x1

    def format_lcdline(self, left_bit, middle_bit,right_bit,line_length):
            padding_val = line_length - len(left_bit) - len(middle_bit) - len(right_bit)
            if self.is_odd(padding_val):
                    half_pad = (padding_val - 1)/2
                    left_pad = half_pad
                    right_pad = half_pad + 1
            else:
                    left_pad = padding_val / 2
                    right_pad = left_pad
            left_spaces = " " * left_pad
            right_spaces = " " * right_pad
            return(left_bit+left_spaces+middle_bit+right_spaces+right_bit)

    def format_number(self, num):
            if (type(num) is int) or (type(num) is float) or (type(num) is long):
                return "{:5.1f}".format(num).lstrip()
            else:
                return num

    def print_screen1(self, mpg_file):
            DFCO_string = "D" if (self.DFCO == 1) else ""
            line1 = self.format_lcdline((self.format_number(self.params.instant_mpg_from_dist)  + "i"), "NOW",(str(self.format_number(self.smooth_cons))+ "s"),15)+"\n"
            line2 = self.format_lcdline(str(self.format_number(self.params.this_run_MPG) ) + "t/"+str(self.params.this_run_duration)+"m",DFCO_string, str(self.throttle_pos)+ "%",15)+"\n"
            mpg_file.write(line1)
            mpg_file.write(line2)


    def print_screen2(self, mpg_file):

            line1 = self.format_lcdline(str(self.format_number(self.params.this_run_distance_cm / 160900 ) ) + "mls","TRP", str(self.format_number(self.params.this_run_fuel_ml / 1000))+ "l",15)+"\n"
            line2 = self.format_lcdline((self.format_number(self.params.this_run_MPG)+"mpg"),"",str("$"+self.format_number(self.params.this_run_fuel_ml * self.params.fuel_price / 1000))    ,15 )+"\n"
            mpg_file.write(line1)
            mpg_file.write(line2)


    def mpgfile_message(self, line1, line2):
            fo = open("/ramcache/MPG.TXT","w+")
            if (line1 == "") and (line2 == ""):
                self.print_screen1(fo)
                self.print_screen2(fo)
            else:
                fo.write(line1)
                fo.write(line2)
                fo.write(line1)
                fo.write(line2)
            fo.write("-----------------------------"+"\n")
    	    for i in range(0,NUM_TRIPS):
                fo.write(str(i)+"\n")
		fo.write(str("Trip "+str(i)+" Fuel Used ml:"+str(self.params.trips[i].trip_fuel_ml)+"\n"))
		fo.write(str("Trip "+str(i)+" Distance cm:"+str(self.params.trips[i].trip_distance_cm)+"\n"))
		fo.write(str("Trip "+str(i)+" Fuel wasted ml:"+str(self.params.trips[i].trip_fuel_wasted_ml)+"\n"))
		fo.write(str("Trip "+str(i)+" Distance on DFCO cm:"+str(self.params.trips[i].trip_distance_DFCO_cm)+"\n"))
		fo.write(str("Trip "+str(i)+" Fuel cost:"+str(self.params.trips[i].trip_fuel_cost)+"\n"))
        #try:
            fo.close()
        #except:
            return 0

    def mpgprint(self,cShortTerm,cLongTerm,cLongTermMinutes):
        str_cShortTerm = str(cShortTerm)[:4]
        if (self.DFCO == 1):
		str_cShortTerm += " DFCO"
        str_cLongTerm = str(cLongTerm)[:4]
        print "Short term MPG"+str_cShortTerm
        print "Long term MPG"+str_cLongTerm
        print "Long term Minutes"+str(cLongTermMinutes)
        self.mpgfile_message("","")
        #self.mpgfile_message((str_cShortTerm+" MPG\n"), (str_cLongTerm+"MPG "+str(cLongTermMinutes)+"min\n"))


##################################################################################################


    def get_smooth_cons(self):
 	vss = 0
        maf = 0
        nb_entry = 0

  	for i in range(0,self.NBSMOOTH):
		vss = vss + self.t_speed[i]
		maf = maf + self.t_maf[i]
		if self.t_maf[i] != 0:
			nb_entry = nb_entry + 1

	if nb_entry>0:
		#maf=(maf*100)/(nb_entry*100)
		maf=maf/nb_entry
        else:
		return "No data"

        vss = vss / self.NBSMOOTH		# average the N latest speed
        self.smooth_maf = maf
        self.smooth_vss = vss
        if self.DFCO == 1:
             self.smooth_maf = float(1)

#        print "Av MAF "+str(maf)
#        print "Av VSS "+str(vss)

  # divide MAF by 100 because our function return MAF*100
  # but multiply by 100 for double digits precision
  # divide MAF by 14.7 air/fuel ratio to have g of fuel/s
  # divide by 730 (g/L at 15C) according to Canadian Gov to have L/s
  # multiply by 3600 to get litre per hour
  # formula: (3600 * MAF) / (14.7 * 730 * VSS)
  # = maf*0.3355/vss L/km
  # mul by 100 to have L/100km

   # SKS the MAF we're dealing with is straight from the ECU no messing about and is therefore 100 times the real value in grams/sec
   # SKS the VSS (speed) we are getting is straight from the ECU and is KM/h

	GasConst = 33.55    # This should be 0.3355 as above but is multiplied by 100 to correct the MAF figures to g/sec rather then centigrams/sec!
        GasMafConst = 107310 # 14.7*730*10

	#vss = vss * 100  # Multiply by params.speed_adjust;
        if vss == 0:        # if speed is zero then set speed to 1 and 1st stage cons becomes litres per hour.
            vss = 1
  # if maf is 0 it will just output 0
        # cons = l/100 km

	cons_l_per_100km= float(((maf * 0.3355)/vss))
        print "l per 100km:"+str(cons_l_per_100km)
        cons_mpg = float(-1)

        if cons_l_per_100km > 0:
# MPG = 4.54 / ( cons/ 62.317) = 62.137 * 4.54 / cons = 282.10198 / cons       (4.54 = litres in 1 UK galon, 62.137 = 100km in UK miles)
        	cons_mpg=float(282.1/cons_l_per_100km)     # convert to MPG UK (1.2 converts from US to UK)
        	print "cons mpg:"+str(cons_mpg)
     
         
  # MPG
  # 6.17 pounds per gallon
  # 454 g in a pound
  # 14.7 * 6.17 * 454 * (VSS * 0.621371) / (3600 * MAF / 100)
  # multipled by 10 for single digit precision
  # new comment: convert from L/100 to MPG

        if cons_mpg > -1:
		return cons_mpg
        else:
		return cons_l_per_100km

#######################################################################################
    def hundred_ms_between_queries(self):
                after_query_time = current_milli_time()
		if after_query_time < (self.before_query_time +110):
			time.sleep (((self.before_query_time+110)-after_query_time)/1000)
                self.before_query_time = after_query_time

#######################################################################################
    def sanity_check_value(self,val, min_val, max_val):

		if (val < min_val) or (val > max_val):
			print "Failed sanity check!!!\nReconnecting!!\n"
                        self.kick_it()
                        return 1
                else:
                        return 0
                        
#######################################################################################
    def accu_trip(self):

        print "==============================================="
        if FAKEIT == 1:
                time.sleep(0.5)
        	fuel_status_value = "0000010000000000"
                maf_value = 1372 + random.randrange(-50,1255)          # 13.72 g/s    with vss = 100kph this should be 62mpg!
                #speed_value = 100 + random.randrange(-30,10)          # 62 mph = 100 kph
                speed_value = 0
                throttle_value = 50 + random.randrange(-20,50)
                rpm_value = random.randrange(500,3000)
                self.FAKEIT_line +=1
                print "FAKEIT_line = "+str(self.FAKEIT_line)
                try:
                	telemetry_array = self.telemetry_file_csv.next()
                except:
                	self.telemetry_file.close()
                        exit(0)
                	self.telemetry_file = open("./fakeit.csv","rb")
        		self.telemetry_file_csv = csv.reader(self.telemetry_file, delimiter = ",", quotechar = '!')
                	telemetry_array = self.telemetry_file_csv.next()
                self.new_milli_time = int(telemetry_array[0])
                if self.FAKEIT_line == 1:
			self.old_milli_time = self.new_milli_time - 0
                milli_time_delta = self.new_milli_time - self.old_milli_time
                print "Milli_time_delta "+str(milli_time_delta)
                self.old_milli_time = self.new_milli_time
                rpm_value = int(telemetry_array[2])
                maf_value = int(telemetry_array[1])
                speed_value = int(telemetry_array[3])
                throttle_value = int(telemetry_array[4])
                fuel_status_value = str(telemetry_array[5])
                
	else:
                sanity_check = 1
                while sanity_check > 0:
                	sanity_check = 0
                	self.new_milli_time = current_milli_time()
                	milli_time_delta = self.new_milli_time - self.old_milli_time
                	self.old_milli_time = self.new_milli_time

			rpm_value = self.get_PID_value(self.rpm_sensor_index)
                	sanity_check += int(self.sanity_check_value(rpm_value,0, 10000))

			maf_value = self.get_PID_value(self.maf_sensor_index)
                	sanity_check += int(self.sanity_check_value(maf_value,0, 20000))

    			speed_value = self.get_PID_value(self.speed_sensor_index)
                	sanity_check += int(self.sanity_check_value(speed_value,0, 200))

    			throttle_value = self.get_PID_value(self.throttle_sensor_index)
                	sanity_check += int(self.sanity_check_value(throttle_value,0, 255))

    			fuel_status_value = self.get_PID_value(self.fuel_status_sensor_index)
                	sanity_check += int(self.sanity_check_value(len(fuel_status_value),16, 16))

			#o211_value = self.get_PID_value(self.o211_sensor_index)
			o211_value = 1
                	sanity_check += int(self.sanity_check_value(o211_value,0, 65535))

			#short_term_fuel_trim_1_value = self.get_PID_value(self.short_term_fuel_trim_1_sensor_index)
			short_term_fuel_trim_1_value = 0
                	sanity_check += int(self.sanity_check_value(short_term_fuel_trim_1_value,-100, 100))

			#long_term_fuel_trim_1_value = self.get_PID_value(self.long_term_fuel_trim_1_sensor_index)
			long_term_fuel_trim_1_value = 0
                	#sanity_check += int(self.sanity_check_value(long_term_fuel_trim_1_value ,-100, 100))


        if FAKEIT == 0:
        	self.telemetry_file.write(str(self.new_milli_time))
        	self.telemetry_file.write(",")
        	self.telemetry_file.write(str(rpm_value))
        	self.telemetry_file.write(",")
        	self.telemetry_file.write(str(maf_value))
        	self.telemetry_file.write(",")
        	self.telemetry_file.write(str(speed_value))
        	self.telemetry_file.write(",")
        	self.telemetry_file.write(str(throttle_value))
        	self.telemetry_file.write(",")
        	self.telemetry_file.write(str(fuel_status_value))
        	self.telemetry_file.write(",")
        	self.telemetry_file.write(str(o211_value))
        	self.telemetry_file.write(",")
        	self.telemetry_file.write(str(short_term_fuel_trim_1_value))
        	self.telemetry_file.write(",")
        	self.telemetry_file.write(str(long_term_fuel_trim_1_value))
        	self.telemetry_file.write("\n")
 

#        if (speed_value >0):
#        	delta_dist = (speed_value * milli_time_delta)/ 36

#  if ((byte)vss>0)
#  {
#    delta_dist=(vss*delta_time)/36;
#    // accumulate for all trips
#    for(byte i=0; i<NBTRIP; i++)
#    {
#      params.trip[i].dist+=delta_dist;
#
#      // collect max data
#      if ((byte)vss > params.tripmax[i].maxspeed)
#        params.tripmax[i].maxspeed = (byte)vss;
#    }  
#  }



#  // if engine is stopped, we can get out now
#  if (!has_rpm)
#  {
#    return;
#  }

#  // need auto-save if car is running
#  #ifdef AutoSave
#    if ((long)(time_now - old_time_params) > 30L * 60000L) // more then 30min
#      params_save();
#  #endif   

        if rpm_value == 0 and self.params.previous_rpm_value >0:
        # we've just stopped the engine so save a fuelup file!
                self.fuelup_data.copy_current_params(self.params)
                self.fuelup_data.save_fuelup()
        self.params.previous_rpm_value = rpm_value

        self.throttle_pos = throttle_value
        print "SPEED VALUE:"+str(speed_value)
        print "MAF VALUE:"+str(maf_value)
	# accumulate fuel only if not in DFCO
	# if throttle position is close to idle and we are in open loop -> DFCO

	# detect idle pos

	if (throttle_value < self.min_throttle_pos) and ( throttle_value != 0): #And make sure its not '0' returned by no response in read byte function
		self.min_throttle_pos = throttle_value

	if fuel_status_value[5] == "1":
        #        print "Yes it's OPEN LOAD time"
		open_load = 1
        else:
		open_load = 0

	if ((throttle_value<(self.min_throttle_pos+4)) and (open_load == 1)):
		self.clear_icons_t_maf()
		maf_value = 1  # decellerate fuel cut-off, fake the MAF as 1 :)
                self.DFCO = 1
                print "We've gone DFCO!!"
	else:
		self.DFCO = 0
	
        # Now store the gathered MAF and speed vales in the smoothing array


        delta_distance_cm =  float(100 * milli_time_delta * speed_value / 3600)
        #print "delta_distance = " + str(delta_distance_cm )
	self.params.this_run_distance_cm += delta_distance_cm
        if self.DFCO == 1:
		self.params.this_run_distance_DFCO_cm += delta_distance_cm
        fuel_per_hour = float(float(maf_value) * 0.3355)

        delta_time_in_millis = float(float(milli_time_delta) / 3600  )
        delta_time_in_hours = float(delta_time_in_millis  / 100000 )
        delta_fuel_l = float(fuel_per_hour * delta_time_in_hours)
        delta_fuel_ml =  float(delta_fuel_l * 1000)
        #print "fuel_per_hour = " + str(fuel_per_hour )
        #print "delta_time_in_millis = " + str(delta_time_in_millis )
        #print "delta_time_in_hours = " + str(delta_time_in_hours )
        #print "delta_fuel_l = " + str(delta_fuel_l )
        #print "delta_fuel_ml = " + str(delta_fuel_ml )
        #delta_fuel_ml =  float(maf_value * .003355 * milli_time_delta / 3600)
	self.params.this_run_fuel_ml += delta_fuel_ml

        if delta_fuel_ml > 0:
            delta_dist_km = float(delta_distance_cm  / 100000)
            delta_dist_miles = (delta_distance_cm / 100000) / 1.609
            delta_fuel_gallons = (delta_fuel_ml / 1000) / 4.54
	    self.params.instant_mpg_from_dist = float((float((delta_distance_cm / 100000)) /1.609) / ((delta_fuel_ml/1000)/4.54))
        else:
            self.params.instant_mpg_from_dist = "No Fuel Flowing"
        #print "delta_fuel_ml = " + str(delta_fuel_ml )
        #print "this_run_distance = " + str(self.params.this_run_distance_cm )
        #print "this_run_fuel = " + str(self.params.this_run_fuel_ml )
        #print "params.instant_mpg_from_dist = " + str(self.params.instant_mpg_from_dist)
        #print "maf_value"+str(maf_value)
       	self.t_speed[self.tindex]=speed_value
       	self.t_maf[self.tindex]=maf_value
       	# increment index and roll over
       	self.tindex = (self.tindex+1)
       	if self.tindex == self.NBSMOOTH:
       		self.tindex = 0

    	for i in range(0,NUM_TRIPS + 1):
                self.params.trips[i].trip_fuel_ml += delta_fuel_ml
                self.params.trips[i].trip_distance_cm += delta_distance_cm
                if self.DFCO == 1:
                    self.params.trips[i].trip_distance_DFCO_cm += delta_distance_cm

        

#######################################################################################
    def get_PID_value(self,sensor_index):
	if FAKEIT == 1:
               	time.sleep(0.1)
		return random.randrange(1,255)
        else:
		(name, value, unit) = self.port.sensor(sensor_index)
		self.hundred_ms_between_queries()
                if (value == "NORESPONSE") or (value == "NODATA") or (value == "ERROR"):
                     # It looks like we need to give it a kick!
                     self.kick_it()
                     return 0
		return value

##########################################################################################
##########################################################################################
        
    def is_number(self,DataToTest):
        try:
            float(DataToTest)
            return True
        except ValueError:
            return False    
                
                
 ###################################################################################################################               
    def capture_data(self):
 
            
	if FAKEIT == 0:
 		#Find supported sensors - by getting PIDs from OBD
		# its a string of binary 01010101010101 
		# 1 means the sensor is supported
		self.supp = self.port.sensor(0)[1]
                if "ERROR" in self.supp:
                      return 0
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
 
        	if(self.port is None):
            		return None

       	self.rpm_sensor_index =  self.find_obd_sensorindex( "rpm")
       	self.maf_sensor_index =  self.find_obd_sensorindex( "maf")
       	self.speed_sensor_index =  self.find_obd_sensorindex( "speed")
       	self.throttle_sensor_index =  self.find_obd_sensorindex( "throttle_pos")
       	self.fuel_status_sensor_index =  self.find_obd_sensorindex( "fuel_status")
       	self.o211_sensor_index =  self.find_obd_sensorindex( "o211")
       	self.short_term_fuel_trim_1_sensor_index =  self.find_obd_sensorindex( "short_term_fuel_trim_1")
       	self.long_term_fuel_trim_1_sensor_index =  self.find_obd_sensorindex( "long_term_fuel_trim_1")
       	min_throttle_value=255
       	tindex = 0
       	self.clear_icons_t_maf()
       	self.clear_icons_t_speed()
        
       	#Loop until Ctrl C is pressed        
       	try:
           	nRunningTotalFuelConsumption = 0
           	nStartTime = time.time()
           	x = 0
           	while True:


                	current_time = time.time()
                	log_string = str(current_time) + "\n"
                    
			self.accu_trip()
                	self.smooth_cons = self.get_smooth_cons()

                	cFuelConsumption = str(self.params.instant_mpg_from_dist)
                        mins = (current_time - nStartTime) /60
                        print "mins" + str(mins)
                	cDurationInMinutes = "{:3.0f}".format(mins).lstrip()
                	#cDurationInMinutes = 4
                	if (cFuelConsumption != "No data"):
                    		x += 1
                	if (x > 0):
                    		if (self.is_number(cFuelConsumption)):
                                        #if int(cDurationInMinutes) == self.longTermAvTime:
				#		nRunningTotalFuelConsumption = nRunningTotalFuelConsumption / x 
                       			nRunningTotalFuelConsumption += float(cFuelConsumption)
                    		nTripAverage = nRunningTotalFuelConsumption/x
                    		cTripAverage = "{:5.2f}".format(nTripAverage).lstrip()
                	else:
                    		cTripAverage = "ZERO"
                
                        if (self.params.this_run_fuel_ml >0 ):
	                    cTripAverage = ((self.params.this_run_distance_cm / 100000) /1.609) / ((self.params.this_run_fuel_ml /1000)/4.54)
                        else:
                            cTripAverage = 0

                        print "This run distance = " + str(self.params.this_run_distance_cm / 100000)
                        print "This run fuel = " + str(self.params.this_run_fuel_ml / 1000)
                        print "This run mpg = " + str(cTripAverage)
		        print "This run DFCO in m ="+str(self.params.this_run_distance_DFCO_cm / 100)
                        self.params.this_run_MPG = cTripAverage
                        self.params.this_run_duration = cDurationInMinutes
                	self.mpgprint(cFuelConsumption,cTripAverage,cDurationInMinutes)
                        self.params.save_params()
                        self.get_control_commands()
                    
                	#print log_string,
                	#time.sleep(0.5)
                

	except KeyboardInterrupt:
                if FAKEIT == 0:
       			self.port.close()
       		print("stopped")
            
if __name__ == "__main__":
    print "Initializing..."
 
    try:
    	o = OBD_Capture()
        o.mpgfile_message ("Initializing...",".....           ")
	while True:
                if FAKEIT == 0:
    		    o.connect()
    		time.sleep(3)
    		if (not o.is_connected()) and (FAKEIT == 0):
        		print "Not connected"
        		print "Error: Not connected to OBDII..."
                        o.mpgfile_message ("Not connected...","Error: Not conne")
        		time.sleep(10)
    		else:
        		o.capture_data()
                        o.telemetry_file.close()
    except KeyboardInterrupt:
	print("stopped")
            
   
