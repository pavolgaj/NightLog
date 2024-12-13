#!/bin/bash

path='data'

for obs in notes/*.json
do
    obsDate=`basename $obs`
    obsDate="${obsDate%.*}"
    python3 make_log.py $path"/"$obsDate    
done

ls -d "$path"/*/ | xargs -I {} python3 make_log.py {}
