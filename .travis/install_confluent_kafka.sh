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

set +ex
