#!/bin/sh

mpc update --wait
rm carplayer.database
./update_database.py

