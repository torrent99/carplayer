#!/bin/bash
#Add 10 random tracks to mpd playlist. Adjust LIMIT to increase/decrease.
var0=0
LIMIT=20
mpc clear
while [ "$var0" -lt "$LIMIT" ]
do
 # List the whole library, and randomly select one item, then do some string manipulation with grep and awk) and finally pipe result to mpc add.
 mpc listall stick1 | sed -n $[RANDOM % $(mpc stats | grep Songs | awk '{print $2}')+1]p | mpc add
 # Increment
 var0=`expr $var0 + 1` 
done
mpc play
echo
exit 0

