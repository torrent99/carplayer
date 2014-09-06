#!/usr/bin/python2

import fnmatch
import os
import os.path
import re

includes = ['*.mp3', '*.wav', '*.MP3', '*.ogg', '*.flac', '*.aac', '*.wma', '*.WMA'] # for files only
excludes = ['/home/paulo-freitas/Documents'] # for dirs and files

# transform glob patterns to regular expressions
includes = r'|'.join([fnmatch.translate(x) for x in includes])
excludes = r'|'.join([fnmatch.translate(x) for x in excludes]) or r'$.'
path = "/mnt/rec1/Music/"

i = 0
for (path, dirs, files) in os.walk(path):
    dirs[:] = [d for d in dirs if not re.match(excludes, d)]
    files = [f for f in files if not re.match(excludes, f)]
    files = [f for f in files if re.match(includes, f)]

#    files = [ fi for fi in files if fi.endswith(".mp3") ] 
    if len(files) >0:
	print i,path
    #print path
    #print dirs
    #print files
    #print "----"
    i += 1
    if i >= 999:
        break

