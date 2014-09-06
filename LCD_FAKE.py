#!/usr/bin/python

#
# based on code from lrvick and LiquidCrystal
# lrvic - https://github.com/lrvick/raspi-hd44780/blob/master/hd44780.py
# LiquidCrystal - https://github.com/arduino/Arduino/blob/master/libraries/LiquidCrystal/LiquidCrystal.cpp
#

from time import sleep

class Adafruit_CharLCD:

    # commands
    LCD_CLEARDISPLAY 		= 0x01
    LCD_RETURNHOME 		= 0x02
    LCD_ENTRYMODESET 		= 0x04
    LCD_DISPLAYCONTROL 		= 0x08
    LCD_CURSORSHIFT 		= 0x10
    LCD_FUNCTIONSET 		= 0x20
    LCD_SETCGRAMADDR 		= 0x40
    LCD_SETDDRAMADDR 		= 0x80

    # flags for display entry mode
    LCD_ENTRYRIGHT 		= 0x00
    LCD_ENTRYLEFT 		= 0x02
    LCD_ENTRYSHIFTINCREMENT 	= 0x01
    LCD_ENTRYSHIFTDECREMENT 	= 0x00

    # flags for display on/off control
    LCD_DISPLAYON 		= 0x04
    LCD_DISPLAYOFF 		= 0x00
    LCD_CURSORON 		= 0x02
    LCD_CURSOROFF 		= 0x00
    LCD_BLINKON 		= 0x01
    LCD_BLINKOFF 		= 0x00

    # flags for display/cursor shift
    LCD_DISPLAYMOVE 		= 0x08
    LCD_CURSORMOVE 		= 0x00

    # flags for display/cursor shift
    LCD_DISPLAYMOVE 		= 0x08
    LCD_CURSORMOVE 		= 0x00
    LCD_MOVERIGHT 		= 0x04
    LCD_MOVELEFT 		= 0x00

    # flags for function set
    LCD_8BITMODE 		= 0x10
    LCD_4BITMODE 		= 0x00
    LCD_2LINE 			= 0x08
    LCD_1LINE 			= 0x00
    LCD_5x10DOTS 		= 0x04
    LCD_5x8DOTS 		= 0x00



    def __init__(self, pin_rs=25, pin_e=24, pins_db=[23, 17, 21, 22], GPIO = None):
         something = 0

    def begin(self, cols, lines):
        return 0

	if (lines > 1):
		self.numlines = lines
    		self.displayfunction |= self.LCD_2LINE
		self.currline = 0


    def home(self):
        return 0

	print "LCD HOME"	

    def clear(self):
        return 0
	print "LCD Clear"


    def setCursor(self, col, row):

        return 0
	print "LCD Set Cursor"




    def noDisplay(self): 
	""" Turn the display off (quickly) """

        return 0
	print "LCD Set Cursor"


    def display(self):
	""" Turn the display on (quickly) """
        return 0
	print "LCD Set Cursor"



    def noCursor(self):
	""" Turns the underline cursor on/off """
        return 0
	print "LCD Set Cursor"


    def cursor(self):
	""" Cursor On """
        return 0
	print "LCD Set Cursor"


    def noBlink(self):
	""" Turn on and off the blinking cursor """
        return 0
	print "LCD Set Cursor"



    def noBlink(self):
	""" Turn on and off the blinking cursor """
        return 0
	print "LCD Set Cursor"


    def DisplayLeft(self):
	""" These commands scroll the display without changing the RAM """
        return 0
	print "LCD Set Cursor"



    def scrollDisplayRight(self):
	""" These commands scroll the display without changing the RAM """
        return 0
	print "LCD Set Cursor"



    def leftToRight(self):
	""" This is for text that flows Left to Right """
        return 0
	print "LCD Set Cursor"



    def rightToLeft(self):
	""" This is for text that flows Right to Left """
        return 0
	print "LCD Set Cursor"


    def autoscroll(self):
	""" This will 'right justify' text from the cursor """
        return 0



    def noAutoscroll(self): 
	""" This will 'left justify' text from the cursor """
        return 0



    def write4bits(self, bits, char_mode=False):
        """ Send command to LCD """
        return 0



    def delayMicroseconds(self, microseconds):
	seconds = microseconds / float(1000000)	# divide microseconds by 1 million for seconds
	sleep(seconds)


    def pulseEnable(self):
        return 0


    def message(self, text):
        print "LCD MESSAGE:"+str(text)+"\n"
        return 0
        """ Send string to LCD. Newline wraps to second line"""


if __name__ == '__main__':

    lcd = Adafruit_CharLCD()

    lcd.clear()
    lcd.message("  Adafruit 16x2\n  Standard LCD")

