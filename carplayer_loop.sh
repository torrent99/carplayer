#!/bin/sh
setterm -blank 0 -powerdown 0

sudo mkfs -q /dev/ram1 100
/usr/bin/setleds -D +num
sudo mkdir -p /ramcache
sudo mount /dev/ram1 /ramcache
sudo chmod ogu+rwx /ramcache/
cp /mnt/music/stick2/carplayer.curr_dir /ramcache/
/home/carplayer/car_player/carplayer/mpg_loop.sh &

while [ 0 -lt 1 ]
do
  mpc single off
#  mpc random off
#  mpc consume off
#  mpc repeat off
  sudo /home/carplayer/car_player/carplayer/carplayer 2>>/mnt/music/stick2/carplayererrs 
  sync
  sync
#  exit 1
   cp /ramcache/carplayer.curr_dir /mnt/music/stick2/carplayer.curr_dir 
  sync
  sync
  sleep 5
done
