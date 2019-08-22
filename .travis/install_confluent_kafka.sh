#!/bin/bash

set -ex

if [ -z "$CHECK" ]; then
    OUT=$(ddev test --list)
    if [[ "$OUT" != *"mapr"* ]]; then
        exit 0
    fi
else
    if [ $CHECK != "mapr" ]; then
        exit 0
    fi
fi


sudo add-apt-repository 'deb http://package.mapr.com/releases/v6.1.0/ubuntu binary trusty'
sudo add-apt-repository 'deb http://package.mapr.com/releases/MEP/MEP-6.1.0/ubuntu binary trusty'
sudo apt-get update
sudo apt-get install mapr-client -y --allow-unauthenticated
#wget
export LD_LIBRARY_PATH=$LD_LIBRARY_PATH:/opt/mapr/lib #:/usr/lib/jvm/java-1.8.0-openjdk-1.8.0.222.b10-0.el7_6.x86_64/jre/lib/amd64/server/
/opt/datadog-agent/embedded/bin/python2 -m pip install confluent_kafka
/opt/datadog-agent/embedded/bin/python3 -m pip install confluent_kafka

set +ex