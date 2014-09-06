#!/bin/sh

cp /mnt/music/stick2/MPG_empty.TXT /ramcache/MPG.TXT
cd /home/carplayer/car_player/carplayer/pyobd/
while [ 0 -lt 1 ]
do
  sudo /home/carplayer/car_player/carplayer/pyobd/mpg.py >>mpg.log 2>&1
  sleep 5
done
