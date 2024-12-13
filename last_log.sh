#!/bin/bash

path='/data'

last=`ls -d $path/*/ | sort | tail -1`
lastDate=`basename $last`

if ! [ -e "logs/"$lastDate"_log.pdf" ]
then
    python3 make_log.py $last
    rm mail/attachments/*
    cp "logs/"$lastDate"_log.pdf" mail/attachments/
    cp "logs/"$lastDate"_log.csv" mail/attachments/
    python3 send_mail.py mail
fi

