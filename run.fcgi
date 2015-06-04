#! /bin/bash

PORT=${1:-7000}
export REAL_SCRIPT_NAME=""
exec python voternet/webapp.py --config config.yml fastcgi $PORT
