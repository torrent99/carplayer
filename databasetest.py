#!/usr/bin/env python
# -*- coding: utf-8 -*-

# IMPORTS
from mpd import (MPDClient, CommandError)
from random import choice
from socket import error as SocketError
from sys import exit
import pickle
import urllib
import fnmatch
import os.path
import pickle
import time

## SETTINGS
##
HOST = 'localhost'
PORT = '6600'
PASSWORD = False
###



client = MPDClient()

try:
    client.connect(host=HOST, port=PORT)
except SocketError:
    exit(1)

if PASSWORD:
    try:
        client.password(PASSWORD)
    except CommandError:
        exit(1)


global directory_database
global file_database
directory_database = [[0,"/mnt/rec1/Music"]]
file_database = [[0,0,0,"/mnt/rec1/Music"]]
includes = ['*.mp3', '*.wav', '*.MP3', '*.ogg', '*.flac', '*.aac', '*.wma', '*.WMA'] # for files only
excludes = ['/home/paulo-freitas/Documents'] # for dirs and files

# transform glob patterns to regular expressions
includes = r'|'.join([fnmatch.translate(x) for x in includes])
excludes = r'|'.join([fnmatch.translate(x) for x in excludes]) or r'$.'
path = "/mnt/rec1/Music/"
tempf = open('workfile', 'w')

global directory_index
global file_index
directory_index = 1
file_index = 1

def add_mpd_directory_to_database( mpd_dir):
        dir_list = client.lsinfo(mpd_dir)
        directory_index = 1
        file_index = 1
        directory_database.append([directory_index,mpd_dir])
        directory_index += 1
        album_file_index = 1
        for item in dir_list:
            if item.has_key('directory'):
                uri = item['directory']
                add_mpd_directory_to_database(uri)
            elif item.has_key('file'):
                uri = item['file']
                file_database.append([directory_index,file_index,album_file_index,uri])
                file_index += 1
                album_file_index += 1

def find_directory_number(uri):
        result = ' '
        tempf = open('workfile', 'w')

        print "########"
        print uri
        #for i,dir_item in enumerate(directory_database):
        for i in range(len(directory_database)):
             dir_item = directory_database[i]
             dir_path = dir_item[1]
             print str(dir_item)
             print dir_item
             print "**********"
             if uri == dir_path:
                print "FOUND IT!!!!"
                time.sleep(10)
                result = dir_item[0]
                break
        tempf.close()
        return result






add_mpd_directory_to_database('')
print directory_database
pickle.dump(directory_database,tempf)
pickle.dump(file_database,tempf)
tempf.close()
print find_directory_number('Dubstar')
   

wierd = [ 1 , "fred" ]
verywierd= [ [1, "fred"], [2, "trew"] ]
print verywierd[1]    
plonk = verywierd[1]
plink = plonk[1]
print plink
#client.add(choice(client.list('file')))
client.disconnect()

# VIM MODLINE
# vim: ai ts=4 sw=4 sts=4 expandtab



