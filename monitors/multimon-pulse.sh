#!/bin/bash

pacat -r --device=$1 --rate=22050 --channels=1 --latency-msec=100 | multimon-ng - -qca eas