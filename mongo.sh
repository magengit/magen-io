#!/usr/bin/env bash
set -u

DATA_DIR="$HOME/data/db"
LOG_DIR="$HOME/log"
if [ "$(pgrep mongod)" == "" ]
then
    echo "************  STARTING LOCAL MONGO ************"
    if [ ! -d ${LOG_DIR} ]
    then
        mkdir ${LOG_DIR}
        if [ $(uname) == "Darwin" ]
        then
            sudo chown -R `whoami` ${LOG_DIR}
        fi
    fi

    if [ ! -d ${DATA_DIR} ]
    then
        mkdir -p ${DATA_DIR}
        if [ $(uname) == "Darwin" ]
        then
            sudo chown -R `whoami` ${DATA_DIR}
        fi
    fi

    mongod --fork --dbpath ${DATA_DIR} --logpath ${LOG_DIR}/mongodb.log
else
    echo "************ MONGO PID FOUND **************"
fi