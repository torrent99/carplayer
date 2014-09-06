#!/usr/bin/python

import sys
from Adafruit_CharLCD import Adafruit_CharLCD
from subprocess import * 
from time import sleep, strftime
from datetime import datetime

lcd = Adafruit_CharLCD()


lcd.begin(16,2)

lcd.clear()
the_message="\n".join(sys.argv[1:])
lcd.message(the_message)
