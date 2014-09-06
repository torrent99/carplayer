#!/bin/sh

echo "stage 1"
sudo sh -c 'echo 4 > /sys/class/gpio/export'
echo "stage 2"
sudo sh -c 'echo in > /sys/class/gpio/gpio4/direction'

echo "stage 3"
pinvalue=`sudo cat /sys/class/gpio/gpio4/value`
echo "pinvalue is:" $pinvalue
echo "stage 3a"

countdown=60

while [ "$countdown" -gt 1 ]
#while [ "$pinvalue" -eq 1 ]
do
echo "stage 4"
  sleep 5
echo "stage 5"
  pinvalue=`cat /sys/class/gpio/gpio4/value`
echo "stage 6"
  echo "pinvalue is:" $pinvalue
  if [ "$pinvalue" -eq 0 ]; then
       countdown=`expr "$countdown" "-" "1"`
       echo "countdown is:" $countdown
       /mnt/music/stick1/carplayer/lcd_print.py "Shutdown $countdown"
       if [ "$countdown" -eq 59 ]; then
           /usr/bin/mpc pause
           cp /ramcache/carplayer.curr_dir /mnt/music/stick1/carplayer.curr_dir
           touch /ramcache/shuttingdown
       fi
  else
       countdown=60
       rm /ramcache/shuttingdown
  fi
done

echo "stage 7"
echo "I'm going to shutdown now!"
poweroff 

