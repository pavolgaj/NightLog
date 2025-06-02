#!/bin/bash

path='data'

#create logs if not observations
for obs in notes/*.json
do
    obsDate=`basename $obs`
    obsDate="${obsDate%.*}"
    if ! [ -e "logs/"$obsDate"_log.pdf" ]
    then
        nohup python3 make_log.py $path"/"$obsDate        
    fi
done

for obs in $path/20*/
do
    obsDate=`basename $obs`
    if ! [ -e "logs/"$obsDate"_log.pdf" ]
    then
        nohup python3 make_log.py $obs
    fi
done
